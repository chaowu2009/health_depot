# Data Model — Proposal (awaiting approval)

Status: **APPROVED** (October 17, 2026). Prompt 1 builds this model.

Conventions for every model unless noted:
- `id` = UUID primary key (no guessable sequential IDs in URLs; helps prevent IDOR).
- `created_at`, `updated_at` timestamps; `created_by` / `updated_by` where staff edit
  records (abstract `TimeStampedModel` / `AuditedModel` in `core`).
- Soft delete (`is_active` / `archived_at`) for records with history; no hard deletes of
  client data from the UI.
- All client-related querysets expose `.for_user(user)` for program scoping.

---

## 1. Organizations and structure (`organizations`)

**Organization** — CCHD itself and each community partner
- `name`, `org_type` (HEALTH_DEPARTMENT | COMMUNITY_PARTNER)
- `slug`, `logo` (S3 file), `brand_color`
- `contact_name`, `contact_email`, `contact_phone`, `address`, `website`
- `service_types` (multi-select: food, housing, transportation, utilities, behavioral
  health, medical, other), `service_area_zips` (list)
- `is_active`

**Division** — e.g., Community Health, Clinical Services
- `organization` → Organization (CCHD), `name`, `code`

**Program** — the unit of access control, e.g., Maternal & Child Health
- `division` → Division, `name`, `code`, `description`, `is_active`
- `overdue_after_days` (default 3; drives overdue referrals)

**PartnerProgram** — which partners work with which programs
- `partner` → Organization, `program` → Program, `is_active`

## 2. Users and access (`accounts`)

**User** — custom user model (email as username), with allauth + MFA
- `email`, `first_name`, `last_name`, `phone`, `title`
- `organization` → Organization (CCHD or a partner)
- `role` (SYSTEM_ADMIN | PROGRAM_MANAGER | STAFF | READ_ONLY | PARTNER_USER)
- `is_active`, `last_login`, `mfa_enrolled` (derived from allauth)

**UserProgramAccess** — program-level scoping for CCHD users
- `user` → User, `program` → Program
- `access_level` (EDIT | READ_ONLY) — lets a STAFF user be read-only in one program
- unique together (`user`, `program`)

Access rules (enforced in `for_user`):
- SYSTEM_ADMIN: everything.
- PROGRAM_MANAGER / STAFF / READ_ONLY: only records in programs listed in
  UserProgramAccess; READ_ONLY can never edit.
- PARTNER_USER: only referrals sent to or from their own organization, and the minimum
  client fields needed to serve them.

*Role is a field, not a separate table — five fixed roles keep the MVP simple. Can be
promoted to a table later if CCHD needs custom roles.*

## 3. Clients (`clients`)

**Client** — synthetic demographics only
- `first_name`, `last_name`, `preferred_name`, `date_of_birth`
- `sex`, `gender_identity` (optional), `race` (multi-select), `ethnicity`,
  `preferred_language`, `needs_interpreter`
- `phone`, `email`, `address_line`, `city`, `zip_code`
- `preferred_contact_method` (PHONE | TEXT | EMAIL)
- `consent_to_share` (bool), `consent_to_contact` (bool), `consent_signed_at`,
  `consent_text_version`
- `external_mrn` (blank in MVP; for future EHR matching)
- `possible_duplicate_of` → Client (nullable; flagged by matching, resolved by staff)

**ClientProgram** — which programs a client is known to (drives scoping)
- `client` → Client, `program` → Program, `enrolled_at`

## 4. Forms (`forms_builder`)

**FormTemplate**
- `name`, `description`, `program` → Program (nullable = shared template)
- `owner_organization` → Organization
- `fields` (JSON list: `key`, `label`, `label_es`, `type`, `required`, `options`,
  `help_text`, `show_if` {field, equals}, `maps_to` (optional Client field))
- `version` (int), `is_published`, `is_system_template` (SDoH Screening, General Intake)

*Submitted answers store `template_id` + `version` so old referrals still render correctly
after a template is edited.*

## 5. Referrals (`referrals`)

**ReferralLink**
- `partner` → Organization, `program` → Program, `form_template` → FormTemplate
- `slug` (unique, random, short), `label` (e.g., "Lusby pantry — front desk")
- `is_active`, `expires_at` (optional)
- `visit_count`, `submission_count` (denormalized counters)

**Referral**
- `reference_number` (human-friendly, e.g., CR-2026-000123)
- `client` → Client, `program` → Program
- `direction` (INBOUND from partner | OUTBOUND from CCHD to partner)
- `sending_organization` → Organization, `receiving_organization` → Organization
- `source_link` → ReferralLink (nullable for staff-created referrals)
- `form_template` → FormTemplate, `form_version`, `answers` (JSON)
- `needs` (multi-select, derived from SDoH answers)
- `status` (SUBMITTED | RECEIVED | ACCEPTED | DECLINED | IN_PROGRESS | COMPLETED |
  CLOSED_UNABLE_TO_CONTACT)
