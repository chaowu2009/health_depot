"""Phase 2 previews (clickable mockups) and the working client spreadsheet import."""

import base64
import io
import random
import uuid
from datetime import timedelta

import qrcode
import qrcode.image.svg
from django.contrib import messages as flash
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.accounts.mixins import ManagePartnersRequiredMixin, StaffRequiredMixin
from apps.organizations.models import Program
from apps.organizations.views import editable_programs

from . import importer, mock


class SchedulingView(StaffRequiredMixin, View):
    def get(self, request):
        offset = int(request.GET.get("week", "0") or 0)
        days = mock.week_days(timezone.localdate() + timedelta(weeks=offset))
        appts = mock.appointments(days)
        grid = {(a["day"], a["clinic"]): [] for a in appts}
        for a in appts:
            grid.setdefault((a["day"], a["clinic"]), []).append(a)
        columns = [
            {
                "day": d,
                "clinics": [
                    {"clinic": c, "appts": grid.get((d, i), [])} for i, c in enumerate(mock.CLINICS)
                ],
            }
            for d in days
        ]
        return render(
            request,
            "phase2/scheduling.html",
            {
                "active": "scheduling",
                "columns": columns,
                "clinics": mock.CLINICS,
                "week": offset,
                "total": len(appts),
                "self_booked": sum(1 for a in appts if a["booked_by"] == "Self-booked"),
            },
        )


class BookingView(StaffRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        dates = [
            today + timedelta(days=i)
            for i in range(1, 15)
            if (today + timedelta(days=i)).weekday() < 5
        ][:8]
        rng = random.Random(today.toordinal())
        slots = [
            f"{h}:{m:02d} {'AM' if h < 12 else 'PM'}".replace("13:", "1:")
            .replace("14:", "2:")
            .replace("15:", "3:")
            for h in range(9, 16)
            for m in (0, 30)
            if rng.random() > 0.35
        ]
        return render(
            request,
            "phase2/booking.html",
            {
                "active": "scheduling",
                "services": mock.SERVICES,
                "clinics": mock.CLINICS,
                "dates": dates,
                "slots": slots,
            },
        )


class EventView(StaffRequiredMixin, View):
    def get(self, request):
        stats = mock.event_stats()
        img = qrcode.make(
            "https://localhost/events/check-in/FLU-2026-PF",
            image_factory=qrcode.image.svg.SvgPathImage,
            box_size=8,
            border=1,
        )
        buf = io.BytesIO()
        img.save(buf)
        return render(
            request,
            "phase2/event.html",
            {
                "active": "events",
                "e": stats,
                "qr_data_uri": "data:image/svg+xml;base64,"
                + base64.b64encode(buf.getvalue()).decode(),
                "pct": round(100 * stats["checked_in"] / stats["booked"]) if stats["booked"] else 0,
            },
        )


class CommunicationsView(StaffRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "phase2/communications.html",
            {"active": "communications", "segments": mock.SEGMENTS},
        )

    def post(self, request):
        seg = next(
            (s for s in mock.SEGMENTS if s[0] == request.POST.get("segment")), mock.SEGMENTS[0]
        )
        rng = random.Random(seg[2])
        recipients = seg[2]
        delivered = recipients - rng.randint(0, max(1, recipients // 25))
        return render(
            request,
            "phase2/communications_report.html",
            {
                "active": "communications",
                "segment": seg,
                "channel": request.POST.get("channel", "email"),
                "subject": request.POST.get("subject", "")[:200],
                "recipients": recipients,
                "delivered": delivered,
                "opted_out": rng.randint(0, 3),
                "bounced": recipients - delivered,
                "sent_at": timezone.now(),
            },
        )


class EHRView(StaffRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "phase2/ehr.html",
            {
                "active": "ehr",
                "mapping": mock.EHR_MAPPING,
                "log": mock.ehr_log(),
                "last_sync": timezone.now() - timedelta(minutes=4),
            },
        )


# --- Spreadsheet import (real) ----------------------------------------------------------------
SESSION_KEY = "client_import"


class ImportView(ManagePartnersRequiredMixin, View):
    template_name = "phase2/import.html"

    def get(self, request):
        state = request.session.get(SESSION_KEY)
        if request.GET.get("restart") and state:
            default_storage.delete(state["key"])
            request.session.pop(SESSION_KEY, None)
            return redirect("client-import")
        if state:
            return self._mapping(request, state)
        return render(
            request,
            self.template_name,
            {"active": "import", "step": "upload", "programs": editable_programs(request.user)},
        )

    def post(self, request):
        step = request.POST.get("step")
        if step == "upload":
            return self._upload(request)
        state = request.session.get(SESSION_KEY)
        if not state:
            return redirect("client-import")
        mapping = {f: request.POST.get(f"map_{f}", "") for f in importer.TARGET_FIELDS}
        try:
            headers, rows = importer.parse_upload(state["name"], self._read(state))
            results = importer.validate(rows, mapping)
        except importer.ImportError_ as exc:
            flash.error(request, str(exc))
            return self._mapping(request, state, mapping)
        if step == "preview":
            return render(
                request,
                self.template_name,
                {
                    "active": "import",
                    "step": "preview",
                    "results": results[:200],
                    "total": len(results),
                    "mapping": mapping,
                    "state": state,
                    "counts": {
                        s: sum(1 for r in results if r["status"] == s)
                        for s in ("new", "existing", "possible_duplicate", "error")
                    },
                },
            )
        if step == "confirm":
            program = Program.objects.get(pk=state["program"])
            counts = importer.run_import(results, program=program, user=request.user)
            default_storage.delete(state["key"])
            request.session.pop(SESSION_KEY, None)
            return render(
                request,
                self.template_name,
                {"active": "import", "step": "done", "counts": counts, "program": program},
            )
        return redirect("client-import")

    def _read(self, state) -> bytes:
        with default_storage.open(state["key"], "rb") as fh:
            return fh.read()

    def _upload(self, request):
        upload = request.FILES.get("file")
        program = editable_programs(request.user).filter(pk=request.POST.get("program")).first()
        if not upload or not program:
            flash.error(request, "Choose a file and a program.")
            return redirect("client-import")
        content = upload.read()
        try:
            headers, rows = importer.parse_upload(upload.name, content)
        except importer.ImportError_ as exc:
            flash.error(request, str(exc))
            return redirect("client-import")
        except Exception:  # noqa: BLE001 - corrupt files
            flash.error(request, "That file couldn't be read. Save it as .csv or .xlsx.")
            return redirect("client-import")
        ext = "xlsx" if upload.name.lower().endswith(".xlsx") else "csv"
        key = default_storage.save(f"imports/{uuid.uuid4().hex}.{ext}", ContentFile(content))
        request.session[SESSION_KEY] = {
            "key": key,
            "name": upload.name[:200],
            "program": str(program.pk),
            "rows": len(rows),
        }
        return redirect("client-import")

    def _mapping(self, request, state, mapping=None):
        try:
            headers, rows = importer.parse_upload(state["name"], self._read(state))
        except Exception:  # noqa: BLE001
            request.session.pop(SESSION_KEY, None)
            flash.error(request, "The uploaded file is no longer available. Please upload again.")
            return redirect("client-import")
        mapping = mapping or importer.guess_mapping(headers)
        return render(
            request,
            self.template_name,
            {
                "active": "import",
                "step": "map",
                "headers": headers,
                "sample": rows[:5],
                "targets": importer.TARGET_FIELDS,
                "mapping": mapping,
                "state": state,
                "program": Program.objects.filter(pk=state["program"]).first(),
            },
        )
