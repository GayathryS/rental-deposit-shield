#!/usr/bin/env python3
"""
Rental Deposit Shield
=====================
An AWS Strands Agents application that helps tenants contest unfair security-deposit
deductions. It reconciles documented move-in baseline evidence against a landlord's
move-out deduction claims, applies state-specific tenant-protection statutes to
separate normal wear-and-tear from chargeable damage, and — only after explicit
human approval — drafts a formal demand letter.

Built for the AWS Strands Agents Hackathon · Everyday Agents track.

Two ways to run
---------------
1. Interactive web dashboard (recommended for the demo):

       streamlit run app.py

2. Terminal / CLI mode (writes ./dispute_letter.txt):

       python app.py
       python app.py --state NY          # CA | NY | TX
       python app.py --auto yes          # non-interactive approve
       RDS_LIVE=1 python app.py          # also invoke the live Bedrock agent (needs AWS)

The same Strands primitives back both entry points:
    * Tools  -> three @tool functions registered on the Agent
    * Hooks  -> a HookProvider that audits every tool call AND enforces a
                human-in-the-loop gate on the demand-letter tool via
                BeforeToolCallEvent.cancel_tool
    * Bounded execution -> SlidingWindowConversationManager caps the agent's context
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import textwrap

from strands import Agent, tool
from strands.hooks import (
    AfterToolCallEvent,
    AgentInitializedEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

try:  # bounded-execution helper (present in strands-agents >= 1.x)
    from strands.agent.conversation_manager import SlidingWindowConversationManager
except Exception:  # pragma: no cover - defensive fallback
    SlidingWindowConversationManager = None

try:  # streamlit is optional so `python app.py` works without it
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

# Where the CLI writes the final demand letter.
DISPUTE_LETTER_PATH = "./dispute_letter.txt"


# =====================================================================================
# 1. MOCK CASE DATA
# ---------------------------------------------------------------------------------
# Everything the agent reasons over lives here so the whole demo runs locally with no
# external calls. In production these would come from a tenant's uploaded photos, the
# signed move-in checklist, and the landlord's itemized statement.
# =====================================================================================

CASE = {
    "tenant": {
        "name": "Jordan Rivera",
        "address": "412 Maple Court, Apt 3B, San Jose, CA 95112",
        "email": "jordan.rivera@example.com",
        "phone": "(408) 555-0142",
    },
    "landlord": {
        "name": "Summit Ridge Property Management",
        "address": "1900 Almaden Expressway, Suite 210, San Jose, CA 95125",
    },
    "lease": {
        "move_in_date": "2023-08-01",
        "move_out_date": "2025-08-15",
        "deposit_amount": 2400.00,
    },
    "state": "CA",
}

# Documented at move-in with time-stamped photos and a signed walkthrough checklist.
MOVE_IN_BASELINE = [
    {
        "area": "Living Room", "component": "Carpet",
        "condition": "Pre-existing stain near the bay window (documented by prior tenant).",
        "pre_existing": True, "photo": "IMG_1012.jpg", "date": "2023-08-01",
    },
    {
        "area": "Kitchen", "component": "Wall",
        "condition": "Several nail holes from a prior tenant's shelving unit.",
        "pre_existing": True, "photo": "IMG_1015.jpg", "date": "2023-08-01",
    },
    {
        "area": "Bathroom", "component": "Grout",
        "condition": "Mildew discoloration along the tub line, present at move-in.",
        "pre_existing": True, "photo": "IMG_1021.jpg", "date": "2023-08-01",
    },
    {
        "area": "Living Room", "component": "Blinds",
        "condition": "One window-blind slat cracked at move-in.",
        "pre_existing": True, "photo": "IMG_1009.jpg", "date": "2023-08-01",
    },
    {
        "area": "Bedroom", "component": "Carpet",
        "condition": "Good condition, light ordinary wear only.",
        "pre_existing": False, "photo": "IMG_1030.jpg", "date": "2023-08-01",
    },
    {
        "area": "Whole Unit", "component": "Walls/Paint",
        "condition": "Freshly painted at move-in; minor scuffs expected with ordinary use.",
        "pre_existing": False, "photo": "IMG_1000.jpg", "date": "2023-08-01",
    },
]

# The landlord's itemized move-out deduction statement (totals $2,365 of a $2,400 deposit).
MOVE_OUT_DEDUCTIONS = [
    {"area": "Living Room", "component": "Carpet", "item": "Carpet replacement",
     "amount": 650.00, "claim": "Tenant-caused staining"},
    {"area": "Kitchen", "component": "Wall", "item": "Wall patch & repaint",
     "amount": 180.00, "claim": "Unauthorized holes in wall"},
    {"area": "Bathroom", "component": "Grout", "item": "Bathroom re-grout",
     "amount": 240.00, "claim": "Mildew damage"},
    {"area": "Living Room", "component": "Blinds", "item": "Blind replacement",
     "amount": 75.00, "claim": "Broken slat"},
    {"area": "Bedroom", "component": "Carpet", "item": "Carpet cleaning",
     "amount": 120.00, "claim": "Wear"},
    {"area": "Whole Unit", "component": "Walls/Paint", "item": "Repaint entire unit",
     "amount": 900.00, "claim": "Wall damage"},
    {"area": "Whole Unit", "component": "Cleaning", "item": "General cleaning",
     "amount": 200.00, "claim": "Unit left dirty"},
]

# Jurisdiction / rental-type rules. Long-term leases (US states, India) are statute-backed;
# short-term stays (Airbnb) are governed by platform policy. The same wear-vs-damage engine
# runs across all of them — only the citation, deadline, forum, and consequence differ.
# Keyword lists drive the wear-vs-damage call.
_WEAR_KEYWORDS = ["repaint", "paint", "carpet cleaning", "wear", "faded", "minor", "scuff"]

STATE_STATUTES = {
    "CA": {
        "citation": "California Civil Code § 1950.5",
        "return_deadline_days": 21,
        "forum": "small claims court",
        "consequence": (
            "under California Civil Code § 1950.5(l), a landlord who retains a deposit in bad "
            "faith may be liable for up to twice the deposit amount"
        ),
        "summary": (
            "A landlord may deduct only for (1) unpaid rent, (2) cleaning to restore the "
            "unit to its move-in level of cleanliness, (3) repair of damage beyond normal "
            "wear and tear, and (4) replacement of personal property where the lease permits. "
            "Normal wear and tear may NOT be deducted, and the landlord must provide an "
            "itemized statement within 21 days of move-out."
        ),
        "wear_and_tear_keywords": _WEAR_KEYWORDS,
    },
    "NY": {
        "citation": "New York Real Property Law § 238-a (see also Gen. Oblig. Law § 7-108)",
        "return_deadline_days": 14,
        "forum": "small claims court",
        "consequence": (
            "under N.Y. General Obligations Law § 7-108, a landlord who willfully violates the "
            "deposit rules may be liable for up to twice the deposit amount"
        ),
        "summary": (
            "A landlord must return the deposit within 14 days of the tenant vacating, along "
            "with an itemized statement of any deductions. Deductions are limited to unpaid "
            "rent and the reasonable cost of repairing damage beyond ordinary wear and tear; "
            "ordinary wear and tear may NOT be charged to the tenant."
        ),
        "wear_and_tear_keywords": _WEAR_KEYWORDS,
    },
    "TX": {
        "citation": "Texas Property Code § 92.101 et seq. (§§ 92.103, 92.104, 92.109)",
        "return_deadline_days": 30,
        "forum": "justice (small claims) court",
        "consequence": (
            "under Texas Property Code § 92.109, a landlord who acts in bad faith may be liable "
            "for $100 plus three times the wrongfully withheld portion plus attorney's fees"
        ),
        "summary": (
            "A landlord must refund the deposit within 30 days of surrender and, if any amount "
            "is withheld, provide an itemized written description of the deductions. Normal "
            "wear and tear — deterioration from ordinary use rather than negligence, "
            "carelessness, accident, or abuse — may NOT be deducted. A landlord who retains a "
            "deposit in bad faith is liable under § 92.109."
        ),
        "wear_and_tear_keywords": _WEAR_KEYWORDS,
    },
    "IN": {
        "citation": "India — Model Tenancy Act, 2021 (§ 11)",
        "return_deadline_days": None,
        "deadline_text": "the period required upon handover of vacant possession under the "
                         "Model Tenancy Act, 2021",
        "forum": "the Rent Authority / Rent Court constituted under the Model Tenancy Act, 2021",
        "consequence": (
            "under the Model Tenancy Act, 2021 the security deposit is capped (a maximum of two "
            "months' rent for residential premises) and must be refunded after only lawful "
            "deductions, and this dispute may be referred to the Rent Authority for adjudication"
        ),
        "summary": (
            "Under the Model Tenancy Act, 2021 — a model law being progressively adopted by "
            "Indian states — the residential security deposit is capped at a maximum of two "
            "months' rent, and the landlord must refund it, after deducting only lawful "
            "liabilities such as unpaid rent or damage beyond normal wear and tear, at the time "
            "of taking over vacant possession. Ordinary wear and tear may NOT be charged to the "
            "tenant. (Some states apply their own Rent Control Acts; adoption varies.)"
        ),
        "wear_and_tear_keywords": _WEAR_KEYWORDS,
    },
    "AIRBNB": {
        "citation": "Airbnb Host Damage Policy & Resolution Center Terms (short-term stay)",
        "return_deadline_days": 14,
        "forum": "Airbnb's Resolution Center (and, if unresolved, a payment dispute with my "
                 "card issuer)",
        "consequence": (
            "Airbnb's damage policy excludes ordinary wear and tear and requires documented "
            "proof, so unsupported or pre-existing-condition charges can be reversed through "
            "the Resolution Center"
        ),
        "summary": (
            "For short-term stays, a host's damage claim is handled through Airbnb's Resolution "
            "Center rather than a security-deposit statute. Hosts must document damage with "
            "evidence, claims exclude normal wear and tear, and guests may dispute a claim "
            "within the response window. Unsupported charges — or charges for conditions that "
            "pre-dated check-in — can be reversed."
        ),
        "wear_and_tear_keywords": _WEAR_KEYWORDS,
    },
}


def _deadline_str(statute) -> str:
    """Human phrasing for the refund deadline, tolerant of jurisdictions with no fixed day count."""
    if statute.get("deadline_text"):
        return statute["deadline_text"]
    days = statute.get("return_deadline_days")
    return f"{days} days" if days else "the required statutory period"


# =====================================================================================
# 2. PURE DOMAIN LOGIC  (parameterized so the web UI can pass user-edited inputs)
# ---------------------------------------------------------------------------------
# All functions fall back to the module mock data when called with no arguments, so the
# CLI, the @tool wrappers, and the Strands agent keep working unchanged.
# =====================================================================================

def _find_baseline(baseline, area: str, component: str):
    for entry in baseline:
        if entry["area"] == area and entry["component"] == component:
            return entry
    return None


def _reconcile(baseline=None, deductions=None):
    """Match each landlord deduction to the move-in baseline and flag disputable items."""
    baseline = baseline if baseline is not None else MOVE_IN_BASELINE
    deductions = deductions if deductions is not None else MOVE_OUT_DEDUCTIONS

    findings = []
    for ded in deductions:
        baseline_hit = _find_baseline(baseline, ded["area"], ded["component"])
        if baseline_hit and baseline_hit["pre_existing"]:
            findings.append({
                **ded,
                "status": "PRE_EXISTING",
                "reason": f"Condition documented at move-in ({baseline_hit['photo']}, "
                          f"{baseline_hit['date']}): {baseline_hit['condition']}",
                "evidence": baseline_hit["photo"],
                "disputable": True,
            })
        else:
            findings.append({
                **ded,
                "status": "NO_BASELINE_RECORD",
                "reason": "No matching pre-existing condition documented at move-in.",
                "evidence": None,
                "disputable": False,  # may still be reclassified by statute below
            })
    disputed_pre_existing = sum(f["amount"] for f in findings if f["status"] == "PRE_EXISTING")
    return {
        "findings": findings,
        "total_deducted": sum(f["amount"] for f in findings),
        "pre_existing_disputed_total": disputed_pre_existing,
    }


def _classify_law(state: str, baseline=None, deductions=None):
    """Apply the state's wear-and-tear rule to items with no pre-existing baseline record."""
    state = state.upper()
    statute = STATE_STATUTES.get(state)
    if statute is None:
        raise ValueError(
            f"No statute data for state '{state}'. Available: {', '.join(STATE_STATUTES)}"
        )

    reconciliation = _reconcile(baseline, deductions)
    classified = []
    for f in reconciliation["findings"]:
        if f["status"] == "PRE_EXISTING":
            classified.append({**f, "law_class": "PRE_EXISTING_EVIDENCE"})
            continue

        text = f"{f['item']} {f['claim']}".lower()
        if any(kw in text for kw in statute["wear_and_tear_keywords"]):
            classified.append({
                **f,
                "law_class": "NORMAL_WEAR",
                "disputable": True,
                "reason": f"Reclassified as normal wear and tear under {statute['citation']}; "
                          f"not chargeable to the tenant.",
            })
        else:
            classified.append({
                **f,
                "law_class": "POTENTIAL_DAMAGE",
                "disputable": False,
                "reason": "No baseline record and not clearly wear-and-tear; "
                          "likely a valid charge — conceded in good faith.",
            })

    disputed = [c for c in classified if c["disputable"]]
    disputed_total = sum(c["amount"] for c in disputed)
    return {
        "state": state,
        "statute": statute,
        "classified": classified,
        "disputed_items": disputed,
        "conceded_items": [c for c in classified if not c["disputable"]],
        "total_deducted": reconciliation["total_deducted"],
        "disputed_total": disputed_total,
        "amount_owed": disputed_total,  # amount wrongfully withheld
    }


