# Build Governance Platform Project Gate and Subgate Requirements Guide

Version: 1.0  
Date: 21 September 2026  
Project: PM/SDLC Tracker — Build Governance Platform  
Project document owner: Freston Kenny Adedeme  
Purpose: Plain-language guidance for carrying out and evidencing this project's gate requirements  
Control: Explanatory companion to the approved BGP baselines; no new gate approval or implementation pass is issued

## What this document is for

This is the guide for **building and delivering BGP**, the current multi-tenant governance platform project. It is not the KenAddme institutional tracker with a new title. Each numbered item below explains the work in BGP terms and the evidence needed to show it has been done. The standing KenAddme frameworks remain the governing references and are not changed by this document.

There are two different uses of gates. BGP's delivery team uses the project and engineering gates below to govern development of the platform. Customers will use configurable framework gates inside BGP. The platform must not force every customer's project to use this guide's gate sequence or institutional labels.

The guide covers PM Gates 1–7, engineering G0–G6 and the separate G4-R release recommendation checkpoint: 15 displayed sections and 172 numbered evidence items. The original gate/item identifiers are retained for reference. Here, “sub-gate” means a numbered evidence requirement under a gate, not a newly invented approval authority.

## How to use it

Start with the gate's purpose, then follow the BGP requirement under each numbered heading. The explanation tells you what the requirement means; the evidence line tells you what a reviewer needs to inspect. Record the actual owner, due date, status, evidence reference, tested version/environment where relevant and reviewer in the project's execution tracker. A single document may support several items if the relevant sections are clearly linked.

Do not mark work complete merely because this guide or a requirements document exists. Use the actual work and review evidence. “Not applicable” needs permitted tailoring and a recorded reason. An approved exception needs valid authority, scope, safeguards, owner and expiry. Missing appointments or choices are explicit gaps, not permission to guess.

Complete evidence allows a gate review; it does not itself approve the gate. Approve permits the authorised next step. Approve with conditions permits only the recorded activities within valid conditions. Hold pauses progression, Redirect changes direction and Terminate stops work. Critical unresolved blockers cannot be hidden inside a conditional approval.

The approved blueprint and frontend supplement already record owner approval of their requirements. This guide neither removes those approvals nor turns them into independent-review certificates, test results, spending authority or production-release approval. Current implementation and gate completion are not reassessed here. Link the latest accepted evidence, including later decision or review closures, rather than assuming an old open item is still open.

## BGP baseline and scope

Use the approved Project Class A and Software Class 3 position unless an authorised later classification supersedes it. The delivery baseline comprises 58 system requirements, 102 frontend requirements, ten screen specifications, five essential journeys, 14 work packages and their linked tests and decisions.

Mandatory coverage includes organisation membership and MFA for approval authority; tenant isolation; immutable template publication; guided template authoring; project and review occurrences; versioned evidence; valid exceptions; deliberate, append-only decisions; concurrency and retry safety; independent integrity verification; complete authorised export/import; accessible phone workflows; truthful save/pending states; and tested service recovery.

Attachments, routine reminders, fictional practice projects and billing remain conditional capabilities. Their safeguards become mandatory when enabled. Do not activate them simply because they appear in a checklist. Paid signup requires accepted billing controls. General scheduling, resource planning, issue tracking, native mobile applications and AI-generated evidence are not silently added to first-release scope.

Initial work must stay within the recorded local-development and synthetic-data authority. Stage A covers foundations and isolated prototypes; Stage B integrates core controls; Stage C proves integrity, portability, recovery and usability; Stage D requires independent acceptance and release authority. Actual progression depends on prerequisites and evidence, not this sequence alone.

## Find the gate you need

