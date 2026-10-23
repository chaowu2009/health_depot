from django.core.management.base import BaseCommand
from django.db import transaction

from apps.forms_builder.models import FormTemplate
from apps.forms_builder.system_templates import SYSTEM_TEMPLATES
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Create the health department organization and prebuilt form templates (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        cchd, created = Organization.objects.get_or_create(
            slug="cchd",
            defaults={
                "name": "Calvert County Health Department",
                "org_type": Organization.OrgType.HEALTH_DEPARTMENT,
                "brand_color": "#0F4C81",
            },
        )
        if created:
            self.stdout.write("Created Calvert County Health Department organization.")
        for spec in SYSTEM_TEMPLATES:
            _, made = FormTemplate.objects.get_or_create(
                name=spec["name"],
                is_system_template=True,
                defaults={
                    "description": spec["description"],
                    "fields": spec["fields"],
                    "owner_organization": cchd,
                    "is_published": True,
                },
            )
            if made:
                self.stdout.write(f"Created template '{spec['name']}'.")
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))
