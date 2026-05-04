# Acceptable Use Policy — RR Command Center

> **Status:** TEMPLATE. This document is **not legally binding** until reviewed by
> a DIFC-registered employment lawyer and signed by the named principal of each
> workspace. Do **not** activate the M365 connector for any workspace until the
> reviewed-and-signed version is on file (premortem rule 5.6).
>
> Generated 2026-05-04 from architecture §5.6 + §5.7 invariants. Update this
> template every time the technical scope changes.

---

## 1. Purpose

This Acceptable Use Policy ("AUP") describes how RR Command Center
("the Platform") accesses and processes the email and operational data
of {{COMPANY_NAME}} ("the Company") for the benefit of its principal,
{{PRINCIPAL_NAME}}, and authorised executives.

It is intended to satisfy:

- The transparency obligation under UAE Federal Decree-Law No. 45 of 2021
  (Personal Data Protection Law / "PDPL"),
- DIFC Data Protection Law (DIFC Law No. 5 of 2020) and ADGM equivalents
  where the Company operates in those jurisdictions,
- The Company's own employment contracts and handbook.

## 2. What the Platform accesses

The Platform reads, classifies, and indexes:

- Email messages sent or received via Company-provided Microsoft 365
  mailboxes (`*@{{COMPANY_DOMAIN}}` accounts).
- Email metadata (sender, recipient, subject, date, message identifiers).
- Email attachments (limited to text extraction for indexing; original files
  are stored encrypted at rest if retained).
- Calendar items (subject, time, attendees) — *only if explicitly enabled
  in a future phase*.

The Platform **does not** access:

- Personal email accounts (any address that is not `*@{{COMPANY_DOMAIN}}`),
  including personal Gmail, iCloud, Outlook.com, or other private mailboxes
  used by employees outside their company role.
- Private chats, SMS, or messaging app content (WhatsApp, iMessage, etc.).
- Files on personal devices.
- Any mailbox marked `monitoring_excluded` (see §4 below).

## 3. Why the Platform accesses this data

The Platform aggregates business communications to provide the principal
with operational visibility across Company projects, deals, and tasks.
Specific purposes:

1. **Project-status synthesis** — auto-categorising emails into projects,
   surfacing open loops, and producing a daily morning brief.
2. **Action coordination** — translating principal-issued directions
   ("follow up Friday") into delegated tasks for team members, sent
   through the team member's normal email account.
3. **Compliance and audit** — every read and every action against this
   data is recorded in tamper-evident audit logs (§7).

The legal bases under PDPL Art. 5 are:
- *Performance of a contract* (employment contracts of monitored employees
  reference business email use);
- *Legitimate interest* of the Company in operational oversight;
- *Compliance with a legal obligation* (record-keeping, DIFC reporting).

## 4. Employee opt-out for individual threads

Any email thread can be excluded from the Platform's reading by:

- Including `[private]` in the email subject line, OR
- Moving the thread into a personal Outlook label named `RR-Excluded`
  (which the employee can create themselves).

The Platform's ingestion worker checks for these markers **before** any
content is read, indexed, or embedded. Excluded threads are never seen by
the principal through the Platform — they remain only in the employee's
own mailbox.

This opt-out is permanent for that thread. If a thread is mistakenly
excluded, the employee can rename the label or remove the marker; future
messages in the thread will be re-indexed.

## 5. Data residency and retention

- **Residency:** all data is stored in {{HOSTING_REGION}} on infrastructure
  contractually committed to that region. No cross-border transfer occurs
  without an additional documented adequacy assessment.
- **Retention:** email content is retained for {{RETENTION_MONTHS}} months,
  after which attachments are dropped and only structured metadata
  (sender / recipient / category / dates) is kept for an additional
  {{ARCHIVE_MONTHS}} months. Audit logs are kept indefinitely for
  regulatory readiness.
- **Termination:** when an employee leaves the Company, their mailbox is
  removed from the Platform's scope within 7 days. Their emails ingested
  prior to departure remain in the Platform under the Company's retention
  policy.

## 6. Access controls

- The principal ({{PRINCIPAL_NAME}}) and named executives in the
  `workspace_members` table with role `principal` or `exec` can access
  Platform data scoped to this Company.
- A second principal must be configured before the M365 connector is
  activated for this Company (premortem rule 5.10) — to ensure no single
  point of access failure.
- Operators (team members assigned tasks) see only the threads and tasks
  routed to them. They have no visibility into other employees' mail or
  the Company-wide aggregate view.
- Read-only audit access can be granted to the Company's compliance
  officer or external auditors on request.

## 7. Audit trail

Every access to email content is recorded in the Platform's
`read_audit_log` table with:
- the actor's email address,
- the resource accessed (thread / message / dossier),
- timestamp and originating IP address,
- user-agent string.

Every mutation (assignment, draft approval, member change, configuration
change) is recorded in the `audit_log` table.

Audit logs are retained indefinitely. They are exportable in
machine-readable format for regulatory inspection within 5 business days
of any reasoned request from a competent authority.

## 8. Security controls

- All API access requires Microsoft Single Sign-On against the Company's
  Entra ID tenant. Multi-factor authentication is enforced.
- The Platform's access to the Company's mailboxes is via Microsoft
  Graph admin-grant OAuth, scoped via Exchange Online RBAC for
  Applications to a defined set of mailboxes — not the whole tenant.
- Secrets (M365 client secrets, API keys) are stored in a vault, never
  in source control, never in plaintext on disk outside the deployed
  runtime.
- The Platform refuses to fetch content from any domain on its
  RESTRICTED_DOMAINS list (premortem rule 5.9), including but not
  limited to Bloomberg, Reuters, FT, WSJ, Kpler, Platts, S&P Global,
  LinkedIn, X.

## 9. Subject access requests

Employees may at any time request:
- A copy of the Platform data referencing them.
- Correction of inaccurate data.
- Deletion of data subject to retention obligations.

Requests should be sent to {{DPO_CONTACT}}; responses within 30 days
per PDPL Art. 14.

## 10. Acknowledgement

By signing below, the named signatory acknowledges that they:
- have read and understood this AUP,
- are authorised to bind the Company,
- have communicated the contents to all employees whose mailboxes
  will be in scope,
- have provided the {{NUMBER_OF_DAYS}} day notice period required
  by the relevant employment law before activation.

---

| Field | Value |
|---|---|
| Workspace slug | `{{WORKSPACE_SLUG}}` |
| Company name | `{{COMPANY_NAME}}` |
| Company domain | `{{COMPANY_DOMAIN}}` |
| Hosting region | `{{HOSTING_REGION}}` |
| Retention (active) | `{{RETENTION_MONTHS}}` months |
| Retention (archive) | `{{ARCHIVE_MONTHS}}` months |
| DPO / contact | `{{DPO_CONTACT}}` |
| Notice period | `{{NUMBER_OF_DAYS}}` days |

| | Name | Title | Date | Signature |
|---|---|---|---|---|
| Principal | {{PRINCIPAL_NAME}} | | | |
| Legal Counsel | | | | |
| Company representative | | | | |

---

*Once signed, scan and store with the Company's HR / compliance records.
Record `aup_signed_at` and `aup_signed_by_email` in the `workspaces` row
via `scripts/onboard_workspace.py` before activating the M365 connector.*
