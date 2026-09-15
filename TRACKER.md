# Governance tracking for this project

This project is registered under the KenAddme IT Links PM Framework v1.1 and
SDLC Framework v1.2 (mandatory institutional governance on this machine,
independent of what this repository builds).

- Classification: **PM Class A — Strategic / High Risk**, **SDLC Class 3 —
  High**. Rationale is recorded on the tracker project record (sensitive
  personal/organisation data, identity and MFA, multi-tenant isolation,
  cybersecurity risk, billing, 14 work packages across 8+ role leads — not
  Class 4, since nothing here is safety-significant or critical-infrastructure).
- Tracked in the `tracker_<slug>` MySQL database via
  `~/.claude/skills/pm-sdlc-tracker/tracker_cli.py`, project id 1.
- Check current gate status with:
  ```
  python "%USERPROFILE%\.claude\skills\pm-sdlc-tracker\tracker_cli.py" --project-dir "C:\Projects\PM_SDLC Tracker" status
  ```

## What's been verified so far (2026-09-15)

SDLC G1 (Requirements baseline): 7 of 12 items Complete, backed by specific
evidence in `docs/blueprint/` (requirements catalogue, NFRs, journeys,
acceptance criteria, traceability). The remaining 5 are **In progress**, not
Complete, because:

- No Public/Internal/Confidential/Restricted data classification scheme exists
  yet in the pack.
- Requirements have only owner adoption (APR-001, a single chat instruction) —
  the blueprint itself says this is not an independent or stakeholder review.
- No explicit requirement-quality-rule review is documented.
- The DEC01–DEC12 open-question log has accountable roles and gate-linked
  deadlines but no named individuals or calendar dates (DEC01 blocks this).

PM Gates 1–2 and SDLC G0 remain **Not started** in the tracker: the documents
that would evidence intake/authorisation (Project Directive v1.2, the earlier
`file.zip`/`2.zip` referenced in Blueprint Section 8) are not present in this
repository, so they cannot be verified from here — do not mark them Complete
without locating and checking those source documents.

## Rules for updating this tracker as work proceeds

1. Draft candidate evidence matches, then **verify each one against the actual
   file/commit/PR before writing a status**, never on a paraphrase.
2. Complete requires a specific, locatable, checked evidence reference.
   Partial or unverifiable stays "In progress" with an honest note.
3. **Never record a gate `decision` from code or documents alone.** A gate
   decision is DEC01's still-unnamed delivery lead / independent reviewer (or
   the sponsor/Project Authority per the PM Framework), recorded manually via
   `tracker_cli.py gate`.
