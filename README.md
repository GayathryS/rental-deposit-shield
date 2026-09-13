# 🛡️ Rental Deposit Shield

**An AWS Strands agent — with an interactive Streamlit dashboard — that helps tenants and
Airbnb guests fight unfair security-deposit deductions.**

*AWS Strands Agents Hackathon · **Everyday Agents** track.*

## Abstract

Rental Deposit Shield takes a renter's **move-in walkthrough video**, extracts **screenshot
evidence** of the unit's condition, and reconciles it against a landlord's or host's
**move-out deduction claims**. It applies the **deposit rules for the tenancy's jurisdiction**
— the demo uses California, and the same flow extends to other regions and to short-term stays
like Airbnb — to separate normal wear-and-tear from chargeable damage. Then, only after
**explicit human approval**, it drafts a formal, **evidence-cited demand letter** you can
download.

It ships as an **interactive web app** (`streamlit run app.py`) and a **terminal app**
(`python app.py`), both powered by the same Strands tools + hook. Runs fully offline —
**no API keys and no AWS credentials required.**

---

## Architecture (ASCII)

```
                    ┌────────────── Streamlit Dashboard (browser) ──────────────┐
                    │  Sidebar inputs   Walkthrough video   Run Audit   HITL btn │
                    └───────────────────────────┬───────────────────────────────┘
                                                 │  (same domain logic + tools)
                                     streamlit run app.py │ python app.py
                                                 ▼
        ┌───────────────────────── Strands Agent ─────────────────────────┐
        │  system prompt · SlidingWindowConversationManager (bounded)      │
        │                                                                  │
        │   Tools (@tool)                    Hook (HookProvider)           │
        │   ├─ reconcile_visual_baseline     DisputeGuardHook              │
        │   ├─ lookup_tenant_law             ├─ AgentInitializedEvent      │
        │   └─ generate_dispute_letter ◄──── ├─ BeforeToolCallEvent ──────┐│
        │        │ writes                     │    (audit + HITL gate)     ││
        │        ▼                            └─ AfterToolCallEvent         ││
        │   ./dispute_letter.txt  /  ⬇ browser download                    ││
        └────────────────────────────────────────────────────────────────┘│
                                     │                                      │
             Step 1 ─ reconcile ─────┤                                      │
             Step 2 ─ apply law ─────┤                                      │
             Step 3 ─ HUMAN GATE ────┼──► "Approve & Generate" (web)  ◄─────┘
                                     │     input("...yes/no") (CLI)
             Step 4 ─ draft letter ──┘     (cancels the tool on decline)
```

Data flow: **move-in baseline** + **move-out deductions** + **state statute** → reconcile →
classify under statute → **human approval** → render + download `dispute_letter.txt`.

---

## Problem Statement

Landlords in the U.S. hold an estimated **$45+ billion** in tenant security deposits, and
wrongful withholding is one of the most common — and least contested — housing disputes.
Tenants routinely get charged for:

- **Pre-existing conditions** already there at move-in (stains, nail holes, mildew).
- **Normal wear and tear**, which nearly every state's law explicitly bars from deductions
  (faded paint, worn carpet, minor scuffs).

Contesting these charges means cross-referencing your own move-in evidence, reading dense
statutes, and drafting a legally-framed letter. That friction is why most tenants just eat
the loss — and the landlord keeps the money.

The same trap is everywhere: **Airbnb guests** hit with host damage claims through the
Resolution Center, and renters in **India**, where the **Model Tenancy Act, 2021** caps
deposits at two months' rent and bars wear-and-tear charges — but enforcement still falls on
the renter. Rental Deposit Shield handles all of these with one agent.

## Solution Overview

Rental Deposit Shield collapses that into a single, auditable agent run:

1. **Reconcile the evidence** — extract screenshots from the move-in walkthrough video and
   match every line on the landlord's statement against them, flagging pre-existing conditions.
2. **Apply the law** — reclassify remaining items as *normal wear-and-tear* (not chargeable)
   vs. *potential damage* (chargeable), citing the jurisdiction's statute or policy.
3. **Draft the demand — with a human in the loop** — only after the user clicks
   **Approve & Generate Dispute Notice** (web) or types `yes` (CLI) does the agent produce
   the letter, citing the specific photos and statute and quantifying the wrongful withholding.

On the built-in demo case, a landlord withholds **$2,365 of a $2,400 deposit** — the agent
identifies **$2,165** as disputable and concedes the one genuinely reasonable charge in good
faith.

