# 🎬 Rental Deposit Shield — 2-Minute Demo Video Script (Web App)

A second-by-second transcript and recording guide for a **120-second browser demo** of the
Streamlit app, for the AWS Strands Agents Hackathon (**Everyday Agents** track).

- **Total runtime:** 2:00
- **Format:** browser screen recording (Loom / QuickTime) + voice-over
- **Goal:** show the problem, the jurisdiction selector (US / India / Airbnb), the evidence
  photo gallery, the three Strands tools running live, the human-in-the-loop approval, and the
  downloadable dispute letter — with no cloud credentials.

---

## ✅ Pre-recording checklist

1. **Launch the app from a clean shell:**
   ```bash
   cd ~/personal/rental-deposit-shield
   source venv/bin/activate
   pip install -r requirements.txt          # first time only
   rm -f dispute_letter.txt
   streamlit run app.py
   ```
2. **Browser prep.** Open `http://localhost:8501`. Zoom to ~110–125% so text is legible.
   Hide the bookmarks bar. Use a clean browser profile (no extensions/notifications).
3. **Theme.** Default light or dark both look good; dark reads better on video.
   (☰ menu → Settings → Theme.)
4. **Window.** Full-screen the browser. Close other tabs. Silence notifications.
5. **Recorder.** Loom (browser) or `Cmd+Shift+5` (macOS). Record the browser window only, mic on.
6. **Dry run once** end-to-end so click timing feels natural, then `rm -f dispute_letter.txt`
   and hard-refresh (`Cmd+Shift+R`) to reset session state before the real take.
7. **Cursor.** Move deliberately; pause on each button ~1s before clicking so viewers track it.

---

## 🎞️ Second-by-second script

### [0:00 – 0:12] — Hook / Problem  *(screen: the app header + badges)*
> **VO:** "Your landlord — or Airbnb host — kept $2,365 of your $2,400 deposit, for stains and
> nail holes that were already there when you moved in. Most people never fight it. Rental
> Deposit Shield does — an AI agent built on the AWS Strands SDK."

**Action:** Land on the **🛡️ Rental Deposit Shield** title with the **🟢 Everyday Agents Track**
badge. Read the one-line subtitle (US / India / Airbnb). Slow scroll to the top.

---

### [0:12 – 0:30] — Inputs + jurisdiction  *(screen: left sidebar)*
> **VO:** "Everything runs locally — no API keys. On the left I set the case, and here's the
> key part: the jurisdiction. It works for California, New York, Texas — and, because this is a
> global problem, India's Model Tenancy Act and Airbnb short-term stays too. I'll start with
> California. Below is the landlord's itemized deduction list — fully editable — $2,365 withheld."

**Action:** Point at **Tenant/Guest** and **Landlord/Host**. Open the **Jurisdiction / Rental
Type** dropdown so all five options are visible (🇺🇸 CA / NY / TX, 🇮🇳 India, 🏠 Airbnb),
select **California**. Scroll the **Claimed Deductions** table; hover a cell to show it's
editable. Point at the **Total Withheld** metric.

---

### [0:30 – 0:45] — Walkthrough video → evidence  *(screen: section 1)*
> **VO:** "Next, my evidence — my move-in walkthrough video. I upload it, and the agent pulls
> out screenshots of each condition. Red means it was already there at move-in, so it's
> disputable."

**Action:** Click **🎬 Load Sample Walkthrough Video**. The video player appears, then the green
"Extracted 6 evidence screenshots" confirms and the **frame gallery** fills in — pan across the
red **PRE-EXISTING** frames vs. the green **MOVE-IN OK** ones.

---

### [0:45 – 1:05] — Run the agent  *(screen: section 2 → live status)*
> **VO:** "Now I run the Strands agent. Three tools fire in order: tool one reconciles my
> photos against the claim; tool two looks up California Civil Code § 1950.5; tool three
> classifies what's just normal wear and tear — which a landlord legally can't charge for."

**Action:** Click **🚀 Run Audit Agent**. Let the **Running agent workflow…** status expand and
tick through Tool 1 → Tool 2 → Tool 3, then collapse to **✅ Audit complete**.

---

### [1:05 – 1:25] — The verdict + evidence thumbnails  *(screen: section 3)*
> **VO:** "The result: of $2,365 withheld, **$2,165 is recoverable**. And right here it shows
> the exact photos backing each disputed charge. The agent even concedes the one fair charge —
> the cleaning — in good faith."

**Action:** Point at the three tool cards, then the **💰 Recoverable $2,165** metric. Scroll the
DISPUTE/concede table, then the **📸 Evidence cited for disputed charges** thumbnail strip.
(Optional: open **Statute detail & agent audit log** to reveal the Strands hook trail, then close.)

---

### [1:25 – 1:40] — Human-in-the-loop  *(screen: section 4)*
> **VO:** "This is the important part. A demand letter is a real legal document — so nothing is
> drafted until a human approves. That safeguard is enforced by a Strands hook. I'll approve."

**Action:** Point at the ⚠️ warning banner. Pause ~1.5s on **✅ Approve & Generate Dispute
Notice**, then click it.

---

### [1:40 – 1:55] — The letter + download  *(screen: section 5)*
> **VO:** "Instantly — a formal demand letter citing my exact photos, the statute, the deadline,
> and the penalty. One click downloads it, ready to sign and send."

**Action:** Scroll the rendered letter card. Click **⬇️ Download Dispute Letter (.txt)**; show
the file landing in the browser's downloads bar.

---

### [1:55 – 2:00] — Close  *(screen: top of the letter or header)*
> **VO:** "Three Strands tools, a human-in-the-loop hook, bounded execution — across the US,
> India, and Airbnb. That's Rental Deposit Shield."

**Action:** Scroll back to the header for a clean final frame.

---

## 🎯 Key beats the judges must see
- [ ] Header with **🟢 Everyday Agents Track** badge.
- [ ] **Jurisdiction dropdown** (demo uses California; others available — keep it universal).
- [ ] **Load Sample Walkthrough Video** → the video player + the **extracted frame gallery** (red vs. green).
- [ ] **Run Audit Agent** → the live **three-tool** status animation.
- [ ] **💰 Recoverable $2,165** + the **evidence thumbnails** beside disputed charges.
- [ ] The **⚠️ approval gate**, then **✅ Approve & Generate Dispute Notice**.
- [ ] The rendered letter + a real **⬇️ Download Dispute Letter (.txt)** click.

## 🗣️ Tips
- Keep narration under ~245 words to fit 2:00 at a natural pace.
- If a step renders faster than the VO, pause your cursor — don't rush to the next click.
- **Multi-jurisdiction flourish (optional):** after downloading, switch the dropdown to
  **🇮🇳 India** or **🏠 Airbnb** and re-run to show the citation, deadline, and forum change in
  the letter (Rent Authority for India; Airbnb Resolution Center for short-term stays).
- Re-record cleanly by hard-refreshing the browser (`Cmd+Shift+R`) to reset the session.
- Prefer the live **Approve** click over any auto mode — the human-in-the-loop beat is the
  most compelling part of the story.
