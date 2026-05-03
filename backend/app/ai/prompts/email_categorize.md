# Email Categorization

You will receive a batch of email messages. For each one, classify it and extract structured data.

## Categories
- `action_required` — needs Marwan's reply, decision, or action soon
- `project` — related to an ongoing project but no immediate action
- `deal` — relates to a specific deal/opportunity
- `intelligence` — news, market signal, sector analysis (not transactional)
- `admin` — internal admin, scheduling, billing, low-stakes
- `newsletter` — automated subscription or digest
- `noise` — promo, spam-adjacent, low signal

## Priority (1–5)
- 1 = drop everything (rare; major project blocker, dollar-loss-class)
- 2 = today
- 3 = this week
- 4 = this month
- 5 = no rush

## Output (strict JSON, one object per email keyed by `id`)
```json
{
  "<email_id_1>": {
    "category": "action_required",
    "priority": 2,
    "action_summary": "Stephen needs Marwan's decision on compliance desk scope by Friday",
    "action_required": true,
    "entity_refs": ["Stephen"],
    "project_refs": ["OPP-001"],
    "extracted_tasks": [
      {"title": "Reply to Stephen re: scope", "due": "2026-05-03"}
    ]
  },
  "<email_id_2>": { ... }
}
```

## Rules
- `entity_refs` must use display names exactly as they appear in the system context (Stephen, Phillippe, Ayham, etc.). If a sender is unknown, omit them.
- `project_refs` must use the project code (OPP-001 etc.) only if there is clear evidence the email touches that project. Empty array if uncertain.
- `extracted_tasks` only when the email contains an explicit ask, deadline, or commitment.
- Be skeptical: if the email is just an FYI or status update with no ask, do not extract a task.
- Output JSON ONLY. No prose, no markdown fences.

---

## Emails to classify
