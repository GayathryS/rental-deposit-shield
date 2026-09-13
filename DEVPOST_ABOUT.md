# Rental Deposit Shield 🛡️

## 💡 Inspiration

Almost everyone who has ever rented has a version of the same story: you move out, and weeks
later a fraction of your deposit comes back with a vague "damages" list attached — a carpet
stain that was there on day one, "repainting" that's really just normal wear, a cleaning fee
for a unit you left spotless. The amounts are small enough that fighting them feels like more
trouble than it's worth, so almost nobody does. Multiply that by hundreds of millions of
tenancies and it's one of the largest quiet transfers of money there is.

We realized the reason people don't fight back isn't that they're wrong — it's **friction**.
Winning means cross-referencing your own move-in evidence, reading a dense statute, and
drafting a formal, correctly-worded demand letter. That's exactly the kind of multi-step,
tool-using, judgment-heavy task that an **agent** is built for. And it's not a US problem or a
long-term-lease problem — it's a renter problem, everywhere, including short-term stays like
Airbnb. That universality is what made us want to build **Rental Deposit Shield**.

## 🧾 What it does

You upload your **move-in walkthrough video**. The agent extracts **screenshots** from it as
evidence, reconciles each one against the landlord's itemized move-out deductions, applies the
**deposit rules for your jurisdiction**, and — only after you explicitly approve — drafts a
formal, evidence-cited **demand letter** you can download and send.

Each deduction is sorted into one of three buckets:

- **Pre-existing** — already visible in the move-in walkthrough → *disputable*
- **Normal wear and tear** — which the law bars from deductions → *disputable*
- **Genuine damage** — no baseline record and not wear → *conceded in good faith*

The recoverable amount is simply the sum of the disputable deductions:

$$
R \;=\; \sum_{i=1}^{n} d_i \,\cdot\, \mathbb{1}\!\left[\,p_i \,\lor\, w_i\,\right]
$$

where $d_i$ is the value of deduction $i$, $p_i = 1$ if it matches a pre-existing condition in
the walkthrough, and $w_i = 1$ if it's normal wear. On our demo case — a landlord withholding
$\$2{,}365$ of a $\$2{,}400$ deposit — the agent recovers

$$
R = 650 + 180 + 240 + 75 + 120 + 900 = \$2{,}165,
$$

conceding the one honest charge (a $\$200$ cleaning fee). Arguing *credibly* rather than
greedily is a feature, not an accident — it's what makes the letter persuasive. The letter also
surfaces the jurisdiction's bad-faith exposure, e.g. in California a landlord acting in bad
faith may owe up to

$$
L_{\max} = 2D \quad (\text{twice the deposit } D),
$$

which is often the sentence that actually gets a deposit returned.

## 🧠 How we built it

The whole thing is an **AWS Strands agent**, exercising three core primitives:

- **Tools** — three `@tool` functions the agent orchestrates:
  `reconcile_visual_baseline` (walkthrough evidence vs. the landlord's claim),
  `lookup_tenant_law` (the jurisdiction's statute or platform policy), and
  `generate_dispute_letter` (the demand letter).
- **Hooks** — a `HookProvider` that logs every tool call for a full audit trail *and* enforces
  the **human-in-the-loop gate**: when the agent tries to generate the letter, the hook stops
  it via `BeforeToolCallEvent.cancel_tool` until a human approves.
- **Bounded execution** — a `SlidingWindowConversationManager` caps context, and the workflow
  is a fixed four-step pipeline with a hard human stop before the one irreversible action.

Around that core we built an interactive **Streamlit** web app. The move-in video is decoded
with **imageio + ffmpeg** to pull the evidence frames; the same agent also runs headless from
the terminal. Everything runs **offline with no API keys or cloud credentials** thanks to
realistic mock case data, so a judge can `pip install -r requirements.txt && streamlit run
app.py` and see the entire flow in under a minute.

To make jurisdictions pluggable, the wear-vs-damage engine is jurisdiction-agnostic — only the
citation, refund deadline, forum, and consequence change per rule set — so California, New York,
Texas, India's Model Tenancy Act, and Airbnb's short-term-stay policy are all just data behind
one classifier.

## 📚 What we learned

- **`BeforeToolCallEvent.cancel_tool` is a beautifully clean place to put a safety gate.**
  Instead of bolting approval onto the UI, the guarantee lives in the agent runtime itself —
  the same hook protects both the web app and the CLI.
- **A good agent knows when to *not* argue.** Conceding the one fair charge made every version
  of the output more convincing than a maximalist "dispute everything" bot.
- **Offline-first is a design constraint worth honoring.** Splitting into a deterministic
  pipeline (that calls the tools directly) and an opt-in live Bedrock path meant the demo is
  reproducible for anyone, instantly.
- **Framing matters as much as code.** The moment we stopped saying "US tenant law" and started
  saying "the rules for *your* jurisdiction," the product read as what it is — a tool for
  renters anywhere.

## 🧗 Challenges we faced

- **Terminal-to-web without forking the logic.** `streamlit run app.py` re-executes the whole
  script and can't block on `input()`, so we detect the Streamlit runtime and dispatch to the
  dashboard while the CLI keeps its terminal gate — both sharing one domain layer and one hook.
- **Getting evidence to actually *show*.** Streamlit lazy-loads images over a separate request,
  so headless captures of the evidence frames kept coming back blank until we polled the DOM
  until every `<img>` had real pixels before snapshotting.
- **Generalizing the law honestly.** India's Model Tenancy Act is a *model* law that states
  adopt individually, and Airbnb is platform policy, not statute — so we labeled each accurately
  (Rent Authority vs. Resolution Center) rather than pretending one rule fits all.
- **Making the demo feel like the product.** We drove the *real* website with a headless
  browser for genuine screenshots and added a natural neural voiceover, so the demo shows what
  we actually built, not a mockup.

## 🚀 What's next

Real vision on the walkthrough video and OCR on the landlord's statement (so the reconciliation
is fully automatic), all-50-states + more countries of deposit rules, and one-click delivery —
certified mail, e-signature, and a small-claims/Rent-Court filing packet.

---

*Rental Deposit Shield is a hackathon prototype and an information tool — not legal advice.*
