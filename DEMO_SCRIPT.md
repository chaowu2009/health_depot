# Health Depot — 7-Minute Demo Script

All data is **synthetic**. Every person and organization is fictional.

## Before you start (5 minutes, once)

1. Start the app: `.\tasks.ps1 up` (Windows) or `make up`. Demo data loads automatically the
   first time. To start fresh at any time: `.\tasks.ps1 reset-demo` (or **Users & access →
   Tools → Reset demo data**).
2. Add the **demo authenticator secret** to an authenticator app on your phone (Google
   Authenticator, Microsoft Authenticator, Authy…) — choose "enter a setup key":
   - Account: `Health Depot demo`
   - Key: `HEALTHDEPOTDEMOKEYCALVERTCOUNTYM` (time-based)
   - Every demo account below uses this same key and the same password.
3. Open two browser windows side by side: a normal window (health department) and a private
   window (community partner). Open http://localhost:8025 (Mailpit) in a third tab.

> Tip: a code works only once. If you sign in to two accounts within the same 30 seconds,
> wait for the next code.

## Demo logins

Password for all: **`HealthDepot-Demo-2026!`**

| Role | Email | What they see |
|---|---|---|
| Community Health Worker (staff) | `staff@demo.healthdepot.local` — Jordan Rivera | CHW + Maternal & Child Health programs |
| Program manager | `manager@demo.healthdepot.local` — Dana Whitfield | All programs; manages partners & forms |
| Leadership (read-only) | `leader@demo.healthdepot.local` — Dr. Patricia Hale | Dashboards and records, no editing |
| System administrator | `admin@demo.healthdepot.local` — Avery Morgan | Everything + users, audit log, tools |
| Partner (food bank) | `partner@demo.healthdepot.local` — Sam Okonkwo | Only Chesapeake Community Food Bank's referrals |

More demo users exist for every program and partner (see **Users & access**).

---

## The story (7 minutes)

### 0:00 — Opening (30 s)
> "Today CCHD tracks referrals in spreadsheets. Health Depot closes the loop: every referral
> is tracked from submission to outcome, both organizations are notified at every step, and
> leadership sees it all live."

### 0:30 — A partner sends a referral through its link (1 min) · RFP 3.1
1. **Window 1** — sign in as **manager@**. Go to **Partners → Chesapeake Community Food Bank
   (fictional)**.
   - *Talking point:* each partner has its own branded, trackable links and QR codes (visit
     and referral counts shown). Click **Download QR code** — "print it at the front desk."
2. Copy the **Front desk** link and open it in the **private window** (no login needed).
   - Click **Español** to show the Spanish version, then back to **English**.
   - Fill in: *Maria Synthetic*, DOB `05/06/1984`, ZIP `20678`, phone `410-555-0123`.
     Answer **Yes** to housing and food, **No** to the rest. Check both consent boxes.
   - *Talking point:* answer "Yes" to "Do you feel unsafe?" to show the follow-up question
     appear (skip logic); set it back to **No**.
   - Submit → note the reference number. *"No personal details are in the link or email."*

### 1:30 — The health department receives and accepts it (1 min 30 s) · RFP 3.2, 3.7
1. **Window 1** — sign out, sign in as **staff@** (Jordan). Click the **bell** — new referral.
2. **Referrals** → open Maria's referral (top of the list, status *Submitted*).
   - Opening it marks it **Received** automatically — show the **Closed-loop timeline**.
   - Point out **Needs: Housing, Food** (from the screening) and the form answers.
3. Click **Accept**. *"The food bank was just notified — in the app and by email."*
4. In **Secure messages**, type: *"Thanks! We'll call Maria tomorrow morning."* → **Send**.
5. **Mailpit tab** — show the notification email: *"details are only shown after you sign
   in"* — no health information ever leaves the system by email.

### 3:00 — The partner sees the loop close in real time (45 s) · RFP 3.2
1. **Private window** — sign in as **partner@** (Sam, food bank).
2. **Referrals** → Maria's referral: status **Accepted**, the message from CCHD, the timeline.
   - Reply: *"Maria picked up a food box today."*
   - *Talking point:* partners see only referrals involving their organization — never case
     notes or internal comments, and never other partners' clients. (Try **Partners**: they
     see only "My organization".)

### 3:45 — Case management (1 min) · RFP 3.5
1. **Window 1** (Jordan) — on Maria's referral click **Open a case**.
2. Add a goal (*"Secure stable housing"*), a task assigned to yourself due Friday, and a phone
   note. Upload any PDF as a consent form.
   - *Talking point:* documents are stored privately; download links expire in 5 minutes.
3. Back on the referral: **Mark completed…** → outcome *Services provided*, note *"Food box
   delivered; housing case opened."* → *"Both sides are notified; the loop is closed."*
4. Show **My work** — Jordan's tasks, overdue referrals and active cases in one place.

### 4:45 — Leadership dashboard and export (1 min 15 s) · RFP 3.6
1. Sign in as **leader@** (read-only) → **Dashboard**.
   - KPIs: referrals this month, **closed-loop rate**, completion rate, median days to first
     response, overdue referrals.
   - Weekly referrals by status, needs from screenings, completion by partner, who we're
     reaching (age, race, language, ZIP), partner performance table.
   - Filter to **Community Health Workers** or one partner.
2. Sign in as **manager@** → **Reports** → pick columns → **Download Excel**.
   - Open **Users & access → Audit log** (as **admin@**): the export, every record viewed,
     every sign-in — *"tamper-proof, with IP addresses."* · RFP 3.9

### 6:00 — Phase 2 previews (60 s) · RFP 3.3, 3.4, 3.8
- **Scheduling** — multi-clinic week view, Google Calendar sync toggle → **Public booking page**
  (book a slot end-to-end).
- **Mass events** — flu clinic slots, live check-in counter, QR check-in.
- **Communications** — compose an SMS to a client group, preview, delivery report.
- **EHR integration** — HL7/FHIR field mapping and sync log.
- **Spreadsheet import** — *this one works today*: upload a client spreadsheet, map columns,
  see errors and possible duplicates before importing.

### 7:00 — Close
> "Secure by design: two-factor sign-in for everyone, role- and program-based access, a full
> audit trail, encryption in transit, and a plan to host in AWS GovCloud. Health Depot is
> built around CCHD's own workflows, and you own your data."

---

## RFP coverage map

| RFP | Where to show it |
|---|---|
| 3.1 Community referral links | Partners → links, QR codes, form builder (**Forms**), public form |
| 3.2 Notifications & communication | Bell, Mailpit email, secure messages, timeline |
| 3.3 EHR interoperability | Phase 2 → EHR integration |
| 3.4 Scheduling | Phase 2 → Scheduling, public booking |
| 3.5 Case management | Cases, My work, mass events (Phase 2) |
| 3.6 Metrics & analytics | Dashboard, Reports (Excel/CSV) |
| 3.7 Roles & collaboration | Partner vs staff views, internal comments with @mentions, assignment |
| 3.8 Google Workspace & spreadsheets | SSO button, Google Calendar toggle, "Save to Google Drive", Spreadsheet import |
| 3.9 Security & HIPAA | Two-factor sign-in, lockout, 15-min timeout, audit log, SECURITY.md |
| 3.10 Implementation & training | Spreadsheet import, form builder, this demo |
| 3.11 Users & scalability | Users & access (roles, read-only, program access) |