def _compose_letter(state: str, case=None, baseline=None, deductions=None) -> str:
    """Assemble the formal demand letter from the reconciliation + statute analysis."""
    case = case if case is not None else CASE
    analysis = _classify_law(state, baseline, deductions)
    statute = analysis["statute"]
    tenant = case["tenant"]
    landlord = case["landlord"]
    lease = case["lease"]
    today = datetime.date.today().isoformat()

    deposit = float(lease["deposit_amount"])
    total_deducted = analysis["total_deducted"]
    amount_returned = max(0.0, deposit - total_deducted)

    def wrap(text, indent="  "):
        return textwrap.fill(" ".join(text.split()), width=78,
                             initial_indent=indent, subsequent_indent=indent)

    disputed_lines = []
    for i, c in enumerate(analysis["disputed_items"], start=1):
        tag = "pre-existing at move-in" if c["law_class"] == "PRE_EXISTING_EVIDENCE" \
            else "normal wear and tear"
        ev = f" [see {c['evidence']}]" if c.get("evidence") else ""
        header = f"{i}. {c['item']} ({c['area']}) — ${c['amount']:,.2f} — " \
                 f"disputed as {tag}.{ev}"
        disputed_lines.append(textwrap.fill(
            " ".join(header.split()), width=78,
            initial_indent="  ", subsequent_indent="     "))
        disputed_lines.append(wrap(c["reason"], indent="     "))
    disputed_block = "\n".join(disputed_lines) or "  (No disputable charges identified.)"

    conceded_block = "\n".join(
        f"  - {c['item']} ({c['area']}) — ${c['amount']:,.2f} — accepted as reasonable."
        for c in analysis["conceded_items"]
    ) or "  - None."

    intro = (
        f"I am writing regarding the ${deposit:,.2f} security deposit for the above "
        f"tenancy. Your itemized statement withheld ${total_deducted:,.2f} and returned "
        f"only ${amount_returned:,.2f}. After reconciling your deductions against my "
        f"time-stamped move-in documentation and the applicable law, I dispute "
        f"${analysis['disputed_total']:,.2f} of those charges and demand its return."
    )
    basis = (
        "The disputed conditions were either documented in writing and with time-stamped "
        "photographs at move-in / check-in, or constitute ordinary wear and tear, which is "
        f"not chargeable under {statute['citation']}. Deducting for pre-existing conditions "
        "and normal wear is not permitted."
    )
    demand = (
        f"I demand return of ${analysis['disputed_total']:,.2f} within "
        f"{_deadline_str(statute)} of the date of this letter. Please be aware that "
        f"{statute['consequence']}. If I do not receive the wrongfully withheld amount, I am "
        f"prepared to pursue this matter in {statute['forum']}."
    )
    contact = (
        f"I can be reached at {tenant.get('email','')} or {tenant.get('phone','')} to "
        "resolve this promptly."
    )

    body = f"""\
{today}

{tenant['name']}
{tenant.get('address','')}
{tenant.get('email','')} | {tenant.get('phone','')}

{landlord['name']}
{landlord.get('address','')}

RE: Demand for Return of Wrongfully Withheld Security Deposit
    Property: {tenant.get('address','')}
    Rental period: {lease.get('move_in_date','')} to {lease.get('move_out_date','')}

To Whom It May Concern:

{wrap(intro, indent="")}

APPLICABLE LAW — {statute['citation']}
{wrap(statute['summary'])}

DISPUTED CHARGES
{disputed_block}

CHARGES ACCEPTED IN GOOD FAITH
{conceded_block}

BASIS FOR DISPUTE
{wrap(basis)}

DEMAND
{wrap(demand)}

{wrap(contact)}

Sincerely,


{tenant['name']}
"""
    return body


