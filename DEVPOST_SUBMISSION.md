# Devpost Submission — Rental Deposit Shield

> Pre-filled answers for the AWS Strands Agents Hackathon Devpost form (**Everyday Agents**
> track). Copy each section into the matching field.

---

## Project name
Rental Deposit Shield

## Elevator Pitch (one sentence)
Rental Deposit Shield is an AWS Strands agent that turns your move-in walkthrough video into
screenshot evidence, reconciles it against a landlord's or Airbnb host's deposit deductions,
applies the deposit rules for your jurisdiction, and — only after you approve — drafts a
formal, evidence-cited demand letter to get your money back.

---

## Problem & Solution summary

**Problem.** Landlords in the U.S. hold **$45+ billion** in security deposits, and wrongful
withholding is one of the most common — and least contested — disputes. Renters get charged
for **pre-existing conditions** (already there at move-in) and **normal wear and tear** (which
the law bars from deductions). The exact same trap hits **Airbnb guests** facing host damage
claims through the Resolution Center, and renters in **India**, where the **Model Tenancy Act,
2021** caps deposits at two months' rent and bars wear-and-tear charges — but enforcement still
falls on the renter. Contesting it means cross-referencing your own evidence, reading dense
rules, and drafting a legally-framed letter, so most people just eat the loss.

**Solution.** Rental Deposit Shield collapses that into one auditable agent run that works
across all of those contexts:
1. **Reconciles visual baseline** — extracts screenshots from the renter's move-in walkthrough
   video and matches every line on the deduction statement against them, flagging pre-existing
   conditions (the cited frames are shown right in the UI).
2. **Looks up the applicable rule** — US state statutes (CA § 1950.5, NY § 238-a,
   TX § 92.101 et seq.), **India — Model Tenancy Act, 2021**, or **Airbnb's short-term-stay
   policy** — to reclassify remaining items as *normal wear-and-tear* vs. *potential damage*.
3. **Generates a dispute letter** — only after the user **explicitly approves** — writing it to
   `./dispute_letter.txt` and offering a one-click download, with the deadline, forum, and
   consequence tailored to the chosen jurisdiction.

On the built-in demo case, a landlord withholds **$2,365 of a $2,400 deposit**; the agent
identifies **$2,165** as disputable and concedes the one genuinely reasonable charge in good
faith — arguing *credibly*, not greedily.

---

## What it does (feature list)
- **Interactive Streamlit dashboard** (`streamlit run app.py`) — sidebar case inputs, an
  editable claimed-deductions table, and a jurisdiction / rental-type selector.
- **Video → screenshot evidence** — upload a move-in walkthrough video (or load the sample);
  the agent extracts frames as evidence, tagged red PRE-EXISTING / green MOVE-IN OK, and the
  cited frames reappear as thumbnails beside each disputed charge.
- **Live agent workflow** — three Strands tools execute with real-time progress cards.
- **Human-in-the-loop safeguard** — nothing is drafted until you click **Approve & Generate
  Dispute Notice**.
- **Multi-jurisdiction** — 🇺🇸 CA / NY / TX, 🇮🇳 India (Model Tenancy Act 2021),
  🏠 Airbnb / short-term stay.
- **Terminal mode too** — the same agent runs headless via `python app.py`.

## How we built it (using the AWS Strands SDK)
- **AWS Strands Agents SDK (`strands-agents`)** as the agent framework, fronted by
  **Streamlit** for the web UI, with **imageio + ffmpeg** extracting screenshot evidence from
  the uploaded walkthrough video and **Pillow** rendering fallbacks.
- **Three custom `@tool`s** — `reconcile_visual_baseline`, `lookup_tenant_law`, and
  `generate_dispute_letter` — registered on a Strands `Agent`.
- **A `HookProvider` (`DisputeGuardHook`)** on `AgentInitializedEvent`, `BeforeToolCallEvent`,
  and `AfterToolCallEvent` for an audit trail and the **human-in-the-loop gate**: in CLI mode
  it cancels the letter tool via `BeforeToolCallEvent.cancel_tool` on a decline; in the web app
  the **Approve** button is the gate (`enforce_terminal_gate=False`).
- **A jurisdiction-agnostic rules engine** — one wear-vs-damage classifier drives every
  jurisdiction; only the citation, deadline, forum, and consequence differ, so adding India and
  Airbnb was purely data.
- **Bounded execution** via `SlidingWindowConversationManager` plus a fixed 4-step pipeline with
  a hard human stop before the irreversible action.
- **Realistic mock data** baked into `app.py` so everything runs offline with **no API keys or
  AWS credentials**, while an opt-in `RDS_LIVE=1` mode runs the same tools/hook against a live
  Amazon Bedrock model.

---

## Challenges we overcame
- **Terminal-to-web without forking the logic.** `streamlit run app.py` re-executes the whole
  script and can't block on `input()`. We detect the Streamlit runtime and dispatch to the
  dashboard, while the CLI keeps its terminal gate — both share one domain layer and one hook.
- **Generalizing the law honestly.** India's **Model Tenancy Act, 2021** is a *model* law that
  states adopt individually (many still use their own Rent Control Acts), and **Airbnb is
  platform policy, not statute** — so we labeled each accurately (forum = Rent Authority for
  India, Resolution Center / card dispute for Airbnb) rather than pretending one law fits all.
- **Making evidence visible.** We extract screenshots from the walkthrough video and show the
  cited frames next to the disputed charges, so the argument is legible at a glance.
- **Keeping the reasoning credible.** The agent concedes charges it can't support in good faith,
  which makes the demand letter far more persuasive.

## Accomplishments we're proud of
- A genuinely useful, end-to-end agent that turns a walkthrough video + rules into a send-ready legal letter.
- One clean demonstration of the core Strands primitives — **Tools, Hooks, Bounded Execution**.
- A hard, auditable **human-in-the-loop** guardrail on the only irreversible action.
- **Multi-jurisdiction from day one** (US, India, Airbnb) on a single rules engine.
- **Zero-friction reproducibility**: `pip install -r requirements.txt && streamlit run app.py`.

## Future Roadmap
- **Real evidence ingestion**: a vision model to analyze the walkthrough video frames (and a
  move-out video) and OCR the landlord's / host's itemized statement.
- **Per-state India coverage** (Maharashtra, Karnataka, Delhi, etc.) instead of one model-law
  entry, plus more US states and other countries.
- **Native Airbnb flow**: pre-fill from a reservation and file directly through the Resolution
  Center.
- **Actual delivery**: certified-mail / e-signature and a small-claims (or Rent Court) filing
  packet.

---

## Built With
`python` · `aws` · `strands-agents` · `amazon-bedrock` · `streamlit` · `imageio` · `ffmpeg` · `pillow` · `pandas`

## How to run (for judges)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py     # offline, no credentials; pick a jurisdiction, approve, download
```

## Disclaimer
Rental Deposit Shield is a prototype and an information tool, **not legal advice**.