- `priority` (LOW | NORMAL | HIGH | URGENT)
- `assigned_to` → User (nullable)
- `decline_reason`, `outcome` (text/choice), `outcome_notes`
- timestamps per status: `submitted_at`, `received_at`, `accepted_at`, `declined_at`,
  `in_progress_at`, `completed_at`, `closed_at`
- `last_status_change_at` (drives overdue), `case` → Case (nullable)

**ReferralEvent** — the closed-loop timeline (append-only)
- `referral` → Referral, `event_type` (STATUS_CHANGE | ASSIGNED | COMMENT | NOTIFIED |
  MESSAGE)
- `from_status`, `to_status`, `actor` → User (nullable for public submissions),
  `actor_organization` → Organization, `note`, `created_at`

**ReferralComment** — internal comments with @mentions (CCHD-only visibility)
- `referral` → Referral, `author` → User, `body`, `mentions` (M2M User)

**Allowed status transitions** (defined once in `referrals/workflow.py`):
SUBMITTED → RECEIVED → ACCEPTED | DECLINED; ACCEPTED → IN_PROGRESS → COMPLETED |
CLOSED_UNABLE_TO_CONTACT; ACCEPTED → COMPLETED (shortcut). DECLINED, COMPLETED and
CLOSED_UNABLE_TO_CONTACT are final (admin can reopen, logged).

## 6. Messaging (`messaging`)

**MessageThread** — one per referral (shared between CCHD and the partner)
- `referral` → Referral (one-to-one), `participants_organizations` (M2M Organization)

**Message**
- `thread` → MessageThread, `sender` → User, `body`, `attachment` (S3 file, optional)
- `read_by` (through table **MessageReceipt**: `message`, `user`, `read_at`)

## 7. Case management (`cases`)

**Case**
- `case_number`, `client` → Client, `program` → Program
- `case_manager` → User, `status` (OPEN | ACTIVE | ON_HOLD | DISCHARGED)
- `admitted_at`, `discharged_at`, `discharge_reason`, `discharge_outcome`,
  `discharge_notes`
- linked referrals via `Referral.case`

**CarePlanGoal** — `case` → Case, `description`, `target_date`, `status` (NOT_STARTED |
IN_PROGRESS | MET | NOT_MET)

**CaseTask** — `case` → Case, `title`, `description`, `assigned_to` → User, `due_date`,
`completed_at`, `priority`

**CaseNote** — `case` → Case, `author` → User, `note_type` (CONTACT | VISIT | PHONE |
GENERAL), `body`, `contact_date`

**CaseDocument** — `case` → Case, `file` (S3 key), `filename`, `content_type`, `size`,
`uploaded_by` → User, `document_type` (CONSENT | ASSESSMENT | OTHER)

## 8. Notifications (`notifications`)

**Notification** — in-app bell
- `recipient` → User, `verb` (e.g., REFERRAL_ACCEPTED), `target_type`, `target_id`,
  `message` (no PHI), `url`, `read_at`

**EmailOutbox** — emails queued by web, sent by worker (retry-safe)
- `to_email`, `subject`, `body_text`, `body_html` (no PHI), `status` (PENDING | SENT |
  FAILED), `attempts`, `last_error`, `sent_at`

## 9. Audit (`audit`)

**AuditLog** — append-only (no update/delete in app or admin)
- `occurred_at`, `actor` → User (nullable), `actor_ip`, `user_agent`
- `action` (CREATE | READ | UPDATE | DELETE | EXPORT | LOGIN | LOGIN_FAILED | MFA_ENROLLED
  | PERMISSION_CHANGE)
- `entity_type`, `entity_id`, `program` → Program (nullable, for filtering)
- `changes` (JSON diff of field names only for client data — no PHI values),
  `request_id`

## 10. Core / reporting support (`core`, `reports`)

**SchedulerLock** — single row per job name so only one worker runs a scheduled job
- `job_name`, `locked_until`, `locked_by`

**SavedView** — saved referral-inbox filters / report definitions
- `owner` → User, `view_type` (REFERRAL_INBOX | REPORT), `name`, `filters` (JSON),
  `columns` (JSON)

*Dashboards are computed from Referral, Case and Client with ORM aggregates — no separate
reporting tables in the MVP.*

---

## Relationships at a glance

```
Organization (CCHD) ─< Division ─< Program >─< PartnerProgram >─ Organization (partner)
Organization ─< User ─< UserProgramAccess >─ Program
Organization (partner) ─< ReferralLink >─ Program, FormTemplate
Client ─< Referral >─ Program            Referral ─< ReferralEvent, ReferralComment
Referral ─ MessageThread ─< Message      Referral >─ Case (optional)
Client ─< Case ─< CarePlanGoal, CaseTask, CaseNote, CaseDocument
User ─< Notification                      AuditLog (references any entity)
```

## Decisions (approved)

1. **No client login in the MVP.** Clients use public intake forms and receive links/messages.
2. **Partner visibility:** partners see name, contact info, needs and form answers only for
   referrals involving their organization; never other referrals or case notes.
3. **Phase 2 entities** (Clinic, Appointment, Event, Campaign, EHR connection) are mockups
   only and not modeled in the MVP.
4. **Product name:** Health Depot.