# =====================================================================================
# 3. CUSTOM STRANDS TOOLS
# =====================================================================================

@tool
def reconcile_visual_baseline() -> dict:
    """Compare the tenant's documented move-in baseline (photos + walkthrough notes)
    against the landlord's move-out deduction claims to surface pre-existing conditions.

    Returns a structured reconciliation flagging each deduction that matches a
    pre-existing condition recorded at move-in and is therefore disputable.
    """
    return _reconcile()


@tool
def lookup_tenant_law(state: str = "CA") -> dict:
    """Apply state-specific security-deposit statutes to classify each deduction as
    normal wear-and-tear (not chargeable) versus potential tenant damage.

    Args:
        state: Two-letter state code. Supported: 'CA', 'NY', 'TX'.

    Returns the governing statute plus the disputable total after the wear-and-tear rule.
    """
    return _classify_law(state)


@tool
def generate_dispute_letter(state: str = "CA", output_path: str = DISPUTE_LETTER_PATH) -> str:
    """Draft a formal demand letter citing the move-in baseline evidence and the
    applicable statute, itemize the disputed charges, demand return of the wrongfully
    withheld deposit, and write it to ./dispute_letter.txt.

    Args:
        state: Two-letter state code governing the tenancy ('CA', 'NY', 'TX').
        output_path: File path to write the letter to (default ./dispute_letter.txt).

    Returns the letter text (and writes the same text to output_path).
    """
    letter = _compose_letter(state)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(letter)
    return letter


