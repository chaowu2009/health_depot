"""Capture proposal screenshots from a running Health Depot demo (synthetic data).

Usage (with the stack running, e.g. `make up-prod`):
    pip install playwright && playwright install chromium
    python scripts/screenshots.py --base https://localhost --out screenshots

Signs in with the demo accounts (see DEMO_SCRIPT.md), walks the demo story and saves PNGs.
"""

import argparse
import base64
import hashlib
import hmac
import struct
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

PASSWORD = "HealthDepot-Demo-2026!"  # noqa: S105  # nosec B105 - demo-only, documented
SECRET = "HEALTHDEPOTDEMOKEYCALVERTCOUNTYM"  # noqa: S105  # nosec B105 - demo key
_last_step = {"value": None}


def totp() -> str:
    """Current code for the demo key (waits for a fresh 30s window; codes are single-use)."""
    step = int(time.time()) // 30
    while step == _last_step["value"]:
        time.sleep(1)
        step = int(time.time()) // 30
    _last_step["value"] = step
    key = base64.b32decode(SECRET + "=" * (-len(SECRET) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def login(browser, base: str, who: str, width=1440, height=900) -> Page:
    ctx = browser.new_context(
        ignore_https_errors=True, viewport={"width": width, "height": height}, device_scale_factor=2
    )
    page = ctx.new_page()
    page.goto(f"{base}/accounts/login/")
    page.fill("#id_login", f"{who}@demo.healthdepot.local")
    page.fill("#id_password", PASSWORD)
    page.click("main form button[type=submit]")
    page.fill("#id_code", totp())
    page.click("main form button[type=submit]")
    page.wait_for_load_state()
    return page


def shot(page: Page, out: Path, name: str, full: bool = False) -> None:
    page.wait_for_timeout(600)
    page.screenshot(path=str(out / f"{name}.png"), full_page=full)
    print(f"saved {name}.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://localhost")
    parser.add_argument("--out", default="screenshots")
    args = parser.parse_args()
    base, out = args.base.rstrip("/"), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # 1. Partner links + QR, and the form builder with live preview (program manager)
        m = login(browser, base, "manager")
        m.goto(f"{base}/partners/")
        m.click("text=Chesapeake Community Food Bank (fictional)")
        link = m.locator("a[href*='/r/']").first.get_attribute("href")
        shot(m, out, "01-partner-referral-links")
        m.goto(f"{base}/forms/")
        m.click("text=SDoH Screening")
        shot(m, out, "02-form-builder-live-preview")

        # 2. Public intake form on a phone (English and Spanish)
        phone = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
        ).new_page()
        phone.goto(f"{link}?lang=es")
        shot(phone, out, "03-public-form-mobile-spanish")
        phone.goto(link)
        phone.fill("#id_id-first_name", "Maria")
        phone.fill("#id_id-last_name", "Synthetic")
        phone.fill("#id_id-date_of_birth", "1984-05-06")
        phone.fill("#id_id-zip_code", "20678")
        phone.fill("#id_id-phone", "410-555-0123")
        for key, value in [
            ("housing_worry", "yes"),
            ("food_worry", "yes"),
            ("transportation", "no"),
            ("utilities", "no"),
            ("safety", "no"),
        ]:
            phone.check(f"input[name='q-{key}'][value='{value}']")
        phone.check("#id_id-consent_to_contact")
        phone.check("#id_id-consent_to_share")
        phone.evaluate("window.scrollTo(0, 0)")
        shot(phone, out, "04-public-form-mobile")
        phone.click("button[type=submit]")
        reference = phone.locator("p.font-mono").inner_text()
        shot(phone, out, "05-public-form-confirmation")

        # 3. Closed loop: CCHD accepts and messages; partner replies; CCHD completes
        j = login(browser, base, "staff")
        j.goto(f"{base}/referrals/")
        shot(j, out, "06-referral-inbox")
        j.click(f"text={reference}")
        j.click("main form button:has-text('Accept')")
        j.fill("#id_body", "Thanks! We'll call Maria tomorrow morning.")
        j.click("button:has-text('Send message')")
        partner = login(browser, base, "partner")
        partner.goto(f"{base}/referrals/")
        partner.click(f"text={reference}")
        partner.fill("#id_body", "Maria picked up a food box today.")
        partner.click("button:has-text('Send message')")
        shot(partner, out, "07-partner-view-of-referral")
        j.reload()
        j.click("button:has-text('Open a case')")
        case_url = j.url
        j.fill("#id_description", "Secure stable housing")
        j.click("button:has-text('Add goal')")
        j.fill("#id_title", "Call landlord about payment plan")
        j.click("button:has-text('Add task')")
        j.goto(f"{base}/referrals/")
        j.click(f"text={reference}")
        j.click("button:has-text('Mark completed')")
        j.fill("textarea[name=note]:visible", "Food box delivered; housing case opened.")
        j.click("button:has-text('Confirm: Mark completed')")
        shot(j, out, "08-referral-closed-loop-timeline", full=True)
        j.goto(case_url)
        shot(j, out, "09-case-management", full=True)

        # 4. Leadership dashboard (read-only) and a Phase 2 preview
        lead = login(browser, base, "leader")
        lead.goto(f"{base}/dashboard/")
        shot(lead, out, "10-leadership-dashboard", full=True)
        lead.goto(f"{base}/scheduling/")
        shot(lead, out, "11-phase2-scheduling")
        lead.goto(f"{base}/events/")
        shot(lead, out, "12-phase2-mass-event")
        admin = login(browser, base, "admin")
        admin.goto(f"{base}/manage/audit/")
        shot(admin, out, "13-audit-log")
        browser.close()


if __name__ == "__main__":
    main()