---

## AWS Strands SDK Integration

### Tools — `@tool`
| Tool | Responsibility |
| --- | --- |
| `reconcile_visual_baseline` | Cross-reference the walkthrough's screenshot evidence vs. the move-out deductions; flag pre-existing conditions. |
| `lookup_tenant_law` | Apply the jurisdiction's rule — US states (CA § 1950.5, NY § 238-a, TX § 92.101 et seq.), India (Model Tenancy Act 2021), or Airbnb short-term-stay policy. |
| `generate_dispute_letter` | Draft the demand letter and write it to `./dispute_letter.txt`. |

### Hooks — `HookProvider`
`DisputeGuardHook` registers callbacks on `AgentInitializedEvent`, `BeforeToolCallEvent`, and
`AfterToolCallEvent`. It keeps an audit trail (surfaced in the web UI) **and enforces the
human-in-the-loop gate**: in CLI mode it cancels `generate_dispute_letter` via
`event.cancel_tool` on a "no"; in the web app the **Approve** button is the gate (the hook is
constructed with `enforce_terminal_gate=False` so it never blocks on terminal input).

### Bounded Execution
The agent is built with `SlidingWindowConversationManager(window_size=20)`, and the workflow
is a fixed 4-step sequence with a hard human stop before the irreversible action — the agent
cannot loop unboundedly or write anything on its own.

---

## Project Structure

```
rental-deposit-shield/
├── app.py                  # Streamlit dashboard + CLI + 3 tools + HITL hook + mock data
├── requirements.txt        # strands-agents, streamlit, pandas, pillow, imageio
├── scripts/                # Media generators (sample/house/demo videos)
│   ├── make_sample_videos.py
│   ├── make_house_videos.py
│   └── make_demo_video.py  # narrated demo from real app screenshots (Kokoro TTS)
├── media/                  # Generated videos (walkthroughs, narrated demo)
├── dispute_letter.txt      # Generated on an approved run
├── README.md               # This file
├── DEVPOST_SUBMISSION.md   # Pre-filled Devpost submission answers
├── VIDEO_SCRIPT.md         # Second-by-second browser demo recording guide
├── .gitignore
├── models/                 # Neural-TTS voice models (git-ignored, re-downloadable)
└── venv/                   # Local virtual environment (git-ignored)
```

---

## 🚀 Run the Web App (recommended)

**Prerequisites:** Python 3.10+ (developed on 3.11).

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate

# 2. Install dependencies (Strands SDK + Streamlit)
pip install -r requirements.txt

# 3. Launch the dashboard — opens http://localhost:8501 in your browser
streamlit run app.py
```

**In the browser:**
1. Adjust the **sidebar** inputs — Tenant/Guest, Landlord/Host, **jurisdiction** (the demo
   uses California; NY, TX, India, and Airbnb are also available), Deposit, and the editable
   **Claimed Deductions** table.
2. Upload a **move-in walkthrough video** — or click **🎬 Load Sample Walkthrough Video** — to
   enable the audit. The agent extracts **screenshot evidence** from the video into a gallery,
   and the cited frames reappear next to the disputed charges.
3. Click **🚀 Run Audit Agent** — watch the three tools execute in real time.
4. Review the reconciliation, statute, and per-item verdicts.
5. Click **✅ Approve & Generate Dispute Notice** (the human-in-the-loop gate).
6. Read the formatted letter and click **⬇️ Download Dispute Letter (.txt)**.

> If port 8501 is busy: `streamlit run app.py --server.port 8502`.

---

## 💻 Run the Terminal App

The same agent, no browser:

```bash
python app.py                   # interactive; type "yes" -> writes ./dispute_letter.txt
python app.py --state NY        # CA | NY | TX
python app.py --auto yes        # non-interactive approve (CI / recording)
python app.py --auto no         # non-interactive decline
RDS_LIVE=1 python app.py        # also invoke the live Strands/Bedrock agent (needs AWS)
```

> **Live mode** requires AWS credentials and Amazon Bedrock model access. Without them, the
> offline demo runs completely and the live step reports Bedrock is unavailable and exits
> cleanly.

---

## Disclaimer

Rental Deposit Shield is a hackathon prototype and an information tool. It is **not legal
advice** and does not create an attorney-client relationship. Consult a licensed attorney or
your local tenant-rights organization before taking legal action.