# =====================================================================================
# 4. HUMAN-IN-THE-LOOP GATE  (terminal / CLI)
# =====================================================================================

def approve_letter_generation() -> bool:
    """Terminal yes/no gate the tenant must clear before any letter file is written.

    Uses the literal prompt `input("Approve letter generation? yes/no: ")`. Honors the
    RDS_AUTO_CONFIRM env var (or --auto flag) for non-interactive runs, and fails safe
    to 'no' on EOF.
    """
    auto = os.environ.get("RDS_AUTO_CONFIRM")
    if auto is not None:
        decision = auto.strip().lower() in ("y", "yes")
        print(f"Approve letter generation? yes/no: [auto-{'yes' if decision else 'no'}]")
        return decision

    while True:
        try:
            answer = input("Approve letter generation? yes/no: ").strip().lower()
        except EOFError:
            print("\n(no input received / EOF — failing safe to 'no')")
            return False
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer 'yes' or 'no'.")


# =====================================================================================
# 5. STRANDS HOOK — audit trail + HITL enforcement on the letter tool
# =====================================================================================

class DisputeGuardHook(HookProvider):
    """A Strands HookProvider that (a) writes an audit line for every tool call and
    (b) enforces the human-in-the-loop gate: if the agent tries to invoke
    generate_dispute_letter without approval, the call is cancelled via
    BeforeToolCallEvent.cancel_tool — so no file is written.

    Set enforce_terminal_gate=False (the web app does this) to keep the audit trail
    without triggering the terminal input() prompt; the UI provides its own approval.
    """

    def __init__(self, state: str = "CA", enforce_terminal_gate: bool = True):
        self.state = state
        self.enforce_terminal_gate = enforce_terminal_gate
        self.audit_log: list[str] = []

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(AgentInitializedEvent, self._on_init)
        registry.add_callback(BeforeToolCallEvent, self._before_tool)
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    @staticmethod
    def _tool_name(event) -> str:
        tu = event.tool_use
        if isinstance(tu, dict):
            return tu.get("name", "<unknown>")
        return getattr(tu, "name", "<unknown>")

    def _on_init(self, event: AgentInitializedEvent) -> None:
        msg = "[audit] Agent initialized — Rental Deposit Shield tools armed."
        self.audit_log.append(msg)
        print(msg)

    def _before_tool(self, event: BeforeToolCallEvent) -> None:
        name = self._tool_name(event)
        self.audit_log.append(f"[audit] -> tool call: {name}")
        print(f"[audit] -> tool call: {name}")

        if name == "generate_dispute_letter" and self.enforce_terminal_gate:
            if not approve_letter_generation():
                event.cancel_tool = (
                    "Tenant declined to authorize the demand letter. No file written."
                )
                self.audit_log.append("[audit] x letter tool CANCELLED by human reviewer.")
                print("[audit] x letter tool CANCELLED by human reviewer.")

    def _after_tool(self, event: AfterToolCallEvent) -> None:
        name = self._tool_name(event)
        self.audit_log.append(f"[audit] done: {name}")
        print(f"[audit] done: {name}")


# =====================================================================================
# 6. AGENT BUILDER (shared by CLI, web UI, and live mode)
# =====================================================================================

SYSTEM_PROMPT = """\
You are Rental Deposit Shield, an assistant that helps tenants contest unfair security
deposit deductions. Always follow this order: (1) reconcile_visual_baseline, then
(2) lookup_tenant_law for the tenant's state, and only then (3) generate_dispute_letter.
Never fabricate evidence or statutes. The demand letter requires explicit human approval.
"""


def build_agent(hook: DisputeGuardHook, model=None) -> Agent:
    """Construct the Strands Agent with our tools, the guard hook, and a bounded
    (sliding-window) conversation manager. Passing model=None keeps construction
    credential-free; a real model is only needed to actually invoke the agent."""
    kwargs = dict(
        model=model,
        tools=[reconcile_visual_baseline, lookup_tenant_law, generate_dispute_letter],
        system_prompt=SYSTEM_PROMPT,
        hooks=[hook],
    )
    if SlidingWindowConversationManager is not None:
        kwargs["conversation_manager"] = SlidingWindowConversationManager(window_size=20)
    return Agent(**kwargs)


# =====================================================================================
# 7. STREAMLIT WEB DASHBOARD
# =====================================================================================

