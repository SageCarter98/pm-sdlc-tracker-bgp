"""WP11: the first real frontend for this project (DEC04 resolved
2026-09-20 -- server-rendered HTML, same-origin, reusing the existing
cookie session exactly as-is; see TRACKER.md for the decision record).

Deliberately thin: every page route below resolves auth/tenant/business
logic by calling the SAME functions the JSON API under app/routers/ uses
(imported and called directly, passing real values instead of FastAPI's
Depends() placeholders) -- there is exactly one implementation of "can this
user record this decision", not two that could quietly drift apart. Pages
only add: server-rendered semantic HTML, an accessible error-summary/focus
pattern (Blueprint Sec.4.2's 'focus moves to validation summaries'), and
cookie-based redirect-to-login instead of a JSON 401 a browser can't do
anything useful with.

Scope of this first increment (see TRACKER.md WP11 entry for the honest
list of what's NOT here yet): login/register/MFA, an org picker, the five
essential journeys (my-work, a guided evidence-revision form with save-as-
draft, blockers explanation, decision recording, decision summary). No
template-authoring UI, no invitation-management UI, no export/import UI --
those remain API-only, same as before this package existed."""
