#!/usr/bin/env python3
"""
make_sample_videos.py — render two SAMPLE preview videos for Rental Deposit Shield.

These are synthetic, programmatically-rendered walkthroughs (Pillow frames -> mp4 via the
ffmpeg bundled with imageio-ffmpeg). They are NOT live screen recordings of the app — every
frame is watermarked "SAMPLE PREVIEW". Use them as concept/teaser previews; record the real
demo with the browser + VIDEO_SCRIPT.md.

Outputs:
    media/sample_teaser.mp4      (~19s punchy teaser)
    media/sample_full_demo.mp4   (~40s guided walkthrough)

Requires (video only, not needed to run the app):  pip install imageio imageio-ffmpeg

Run:
    ./venv/bin/python scripts/make_sample_videos.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import imageio.v2 as imageio

# Import the real app for authentic numbers / statute / letter text.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402

W, H = 1280, 720
FPS = 24
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")

# ---- palette (Streamlit dark theme) -------------------------------------------------
BG = (14, 17, 23)
PANEL = (22, 26, 34)
SIDEBAR = (18, 21, 28)
BORDER = (42, 52, 65)
TXT = (250, 250, 250)
MUTED = (139, 152, 165)
BLUE = (102, 178, 255)
BLUE_BG = (19, 47, 76)
AMBER = (255, 184, 77)
AMBER_BG = (58, 44, 10)
GREEN = (46, 204, 113)
GREEN_D = (33, 150, 83)
RED = (235, 77, 90)
RED_D = (200, 55, 66)

# ---- real data ----------------------------------------------------------------------
A = app._classify_law("CA")
DEPOSIT = float(app.CASE["lease"]["deposit_amount"])
WITHHELD = A["total_deducted"]
RECOVER = A["disputed_total"]
CONCEDED = sum(c["amount"] for c in A["conceded_items"])
STATUTE = A["statute"]["citation"]
LETTER = app._compose_letter("CA")


# ---- fonts --------------------------------------------------------------------------
_FONT_CACHE = {}


def font(size, mono=False):
    key = (size, mono)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    cands = (["/System/Library/Fonts/Menlo.ttc",
              "/System/Library/Fonts/Courier.ttc"] if mono else
             ["/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/Library/Fonts/Arial.ttf"])
    f = None
    for p in cands:
        try:
            f = ImageFont.truetype(p, size)
            break
        except Exception:
            continue
    if f is None:
        try:
            f = ImageFont.load_default(size=size)
        except TypeError:
            f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


# ---- drawing helpers ----------------------------------------------------------------

def new_frame(bg=BG):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    # honesty watermark, bottom-right
    d.text((W - 14, H - 22), "SAMPLE PREVIEW · synthetic render",
           font=font(13), fill=(90, 100, 112), anchor="rs")
    return img, d


def panel(d, box, fill=PANEL, outline=BORDER, radius=16, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def chip(d, xy, text, fg, bg, pad=(12, 6), fsize=15):
    f = font(fsize)
    tw = d.textlength(text, font=f)
    x, y = xy
    d.rounded_rectangle([x, y, x + tw + pad[0] * 2, y + fsize + pad[1] * 2],
                        radius=999, fill=bg)
    d.text((x + pad[0], y + pad[1]), text, font=f, fill=fg)
    return x + tw + pad[0] * 2


def shield(d, cx, cy, s, color=BLUE):
    # simple shield silhouette + check
    w, h = s, int(s * 1.15)
    pts = [(cx - w // 2, cy - h // 2), (cx + w // 2, cy - h // 2),
           (cx + w // 2, cy + h // 6), (cx, cy + h // 2), (cx - w // 2, cy + h // 6)]
    d.polygon(pts, fill=color)
    # check mark
    d.line([(cx - w // 5, cy), (cx - w // 30, cy + h // 6),
            (cx + w // 4, cy - h // 6)], fill=BG, width=max(3, s // 12), joint="curve")


def header_band(d, small=False):
    shield(d, 54, 52, 40)
    d.text((88, 30), "Rental Deposit Shield", font=font(30), fill=TXT)
    d.text((90, 66), "AWS Strands AI Agent", font=font(16), fill=MUTED)
    x = chip(d, (400, 40), "Everyday Agents Track", BLUE, BLUE_BG)
    chip(d, (x + 10, 40), "AWS Strands Hackathon", AMBER, AMBER_BG)


# ---- scene builders (return a base PIL image) ---------------------------------------

def sc_title():
    img, d = new_frame()
    shield(d, W // 2, 250, 96)
    d.text((W // 2, 340), "Rental Deposit Shield", font=font(58), fill=TXT, anchor="ms")
    d.text((W // 2, 392), "An AWS Strands AI Agent that gets your deposit back",
           font=font(24), fill=MUTED, anchor="ms")
    x0 = W // 2 - 205
    x = chip(d, (x0, 430), "Everyday Agents Track", BLUE, BLUE_BG, fsize=17)
    chip(d, (x + 12, 430), "US · India · Airbnb", GREEN, (16, 46, 30), fsize=17)
    return img


def sc_problem():
    img, d = new_frame()
    d.text((W // 2, 150), "The problem", font=font(22), fill=BLUE, anchor="ms")
    d.text((W // 2, 250), "Your landlord kept", font=font(34), fill=MUTED, anchor="ms")
    d.text((W // 2, 320), f"${WITHHELD:,.0f} of your ${DEPOSIT:,.0f} deposit",
           font=font(52), fill=TXT, anchor="ms")
    d.text((W // 2, 400), "for damage that was already there when you moved in.",
           font=font(24), fill=MUTED, anchor="ms")
    d.text((W // 2, 470), "Most tenants never fight it.", font=font(22),
           fill=(120, 130, 142), anchor="ms")
    return img


def sc_solution():
    img, d = new_frame()
    d.text((W // 2, 130), "The solution", font=font(22), fill=BLUE, anchor="ms")
    d.text((W // 2, 190), "One agent. Three tools. A human in the loop.",
           font=font(30), fill=TXT, anchor="ms")
    tools = [
        ("1 · Reconcile evidence", "move-in photos vs. the landlord's claim", RED),
        ("2 · Look up the law", STATUTE, BLUE),
        ("3 · Draft the demand", "evidence-cited letter — only after you approve", GREEN),
    ]
    y = 260
    for title, sub, col in tools:
        panel(d, [260, y, W - 260, y + 92])
        d.rounded_rectangle([260, y, 268, y + 92], radius=4, fill=col)
        d.text((296, y + 22), title, font=font(23), fill=TXT)
        d.text((298, y + 56), sub, font=font(16), fill=MUTED)
        y += 108
    return img


def sc_result(big=RECOVER):
    img, d = new_frame()
    d.text((W // 2, 210), "Recoverable", font=font(26), fill=MUTED, anchor="ms")
    d.text((W // 2, 330), f"${big:,.0f}", font=font(120), fill=GREEN, anchor="ms")
    d.text((W // 2, 430), "wrongfully withheld — and the agent proves it.",
           font=font(24), fill=MUTED, anchor="ms")
    return img


def sc_cta():
    img, d = new_frame()
    shield(d, W // 2, 250, 80)
    d.text((W // 2, 340), "Rental Deposit Shield", font=font(46), fill=TXT, anchor="ms")
    panel(d, [W // 2 - 210, 400, W // 2 + 210, 456], fill=(24, 28, 36))
    d.text((W // 2, 428), "streamlit run app.py", font=font(24, mono=True),
           fill=BLUE, anchor="ms")
    return img


def sc_app_home():
    img, d = new_frame()
    header_band(d)
    d.line([(0, 104), (W, 104)], fill=BORDER, width=1)
    d.text((40, 130),
           "Audits a landlord's or Airbnb host's deposit deductions against your",
           font=font(18), fill=MUTED)
    d.text((40, 158),
           "evidence and the applicable law (US, India) or platform policy.",
           font=font(18), fill=MUTED)
    # a hint of the layout
    panel(d, [40, 210, 320, H - 40], fill=SIDEBAR)
    d.text((60, 232), "Case Inputs", font=font(20), fill=TXT)
    for i, lbl in enumerate(["Tenant / Guest", "Landlord / Host", "Jurisdiction",
                             "Deposit ($)", "Claimed deductions"]):
        yy = 276 + i * 40
        d.text((60, yy), lbl, font=font(15), fill=MUTED)
    panel(d, [352, 210, W - 40, H - 40])
    d.text((376, 236), "1 · Move-in Baseline Evidence", font=font(22), fill=TXT)
    d.text((376, 280), "Upload photos or load the documented sample walkthrough.",
           font=font(16), fill=MUTED)
    return img


def _field(d, x, y, w, label, value):
    d.text((x, y), label, font=font(14), fill=MUTED)
    panel(d, [x, y + 22, x + w, y + 58], fill=(24, 28, 36))
    d.text((x + 12, y + 32), value, font=font(16), fill=TXT)


def sc_sidebar():
    img, d = new_frame()
    header_band(d)
    d.line([(0, 104), (W, 104)], fill=BORDER, width=1)
    panel(d, [40, 130, 470, H - 30], fill=SIDEBAR)
    d.text((64, 150), "Case Inputs", font=font(22), fill=TXT)
    _field(d, 64, 190, 380, "Tenant / Guest Name", "Jordan Rivera")
    _field(d, 64, 258, 380, "Landlord / Host Name", "Summit Ridge Property Mgmt")
    d.text((64, 326), "Jurisdiction / Rental Type", font=font(14), fill=BLUE)
    # open dropdown
    opts = ["California (US)", "New York (US)", "Texas (US)",
            "India — Model Tenancy Act 2021", "Airbnb / Short-term stay"]
    panel(d, [64, 348, 444, 348 + len(opts) * 34 + 12], fill=(20, 24, 32), outline=BLUE)
    for i, o in enumerate(opts):
        yy = 356 + i * 34
        if i == 0:
            d.rounded_rectangle([70, yy - 3, 438, yy + 27], radius=8, fill=BLUE_BG)
        d.text((80, yy), o, font=font(16), fill=(BLUE if i == 0 else TXT))
    _field(d, 64, 348 + len(opts) * 34 + 26, 380, "Deposit Amount ($)", "2,400.00")

    # main: callout
    panel(d, [500, 150, W - 40, 320])
    d.text((524, 176), "One agent, five jurisdictions", font=font(24), fill=TXT)
    d.text((524, 220), "US state statutes · India's Model Tenancy Act 2021 ·",
           font=font(18), fill=MUTED)
    d.text((524, 248), "Airbnb short-term-stay policy — same wear-and-tear engine.",
           font=font(18), fill=MUTED)
    d.text((524, 288), f"Selected: {STATUTE}", font=font(15), fill=BLUE)
    return img


def _defect_tile(d, x, y, w, h, area, comp, fname, pre, kind):
    tint = {"carpet": (150, 120, 96), "wall": (210, 205, 194),
            "grout": (205, 214, 210), "blind": (196, 202, 210)}.get(kind, (160, 160, 168))
    d.rounded_rectangle([x, y, x + w, y + h], radius=12, fill=tint)
    # speckle texture
    rng = np.random.RandomState(hash(fname) % (2**31))
    for _ in range(280):
        px = int(x + 6 + rng.rand() * (w - 12))
        py = int(y + 34 + rng.rand() * (h - 74))
        c = tuple(int(max(0, min(255, v + rng.randint(-28, 28)))) for v in tint)
        d.point((px, py), fill=c)
    # simulated defect
    cx, cy = x + w // 2, y + h // 2 + 4
    if kind == "carpet":
        for r in (34, 26, 18):
            d.ellipse([cx - r, cy - r // 2, cx + r, cy + r // 2], fill=(70, 55, 45))
    elif kind == "wall":
        for dx in (-24, -6, 12, 30):
            d.ellipse([cx + dx - 3, cy - 3, cx + dx + 3, cy + 3], fill=(60, 55, 48))
    elif kind == "grout":
        for gx in range(x + 10, x + w - 10, 34):
            d.line([(gx, y + 34), (gx, y + h - 40)], fill=(150, 160, 156), width=2)
        for _ in range(60):
            px = int(x + 10 + rng.rand() * (w - 20)); py = int(y + 40 + rng.rand() * (h - 84))
            d.ellipse([px, py, px + 4, py + 4], fill=(70, 96, 74))
    elif kind == "blind":
        for by in range(y + 40, y + h - 44, 12):
            d.line([(x + 10, by), (x + w - 10, by)], fill=(170, 176, 184), width=4)
        d.line([(x + 10, cy), (x + w - 10, cy + 10)], fill=(120, 126, 134), width=5)
    # header + badge
    d.rounded_rectangle([x, y, x + w, y + 28], radius=12, fill=(28, 31, 38))
    d.rectangle([x, y + 16, x + w, y + 28], fill=(28, 31, 38))
    d.text((x + 10, y + 6), f"{area} · {comp}", font=font(14), fill=TXT)
    btxt, bcol = ("PRE-EXISTING", RED_D) if pre else ("MOVE-IN OK", GREEN_D)
    bf = font(11)
    bw = d.textlength(btxt, font=bf)
    d.rounded_rectangle([x + w - bw - 20, y + 6, x + w - 6, y + 22], radius=6, fill=bcol)
    d.text((x + w - bw - 13, y + 8), btxt, font=bf, fill=(255, 255, 255))
    # footer filename
    d.rectangle([x, y + h - 22, x + w, y + h], fill=(248, 249, 250))
    d.text((x + 8, y + h - 19), fname, font=font(12), fill=(73, 80, 87))


def sc_evidence():
    img, d = new_frame()
    header_band(d)
    d.text((40, 128), "1 · Move-in evidence photos", font=font(22), fill=TXT)
    d.text((40, 160), "Red = pre-existing at move-in (disputable) · green = good.",
           font=font(15), fill=MUTED)
    tiles = [("Living Room", "Carpet", "IMG_1012.jpg", True, "carpet"),
             ("Kitchen", "Wall", "IMG_1015.jpg", True, "wall"),
             ("Bathroom", "Grout", "IMG_1021.jpg", True, "grout"),
             ("Living Room", "Blinds", "IMG_1009.jpg", True, "blind"),
             ("Bedroom", "Carpet", "IMG_1030.jpg", False, "carpet"),
             ("Whole Unit", "Walls", "IMG_1000.jpg", False, "wall")]
    tw, th, gap = 380, 210, 24
    for i, t in enumerate(tiles):
        col, row = i % 3, i // 3
        x = 40 + col * (tw + gap)
        y = 196 + row * (th + gap)
        _defect_tile(d, x, y, tw, th, *t)
    return img


def _tool_card(d, x, y, w, h, title, sub, state):
    panel(d, [x, y, x + w, y + h])
    d.text((x + 20, y + 18), title, font=font(19), fill=TXT)
    d.text((x + 20, y + 50), sub, font=font(14), fill=MUTED)
    # status dot
    cx, cy = x + w - 34, y + 34
    if state == "done":
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=GREEN_D)
        d.line([(cx - 7, cy), (cx - 2, cy + 6), (cx + 8, cy - 6)], fill=TXT, width=3,
               joint="curve")
    elif state == "run":
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=AMBER, width=3)
        d.arc([cx - 14, cy - 14, cx + 14, cy + 14], 0, 110, fill=AMBER, width=3)
    else:
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=BORDER, width=3)


def frame_audit(states, bar):
    """One frame of the 'running audit' scene. states: list of 3 in {wait,run,done}."""
    img, d = new_frame()
    header_band(d)
    d.text((40, 128), "2 · Running the Strands Audit Agent", font=font(22), fill=TXT)
    tools = [("Tool 1 · Reconciliation", "baseline vs. landlord claim"),
             ("Tool 2 · Tenant Law / Policy", STATUTE),
             ("Tool 3 · Wear & Tear", "reclassify non-chargeable wear")]
    for i, (t, s) in enumerate(tools):
        _tool_card(d, 40, 190 + i * 116, W - 80, 96, t, s, states[i])
    # progress bar
    panel(d, [40, 560, W - 40, 588], fill=(24, 28, 36), radius=14)
    d.rounded_rectangle([40, 560, 40 + int((W - 80) * bar), 588], radius=14, fill=BLUE)
    d.text((40, 604), "[audit] hook: AgentInitialized · tool calls logged",
           font=font(14, mono=True), fill=MUTED)
    return img


def _metric(d, x, y, w, label, value, col=TXT):
    panel(d, [x, y, x + w, y + 96])
    d.text((x + 16, y + 16), label, font=font(14), fill=MUTED)
    d.text((x + 16, y + 44), value, font=font(30), fill=col)


def sc_verdict():
    img, d = new_frame()
    header_band(d)
    d.text((40, 128), "3 · Execution Results", font=font(22), fill=TXT)
    cw = (W - 80 - 3 * 18) // 4
    _metric(d, 40 + 0 * (cw + 18), 176, cw, "Deposit", f"${DEPOSIT:,.0f}")
    _metric(d, 40 + 1 * (cw + 18), 176, cw, "Withheld", f"${WITHHELD:,.0f}")
    _metric(d, 40 + 2 * (cw + 18), 176, cw, "Recoverable", f"${RECOVER:,.0f}", GREEN)
    _metric(d, 40 + 3 * (cw + 18), 176, cw, "Conceded", f"${CONCEDED:,.0f}", MUTED)
    # table
    rows = [("DISPUTE", "Carpet replacement", "$650", "pre-existing", RED),
            ("DISPUTE", "Wall patch & repaint", "$180", "pre-existing", RED),
            ("DISPUTE", "Bathroom re-grout", "$240", "pre-existing", RED),
            ("DISPUTE", "Repaint entire unit", "$900", "normal wear", RED),
            ("concede", "General cleaning", "$200", "reasonable", GREEN)]
    y = 300
    panel(d, [40, y, W - 40, y + 300])
    for i, (verdict, item, amt, why, col) in enumerate(rows):
        ry = y + 20 + i * 54
        d.rounded_rectangle([60, ry, 158, ry + 32], radius=8,
                            fill=(46, 20, 24) if col == RED else (16, 40, 26))
        d.text((72, ry + 6), verdict, font=font(15), fill=col)
        d.text((180, ry + 6), item, font=font(18), fill=TXT)
        d.text((720, ry + 6), amt, font=font(18), fill=TXT)
        d.text((840, ry + 6), why, font=font(16), fill=MUTED)
    return img


def frame_hitl(pressed=False):
    img, d = new_frame()
    header_band(d)
    d.text((40, 128), "4 · Human-in-the-Loop Safeguard", font=font(22), fill=TXT)
    panel(d, [40, 190, W - 40, 300], fill=(40, 33, 12), outline=(90, 74, 24))
    d.text((64, 214), "A demand letter is a real, outbound legal document.",
           font=font(20), fill=AMBER)
    d.text((64, 248), "Nothing is drafted until you approve.", font=font(18), fill=(220, 200, 150))
    # button
    bx1, by1, bx2, by2 = 40, 340, 520, 404
    bcol = (24, 110, 60) if pressed else GREEN_D
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=12, fill=bcol)
    d.text(((bx1 + bx2) // 2, (by1 + by2) // 2), "Approve & Generate Dispute Notice",
           font=font(20), fill=TXT, anchor="mm")
    # cursor
    cxp = bx2 - 120 if pressed else bx2 + 40
    cyp = by2 - 8 if pressed else by2 + 30
    d.polygon([(cxp, cyp), (cxp, cyp + 22), (cxp + 6, cyp + 16), (cxp + 12, cyp + 26),
               (cxp + 16, cyp + 24), (cxp + 10, cyp + 14), (cxp + 18, cyp + 14)],
              fill=TXT, outline=BG)
    return img


def sc_letter(scroll=0):
    img, d = new_frame()
    header_band(d)
    d.text((40, 128), "5 · Formal Dispute Letter", font=font(22), fill=TXT)
    panel(d, [40, 168, W - 40, 604], fill=(11, 13, 18))
    lines = LETTER.splitlines()
    f = font(15, mono=True)
    top = 186 - scroll
    for i, ln in enumerate(lines):
        yy = top + i * 20
        if 176 <= yy <= 590:
            d.text((64, yy), ln[:96], font=f, fill=(206, 214, 222))
    # download button
    d.rounded_rectangle([40, 620, 360, 672], radius=12, fill=BLUE)
    d.text((200, 646), "Download Dispute Letter (.txt)", font=font(17),
           fill=(10, 20, 34), anchor="mm")
    return img


def sc_close():
    img, d = new_frame()
    shield(d, W // 2, 210, 74)
    d.text((W // 2, 300), "Three tools · a human-in-the-loop hook · bounded execution",
           font=font(26), fill=TXT, anchor="ms")
    x0 = W // 2 - 150
    x = chip(d, (x0, 340), "United States", BLUE, BLUE_BG, fsize=17)
    x = chip(d, (x + 10, 340), "India", GREEN, (16, 46, 30), fsize=17)
    chip(d, (x + 10, 340), "Airbnb", AMBER, AMBER_BG, fsize=17)
    d.text((W // 2, 430), "Built on the AWS Strands Agents SDK", font=font(20),
           fill=MUTED, anchor="ms")
    panel(d, [W // 2 - 200, 470, W // 2 + 200, 522], fill=(24, 28, 36))
    d.text((W // 2, 496), "streamlit run app.py", font=font(22, mono=True),
           fill=BLUE, anchor="ms")
    return img


# ---- streaming video writer ---------------------------------------------------------

class Video:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.w = imageio.get_writer(path, fps=FPS, codec="libx264", quality=8,
                                    macro_block_size=16, ffmpeg_log_level="error")
        self.path = path

    def _push(self, img):
        self.w.append_data(np.asarray(img.convert("RGB")))

    def hold(self, img, secs):
        arr = np.asarray(img.convert("RGB"))
        for _ in range(max(1, int(secs * FPS))):
            self.w.append_data(arr)

    def crossfade(self, a, b, secs=0.4):
        n = max(1, int(secs * FPS))
        for i in range(n):
            self._push(Image.blend(a, b, (i + 1) / n))

    def anim(self, frames_iter):
        for im in frames_iter:
            self._push(im)

    def close(self):
        self.w.close()
        print(f"  wrote {self.path} ({os.path.getsize(self.path)//1024} KB)")


# ---- timelines ----------------------------------------------------------------------

def build_teaser():
    v = Video(os.path.join(OUT_DIR, "sample_teaser.mp4"))
    scenes = [sc_title(), sc_problem(), sc_solution(), sc_result(), sc_cta()]
    holds = [3.2, 3.6, 4.6, 3.2, 3.0]
    v.hold(scenes[0], holds[0])
    for i in range(1, len(scenes)):
        v.crossfade(scenes[i - 1], scenes[i], 0.4)
        v.hold(scenes[i], holds[i])
    v.close()


def build_full():
    v = Video(os.path.join(OUT_DIR, "sample_full_demo.mp4"))

    def audit_frames():
        # tools tick to done, progress bar fills
        seq = [("wait", "wait", "wait"), ("run", "wait", "wait"),
               ("done", "run", "wait"), ("done", "done", "run"),
               ("done", "done", "done")]
        total = int(5.5 * FPS)
        for k in range(total):
            p = k / (total - 1)
            idx = min(len(seq) - 1, int(p * len(seq)))
            yield frame_audit(list(seq[idx]), p)

    def hitl_frames():
        for _ in range(int(2.4 * FPS)):
            yield frame_hitl(False)
        for _ in range(int(0.8 * FPS)):
            yield frame_hitl(True)

    def letter_frames():
        max_scroll = max(0, len(LETTER.splitlines()) * 20 - 380)
        n = int(6.0 * FPS)
        for k in range(n):
            yield sc_letter(int(max_scroll * (k / (n - 1)) ** 1.0))

    home, side, ev, verdict, close = (sc_app_home(), sc_sidebar(), sc_evidence(),
                                      sc_verdict(), sc_close())
    v.hold(home, 3.0)
    v.crossfade(home, side, 0.4); v.hold(side, 5.0)
    v.crossfade(side, ev, 0.4); v.hold(ev, 5.0)
    a0 = frame_audit(["wait", "wait", "wait"], 0.0)
    v.crossfade(ev, a0, 0.4); v.anim(audit_frames())
    v.crossfade(frame_audit(["done", "done", "done"], 1.0), verdict, 0.4); v.hold(verdict, 5.5)
    h0 = frame_hitl(False)
    v.crossfade(verdict, h0, 0.4); v.anim(hitl_frames())
    l0 = sc_letter(0)
    v.crossfade(frame_hitl(True), l0, 0.4); v.anim(letter_frames()); v.hold(sc_letter(9999), 1.2)
    v.crossfade(sc_letter(9999), close, 0.5); v.hold(close, 3.4)
    v.close()


if __name__ == "__main__":
    print("Rendering sample videos (synthetic previews)...")
    if "--frames" in sys.argv:
        # QA mode: dump a few key frames as PNGs
        os.makedirs(OUT_DIR, exist_ok=True)
        for name, im in [("title", sc_title()), ("sidebar", sc_sidebar()),
                         ("evidence", sc_evidence()), ("verdict", sc_verdict()),
                         ("letter", sc_letter(0)), ("hitl", frame_hitl(False))]:
            im.save(os.path.join(OUT_DIR, f"_qa_{name}.png"))
            print("  QA frame:", name)
    else:
        build_teaser()
        build_full()
    print("Done.")