JURISDICTION_LABELS = {
    "CA": "🇺🇸 California (US)",
    "NY": "🇺🇸 New York (US)",
    "TX": "🇺🇸 Texas (US)",
    "IN": "🇮🇳 India — Model Tenancy Act 2021",
    "AIRBNB": "🏠 Airbnb / Short-term stay",
}

RDS_CSS = """
<style>
  .rds-badge {display:inline-block; padding:4px 12px; border-radius:999px;
    background:#132f4c; color:#66b2ff; font-weight:600; font-size:0.78rem;
    border:1px solid #1e4976; letter-spacing:.02em;}
  .rds-badge.aws {background:#3a2c0a; color:#ffb84d; border-color:#6b4e12; margin-left:6px;}
  .rds-title {font-size:2.05rem; font-weight:800; margin:2px 0 0 0; line-height:1.1;}
  .rds-sub {color:#8b98a5; margin:2px 0 0 0; font-size:0.95rem;}
  .rds-hr {margin:10px 0 4px 0; border:none; border-top:1px solid #2a3441;}
</style>
"""


def _build_case_from_inputs(tenant_name, landlord_name, state, deposit):
    return {
        "tenant": {**CASE["tenant"], "name": tenant_name},
        "landlord": {**CASE["landlord"], "name": landlord_name},
        "lease": {**CASE["lease"], "deposit_amount": float(deposit)},
        "state": state,
    }


# Bundled sample walkthrough (rendered by scripts/make_house_videos.py).
SAMPLE_WALKTHROUGH = os.path.join("media", "house_move_in_before.mp4")

# Where to sample evidence frames from (fractions of the video) — skips the intro/outro
# cards in the sample walkthrough and lands on the room shots.
_FRAME_FRACTIONS = [0.20, 0.35, 0.49, 0.63, 0.75, 0.87]


def _extract_evidence_frames(video_src, n=6):
    """Pull up to n screenshots from a walkthrough video — the renter's real input.

    `video_src` is a file path or a Streamlit UploadedFile. Returns a list of PIL images;
    returns [] if imageio/ffmpeg is unavailable or the video can't be read, so callers
    can fall back to the rendered condition placeholders.
    """
    try:
        import imageio.v2 as imageio
        from PIL import Image
    except Exception:
        return []

    tmp_path, path = None, video_src
    if not isinstance(video_src, str):          # UploadedFile -> temp file for ffmpeg
        import tempfile
        fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as fh:
            fh.write(video_src.getvalue())
        path = tmp_path

    frames = []
    try:
        reader = imageio.get_reader(path, "ffmpeg")
        try:
            total = reader.count_frames()
        except Exception:
            total = reader.get_meta_data().get("nframes") or 0
        if total and total != float("inf"):
            for f in _FRAME_FRACTIONS[:n]:
                idx = max(0, min(int(total * f), int(total) - 1))
                frames.append(Image.fromarray(reader.get_data(idx)))
        reader.close()
    except Exception:
        frames = []
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return frames


def _evidence_image(entry, width: int = 440, height: int = 300):
    """Render a labeled placeholder 'photo' for a documented move-in condition.

    A real deployment would display the tenant's actual uploaded photo; for the offline
    demo this simulates one so the evidence is visible in the UI. Returns a PIL image.
    """
    import textwrap as _tw

    from PIL import Image, ImageDraw, ImageFont

    def font(size):
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # very old Pillow
            return ImageFont.load_default()

    room_tint = {
        "Living Room": (214, 229, 245),
        "Kitchen": (245, 236, 214),
        "Bathroom": (214, 245, 238),
        "Bedroom": (232, 224, 245),
        "Whole Unit": (236, 238, 240),
    }.get(entry["area"], (230, 232, 235))

    pre = bool(entry.get("pre_existing"))
    badge_color = (220, 53, 69) if pre else (33, 150, 83)
    badge_text = "PRE-EXISTING" if pre else "MOVE-IN OK"

    img = Image.new("RGB", (width, height), room_tint)
    d = ImageDraw.Draw(img)

    # Header strip.
    d.rectangle([0, 0, width, 46], fill=(33, 37, 41))
    d.text((14, 13), f"{entry['area']} · {entry['component']}",
           fill=(255, 255, 255), font=font(18))

    # Status badge (top-right, over the header).
    bt = font(13)
    tw = d.textlength(badge_text, font=bt)
    d.rounded_rectangle([width - tw - 26, 10, width - 10, 36], radius=8, fill=badge_color)
    d.text((width - tw - 18, 15), badge_text, fill=(255, 255, 255), font=bt)

    # "Simulated" watermark so it's clearly a demo placeholder.
    d.text((14, 56), "simulated evidence photo", fill=(120, 128, 138), font=font(12))

    # Documented condition, wrapped.
    y = 84
    for line in _tw.wrap(entry["condition"], width=46):
        d.text((14, y), line, fill=(33, 37, 41), font=font(15))
        y += 22

    # Footer strip: filename + capture date.
    d.rectangle([0, height - 40, width, height], fill=(248, 249, 250))
    d.text((14, height - 29), f"photo: {entry['photo']}", fill=(73, 80, 87), font=font(13))
    dt = str(entry.get("date", ""))
    if dt:
        dtw = d.textlength(dt, font=font(13))
        d.text((width - dtw - 14, height - 29), dt, fill=(73, 80, 87), font=font(13))

    return img