- [Gate 1 — Intake decision](#gate-1)
- [Gate 2 — Project authorisation](#gate-2)
- [Gate 3 — Delivery readiness](#gate-3)
- [Gate 4 — Major deliverable or release readiness](#gate-4)
- [Gate 5 — Continuation or exception decision](#gate-5)
- [Gate 6 — Closure approval](#gate-6)
- [Gate 7 — Benefits confirmation](#gate-7)
- [G0 — Intake](#g0)
- [G1 — Requirements baseline](#g1)
- [G2 — Design readiness](#g2)
- [G3 — Code complete](#g3)
- [G4-R — Release recommendation (verification and acceptance)](#g4-r)
- [G4 — Release readiness authorisation](#g4)
- [G5 — Operational acceptance](#g5)
- [G6 — Retirement / closure](#g6)

## Project management gates

These decisions govern BGP as a delivery project. Reuse engineering evidence where the scopes match, and apply the stronger control and required authority.

<a id="gate-1"></a>

## Gate 1 Intake decision

Decide whether BGP is worth investigating as a platform that keeps project requirements, evidence and approval records together for different organisations.

**Decision responsibility:** Project Authority for BGP Project Class A. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** Blueprint Sections 1–2 and 9; REQ-051–052.

### Gate 1.01 Project idea / intake record: problem or opportunity, proposed outcome, beneficiaries, owner, urgency and known constraints

**For BGP:** Describe BGP's scattered-evidence problem, intended small-agency and consultancy users, proposed outcome and project owner in its intake record.

**In simple terms:** Write a short record explaining the problem, who will benefit, the intended improvement, the person responsible and any time or resource limits.

**Evidence to provide:** A completed intake form or concept note covering each of these points. Use the actual BGP record and its controlled reference.

### Gate 1.02 Current situation described with evidence that a problem or opportunity exists

**For BGP:** Attach examples of difficulty finding approvals, inconsistent tracker records or user interviews; distinguish observations from assumptions about demand.

**In simple terms:** Describe what happens today and show why it needs attention. Use observations or records rather than an unsupported claim.

**Evidence to provide:** For example, user feedback, error records, service figures or a description of the current process. Use the actual BGP record and its controlled reference.

### Gate 1.03 Affected users, clients, services and institutional goals identified

**For BGP:** Identify BGP contributors, client approvers, sponsors, administrators and assurance reviewers, and the value each expects.

**In simple terms:** Identify the people and services affected and explain which organisational goal the idea supports.

**Evidence to provide:** A stakeholder list and a short link to the relevant business or institutional objective. Use the actual BGP record and its controlled reference.

### Gate 1.04 Expected outcome stated without assuming a solution too early

**For BGP:** State the desired outcome as reliable, retrievable governance decisions and simpler user journeys, not merely building a web application.

**In simple terms:** Describe the improvement you want to achieve before choosing a product or technology.

**Evidence to provide:** An outcome statement, such as reducing the time needed to retrieve approval records. Use the actual BGP record and its controlled reference.

### Gate 1.05 Initial screening for legal, ethical, security, privacy, safety, financial and reputational concerns

**For BGP:** Record initial concerns about cross-tenant disclosure, false approval, audit tampering, personal data and licensed starter content.

**In simple terms:** Check whether the idea could create harm, misuse data, break an obligation, lose money or damage trust. Record concerns that need specialist review.

**Evidence to provide:** An initial screening record with concerns, responsible reviewers and next actions. Use the actual BGP record and its controlled reference.

### Gate 1.06 Urgency, rough scale and project-versus-operations judgement recorded

**For BGP:** Explain why turning the single-organisation tracker into a multi-tenant product is project work, and estimate the discovery effort without inventing a deadline.

**In simple terms:** Explain how soon the work is needed, its rough size and whether it is a temporary project or routine ongoing work.

**Evidence to provide:** An intake assessment giving the urgency, approximate effort and reasons for the chosen route. Use the actual BGP record and its controlled reference.

### Gate 1.07 Comparison against active commitments and resource capacity

**For BGP:** Check available BGP development and independent-review capacity against other commitments before promising delivery dates.

**In simple terms:** Check whether the organisation has enough people, money and time alongside its existing commitments.

**Evidence to provide:** A capacity check showing competing work and any resource shortfall. Use the actual BGP record and its controlled reference.

### Gate 1.08 Initial classification proposed (Class A / B / C) with reasons

**For BGP:** Record BGP's Project Class A and Software Class 3 assessment and any later approved reclassification; do not reduce them because the first prototype is small.

**In simple terms:** Propose Class A, B or C using the framework criteria. Use the highest class triggered by any relevant condition.

**Evidence to provide:** A classification assessment explaining the factors behind the proposed class. Use the actual BGP record and its controlled reference.

### Gate 1.09 Portfolio recommendation: proceed to feasibility, defer, merge, return or decline

**For BGP:** Record whether BGP discovery should proceed and why the expected governance value justifies that investigation.

**In simple terms:** Recommend whether to investigate now, wait, combine with another initiative, return for clarification or decline.

**Evidence to provide:** A written recommendation with reasons and any follow-up action. Use the actual BGP record and its controlled reference.

### Gate 1.10 Gate 1 decision recorded with approver, date and conditions

**For BGP:** Link the actual BGP intake decision and its authority; do not use this guide as a substitute for that decision.

**In simple terms:** Record what the authorised person decided after reviewing the intake evidence. Include any conditions and who must meet them.

**Evidence to provide:** A dated Gate 1 decision naming the approver, outcome, evidence and conditions. Use the actual BGP record and its controlled reference.

### Gate 1.11 Expedited Gate 1/2 path used? If yes, record urgency justification, authority, maximum spend, time limit and stop authority (Section 4.6)

**For BGP:** If BGP used an expedited intake path, link its specific authority and limits. Development-initiation approval alone is not an expedited spending authorisation.

**In simple terms:** If urgent feasibility work must start through the expedited route, explain why and record its limits before proceeding.

**Evidence to provide:** The Section 4.6 authorisation stating the spending cap, end date and person who can stop the work; otherwise a justified not-applicable record. Use the actual BGP record and its controlled reference.

<a id="gate-2"></a>

## Gate 2 Project authorisation

Agree BGP's purpose, boundaries, ownership and feasibility. Confirm what is being built and which business, data and licensing decisions are needed before larger commitments.

**Decision responsibility:** Project Authority for BGP Project Class A. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** Blueprint Sections 2, 7 and 9; DEC01–DEC03, DEC09; REQ-051–052, REQ-057.

### Gate 2.01 Project charter completed against the Appendix B template

**For BGP:** Use BGP's charter to define the multi-tenant governance product, its owner, intended outcomes, exclusions and governing approvals.

**In simple terms:** Complete the project charter so everyone can see why the project exists, what it covers and who is accountable.

**Evidence to provide:** The charter completed using Appendix B and ready for the required approval. Use the actual BGP record and its controlled reference.

### Gate 2.02 Proportionate business case prepared

**For BGP:** Explain BGP's expected adoption, operating costs and value to agencies or consultancies; identify uncertain commercial assumptions rather than invent revenue figures.

**In simple terms:** Explain why the expected value justifies the cost and risk. Match the detail to the project's size and class.

**Evidence to provide:** A business case showing expected benefits, costs, main risks and the basis for the recommendation. Use the actual BGP record and its controlled reference.

### Gate 2.03 Feasibility assessed: strategic, technical, operational, economic, schedule, legal/contractual, ethical/social and resource dimensions

**For BGP:** Assess whether the team can deliver tenant isolation, protected decisions, reliable recovery and accessible workflows within available resources.

**In simple terms:** Check whether the project can realistically work across every listed dimension, including people, technology, money and obligations.

**Evidence to provide:** A feasibility assessment with findings, uncertainties and any conditions that must be resolved. Use the actual BGP record and its controlled reference.

### Gate 2.04 Alternative approaches identified, including do nothing, buy, build, partner or change the process

**For BGP:** Compare retaining the tracker, adapting an existing tool and building BGP; explain why configurable governance and trustworthy records justify the chosen approach.

**In simple terms:** Compare realistic options before committing to a preferred approach. Include leaving the situation unchanged.

**Evidence to provide:** An options comparison explaining the benefits, costs and risks of each credible approach. Use the actual BGP record and its controlled reference.

### Gate 2.05 High-level scope, exclusions, assumptions and acceptance concept prepared

**For BGP:** Use Blueprint Section 2 and frontend Section 20 to distinguish mandatory governance workflows from excluded scheduling, resource planning and issue tracking.

**In simple terms:** State what the project includes, what it excludes, what it assumes and how success will be accepted.

**Evidence to provide:** A high-level scope statement and an initial description of acceptance. Use the actual BGP record and its controlled reference.

### Gate 2.06 Cost, duration, resource demand and expected benefits estimated as ranges where uncertainty is high

**For BGP:** Prepare BGP estimates by WP01–WP14, including assurance, usability testing and operations; record ranges and staffing assumptions under DEC09.

**In simple terms:** Estimate money, time, people and benefits. Where information is uncertain, give a range and explain its basis.

**Evidence to provide:** An estimate with assumptions, ranges and supporting calculations or comparable experience. Use the actual BGP record and its controlled reference.

### Gate 2.07 Principal risks, dependencies and constraints identified

**For BGP:** Start BGP risks for tenant isolation, decision durability, rule complexity, licensing, operator access and independent-review availability.

**In simple terms:** Identify what could go wrong, what the project relies on and the limits it must work within.

**Evidence to provide:** An initial risk and dependency register with owners and major constraints. Use the actual BGP record and its controlled reference.

### Gate 2.08 Sponsor, project manager and key decision makers nominated

**For BGP:** Resolve named delivery and independent-review appointments under DEC01; Freston Kenny Adedeme's document ownership does not automatically fill every delivery role.

**In simple terms:** Name the sponsor, project manager and people authorised to make key decisions.

**Evidence to provide:** A role and authority record showing named people and their responsibilities. Use the actual BGP record and its controlled reference.

### Gate 2.09 Software framework alignment recorded in the charter (software class, aligned G0-G6 checkpoints, Appendix I mapping)

**For BGP:** Record the Class A/Class 3 alignment and show how BGP's project decisions reuse engineering evidence without duplicating approval work.

**In simple terms:** For software work, record its software class and map project gates to the relevant engineering checkpoints.

**Evidence to provide:** The charter's software-governance section and Appendix I alignment, with shared evidence references. Use the actual BGP record and its controlled reference.

### Gate 2.10 Governance and tolerances recorded: decision rights, reporting, escalation, role separation, financial band, change authority

**For BGP:** State BGP's actual approval roles, Class A reporting and tolerances, change authority and separation of duties; do not infer authority from a username.

**In simple terms:** Explain who may decide, when progress is reported and how much variation is allowed before escalation. Include spending and change limits.

**Evidence to provide:** A governance section covering all listed controls and the applicable class tolerances. Use the actual BGP record and its controlled reference.

### Gate 2.11 Benefits ownership, measures, default Gate 7 date and protected review effort recorded

**For BGP:** Plan BGP adoption and outcome measures, name the operational benefits owner and reserve the interim three-month and formal six-month reviews.

**In simple terms:** Decide who will measure benefits, what they will measure and when Gate 7 will take place. Reserve time for the review.

**Evidence to provide:** A benefits plan with an owner, measures, review date and planned review effort. Use the actual BGP record and its controlled reference.

### Gate 2.12 Gate 2 decision recorded with approver, date and conditions

**For BGP:** Link BGP's actual charter/project-authorisation decision. APR-001 and FE-APR-001 approve development baselines, not every governing gate.

**In simple terms:** Obtain and record the authorised decision on the charter and project, including unresolved conditions.

**Evidence to provide:** A dated Gate 2 decision naming the approver and linking the reviewed charter and business case. Use the actual BGP record and its controlled reference.

<a id="gate-3"></a>

## Gate 3 Delivery readiness

Confirm that BGP has a realistic delivery plan and a design capable of meeting its security, integrity and usability requirements before the corresponding implementation commitment.

**Decision responsibility:** Project Authority for BGP Project Class A. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** Blueprint Sections 3–7; REQ-044–052, REQ-057–058; frontend Sections 16–19.

### Gate 3.01 Scope statement, deliverables, exclusions, requirements and acceptance criteria

**For BGP:** Baseline REQ-001–REQ-058 and FE-001–FE-102 with their conditional scope, test links and explicit exclusions; retain their original IDs.

**In simple terms:** Describe each promised output and the checks it must pass. Make the boundaries and exclusions clear.

**Evidence to provide:** A scope and requirements baseline with testable acceptance criteria. Use the actual BGP record and its controlled reference.

### Gate 3.02 Work breakdown structure with manageable work packages

**For BGP:** Use WP01–WP14 as BGP's work breakdown, assigning implementation and review work rather than treating a document approval as completed code.

**In simple terms:** Break the project into pieces small enough to assign, estimate and track.

**Evidence to provide:** A work breakdown structure identifying work packages and their outputs. Use the actual BGP record and its controlled reference.

### Gate 3.03 Schedule with dependencies, milestones, estimates, critical constraints and contingency

**For BGP:** Schedule package dependencies, decision deadlines, independent testing and recovery rehearsals; include capacity and contingency under DEC09.

**In simple terms:** Put the work in a realistic order, allowing for dependencies, key dates and uncertainty.

**Evidence to provide:** A schedule showing estimates, milestones, dependencies and contingency. Use the actual BGP record and its controlled reference.

### Gate 3.04 Budget, procurement, staff effort, tools, infrastructure and reserves

**For BGP:** Record BGP staffing, environments, tools, assurance funding and operating resources with actual authorised values, not assumed budgets.

**In simple terms:** Confirm the money, people, purchases, tools and infrastructure needed, including reserves for uncertainty.

**Evidence to provide:** A resource and budget plan with commitments and reserve arrangements. Use the actual BGP record and its controlled reference.

### Gate 3.05 Responsibility assignment and decision authority (Appendix H, one accountable per activity)

**For BGP:** Assign delivery, technical, UX, QA, security/privacy, data, service and release responsibilities; retain explicit vacancies until appointments are accepted.

**In simple terms:** Assign who does, reviews and approves each activity. Give each activity one accountable role.

**Evidence to provide:** The Appendix H responsibility mapping with named people or agreed role assignments. Use the actual BGP record and its controlled reference.

### Gate 3.06 Quality plan, review points, test strategy and evidence required for acceptance

**For BGP:** Plan TST-001–TST-058, AC01–AC23 and all applicable frontend checks, including independent security and inclusive usability evidence.

**In simple terms:** Explain how the team will check quality, when reviews happen and what proof is needed for acceptance.

**Evidence to provide:** A quality plan and test strategy linked to acceptance criteria. Use the actual BGP record and its controlled reference.

### Gate 3.07 Risk register, response actions, issue process and escalation thresholds

**For BGP:** Maintain BGP's risk register with response owners for isolation, stale decisions, tampering, recovery, template escalation and misunderstood approval.

**In simple terms:** List risks and planned responses, explain how actual problems are handled and state when higher authority must be involved.

**Evidence to provide:** A current risk register, response owners and issue/escalation process. Use the actual BGP record and its controlled reference.

### Gate 3.08 Communication, stakeholder engagement and reporting calendar

**For BGP:** Set BGP's Class A review calendar and define what the sponsor, contributors, reviewers and operations team receive.

**In simple terms:** Agree who needs updates, what they need to know and how often they receive them.

**Evidence to provide:** A communication plan, stakeholder engagement approach and reporting calendar. Use the actual BGP record and its controlled reference.

### Gate 3.09 Security, privacy, data, access, backup, continuity and release controls where relevant

**For BGP:** Plan BGP membership checks, MFA, RLS, key custody, audit protection, backups, export controls and incident response under REQ-001–009 and REQ-026–029.

**In simple terms:** Plan the relevant protections for systems and information, including access, backups and recovery from disruption.

**Evidence to provide:** Documented control plans and assigned owners for the applicable areas. Use the actual BGP record and its controlled reference.

### Gate 3.10 Change, configuration, version, document and records management method

**For BGP:** Define how BGP requirement changes, ADRs, schema migrations, code reviews, template versions and decision corrections are controlled.

**In simple terms:** Explain how proposed changes are approved and how the team identifies the current authorised versions of records and deliverables.

**Evidence to provide:** A change-control method and version/document management arrangements. Use the actual BGP record and its controlled reference.

### Gate 3.11 Transition, training, support, handover, rollback and closure approach

**For BGP:** Plan BGP onboarding, operating handover, migration, rollback, support instructions and project closure without implying service retirement.

**In simple terms:** Plan how users and support teams will take over, how they will be trained and how a failed transition can be reversed.

**Evidence to provide:** A transition and handover plan covering training, support, rollback and closure. Use the actual BGP record and its controlled reference.

### Gate 3.12 Funded benefits-review effort, operational benefit owner and default Gate 7 due date

**For BGP:** Include the protected benefits-review effort and independent assurance in BGP's authorised plan; retain the three-month and six-month review points.

**In simple terms:** Reserve funded time for the benefits review and confirm the operational owner and Gate 7 deadline.

**Evidence to provide:** The budgeted review effort, named benefits owner and scheduled review date. Use the actual BGP record and its controlled reference.

### Gate 3.13 Baseline quality tests passed: complete, consistent, achievable, controlled, acceptable

**For BGP:** Check that BGP's requirements, package dependencies, API contracts, delivery estimates and acceptance plan agree and are feasible together.

**In simple terms:** Check that the plan covers the work, contains no conflicts, is achievable, is version-controlled and is acceptable to decision makers.

**Evidence to provide:** A baseline review recording the result of each of the five quality checks. Use the actual BGP record and its controlled reference.

### Gate 3.14 Role separation meets Section 3.3, or compensating assurance approved and recorded

**For BGP:** Show that BGP's release author cannot be its sole release approver; record required independent assurance and any permitted compensating arrangement.

**In simple terms:** Check that people do not approve work they are prohibited from approving themselves. Where permitted, obtain approval for alternative independent checks.

**Evidence to provide:** The role-separation assessment or the Project Authority's recorded compensating-assurance approval. Use the actual BGP record and its controlled reference.

### Gate 3.15 Plan readiness checklist (Appendix C) signed by Sponsor, PM and reviewers

**For BGP:** Complete the plan-readiness review using BGP's actual baseline versions, assigned people, decisions and evidence links.

**In simple terms:** Have the sponsor, project manager and reviewers confirm the plan is ready using the required checklist.

**Evidence to provide:** The completed and signed Appendix C plan-readiness checklist. Use the actual BGP record and its controlled reference.

### Gate 3.16 Gate 3 decision recorded with approver, date and conditions

**For BGP:** Link the authorised BGP delivery-readiness decision and its conditions to the approved integrated plan and G2 design evidence.

**In simple terms:** Record the authorised decision approving the baselines and allowing execution to begin.

**Evidence to provide:** A dated Gate 3 decision linking the approved plan versions and any conditions. Use the actual BGP record and its controlled reference.

<a id="gate-4"></a>

## Gate 4 Major deliverable or release readiness

Decide whether a BGP deliverable or release can be accepted. For production, combine project acceptance with the required independent testing and engineering release authorisation.

**Decision responsibility:** Named acceptance authority, with Project Authority concurrence for Class A; production also requires the engineering release authority. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-049–052, REQ-058; WP13; frontend Section 19.

### Gate 4.01 Formal kickoff held confirming objectives, roles, ways of working, reporting and escalation

**For BGP:** Record a BGP kickoff confirming the product boundaries, synthetic-data restriction, responsibilities, review process and evidence expectations.

**In simple terms:** Bring the team together to confirm the purpose, roles, working arrangements and how to report or escalate problems.

**Evidence to provide:** Kickoff minutes or an agreed briefing record with participants and actions. Use the actual BGP record and its controlled reference.

### Gate 4.02 Work packages authorised with outputs, owners, dates, quality criteria and dependencies

**For BGP:** Authorise BGP work packages with defined outputs and test evidence, using the blueprint dependencies and actual assigned owners.

**In simple terms:** Authorise each work package with a clear output, owner, deadline and quality checks.

**Evidence to provide:** Approved work-package records covering outputs, dates, criteria and dependencies. Use the actual BGP record and its controlled reference.

### Gate 4.03 One controlled source maintained for plans, decisions, risks, issues, changes and deliverable versions

**For BGP:** Keep BGP's requirement ledger, decisions, risks, code references and acceptance evidence in controlled locations with stable links.

**In simple terms:** Keep the authoritative plans, decisions and working records in controlled locations so people can find the current versions.

**Evidence to provide:** A controlled record index or repository with current links and version history. Use the actual BGP record and its controlled reference.

### Gate 4.04 Deliverables reviewed early and progressively rather than at final testing only

**For BGP:** Review BGP journeys and controls incrementally, especially isolation and approval semantics, before the final release review.

**In simple terms:** Review outputs while they are being produced so problems are found early.

**Evidence to provide:** Dated review records from relevant delivery stages and tracked follow-up actions. Use the actual BGP record and its controlled reference.

### Gate 4.05 Vendors, external contributors and client dependencies controlled against agreed obligations

**For BGP:** Track any BGP hosting, testing, licensing or other external obligations against recorded approvals; do not treat an unselected supplier as contracted.

**In simple terms:** Track supplier and external contributions against the obligations and dates agreed with them.

**Evidence to provide:** Supplier or dependency records showing commitments, progress and action on shortfalls. Use the actual BGP record and its controlled reference.

### Gate 4.06 Users, operations, training, support, data migration and release environments prepared in parallel

**For BGP:** Prepare BGP user guidance, support procedures, migration rehearsal and release environment alongside feature development.

**In simple terms:** Prepare the people, data, support arrangements and environments while delivery is still underway.

**Evidence to provide:** Readiness records for training, migration, support and release environments. Use the actual BGP record and its controlled reference.

### Gate 4.07 Work package acceptance evidence: output exists, checks passed, defects resolved or formally accepted, documentation updated, reviewer accepted

**For BGP:** For each delivered BGP package, link the implementation revision, passing checks, reviewer and accepted limitations; a closed task label alone is insufficient.

**In simple terms:** Check that the work-package output exists, passes its checks and has updated documentation. Resolve or formally accept remaining defects.

**Evidence to provide:** A reviewer acceptance record linked to the output, checks and any accepted limitations. Use the actual BGP record and its controlled reference.

### Gate 4.08 Test and review evidence identifying deliverable version and test environment

**For BGP:** Identify the BGP commit/build, environment, synthetic fixtures and actual test results in every acceptance report.

**In simple terms:** Make it possible to identify exactly what was tested and where the checks ran.

**Evidence to provide:** Test and review reports naming the deliverable version and test environment. Use the actual BGP record and its controlled reference.

### Gate 4.09 Defect and risk position within approved limits

**For BGP:** Show the release's defect and residual-risk position, including no open S1 and authorised treatment of any S2.

**In simple terms:** Check remaining defects and risks against the approved acceptance limits.

**Evidence to provide:** A current defect and risk assessment with closure evidence or authorised acceptance where allowed. Use the actual BGP record and its controlled reference.

### Gate 4.10 Operational and user readiness confirmed

**For BGP:** Demonstrate that BGP users can complete the core journeys and the service owner can monitor, support and recover the release.

**In simple terms:** Confirm that users can work with the outcome and operations can support it.

**Evidence to provide:** User and operational readiness confirmations, including training and support evidence. Use the actual BGP record and its controlled reference.

### Gate 4.11 Security and privacy conditions satisfied

**For BGP:** Link BGP's isolation tests, privacy review, penetration-test findings where required, secrets checks and approved residual-risk decisions.

**In simple terms:** Close the security and privacy conditions that apply to this release or deliverable.

**Evidence to provide:** Security/privacy review records showing each condition met or a permitted approved exception. Use the actual BGP record and its controlled reference.

### Gate 4.12 Gate 4 decision recorded with acceptance authority, date and conditions

**For BGP:** Link BGP's named acceptance authority, Class A Project Authority concurrence and engineering release authorisation for the exact deliverable.

**In simple terms:** Record the authorised acceptance, release or transition decision and its conditions.

**Evidence to provide:** The Gate 4 decision, including Project Authority concurrence for Class A. Use the actual BGP record and its controlled reference.

<a id="gate-5"></a>

## Gate 5 Continuation or exception decision

Review whether BGP remains worth continuing and whether delivery is within its approved limits. Repeat this review when material risks, scope or forecasts change.

**Decision responsibility:** Project Authority for BGP Project Class A. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-051; Blueprint Sections 6–7; current BGP decision, risk and change records.

### Gate 5.01 Status reporting running at the class cadence (Class A weekly review plus formal status fortnightly; Class B monthly with fortnightly team review; Class C monthly plus midpoint check beyond 20 business days)

**For BGP:** Maintain BGP's Class A weekly delivery review, at least fortnightly formal status and the directive's monthly continuation review, plus triggered reviews.

**In simple terms:** Run reviews and status reports at the frequency required for the project class. A fortnight is two weeks.

**Evidence to provide:** Dated reports and meetings demonstrating the stated Class A, B or C cadence. Use the actual BGP record and its controlled reference.

### Gate 5.02 Minimum status report content complete: overall status, achievements, next period, schedule, cost/resources, scope/quality, risks/issues, decisions required

**For BGP:** Report BGP package progress, blocked decisions, frontend/backend integration, assurance readiness, costs, forecasts and decisions required.

**In simple terms:** Make each report explain progress, next steps, time, money, scope, quality, problems and decisions needed.

**Evidence to provide:** A status report covering every listed minimum section. Use the actual BGP record and its controlled reference.

### Gate 5.03 Status colour supported by evidence, not by activity or an unexpired deadline

**For BGP:** Base BGP's status on linked implementation and review evidence, not the number of documents approved or tasks marked closed.

**In simple terms:** Support green, amber or red status with evidence about delivery and risk. Activity alone does not show that the project is healthy.

**Evidence to provide:** A status assessment linked to current results, forecasts and unresolved problems. Use the actual BGP record and its controlled reference.

### Gate 5.04 Tolerance position measured against approved cost, schedule, scope, quality and risk limits

**For BGP:** Compare BGP forecasts with the approved Class A cost and schedule tolerances and its quality/risk boundaries; do not invent a baseline where none is recorded.

**In simple terms:** Compare the latest forecast with the approved limits for cost, time, scope, quality and risk.

**Evidence to provide:** A tolerance assessment showing the baseline, forecast, variance and applicable limits. Use the actual BGP record and its controlled reference.

### Gate 5.05 Variance analysis with root causes, consequences and corrective options

**For BGP:** Explain BGP delays or cost changes in terms of causes such as unresolved durability choices, contract gaps or independent-review capacity.

**In simple terms:** Explain why actual or forecast performance differs from the plan, what it affects and which corrections are possible.

**Evidence to provide:** A variance analysis with causes, consequences and corrective options. Use the actual BGP record and its controlled reference.

### Gate 5.06 Gate 5 trigger log maintained (escalation trigger, forecast tolerance breach, material change, rebaseline, funding release, supplier failure, recovery plan, critical dependency change, doubtful acceptance, or a call by Sponsor/Authority/assurance)

**For BGP:** Record triggers such as a failed isolation check, uncertain recovery guarantee, missing assurance, scope expansion or a forecast tolerance breach.

**In simple terms:** Record events that require a continuation or exception decision, including expected breaches and significant changes.

**Evidence to provide:** A dated trigger log naming each event, its impact and the person responsible for escalation. Use the actual BGP record and its controlled reference.

### Gate 5.07 Gate 5 convened within 2 business days for a red condition and 5 business days for any other material trigger

**For BGP:** Record when each BGP material trigger was detected and when the required review took place, applying the governing two/five-business-day limits.

**In simple terms:** Hold the triggered review within two business days for red conditions or five business days for other material triggers.

**Evidence to provide:** The trigger date and Gate 5 meeting/decision date showing the deadline was met. Use the actual BGP record and its controlled reference.

### Gate 5.08 Corrective actions implemented, affected plans updated and effectiveness verified

**For BGP:** Track BGP corrective actions through implementation and retest, retaining the evidence that the action addressed the original problem.

**In simple terms:** Carry out the agreed corrective actions, update affected plans and check whether the actions worked.

**Evidence to provide:** An action log with completion records, revised plans and effectiveness checks. Use the actual BGP record and its controlled reference.

### Gate 5.09 Rebaseline decisions retain original commitment, approved changes and current forecast

**For BGP:** Retain BGP's original commitments, approved changes and current forecast when approving a revised baseline.

**In simple terms:** When a new baseline is approved, retain the original promise and the history of approved changes.

**Evidence to provide:** The original baseline, change approvals, revised baseline and current forecast. Use the actual BGP record and its controlled reference.

### Gate 5.10 Gate 5 decision recorded with approver, date and conditions

**For BGP:** Record the actual BGP continuation, correction, rebaseline or stop decision for each occurrence; keep earlier occurrences intact.

**In simple terms:** Record the authorised decision to continue, correct, change the baseline, escalate, redirect or stop as applicable.

**Evidence to provide:** A dated Gate 5 decision with reasons, conditions, owners and follow-up dates. Use the actual BGP record and its controlled reference.

<a id="gate-6"></a>

## Gate 6 Closure approval

Close BGP's development project only after the accepted platform and its responsibilities have been handed over. Keep benefits review and continuing service ownership visible.

**Decision responsibility:** Project Sponsor. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-048, REQ-051, REQ-057–058; DEC06 and DEC12; operational handover.

### Gate 6.01 Formal acceptance obtained against approved criteria, with accepted limitations recorded

**For BGP:** Obtain BGP acceptance against the applicable REQ, FE, TST and AC baseline, identifying the accepted release and limitations.

**In simple terms:** Ask the authorised client or sponsor to accept the result against the agreed criteria and acknowledge any permitted limitations.

**Evidence to provide:** A signed or otherwise controlled acceptance record linked to the criteria and delivered version. Use the actual BGP record and its controlled reference.

### Gate 6.02 Release, migration, training, support, security, backup, recovery and operational-readiness actions complete

**For BGP:** Complete BGP release, support, training, security, backup and tested recovery handover for the accepted service.

**In simple terms:** Finish the activities needed to make the outcome usable and supportable, including recovery and security preparations.

**Evidence to provide:** A completed transition/readiness checklist with supporting records. Use the actual BGP record and its controlled reference.

### Gate 6.03 Ownership transferred: products, data, licences, environments, documentation and unresolved actions

**For BGP:** Transfer BGP code, environments, data responsibilities, licences, runbooks, monitoring and outstanding actions to named receiving owners.

**In simple terms:** Transfer responsibility for the output and its supporting assets, information and open actions.

**Evidence to provide:** A handover record listing each transferred item and its receiving owner. Use the actual BGP record and its controlled reference.

### Gate 6.04 Contracts, invoices, assets, accounts and access rights closed or handed over

**For BGP:** Settle or transfer BGP project contracts, invoices, equipment and accounts; remove development access that is no longer needed.

**In simple terms:** Close or transfer contracts, bills, assets, accounts and permissions so nothing is left without an owner.

**Evidence to provide:** Financial, contractual and access handover/closure records. Use the actual BGP record and its controlled reference.

### Gate 6.05 Budget reconciled; final cost, schedule, scope and quality performance recorded

**For BGP:** Record BGP's final delivery cost, schedule, scope and quality against its authorised commitments.

**In simple terms:** Reconcile spending and record the final results against the approved cost, time, scope and quality commitments.

**Evidence to provide:** A final financial reconciliation and delivery performance summary. Use the actual BGP record and its controlled reference.

### Gate 6.06 Current versions, approvals, evidence, decisions, lessons and closure records archived

**For BGP:** Archive BGP's approved baselines, release evidence, immutable decisions, review records, lessons and closure report under the retention policy.

**In simple terms:** Store the final versions and supporting decisions where authorised people can retrieve them later.

**Evidence to provide:** An archive index linking approvals, evidence, lessons and closure records. Use the actual BGP record and its controlled reference.

### Gate 6.07 People and resources released responsibly and contributions acknowledged

**For BGP:** Record how BGP developers and reviewers are released or reassigned while the ongoing service remains adequately staffed.

**In simple terms:** Arrange the end or reassignment of team duties and release equipment and other resources responsibly.

**Evidence to provide:** A resource-release or reassignment record and acknowledgement of contributions. Use the actual BGP record and its controlled reference.

### Gate 6.08 Benefits measures, owners, review dates and outstanding corrective actions assigned

**For BGP:** Assign BGP adoption/outcome measurement and outstanding corrective actions to their post-project owners.

**In simple terms:** Assign the people who will measure benefits and finish any remaining corrective actions after delivery.

**Evidence to provide:** A benefits/action handover with measures, owners and review dates. Use the actual BGP record and its controlled reference.

### Gate 6.09 Records reviewed against the Appendix J retention schedule; legal holds identified

**For BGP:** Apply the approved retention/legal-hold decisions to BGP records; do not destroy attribution or evidence merely because development has ended.

**In simple terms:** Apply the framework's retention periods and identify records that must be kept because of a legal hold.

**Evidence to provide:** A records assessment against Appendix J with retention and hold decisions. Use the actual BGP record and its controlled reference.

### Gate 6.10 Project register status set to 'Operational - Benefits Pending' with Gate 7 due date and evidence owner

**For BGP:** Set BGP's project record to Operational - Benefits Pending when appropriate, with the formal Gate 7 date and evidence owner.

**In simple terms:** Show that delivery is closed but the benefits review is still due. Name the person responsible for its evidence.

**Evidence to provide:** The project register set to Operational - Benefits Pending, with Gate 7 date and evidence owner. Use the actual BGP record and its controlled reference.

### Gate 6.11 Closure report completed (Appendix G)

**For BGP:** Prepare BGP's closure report covering acceptance, handover, final performance, unresolved actions and benefits-review arrangements.

**In simple terms:** Summarise the delivery result, acceptance, finances, handover, lessons and remaining actions using the required template.

**Evidence to provide:** The completed Appendix G closure report. Use the actual BGP record and its controlled reference.

### Gate 6.12 Gate 6 decision recorded with approver, date and conditions

**For BGP:** Link the sponsor's BGP closure decision; keep service operations and the later benefits review separate from project delivery closure.

**In simple terms:** Obtain the sponsor's formal decision to close the project and release its resources.

**Evidence to provide:** A dated Gate 6 decision with any remaining conditions assigned. Use the actual BGP record and its controlled reference.

<a id="gate-7"></a>

## Gate 7 Benefits confirmation

Check whether BGP actually improved governance work after delivery. Measure adoption, time saved and user understanding, then decide what should be improved or continued.

**Decision responsibility:** Project Sponsor, supported by the Service or Operations Owner. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-041–042, REQ-051, REQ-057; benefits plan and service-review evidence.

### Gate 7.01 Benefits plan complete: benefit, baseline, measure, target, owner, dependencies and review dates

**For BGP:** Define BGP benefits using measured baselines and approved targets; possible measures include evidence-retrieval time, adoption and unaided task completion.

**In simple terms:** For each benefit, state the starting position, target, measurement method, owner, dependencies and review dates.

**Evidence to provide:** A complete benefits plan linked to the approved project baseline. Use the actual BGP record and its controlled reference.

### Gate 7.02 Protected review effort used as budgeted at Gate 3 (Class A two person-days, Class B one, Class C half)

**For BGP:** Record the Class A protected review effort used for BGP's benefits evaluation rather than absorbing it into untracked support work.

**In simple terms:** Use the review time reserved at Gate 3: two person-days for Class A, one for B and half a day for C.

**Evidence to provide:** Review activity or effort records compared with the protected allocation. Use the actual BGP record and its controlled reference.

### Gate 7.03 Usage evidence gathered: is the product or capability being used as intended?

**For BGP:** Collect BGP usage evidence by intended role and organisation type without treating raw sign-up counts as successful adoption.

**In simple terms:** Check whether the intended people actually use the product or service in the intended way.

**Evidence to provide:** Usage records, adoption measures or user feedback with a stated period. Use the actual BGP record and its controlled reference.

### Gate 7.04 Outcome evidence gathered: service, revenue, efficiency, learning, quality, safety or client improvement

**For BGP:** Compare BGP's actual governance outcomes with its approved benefits targets, keeping usability acceptance results distinct from long-term business benefits.

**In simple terms:** Measure the improvements the project was meant to produce and compare them with the starting position and targets.

**Evidence to provide:** Benefits results showing the relevant service, financial, quality or other outcome measures. Use the actual BGP record and its controlled reference.

### Gate 7.05 Costs, delays, negative impacts or risks transferred elsewhere identified

**For BGP:** Record whether BGP introduced extra administration, support burden, cost or confusion for contributors and client approvers.

**In simple terms:** Look for extra costs, delays or harmful effects, including problems shifted to another team.

**Evidence to provide:** A review of adverse effects and transferred risks, with owners for follow-up. Use the actual BGP record and its controlled reference.

### Gate 7.06 Correct and incorrect assumptions reviewed

**For BGP:** Review assumptions about agency demand, template flexibility, onboarding difficulty and the effort needed to maintain trustworthy records.

**In simple terms:** Compare the project's original assumptions with what actually happened.

**Evidence to provide:** An assumption review showing which held true, which failed and the implications. Use the actual BGP record and its controlled reference.

### Gate 7.07 Corrective actions, follow-on investment or retirement decisions identified with owners

**For BGP:** Assign BGP improvements, follow-on investment or retirement proposals to named owners with recorded authority.

**In simple terms:** Decide what needs improvement, additional investment or retirement, and assign responsibility.

**Evidence to provide:** An agreed action or investment/retirement decision record with owners. Use the actual BGP record and its controlled reference.

### Gate 7.08 Lessons routed into institutional standards or training content

**For BGP:** Feed BGP lessons into its product backlog, training and future delivery practice; institutional policy changes need their own approval.

**In simple terms:** Turn useful lessons into changes people can use in future work.

**Evidence to provide:** Updated standards or training, or tracked actions assigned to their custodians. Use the actual BGP record and its controlled reference.

### Gate 7.09 Project register status changed to 'Closed - Benefits Reviewed'

**For BGP:** Change BGP's project status to Closed - Benefits Reviewed only after the benefits evidence and decision are recorded.

**In simple terms:** After the benefits review and decision, update the register to show that this final review is complete.

**Evidence to provide:** The project register set to Closed - Benefits Reviewed and linked to the decision. Use the actual BGP record and its controlled reference.

### Gate 7.10 Gate 7 decision recorded with approver, date and conditions

**For BGP:** Link the sponsor's BGP benefits decision, including whether to sustain, improve, expand, replace or retire the outcome.

**In simple terms:** Record the sponsor's benefits decision with support from the service or operations owner.

**Evidence to provide:** A dated Gate 7 decision recording results, future direction and outstanding actions. Use the actual BGP record and its controlled reference.

## Software engineering gates

These checkpoints establish BGP requirements, design, implementation, testing, release and operational readiness. G4-R recommends a release; G4 authorises it.

<a id="g0"></a>

## G0 Intake

Confirm BGP's software purpose and discovery authority before development commitment. The product is a multi-tenant governance platform, not a KenAddme-only tracker.

**Decision responsibility:** Sponsor and delivery lead. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** Blueprint Sections 1–2, 6 and 9; REQ-049, REQ-051–052.

### G0.01 Project request or concept note

**For BGP:** Use BGP's concept/intake record to explain configurable frameworks, evidence, decisions, audit history and intended users.

**In simple terms:** Explain the software need, the intended users and the improvement sought.

**Evidence to provide:** A project request or concept note that gives enough context for an intake decision. Use the actual BGP record and its controlled reference.

### G0.02 Preliminary business case and feasibility assessment (technical, economic, operational, schedule, legal, data, security, resource)

**For BGP:** Assess the feasibility of BGP's FastAPI/PostgreSQL direction, multi-tenant controls, decision integrity, recovery and accessible interface.

**In simple terms:** Check whether the software idea is worthwhile and possible, including its cost, people, data and security constraints.

**Evidence to provide:** An initial business case and feasibility assessment covering the listed dimensions. Use the actual BGP record and its controlled reference.

### G0.03 Named sponsor, delivery lead and technical owner

**For BGP:** Record BGP's named sponsor, delivery lead and technical owner, referring to DEC01 for unresolved appointments.

**In simple terms:** Identify who sponsors the work, coordinates delivery and takes technical responsibility.

**Evidence to provide:** A named ownership record for all three roles. Use the actual BGP record and its controlled reference.

### G0.04 Initial scope, stakeholder list, risk class and risk register

**For BGP:** Describe BGP's initial first-release scope, stakeholders, Software Class 3 assessment and project-specific risks.

**In simple terms:** Describe the initial boundaries, affected people and software risk class, and start recording the risks.

**Evidence to provide:** A scope note, stakeholder list, classification rationale and initial risk register. Use the actual BGP record and its controlled reference.

### G0.05 Alternatives considered, including process change, configuration or acquisition instead of custom development

**For BGP:** Record why a hosted governance platform is preferred over extending the local tracker or using an existing product.

**In simple terms:** Check whether changing the process, configuring an existing tool or buying a solution could meet the need.

**Evidence to provide:** An options assessment explaining why the recommended approach is suitable. Use the actual BGP record and its controlled reference.

### G0.06 Discovery effort estimated and authority to proceed obtained

**For BGP:** Link the actual authority and time/resource limits for BGP discovery or local prototypes, including the synthetic-data boundary.

**In simple terms:** Estimate the time and resources needed to investigate the idea and obtain authority for that discovery work.

**Evidence to provide:** A discovery estimate and recorded authorisation to proceed. Use the actual BGP record and its controlled reference.

### G0.07 G0 decision record

**For BGP:** Keep BGP's G0 record linked to its intake evidence and actual authority, separately from the guide itself.

**In simple terms:** Record the authorised intake outcome and any conditions for discovery.

**Evidence to provide:** A dated G0 decision naming the decision makers and evidence reviewed. Use the actual BGP record and its controlled reference.

### G0.08 No coding started as an informal commitment before owner, outcome, data constraints and acceptance authority exist

**For BGP:** Check that BGP's intended outcome, responsible owner, data restrictions and acceptance authority were established before relying on development commitment.

**In simple terms:** Before starting code, identify the owner, intended result, restrictions on data and the person authorised to accept it.

**Evidence to provide:** Dated intake and ownership records established before development commitment. Use the actual BGP record and its controlled reference.

<a id="g1"></a>

## G1 Requirements baseline

Agree BGP's observable behaviour, user journeys and acceptance checks. Include backend controls and the full approved frontend requirements rather than treating screens alone as the product.

**Decision responsibility:** Product owner and delivery lead. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-001–REQ-058; FE-001–FE-102; UI01–UI10; Blueprint Sections 3–4 and 7.

### G1.01 Software Requirements Specification, product backlog or equivalent controlled requirements set

**For BGP:** Use the approved Blueprint v0.2 requirement catalogue and Frontend Requirements v1.1 as BGP's linked controlled requirements set.

**In simple terms:** Keep the agreed requirements in one controlled specification, backlog or equivalent record.

**Evidence to provide:** A versioned requirements set with stable identifiers and ownership. Use the actual BGP record and its controlled reference.

### G1.02 Functional requirements, business rules, data needs, interfaces, roles and permissions documented

**For BGP:** Describe BGP registration, memberships, template versions, project creation, evidence revisions, decisions, exceptions, history and export/import rules.

**In simple terms:** Describe what users and the system can do, the rules they must follow, the data they need and who has access.

**Evidence to provide:** Functional requirements covering rules, data, interfaces, roles and permissions. Use the actual BGP record and its controlled reference.

### G1.03 Non-functional requirements defined: security, privacy, performance, availability, reliability, accessibility, usability, compatibility, maintainability, scalability, portability, logging, backup and recovery

**For BGP:** Record BGP's availability, recovery, decision-loss, accessibility and usability requirements; resolve unspecified numeric budgets through DEC08.

**In simple terms:** Define measurable quality expectations, such as speed, availability, ease of use, protection and recovery.

**Evidence to provide:** Non-functional requirements with targets or clear checks for each applicable quality area. Use the actual BGP record and its controlled reference.

### G1.04 User journeys, process maps, use cases or stories as appropriate

**For BGP:** Use UI01–UI10 and journeys A–E to cover sign-in, first project, assigned evidence, decision review/correction and framework authoring.

**In simple terms:** Show how users complete their work and how the software supports each step.

**Evidence to provide:** Relevant user journeys, process maps, use cases or stories, including important alternatives and failures. Use the actual BGP record and its controlled reference.

### G1.05 Acceptance criteria and initial test conditions

**For BGP:** Link each BGP REQ to its TST, relevant directive AC and applicable FE checks; all expected results remain planned until executed.

**In simple terms:** State the observable result that will make each requirement acceptable and identify initial test conditions.

**Evidence to provide:** Acceptance criteria and test conditions linked to the requirements. Use the actual BGP record and its controlled reference.

### G1.06 Data inventory and classification (Public / Internal / Confidential / Restricted)

**For BGP:** Inventory BGP identity, membership, project, evidence, audit, decision and optional attachment data with sensitivity and handling rules.

**In simple terms:** List the data the software will handle and classify it by sensitivity using the four framework categories.

**Evidence to provide:** A data inventory showing Public, Internal, Confidential or Restricted classifications and reasons. Use the actual BGP record and its controlled reference.

### G1.07 Preliminary privacy and security requirements

**For BGP:** State BGP's MFA, tenant isolation, separation, encryption, operator-access and attribution requirements with their identified risks.

**In simple terms:** Identify the privacy and security protections required by the planned users, data and access.

**Evidence to provide:** An initial set of security/privacy requirements linked to identified needs and risks. Use the actual BGP record and its controlled reference.

### G1.08 Requirements traceability matrix or linked work-item structure

**For BGP:** Maintain a BGP ledger linking REQ/FE to WP, implementation, test, evidence and reviewer while preserving existing identifiers.

**In simple terms:** Link each requirement to its design, implementation and tests as those records become available.

**Evidence to provide:** A traceability matrix or linked work items showing the relationships and any gaps. Use the actual BGP record and its controlled reference.

### G1.09 Requirements reviewed with affected stakeholders and formally baselined

**For BGP:** Record review and baseline versions for BGP's approved requirements; retain APR-001 and FE-APR-001 within their document-approval scope.

**In simple terms:** Review the requirements with the affected people and formally agree the version to be used.

**Evidence to provide:** Stakeholder review records and a dated requirements-baseline approval. Use the actual BGP record and its controlled reference.

### G1.10 Requirement quality rules applied: clear, atomic, feasible, testable, traceable, consistent, controlled

**For BGP:** Check BGP requirements for ambiguous approval meaning, missing API details, conflicting retention rules and untestable performance claims.

**In simple terms:** Check that each requirement expresses one clear need, can be delivered and tested, has a source and does not conflict with others.

**Evidence to provide:** A requirements quality review with corrections or tracked unresolved findings. Use the actual BGP record and its controlled reference.

### G1.11 Unresolved-question log with owners and dates

**For BGP:** Track missing BGP choices under DEC01–DEC12 and frontend API gaps; link later resolutions instead of assuming old gaps remain open.

**In simple terms:** Record questions that still need answers, the people responsible and the dates by which answers are needed.

**Evidence to provide:** An open-question log with owners, due dates and effects on commitment. Use the actual BGP record and its controlled reference.

### G1.12 G1 approval recorded

**For BGP:** Link the actual BGP G1 requirements-baseline approval and any conditions; a frontend supplement does not waive system review.

**In simple terms:** Record the product owner's and delivery lead's approval of the requirements baseline.

**Evidence to provide:** A G1 approval identifying the exact version and any conditions. Use the actual BGP record and its controlled reference.

<a id="g2"></a>

## G2 Design readiness

Approve a BGP design that protects tenants and history, handles concurrent decisions safely and supports usable workflows. Resolve architecture choices before relying on them.

**Decision responsibility:** Technical lead with the security review required for this higher-risk software. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** Blueprint Sections 4–5 and 7; DEC04–DEC08, DEC11; frontend Sections 16–18.

### G2.01 Project delivery plan and updated estimates

**For BGP:** Update BGP's package plan and estimates using the approved requirements and actual decisions, not assumed staffing or completion dates.

**In simple terms:** Update the delivery plan and estimates using what discovery and requirements work have revealed.

**Evidence to provide:** A current plan with effort, dates, dependencies and estimate assumptions. Use the actual BGP record and its controlled reference.

### G2.02 Assurance effort, schedule and budget as a distinct line item; commercial disclosure for Class 3 and Class 4 client work

**For BGP:** Show BGP's separately planned independent QA, penetration testing, accessibility/usability checks and recovery assurance effort.

**In simple terms:** Set aside visible time and money for independent checking and review. For Class 3 or 4 client work, make the assurance provision commercially explicit.

**Evidence to provide:** A separate assurance budget/schedule line and the required client commercial disclosure. Use the actual BGP record and its controlled reference.

### G2.03 Architecture description with context, component, deployment and data-flow views

**For BGP:** Document BGP's browser, same-origin API, modular service, PostgreSQL store, workers and any enabled object storage, including data flows.

**In simple terms:** Explain the system's surroundings, main parts, where it runs and how information moves.

**Evidence to provide:** Architecture views for context, components, deployment and data flows. Use the actual BGP record and its controlled reference.

### G2.04 Architecture Decision Records for material choices, including rejected alternatives

**For BGP:** Record BGP architecture choices for sessions, frontend stack, durability, rule limits, key custody, retention and import with reasons and rejected alternatives.

**In simple terms:** Record important design choices and why other credible options were rejected.

**Evidence to provide:** Architecture Decision Records, commonly called ADRs, linked to the design. Use the actual BGP record and its controlled reference.

### G2.05 UX prototypes/designs, database model and API/interface specifications

**For BGP:** Provide BGP UI01–UI10 designs, tenant-scoped database relationships and complete API schemas, including the gaps listed in frontend Section 16.

**In simple terms:** Show the intended screens and interactions, how data is organised and how systems communicate.

**Evidence to provide:** User-experience designs or prototypes, a database model and API/interface specifications. Use the actual BGP record and its controlled reference.

### G2.06 Threat model and privacy assessment

**For BGP:** Model BGP threats such as tenant leakage, role escalation, stale approvals, evidence substitution, privileged tampering and unsafe imports.

**In simple terms:** Identify how the design could be attacked or misuse personal data, then decide how to reduce those risks.

**Evidence to provide:** A threat model and privacy assessment with actions and owners. Use the actual BGP record and its controlled reference.

### G2.07 Security design: authentication, authorisation, secrets, encryption, logging and recovery controls

**For BGP:** Design BGP session/MFA checks, least-privilege database access, CSRF where applicable, secret storage, encryption and independent verification custody.

**In simple terms:** Explain how the design checks identity, limits permissions, protects secrets/data, records events and recovers safely.

**Evidence to provide:** Security design records covering authentication, authorisation, secrets, encryption, logging and recovery. Use the actual BGP record and its controlled reference.

### G2.08 Test strategy, environment plan, migration approach, observability, support model, backup and rollback concept

**For BGP:** Plan BGP's two-tenant tests, migration/rollback, monitoring, support, one-hour ordinary-data RPO and eight-hour restoration target.

**In simple terms:** Plan how the system will be tested, hosted, moved into use, monitored, supported, backed up and reversed if deployment fails.

**Evidence to provide:** The test and environment plans plus migration, monitoring, support, backup and rollback designs. Use the actual BGP record and its controlled reference.

### G2.09 Risky assumptions validated with controlled prototypes or spikes

**For BGP:** Use controlled BGP prototypes to prove uncertain RLS, rule-interpreter, decision-concurrency and durability designs with synthetic fixtures.

**In simple terms:** Use small, controlled experiments to check uncertain ideas that could cause major failure or rework.

**Evidence to provide:** Prototype or technical-spike results stating the question, findings and design consequences. Use the actual BGP record and its controlled reference.

### G2.10 Architecture expectations addressed: modularity, least privilege, failure containment, observability, recoverability, technology fitness

**For BGP:** Review whether BGP modules enforce clear responsibilities, tenant boundaries, observable failures and recoverability without relying on frontend trust.

**In simple terms:** Check that components have clear responsibilities, access is limited, failures are contained and the system can be observed and recovered.

**Evidence to provide:** An architecture review against all listed expectations, including suitability of the chosen technologies. Use the actual BGP record and its controlled reference.

### G2.11 G2 review and approval record

**For BGP:** Link BGP's G2 design approval to the actual ADRs and required security review, showing which DEC choices are resolved or still blocking affected work.

**In simple terms:** Record the design review outcome and the authorised decision to proceed.

**Evidence to provide:** A G2 approval identifying the reviewed design versions, findings and conditions. Use the actual BGP record and its controlled reference.

<a id="g3"></a>

## G3 Code complete

Show that BGP's implementation is controlled, reviewed and ready for formal testing. Cover frontend, API, migrations and worker behaviour, not only visible screens.

**Decision responsibility:** Technical lead and QA lead. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-007–009, REQ-049, REQ-051–052; FE-087–096; Blueprint Section 6.

### G3.01 Version-controlled source code, configuration and infrastructure definitions

**For BGP:** Identify BGP's controlled frontend/API source, migrations, worker code, infrastructure definitions and release configuration.

**In simple terms:** Keep application code, configuration and infrastructure definitions in version control.

**Evidence to provide:** Repository references identifying the controlled versions for the build. Use the actual BGP record and its controlled reference.

### G3.02 Work items, commits and pull/merge requests linked with reviewer evidence

**For BGP:** Link BGP changes to their REQ/FE/WP records and reviewed commits or pull requests.

**In simple terms:** Connect each change to the work it delivers and to the people who reviewed it.

**Evidence to provide:** Linked work items, commits and pull or merge requests with review evidence. Use the actual BGP record and its controlled reference.

### G3.03 Protected release branches enforced; merges require successful checks and review

**For BGP:** Provide BGP branch-protection evidence showing that review and required CI checks cannot be skipped through the normal merge path.

**In simple terms:** Prevent release-branch changes from bypassing the required review and automated checks.

**Evidence to provide:** Branch protection settings and merge records showing the checks were enforced. Use the actual BGP record and its controlled reference.

### G3.04 Peer review completed (two-person or specialist review for critical security, data, payment or infrastructure changes)

**For BGP:** Record competent independent review of BGP's tenant, approval, data and infrastructure changes at the required risk depth.

**In simple terms:** Have a competent reviewer examine the change. Apply the required two-person or specialist review to critical changes.

**Evidence to provide:** Review records with the appropriate reviewers, findings and resolutions. Use the actual BGP record and its controlled reference.

### G3.05 Unit tests written with the code; integration, contract or component tests added where interfaces are affected

**For BGP:** Provide BGP unit and interface tests for rule interpretation, evidence validation, membership, concurrency and client/API state handling.

**In simple terms:** Write tests for the code's behaviour and add checks for affected component or system interfaces.

**Evidence to provide:** Unit tests and applicable integration, contract or component tests with results. Use the actual BGP record and its controlled reference.

### G3.06 Continuous integration passing: formatting, linting, build, test, secret and dependency/security scans

**For BGP:** Run BGP's build, tests, secret/dependency checks and blocking cross-tenant suite; demonstrate that a planted isolation defect is detected.

**In simple terms:** Run the automated pipeline and resolve failures in formatting, code checks, builds, tests and security scans.

**Evidence to provide:** A passing continuous-integration run for the exact candidate version. Use the actual BGP record and its controlled reference.

### G3.07 Successful automated build and test results retained

**For BGP:** Retain BGP pipeline outputs with exact source revision, configuration and environment so reviewers can reproduce the result.

**In simple terms:** Keep the successful build and test results so reviewers can inspect them later.

**Evidence to provide:** Retained pipeline logs or reports tied to the build identifier. Use the actual BGP record and its controlled reference.

### G3.08 Dependency and licence inventory; software bill of materials where required

**For BGP:** Keep BGP's dependency and licence inventory, including frontend packages and the licensing position of any shipped starter content.

**In simple terms:** List third-party components and their licences. Produce a software bill of materials when required.

**Evidence to provide:** A dependency/licence inventory and, where applicable, the software bill of materials. Use the actual BGP record and its controlled reference.

### G3.09 Secrets held in an approved secret store and absent from code, fixtures, logs and collaboration tools

**For BGP:** Verify that BGP fixtures, logs, code, bundles and collaboration records contain no live secrets and that approved secret storage is used.

**In simple terms:** Keep passwords, tokens and keys in the approved secret store and out of code, test samples, logs and messages.

**Evidence to provide:** Secret-storage configuration and scan/review evidence showing no exposed secrets. Use the actual BGP record and its controlled reference.

### G3.10 AI- or tool-generated code reviewed, tested and accepted by a competent human

**For BGP:** Record human understanding, review and tests for AI-assisted BGP code; generated output is not automatically accepted.

**In simple terms:** Have a competent person understand, review, test and accept code produced by AI or other tools.

**Evidence to provide:** Human review and test records for the generated changes. Use the actual BGP record and its controlled reference.

### G3.11 Architecture, API, data, operational and user documentation updated with the change

**For BGP:** Update BGP's API schemas, data model, setup instructions, runbooks and user guidance alongside affected code.

**In simple terms:** Update the documents affected by the change so they still describe the actual system.

**Evidence to provide:** Current architecture, interface, data, operations and user documents, as applicable. Use the actual BGP record and its controlled reference.

### G3.12 Known-defect, technical-debt and deviation records

**For BGP:** Maintain BGP's defects, technical debt and deviations; link TR01–TR07 to current evidence without reopening or closing findings merely from this guide.

**In simple terms:** Record known faults, postponed engineering improvements and departures from the agreed approach.

**Evidence to provide:** Current defect, technical-debt and deviation records with owners and disposition. Use the actual BGP record and its controlled reference.

### G3.13 G3 code-complete decision

**For BGP:** Link BGP's G3 decision for the exact candidate build. Code complete permits the relevant testing step, not production deployment.

**In simple terms:** Record that the implementation meets the code-complete criteria for the identified version. This does not itself authorise production deployment.

**Evidence to provide:** A G3 decision linked to code, review, build and test evidence. Use the actual BGP record and its controlled reference.

<a id="g4-r"></a>

## G4-R Release recommendation (verification and acceptance)

Decide whether BGP's tested candidate deserves a release recommendation. Independent assurance and usability evidence must support the recommendation before release authority is requested.

**Decision responsibility:** QA lead and product owner, with independent QA for Software Class 3. This is a recommendation, not production authorisation. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** TST-001–TST-058, AC01–AC23, applicable FE checks; REQ-040–042, REQ-050; Blueprint Section 6.2.

### G4-R.01 Approved risk-based test plan with traceability to requirements

**For BGP:** Use a BGP risk-based plan covering REQ-001–058, AC01–23, FE-001–102 as applicable, and requirement-specific negative scenarios.

**In simple terms:** Plan testing around the most important risks and show which requirements each test covers.

**Evidence to provide:** An approved test plan with risk priorities and requirements traceability. Use the actual BGP record and its controlled reference.

### G4-R.02 Test cases, automated suites, actual results and evidence recorded with environment, build identifier and tester

**For BGP:** Record BGP test IDs, steps, expected/actual results, source revision, environment, fixtures and tester/reviewer.

**In simple terms:** Record what was tested, the expected and actual results, who ran the tests and the exact build/environment.

**Evidence to provide:** Test cases, automated results and supporting evidence with all required identifiers. Use the actual BGP record and its controlled reference.

### G4-R.03 Unit, integration, contract, system, regression and user-acceptance tests executed as applicable

**For BGP:** Run BGP unit, integration, system, regression and user-acceptance checks, including all five essential journeys.

**In simple terms:** Run the applicable checks at code, interface, whole-system and user levels, including checks for broken existing behaviour.

**Evidence to provide:** Results for the applicable unit, integration, contract, system, regression and user-acceptance tests. Use the actual BGP record and its controlled reference.

### G4-R.04 Security, privacy, performance, accessibility, compatibility, migration, backup/restore and resilience testing according to risk

**For BGP:** Test BGP isolation, penetration resistance, decision concurrency, integrity, recovery, portability, accessibility and inclusive task completion.

**In simple terms:** Test the quality and protection areas that the system's risk requires, including migration and recovery.

**Evidence to provide:** Results for the applicable specialist tests, with gaps and findings addressed. Use the actual BGP record and its controlled reference.

### G4-R.05 Production-like environments used with representative, lawful test data and no uncontrolled production-data copying

**For BGP:** Use production-like BGP configurations with fictional tenants and permitted test data; do not copy real customer evidence into uncontrolled tests.

**In simple terms:** Use a test environment that represents production and data that is permitted for testing.

**Evidence to provide:** Environment details and test-data provenance/handling records demonstrating lawful, controlled use. Use the actual BGP record and its controlled reference.

### G4-R.06 Defect register with severity, disposition, owner and retest status

**For BGP:** Maintain BGP's severity-ranked defect list, including approval misunderstanding and cross-tenant disclosure as material release concerns.

**In simple terms:** Record each defect, its severity, who owns it, what will happen to it and whether the fix has been checked.

**Evidence to provide:** A current defect register with disposition and retest status. Use the actual BGP record and its controlled reference.

### G4-R.07 Corrections retested and targeted regression tests run

**For BGP:** Retest BGP corrections against their original failure and related regression scenarios; link review-closure records to actual supporting results.

**In simple terms:** Run failed checks again after fixes and test related behaviour that might have been affected.

**Evidence to provide:** Retest and targeted regression results linked to the fixes. Use the actual BGP record and its controlled reference.

### G4-R.08 No open S1 defect; any S2 released only with documented residual-risk acceptance

**For BGP:** Show that the BGP candidate has no open S1 and that any released S2 has the required residual-risk acceptance.

**In simple terms:** Do not release with an open S1 critical defect. An S2 high defect needs documented acceptance of the remaining risk by the required authority.

**Evidence to provide:** A release defect summary showing no open S1 and approved residual-risk records for any released S2. Use the actual BGP record and its controlled reference.

### G4-R.09 Security/privacy scan and review records

**For BGP:** Attach BGP security/privacy review and scan reports, including independent penetration testing before general availability.

**In simple terms:** Retain the security and privacy scans and human reviews used to assess this release.

**Evidence to provide:** Dated scan/review reports tied to the release, with findings and dispositions. Use the actual BGP record and its controlled reference.

### G4-R.10 User-acceptance record from the authorised product owner or client representative

**For BGP:** Obtain authorised BGP acceptance of core journeys and approved usability targets, including twenty-minute onboarding and 90% unaided completion per group.

**In simple terms:** Have the authorised business representative confirm that the software meets the agreed user acceptance criteria.

**Evidence to provide:** A user-acceptance record from the product owner or authorised client representative. Use the actual BGP record and its controlled reference.

### G4-R.11 G4 recommendation issued

**For BGP:** Record the independent QA/product-owner BGP recommendation with candidate ID, remaining risks and evidence; do not represent it as release authorisation.

**In simple terms:** Have QA and the product owner state whether the tested candidate is ready to be presented for release authorisation. A recommendation is not permission to deploy.

**Evidence to provide:** A dated G4 recommendation linked to the candidate, test results, remaining defects and required independent QA evidence. Use the actual BGP record and its controlled reference.

<a id="g4"></a>

## G4 Release readiness authorisation

Authorise one identified BGP production release only after its required evidence is accepted. Then execute the approved deployment and record the actual checks and outcome.

**Decision responsibility:** Product owner, service owner and release authority. For Software Class 3, release authority is the Executive Sponsor or formally recorded delegate; required role separation applies. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-050, REQ-058; WP13; frontend Section 19.

**Order of work:** G4.11 authorisation must precede the production deployment evidenced at G4.10. The inherited item order is not a command to deploy before approval. Emergency changes require their separate authorised procedure; delivery delay is not an emergency.

### G4.01 Release package assembled: version, approved changes, dependencies, configuration, migration and known limitations

**For BGP:** Assemble the BGP release manifest with build ID, approved changes, dependencies, configuration, migrations and known limitations.

**In simple terms:** Assemble everything needed to identify and install the approved release, including dependencies and known limitations.

**Evidence to provide:** A release package or manifest listing the version, changes, configuration and migration materials. Use the actual BGP record and its controlled reference.

### G4.02 Release notes and immutable release/build identifier

**For BGP:** Publish BGP release notes tied to an immutable build and the exact frontend/API versions being deployed.

**In simple terms:** Explain what changed and give the release a fixed identifier that cannot silently point to a different build.

**Evidence to provide:** Release notes and an immutable version, build ID or equivalent controlled reference. Use the actual BGP record and its controlled reference.

### G4.03 Production access, infrastructure, capacity, monitoring, backup, support and communication readiness confirmed

**For BGP:** Confirm BGP production membership/access controls, infrastructure, monitoring, backup, on-call support and user communications are ready.

**In simple terms:** Confirm that production has the required permissions, capacity, monitoring, backups, support and communications.

**Evidence to provide:** A production-readiness record covering all listed areas. Use the actual BGP record and its controlled reference.

### G4.04 Approved deployment, data migration, rollback and communication plans with named decision authority

**For BGP:** Approve BGP deployment, schema/data migration and rollback plans with explicit go/no-go and rollback authority.

**In simple terms:** Approve the steps for deployment, migration, reversal and communication, and name who can decide to proceed or roll back.

**Evidence to provide:** Approved plans with named decision authority and decision points. Use the actual BGP record and its controlled reference.

### G4.05 Build and deployment credentials kept separate; deployment automated and repeatable where practical

**For BGP:** Separate BGP build credentials from deployment credentials and make the deployment repeatable through controlled procedures or automation.

**In simple terms:** Use separate credentials for building and deploying. Make deployment repeatable through automation where practical.

**Evidence to provide:** Credential/access configuration and a documented deployment pipeline or repeatable procedure. Use the actual BGP record and its controlled reference.

### G4.06 Affected data backed up or checkpointed; restoration or rollback feasibility validated before irreversible change

**For BGP:** Take the required BGP backups/checkpoints and validate recovery before irreversible migration, including decision/manifest reconciliation.

**In simple terms:** Protect affected data before an irreversible change and prove that recovery or rollback is feasible.

**Evidence to provide:** Backup/checkpoint evidence and recovery validation completed before the change. Use the actual BGP record and its controlled reference.

### G4.07 Operational runbook, monitoring/alert configuration and support handover ready

**For BGP:** Hand over BGP operational instructions for alerts, failed saves, pending decisions, integrity incidents, exports and recovery.

**In simple terms:** Give operations the instructions, alerts and support information needed to run the release.

**Evidence to provide:** An operational runbook, monitoring/alert configuration and support handover record. Use the actual BGP record and its controlled reference.

### G4.08 Release-readiness checklist (Appendix F) completed across scope, requirements, code, tests, security/privacy, dependencies, data, operations, deployment and approval

**For BGP:** Complete the BGP release-readiness checklist with all applicable system and frontend evidence, not a screenshot-only sign-off.

**In simple terms:** Use Appendix F to check the complete readiness pack, including evidence from earlier engineering gates.

**Evidence to provide:** The completed release-readiness checklist with links to each supporting record. Use the actual BGP record and its controlled reference.

### G4.09 Release authority is not the sole author of the release (role separation for Class 3-4)

**For BGP:** Record the named BGP release authority and demonstrate that the sole author is not the sole approver for this Class 3 release.

**In simple terms:** For Class 3 and 4, ensure that the sole release author is not also the sole release approver.

**Evidence to provide:** The release authorship and approval record demonstrating the required separation. Use the actual BGP record and its controlled reference.

### G4.10 Deployment executed with smoke tests and business verification; actual deployment, deviations, approvers and outcome recorded

**For BGP:** After authorisation, deploy BGP and record smoke tests, business checks, health monitoring, deviations and any rollback.

**In simple terms:** After release authorisation, deploy and run quick health checks and key business checks. Record what actually happened and any deviations.

**Evidence to provide:** The deployment log, smoke-test results, business verification and outcome record. This is post-authorisation evidence, not permission to deploy early. Use the actual BGP record and its controlled reference.

### G4.11 G4 release authorisation recorded

**For BGP:** Record BGP's production-release authorisation before production change, tied to the exact candidate and permitted conditions.

**In simple terms:** Record the authorised release decision before production deployment, identifying the exact release and any conditions.

**Evidence to provide:** A dated G4 decision with the release authority and reviewed evidence; link the later deployment outcome separately. Use the actual BGP record and its controlled reference.

<a id="g5"></a>

## G5 Operational acceptance

Accept BGP into normal operation after deployment. Confirm that the service team can support users, monitor trustworthy decisions and restore the platform safely.

**Decision responsibility:** Service owner and product owner. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-026–029, REQ-043, REQ-045–047, REQ-058; Blueprint Section 5.7.

### G5.01 Service catalogue entry, named service owner and support model

**For BGP:** Register the BGP service, named owner, support contacts and responsibilities for tenancy, integrity and recovery.

**In simple terms:** Register the live service, name its accountable owner and explain how it will be supported.

**Evidence to provide:** A service catalogue entry and agreed support model. Use the actual BGP record and its controlled reference.

### G5.02 Deployment record, smoke tests and early-life review

**For BGP:** Review BGP deployment and early-life evidence, including successful core journeys and any outstanding service issues.

**In simple terms:** Review the actual deployment and the service's first period in use, including basic health checks.

**Evidence to provide:** Deployment records, smoke-test results and an early-life review with actions. Use the actual BGP record and its controlled reference.

### G5.03 Monitoring of availability, performance, capacity, errors, security events, backups, certificate expiry and critical dependencies

**For BGP:** Monitor BGP availability, latency, errors, queues, draft-save failures, pending decisions, denied approvals, integrity checks, backups and dependencies.

**In simple terms:** Monitor service health and the supporting components so failures and approaching limits can be detected.

**Evidence to provide:** Monitoring and alert records covering the listed measures, events, backups, certificates and dependencies. Use the actual BGP record and its controlled reference.

### G5.04 Documented support channels, service hours, escalation paths and response targets

**For BGP:** Publish BGP support hours, incident contacts, escalation paths and response targets with named responsibility.

**In simple terms:** Tell users how to get help, when support operates and how urgent problems are escalated.

**Evidence to provide:** Published support contacts, hours, escalation paths and response targets. Use the actual BGP record and its controlled reference.

### G5.05 Incident, problem, change, maintenance and vulnerability records

**For BGP:** Keep BGP incident, problem, change, maintenance and vulnerability records with owners and dates.

**In simple terms:** Keep records of outages, underlying problems, changes, maintenance and security weaknesses.

**Evidence to provide:** Current service-management records with owners, status and relevant dates. Use the actual BGP record and its controlled reference.

### G5.06 Root-cause analysis for significant or recurring incidents with tracked corrective actions

**For BGP:** Investigate significant or recurring BGP failures such as unconfirmed decisions, repeated save loss or integrity mismatches and verify corrective action.

**In simple terms:** Investigate major or repeated incidents to find their underlying causes and prevent recurrence.

**Evidence to provide:** Root-cause reports and tracked corrective actions with completion checks. Use the actual BGP record and its controlled reference.

### G5.07 Vulnerability remediation within service targets (critical: 7 days Class 3-4, 14 days Class 2; high: 30 days Class 3-4, 60 days Class 2)

**For BGP:** Track BGP Class 3 critical vulnerability remediation within seven calendar days and high vulnerabilities within thirty, subject to stricter obligations.

**In simple terms:** Fix vulnerabilities within the applicable service target: critical within 7 days for Class 3–4 or 14 for Class 2; high within 30 or 60 days respectively. Apply stricter agreed obligations where relevant.

**Evidence to provide:** A vulnerability log showing severity, relevant dates, remediation and any permitted authorised deviation. Use the actual BGP record and its controlled reference.

### G5.08 S1 incident acknowledgement within target (1 hour Class 3-4, 4 hours Class 2)

**For BGP:** Demonstrate BGP's S1 acknowledgement process meets the one-hour Class 3 target and assigns active ownership.

**In simple terms:** Acknowledge an S1 critical incident within one hour for Class 3–4 or four hours for Class 2. Acknowledgement means responding and taking ownership, not necessarily resolving it.

**Evidence to provide:** Incident timestamps and ownership records demonstrating the response target. Use the actual BGP record and its controlled reference.

### G5.09 Backup restoration tested on schedule (quarterly Class 3-4, at least semi-annually Class 2) with results compared to RPO/RTO

**For BGP:** Test BGP restoration at least quarterly in a clean environment; check ordinary data against one-hour RPO/eight-hour RTO and acknowledged decisions against the separate zero-loss requirement.

**In simple terms:** Test restoring backups at least quarterly for Class 3–4 or twice a year for Class 2. Compare data loss and recovery time with the agreed limits.

**Evidence to provide:** Restore-test reports showing the schedule, recovered data and results against RPO and RTO. Use the actual BGP record and its controlled reference.

### G5.10 Access review completed on schedule (quarterly Class 3-4, at least annually Class 2)

**For BGP:** Review BGP access at least quarterly, including approvers, administrators, service accounts, operators and independent verification custody.

**In simple terms:** Check that people still need their permissions at least quarterly for Class 3–4 or annually for Class 2.

**Evidence to provide:** Access-review records and evidence that unnecessary access was removed. Use the actual BGP record and its controlled reference.

### G5.11 Enhancements and changes processed through the same traceability, review, testing and release controls

**For BGP:** Apply BGP requirements, review, testing and release controls to later enhancements; do not weaken immutable-history or tenant protections during maintenance.

**In simple terms:** Apply the same change controls to later enhancements as to the original release.

**Evidence to provide:** Change records linked to requirements, reviews, tests and release approvals. Use the actual BGP record and its controlled reference.

### G5.12 Service review reports and improvement backlog maintained

**For BGP:** Review BGP operational results and maintain improvements linked to user difficulty, support incidents and service measures.

**In simple terms:** Review how the service is performing and maintain an ordered list of improvements.

**Evidence to provide:** Service-review reports and a current improvement backlog with owners. Use the actual BGP record and its controlled reference.

### G5.13 G5 operational acceptance recorded

**For BGP:** Record the service and product owners' actual BGP operational acceptance, including any permitted remaining conditions.

**In simple terms:** Record the authorised acceptance of the service into normal operations and any remaining conditions.

**Evidence to provide:** A G5 operational-acceptance decision linked to readiness and early-life evidence. Use the actual BGP record and its controlled reference.

<a id="g6"></a>

## G6 Retirement / closure

Close BGP software delivery or retire a defined BGP service scope. Preserve tenant records and governance history, and avoid disabling a continuing service during project closure.

**Decision responsibility:** Sponsor, data owner and service owner. Named appointments and delegation must be recorded; the role label is not an appointment.

**BGP source links:** REQ-030–031, REQ-048, REQ-051, REQ-057–058; DEC06 and DEC12.

### G6.01 Retirement reason, affected users, replacement service, dependencies and approved date confirmed

**For BGP:** If BGP is being retired, approve the reason, tenant impact, replacement/export arrangements, dependencies and retirement date.

**In simple terms:** For retirement, explain why the service is ending, who is affected, what replaces it and when it will stop.

**Evidence to provide:** An approved retirement record covering users, dependencies, replacement arrangements and date. Use the actual BGP record and its controlled reference.

### G6.02 Transition and communication plan, including data export or migration

**For BGP:** Plan BGP tenant communication, authorised exports, migrations and reconciliation before any service shutdown.

**In simple terms:** Plan how users and data will move and how affected people will be informed.

**Evidence to provide:** A transition and communication plan with applicable export or migration steps. Use the actual BGP record and its controlled reference.

### G6.03 Retention, archival, transfer or secure-deletion decisions applied to data and records

**For BGP:** Apply BGP's approved retention, legal-hold, actor-attribution and disposal decisions; retain DEC06 resolutions as the policy basis.

**In simple terms:** Decide which records to keep, archive, transfer or securely delete, then carry out those decisions under the applicable retention rules.

**Evidence to provide:** Approved data-disposition decisions and evidence of transfer, archival or secure deletion. Use the actual BGP record and its controlled reference.

### G6.04 Accounts, credentials, integrations, domains, certificates, pipelines, infrastructure and supplier services disabled

**For BGP:** Disable only BGP accounts, integrations, domains, certificates, pipelines and infrastructure included in the approved retirement scope.

**In simple terms:** For assets in the approved retirement scope, remove the accounts, connections, infrastructure and supplier services no longer needed.

**Evidence to provide:** A decommissioning checklist and completion records. Keep operational assets needed by a continuing service under its handover owner. Use the actual BGP record and its controlled reference.

### G6.05 Source, releases, configuration, decisions, test evidence, licences and operational records archived

**For BGP:** Archive BGP source/releases, configuration, decision records, tests, licences, ADRs and operational evidence under controlled access.

**In simple terms:** Preserve the controlled technical and operational history needed after closure.

**Evidence to provide:** An archive containing the listed source, releases, configuration, approvals, tests, licences and service records. Use the actual BGP record and its controlled reference.

### G6.06 Final asset inventory and archive location recorded

**For BGP:** Record BGP's final asset inventory and the locations and custodians of retained tenant and project records.

**In simple terms:** Record the final assets and where the retained records can be found.

**Evidence to provide:** A final asset inventory and archive index with responsible custodians. Use the actual BGP record and its controlled reference.

### G6.07 Financial and contractual closure verified

**For BGP:** Settle or transfer BGP contractual and financial obligations, including ongoing support commitments if the service continues.

**In simple terms:** Settle or transfer payments and contractual obligations for the work being closed.

**Evidence to provide:** Financial reconciliation and contract closure/transfer confirmations. Use the actual BGP record and its controlled reference.

### G6.08 Lessons learned, benefits achieved and outstanding actions captured

**For BGP:** Document BGP delivery lessons, measured benefits and outstanding actions; preserve links to the later Gate 7 review where still due.

**In simple terms:** Record what was learned, what value was achieved and who owns anything still outstanding.

**Evidence to provide:** A closure review with lessons, benefits evidence and assigned open actions. Use the actual BGP record and its controlled reference.

### G6.09 Client or sponsor acceptance recorded

**For BGP:** Obtain the authorised BGP client/sponsor acceptance of the specific closure or retirement scope.

**In simple terms:** Obtain the authorised client's or sponsor's acceptance of the closure or retirement outcome.

**Evidence to provide:** An acceptance record stating the scope and any accepted outstanding actions. Use the actual BGP record and its controlled reference.

### G6.10 G6 closure decision

**For BGP:** Record BGP's G6 decision, responsible authorities and evidence; distinguish closing delivery from ending the live platform.

**In simple terms:** Record the final authorised closure decision and its scope. Project closure does not by itself require a continuing live service to be shut down.

**Evidence to provide:** A G6 decision linked to the closure/retirement evidence and any continuing operational ownership. Use the actual BGP record and its controlled reference.

## BGP work packages and their gate evidence

Work packages are implementation units, not extra approval gates. The following is a navigation aid derived from the approved sequence. Completing a package does not waive the gate controls above.

| Package | What BGP needs | Main gate evidence |
| --- | --- | --- |
| WP01 Repository and delivery controls | Reproducible source, synthetic fixtures and a requirement ledger | G0 authority, G3 implementation controls and recurring Gate 5 reporting |
| WP02 Discovery and assurance decisions | Users, roles, data, threat/privacy review and independent assurance plan | Gate 2/G1 requirements and Gate 3/G2 design readiness |
| WP03 Identity and membership | Registration, sessions, MFA, invitations and project permissions | G2 design, G3 code and G4-R access/revocation tests |
| WP04 Tenant isolation | Restricted PostgreSQL roles, RLS and pooled-connection/worker isolation | G2 design, blocking G3 isolation checks and G4-R adversarial tests |
| WP05 Templates and rule interpreter | Three framework fixtures, bounded rules, immutable publication and guided authoring | G1 scope, G2 rules/authoring design and G4-R publication/migration tests |
| WP06 Projects and evidence revisions | Atomic seeding, immutable evidence revisions and repeated occurrences | G3 implementation and G4-R evidence/concurrency checks |
| WP07 Decisions and exceptions | Valid exclusions, atomic authority/revision checks and append-only decisions | G2 transaction design and G4-R denial, retry and supersession evidence |
| WP08 Integrity and recovery | Separately controlled verification, failure tests and clean restoration | G2 DEC05 choice, G4-R integrity/durability tests and G5 restore evidence |
| WP09 Export and import | Complete versioned archives, safe actor mapping and reconciliation | G4-R round-trip/authorisation tests and G4 release evidence |
| WP10 Essential user journeys | Assigned work, forms, saves, blockers and decision summaries | G2 UI designs, G3 frontend implementation and G4-R journeys A–E |
| WP11 Usability and accessibility | Inclusive task testing, assistive-technology review and corrected failures | G4-R recommendation and release-blocker closure |
| WP12 Operations and hardening | Secrets, monitoring, vulnerabilities, performance and recovery readiness | G4 production readiness and G5 operational acceptance |
| WP13 Independent acceptance and release | Independent testing, user acceptance, migration/rollback and authorised release | G4-R, Gate 4/G4 and G5 handover |
| WP14 Optional and paid capabilities | Approved enabled scope and its attachment/reminder/practice/billing safeguards | Applicable G1/G2 decisions, G4-R conditional tests and G4 release controls |

The actual dependency graph remains the blueprint's Section 6 sequence. This table maps evidence; it does not replace the dependency graph or assign completion dates.

## Frontend coverage within the gates

The frontend requirements are part of BGP's delivery scope, not an optional visual layer. Preserve all 102 FE identifiers and record their individual implementation and acceptance evidence.

| Approved frontend area | Requirements | What the gate reviewer should be able to establish |
| --- | --- | --- |
| Navigation and shared context | FE-001–009 | The active organisation and next action are clear; switching organisations cannot leak old content |
| Identity and membership | FE-010–020 | Invitations, MFA, recovery, permissions and revocation respect server authority |
| Project creation and assigned work | FE-021–028 | First-project creation is atomic and retry-safe; users see only permitted tasks |
| Evidence and drafts | FE-029–039 | Revisions are preserved, completion remains valid and save status is truthful |
| Readiness and decisions | FE-040–054 | Blockers, exclusions, conditions, stale previews and uncertain outcomes cannot become false approvals |
| History and correction | FE-055–058 | Corrections supersede rather than overwrite the original record |
| Template authoring | FE-059–066 | Guided authoring, rule validation, immutable publication and explicit migration work |
| Export and import | FE-067–074 | Authorised records round-trip without transferring credentials or inventing historical authority |
| Inclusive use | FE-075–086 | Essential phone, keyboard and screen-reader journeys work; each user group meets the approved usability target |
| Integration and reliability | FE-087–096 | API errors, caches, sessions, network failures and version changes are handled safely |
| Conditional capabilities | FE-097–102 | Enabled optional features meet their approved safeguards; approval of controls does not itself enable scope |

At G1, confirm coverage and testable criteria. At G2, review UI01–UI10 layouts, phone variants, states and complete API contracts. At G3, review implementation and reproducible checks. At G4-R, inspect actual journey and inclusive-use results. At G4/G5, include frontend deployment compatibility, failure monitoring and support handover.

UI05 Gate readiness should explain each missing requirement in plain language and offer a permitted corrective action. UI06 Decision summary should explain the evidence reviewed and what the proposed outcome allows. This guide supplies BGP project guidance; it is not evidence that those interface behaviours have already been implemented.

## Choices that must come from actual project decisions

The approved sources identify these decision records. They may have been resolved later. Find the latest recorded resolution before marking a dependency blocked or satisfied.

| Record | Plain-language question |
| --- | --- |
| DEC01 | Who has accepted delivery and independent-review responsibility? |
| DEC02 | Which users and countries are served, and where may their data be hosted? |
| DEC03 | Which starter/framework and platform content may legally be used or distributed? |
| DEC04 | Which frontend stack, session/CSRF mechanism and pinned versions are selected? |
| DEC05 | Which failures are covered by decision durability, which mechanism supplies it, and who controls independent verification? |
| DEC06 | How long is each record kept, how do legal holds work, and how are disposal and attribution reconciled? |
| DEC07 | Which rule vocabulary, limits and three permitted framework fixtures are approved? |
| DEC08 | Which user samples, devices, networks and numeric performance budgets apply? |
| DEC09 | What staffing, funding, estimates and delivery dates are actually committed? |
| DEC10 | If paid use is enabled, which payment, tier, grace-period and deletion policies apply? |
| DEC11 | What emergency operator access is allowed, who authorises it, and how is it visible and independently controlled? |
| DEC12 | Who authorises a real-data import, and how are provenance and reconciliation verified? |

Approval of a requirement to decide something does not supply the missing choice. Where a later decision changes an approved contract or requirement, retain its authority and impact assessment.

## Example of one properly evidenced BGP subgate

For G4-R.05, a useful evidence entry identifies the test environment, configuration, two fictional tenants, data provenance and the tested build. The reviewer checks that the environment represents the intended production controls and that real customer evidence was not copied into an uncontrolled test. Writing “tested” or attaching a screen image without this context does not establish the requirement.

For a decision-concurrency test under G4-R.03, record the initial preview, the intervening evidence or membership change, the rejected stale submission and the resulting audit evidence. Identify the REQ/TST/FE links and actual build. This proves a specific behaviour; it does not by itself prove every release requirement.

These are examples of the evidence format, not claims that the tests have passed.

## Terms used in the guide

**Baseline:** The agreed version of a plan or requirement set used to judge changes and progress.

**Acceptance criteria:** Observable checks that show whether the result meets the agreed need.

**Traceability:** Links from a requirement to the work, tests, results and review that establish it.

**Evidence manifest:** The exact list of evidence revisions and related versions bound to a decision.

**RLS:** Row-level security. Database rules that restrict which tenant-owned rows a session can access.

**Idempotency:** Retrying the same permitted request does not create another project or decision accidentally.

**Superseding decision:** A new authorised correction linked to the original, with both records preserved.

**Residual risk:** Risk remaining after the protective actions have been applied.

**RPO:** The maximum acceptable period of ordinary data loss. BGP's baseline is at most one hour, distinct from the zero-loss requirement for acknowledged decisions within the approved failure envelope.

**RTO:** The maximum acceptable time to restore service. BGP's baseline is eight hours, with clean-environment restoration evidence.

**Independent assurance:** Review or testing by an appropriately separate, competent person; owner approval alone is not a substitute.

## Sources and revision boundary

Directly reviewed current project sources:

- Build_Governance_Platform_Development_Blueprint_v0.2_Approved.docx, 15 September 2026: Sections 1–9, REQ-001–058, UI01–UI10, WP01–WP14, TST/AC links, DEC01–DEC12 and APR-001.
- BGP_Complete_Frontend_Requirements_v1.1_Approved.md, 20 September 2026: FE-001–102, screen/state coverage, API gaps and FE-APR-001.

Gate and evidence numbering is inherited from the supplied tracker HTML/Markdown catalogue and governing PM Framework v1.1 and Software Development and Engineering Framework v1.2. Institutional rules are applied to BGP; they are not renamed as project-owned policy. G4-R is retained as the catalogue's separate recommendation checkpoint, not an additional production authorisation.

The supplied local directive copy identifies itself internally as version 1.0 Draft, while the attachment label names version 1.2 Approved. It was not substituted for the approved baseline. The directly reviewed approved BGP blueprint identifies Directive v1.2 as controlling. This guide does not claim direct verification of the approved directive's full text or a current repository audit.

The supplied JSON/API tracker uses a combined G4 layout with different item numbers. This guide follows the HTML/Markdown numbering: G4-R.01–10 correspond to JSON/API G4.01–10; the separate G4-R.11 recommendation record has no standalone item there; G4.01–11 correspond to JSON/API G4.11–21. Do not match the two catalogues on the G4 number alone.

Version 1.0 creates the BGP-specific guide requested on 21 September 2026. It does not overwrite the KenAddme package, change BGP's approved requirements, rewrite existing evidence, reset completed work, claim new approvals or modify a deployed application. Keep the current execution tracker as the source of actual status and evidence.