def render_dashboard() -> None:
    import time
    import pandas as pd

    st.set_page_config(page_title="Rental Deposit Shield", page_icon="🛡️", layout="wide")
    st.markdown(RDS_CSS, unsafe_allow_html=True)

    # ---- Header ---------------------------------------------------------------
    st.markdown(
        '<div class="rds-title">🛡️ Rental Deposit Shield '
        '<span style="font-size:1.1rem;font-weight:600;color:#8b98a5;">'
        '— AWS Strands AI Agent</span></div>'
        '<div style="margin-top:8px;">'
        '<span class="rds-badge">🟢 Everyday Agents Track</span>'
        '<span class="rds-badge aws">⚡ AWS Strands Agents Hackathon</span>'
        '</div>'
        '<p class="rds-sub">Audits a landlord\'s or Airbnb host\'s deposit deductions against '
        'your move-in / check-in evidence and the applicable tenant law (US, India) or '
        'platform policy — then drafts a demand letter, with a human in the loop.</p>'
        '<hr class="rds-hr"/>',
        unsafe_allow_html=True,
    )

    # ---- Sidebar: inputs ------------------------------------------------------
    with st.sidebar:
        st.header("⚙️ Case Inputs")
        tenant_name = st.text_input("Tenant / Guest Name", value=CASE["tenant"]["name"])
        landlord_name = st.text_input("Landlord / Host Name", value=CASE["landlord"]["name"])
        state = st.selectbox(
            "Jurisdiction / Rental Type",
            options=list(STATE_STATUTES.keys()), index=0,
            format_func=lambda k: JURISDICTION_LABELS.get(k, k),
            help="Long-term leases (US states, India) are statute-backed; "
                 "Airbnb short-term stays follow platform policy.",
        )
        st.caption(f"📖 {STATE_STATUTES[state]['citation']}")
        deposit = st.number_input(
            "Deposit Amount ($)", min_value=0.0,
            value=float(CASE["lease"]["deposit_amount"]), step=50.0, format="%.2f",
        )

        st.markdown("**Claimed Deductions** (editable)")
        st.caption("The landlord's itemized move-out statement.")
        ded_df = pd.DataFrame(MOVE_OUT_DEDUCTIONS)
        edited = st.data_editor(
            ded_df, num_rows="dynamic", hide_index=True, width="stretch",
            key="ded_editor",
            column_config={
                "area": st.column_config.TextColumn("Area"),
                "component": st.column_config.TextColumn("Component"),
                "item": st.column_config.TextColumn("Item"),
                "amount": st.column_config.NumberColumn("Amount ($)", format="$%.2f",
                                                        min_value=0.0),
                "claim": st.column_config.TextColumn("Landlord's Claim"),
            },
        )
        deductions = [
            {k: (float(r[k]) if k == "amount" else str(r[k])) for k in
             ("area", "component", "item", "amount", "claim")}
            for r in edited.to_dict("records")
        ]
        total_claimed = sum(d["amount"] for d in deductions)
        st.metric("Total Withheld by Landlord", f"${total_claimed:,.2f}")

    case = _build_case_from_inputs(tenant_name, landlord_name, state, deposit)

    # ---- Section 1: Move-in baseline upload -----------------------------------
    st.subheader("1 · Move-in Walkthrough Video")
    st.caption("The renter uploads a dated walkthrough video; the agent extracts "
               "screenshots as evidence of the unit's condition at move-in.")
    up_col, btn_col = st.columns([2, 1])
    with up_col:
        video_file = st.file_uploader(
            "Upload your move-in walkthrough video",
            type=["mp4", "mov", "m4v", "webm"], accept_multiple_files=False)
    with btn_col:
        st.write("")
        st.write("")
        if st.button("🎬 Load Sample Walkthrough Video", width="stretch"):
            st.session_state["baseline_loaded"] = True
            st.session_state["use_sample_video"] = True
    if video_file is not None:
        st.session_state["baseline_loaded"] = True
        st.session_state["use_sample_video"] = False

    baseline_ready = st.session_state.get("baseline_loaded", False)
    if baseline_ready:
        # Resolve the walkthrough source: uploaded file, else the bundled sample.
        video_src = None
        if video_file is not None:
            video_src = video_file
        elif st.session_state.get("use_sample_video") and os.path.exists(SAMPLE_WALKTHROUGH):
            video_src = SAMPLE_WALKTHROUGH

        if video_src is not None:
            st.video(video_src)

        frames = _extract_evidence_frames(video_src) if video_src is not None else []
        if frames:
            st.success(f"✅ Extracted {len(frames)} evidence screenshots from the "
                       "walkthrough — matched to the documented conditions.")
        else:
            st.success(f"✅ Walkthrough loaded — {len(MOVE_IN_BASELINE)} documented conditions.")

        evidence_by_photo = {}
        with st.expander("🖼️ Evidence screenshots (from the walkthrough video)", expanded=True):
            st.caption("Frames pulled from the video. Red = pre-existing at move-in "
                       "(disputable); green = good at move-in.")
            cols = st.columns(3)
            for i, entry in enumerate(MOVE_IN_BASELINE):
                img = frames[i] if i < len(frames) else _evidence_image(entry)
                evidence_by_photo[entry["photo"]] = img
                badge = "🔴 pre-existing" if entry["pre_existing"] else "🟢 good at move-in"
                cols[i % 3].image(
                    img, width="stretch",
                    caption=f"{entry['area']} / {entry['component']} — {badge}")
        st.session_state["evidence_by_photo"] = evidence_by_photo

        with st.expander("View documented conditions as a table", expanded=False):
            st.dataframe(pd.DataFrame(MOVE_IN_BASELINE), hide_index=True, width="stretch")
    else:
        st.info("Upload a walkthrough video or click **Load Sample Walkthrough Video** "
                "to enable the audit.")

    # ---- Run Audit Agent ------------------------------------------------------
    st.subheader("2 · Run the Strands Audit Agent")
    run = st.button("🚀 Run Audit Agent", type="primary", disabled=not baseline_ready,
                    width="stretch")

    if run:
        # Construct the real Strands agent (registers tools + hook, fires
        # AgentInitializedEvent). enforce_terminal_gate=False -> the browser button is
        # the human gate, so no terminal input() is attempted.
        hook = DisputeGuardHook(state=state, enforce_terminal_gate=False)
        build_agent(hook)

        with st.status("Running agent workflow…", expanded=True) as status:
            st.write("🔧 Tool 1 — **Visual Evidence Reconciliation** (baseline vs. claim)")
            time.sleep(0.7)
            recon = _reconcile(MOVE_IN_BASELINE, deductions)
            hook.audit_log.append("[audit] -> tool call: reconcile_visual_baseline")
            n_pre = sum(1 for f in recon["findings"] if f["status"] == "PRE_EXISTING")
            st.write(f"   → {n_pre} deduction(s) match pre-existing move-in conditions.")

            st.write(f"🔧 Tool 2 — **Tenant Law / Platform Policy Lookup** "
                     f"({JURISDICTION_LABELS.get(state, state)})")
            time.sleep(0.7)
            analysis = _classify_law(state, MOVE_IN_BASELINE, deductions)
            hook.audit_log.append("[audit] -> tool call: lookup_tenant_law")
            st.write(f"   → Applied {analysis['statute']['citation']}.")

            st.write("🔧 Tool 3 — **Normal Wear & Tear Classification**")
            time.sleep(0.7)
            n_wear = sum(1 for c in analysis["classified"] if c["law_class"] == "NORMAL_WEAR")
            st.write(f"   → {n_wear} charge(s) reclassified as non-chargeable wear and tear.")
            hook.audit_log.append("[audit] classification complete")

            status.update(label="✅ Audit complete", state="complete", expanded=False)

        st.session_state["audit"] = {
            "state": state, "recon": recon, "analysis": analysis, "case": case,
            "baseline": MOVE_IN_BASELINE, "deductions": deductions,
            "audit_log": hook.audit_log,
            "evidence_by_photo": st.session_state.get("evidence_by_photo", {}),
        }
        st.session_state["approved"] = False

    # ---- Results (persist across reruns) --------------------------------------
    audit = st.session_state.get("audit")
    if audit:
        _render_results(audit)
        _render_hitl_and_letter(audit)


def _render_results(audit) -> None:
    import pandas as pd
    analysis = audit["analysis"]
    recon = audit["recon"]
    statute = analysis["statute"]

    st.subheader("3 · Execution Results")

    # Three visual tool cards.
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.markdown("**🔍 Tool 1 · Reconciliation**")
        n_pre = sum(1 for f in recon["findings"] if f["status"] == "PRE_EXISTING")
        st.metric("Pre-existing matches", n_pre)
        st.caption("Walkthrough frames vs. landlord claim")
    with c2.container(border=True):
        st.markdown("**⚖️ Tool 2 · Tenant Law / Policy**")
        st.metric("Rule applied", audit["state"])
        st.caption(statute["citation"])
    with c3.container(border=True):
        st.markdown("**🧹 Tool 3 · Wear & Tear**")
        n_wear = sum(1 for c in analysis["classified"] if c["law_class"] == "NORMAL_WEAR")
        st.metric("Reclassified as wear", n_wear)
        st.caption("Not chargeable to tenant")

    # Headline financial metrics.
    m1, m2, m3, m4 = st.columns(4)
    deposit = float(audit["case"]["lease"]["deposit_amount"])
    m1.metric("Deposit", f"${deposit:,.0f}")
    m2.metric("Landlord withheld", f"${analysis['total_deducted']:,.0f}")
    m3.metric("💰 Recoverable", f"${analysis['disputed_total']:,.0f}",
              help="Amount wrongfully withheld — the agent's demand.")
    conceded = sum(c["amount"] for c in analysis["conceded_items"])
    m4.metric("Conceded (good faith)", f"${conceded:,.0f}")

    # Per-item classification table.
    rows = []
    for c in analysis["classified"]:
        rows.append({
            "Verdict": "🔴 DISPUTE" if c["disputable"] else "🟢 concede",
            "Item": c["item"],
            "Area": c["area"],
            "Amount": f"${c['amount']:,.2f}",
            "Classification": c["law_class"].replace("_", " ").title(),
            "Evidence": c.get("evidence") or "—",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    # Evidence thumbnails (frames pulled from the walkthrough) for disputed charges.
    by_photo = {e["photo"]: e for e in audit.get("baseline", [])}
    ev_frames = audit.get("evidence_by_photo", {})
    ev_items = [c for c in analysis["disputed_items"]
                if c.get("evidence") and c["evidence"] in by_photo]
    if ev_items:
        st.markdown("**📸 Evidence screenshots cited for disputed charges**")
        cols = st.columns(min(4, len(ev_items)))
        for i, c in enumerate(ev_items):
            img = ev_frames.get(c["evidence"]) or _evidence_image(
                by_photo[c["evidence"]], width=360, height=260)
            cols[i % len(cols)].image(
                img, width="stretch",
                caption=f"{c['item']} — ${c['amount']:,.0f} disputed")

    with st.expander("📋 Statute detail & agent audit log", expanded=False):
        st.markdown(f"**{statute['citation']}** · return within {_deadline_str(statute)}")
        st.write(statute["summary"])
        st.markdown("**Consequence / escalation:** " + statute["consequence"])
        st.markdown("---")
        st.markdown("**Strands hook audit trail:**")
        st.code("\n".join(audit.get("audit_log", [])) or "(empty)", language="text")


def _render_hitl_and_letter(audit) -> None:
    st.subheader("4 · Human-in-the-Loop Safeguard")

    if not st.session_state.get("approved"):
        st.warning(
            "⚠️ A demand letter is a real, outbound legal document. Review the analysis "
            "above, then approve to generate it. **Nothing is drafted until you approve.**"
        )
        if st.button("✅ Approve & Generate Dispute Notice", type="primary",
                     width="stretch"):
            st.session_state["approved"] = True

    if st.session_state.get("approved"):
        letter = _compose_letter(audit["state"], audit["case"], audit["baseline"],
                                 audit["deductions"])
        # Persist to disk for parity with the CLI (and so a reviewer can find the artifact).
        try:
            with open(DISPUTE_LETTER_PATH, "w", encoding="utf-8") as fh:
                fh.write(letter)
        except OSError:
            pass

        st.success("✅ Dispute notice generated. Review, sign, and send by certified mail.")
        st.subheader("5 · Formal Dispute Letter")
        st.code(letter, language="text")
        st.download_button(
            "⬇️ Download Dispute Letter (.txt)",
            data=letter,
            file_name="dispute_letter.txt",
            mime="text/plain",
            type="primary",
            width="stretch",
        )
        st.caption("⚖️ Prototype / information tool — not legal advice.")


# =====================================================================================
# 8. CLI PRESENTATION + PIPELINE  (python app.py)
# =====================================================================================

def _hr(char: str = "-") -> str:
    return char * 80


def print_banner(state: str, live: bool) -> None:
    print(_hr("="))
    print("  RENTAL DEPOSIT SHIELD".center(80))
    print("  AWS Strands Agents — tenant security-deposit dispute assistant".center(80))
    print(_hr("="))
    mode = "LIVE (Strands + Bedrock)" if live else "OFFLINE DEMO (no API keys / no AWS creds)"
    print(f"  Mode : {mode}")
    print(f"  State: {state}  |  Statute: {STATE_STATUTES[state]['citation']}")
    print(f"  Output letter: {DISPUTE_LETTER_PATH}")
    print(f"  Tip  : run the web app with  streamlit run app.py")
    print(_hr("="))


def print_reconciliation(recon: dict) -> None:
    print("\nSTEP 1 — reconcile_visual_baseline()")
    print(_hr())
    print(f"  Landlord withheld: ${recon['total_deducted']:,.2f}\n")
    print(f"  {'Item':<26}{'Area':<14}{'Amount':>10}   Status")
    print(f"  {'-'*26}{'-'*14}{'-'*10}   {'-'*22}")
    for f in recon["findings"]:
        amount = f"${f['amount']:,.2f}"
        print(f"  {f['item']:<26}{f['area']:<14}{amount:>10}   {f['status']}")
    print(f"\n  Pre-existing (evidence-based) disputed so far: "
          f"${recon['pre_existing_disputed_total']:,.2f}")


def print_law(analysis: dict) -> None:
    statute = analysis["statute"]
    print(f"\nSTEP 2 — lookup_tenant_law(state='{analysis['state']}')")
    print(_hr())
    print(f"  {statute['citation']}  (return within {_deadline_str(statute)})")
    print(textwrap.fill(statute["summary"], width=78,
                        initial_indent="  ", subsequent_indent="  "))
    print("\n  Per-item classification:")
    for c in analysis["classified"]:
        flag = "DISPUTE" if c["disputable"] else "concede"
        print(f"    [{flag:>7}] {c['item']:<26} ${c['amount']:>8,.2f}  ({c['law_class']})")
    print(f"\n  >> Total wrongfully withheld (disputed): ${analysis['disputed_total']:,.2f}")


def run_offline_pipeline(state: str) -> None:
    recon = reconcile_visual_baseline()
    print_reconciliation(recon)

    analysis = lookup_tenant_law(state=state)
    print_law(analysis)

    print("\n" + _hr("="))
    print("  HUMAN-IN-THE-LOOP CONFIRMATION REQUIRED")
    print(_hr("="))
    print(f"  About to draft a demand letter demanding ${analysis['disputed_total']:,.2f}")
    print(f"  under {analysis['statute']['citation']} and write it to {DISPUTE_LETTER_PATH}.")
    approved = approve_letter_generation()

    if not approved:
        print("\n" + _hr("="))
        print("  x Letter generation ABORTED by tenant. No file was written.")
        print(_hr("="))
        return

    print("\nSTEP 4 — generate_dispute_letter()  ->  " + DISPUTE_LETTER_PATH)
    print(_hr())
    letter = generate_dispute_letter(state=state)
    print(_hr("="))
    print(letter)
    print(_hr("="))
    print(f"  Draft written to {os.path.abspath(DISPUTE_LETTER_PATH)}")


def run_live_agent(state: str, hook: DisputeGuardHook) -> None:
    print("\n" + _hr("="))
    print("  LIVE MODE — invoking the Strands agent via Amazon Bedrock")
    print(_hr("="))
    try:
        agent = build_agent(hook)
        prompt = (
            f"My landlord in {state} withheld most of my security deposit. "
            "Reconcile my move-in baseline against their deductions, check the tenant "
            "law, and if there is a valid dispute, draft the demand letter."
        )
        result = agent(prompt)
        print("\n--- Agent response ---")
        print(result)
    except Exception as exc:
        print(f"\n  Live agent could not run: {type(exc).__name__}: {exc}")
        print("  This is expected without AWS credentials / Bedrock model access.")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rental Deposit Shield — Strands agent")
    parser.add_argument("--state", default=CASE["state"], choices=sorted(STATE_STATUTES),
                        help="Jurisdiction / rental type: CA, NY, TX (US), IN (India), "
                             "or AIRBNB (short-term stay).")
    parser.add_argument("--auto", choices=["yes", "no"], default=None,
                        help="Non-interactive answer for the human-in-the-loop prompt.")
    parser.add_argument("--live", action="store_true",
                        help="Also run the live Strands/Bedrock agent (needs AWS creds).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    state = args.state.upper()

    if args.auto is not None:
        os.environ["RDS_AUTO_CONFIRM"] = args.auto

    live = args.live or os.environ.get("RDS_LIVE") == "1"

    print_banner(state, live)

    hook = DisputeGuardHook(state=state)
    build_agent(hook)

    run_offline_pipeline(state)

    if live:
        run_live_agent(state, hook)

    print("\n[audit] tool-call log:")
    for line in hook.audit_log:
        print("   " + line)
    return 0


# =====================================================================================
# 9. ENTRY POINT  — dispatch between Streamlit dashboard and CLI
# =====================================================================================

def _in_streamlit_runtime() -> bool:
    """True only when launched via `streamlit run app.py` (not plain `python app.py`)."""
    if st is None:
        return False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


if _in_streamlit_runtime():
    render_dashboard()
elif __name__ == "__main__":
    sys.exit(main())
