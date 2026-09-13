#!/usr/bin/env python3
"""
make_house_videos.py — render two SAMPLE "walkthrough" videos of the rental unit:

    media/house_move_in_before.mp4    move-in condition  (dated 2023-08-01)
    media/house_move_out_after.mp4    move-out condition (dated 2025-08-15)

These are the kind of phone walkthrough a tenant records as evidence. The "before" video
documents the unit at move-in; the "after" video shows the SAME pre-existing defects still
present at move-out (proving the tenant didn't cause them), plus a little normal wear.

They are synthetic, programmatically-rendered scenes (Pillow frames -> mp4 via the ffmpeg
bundled with imageio-ffmpeg) — NOT real footage. Every frame is watermarked "SAMPLE".

Run:
    ./venv/bin/python scripts/make_house_videos.py            # encode both
    ./venv/bin/python scripts/make_house_videos.py --frames   # dump QA PNGs
"""

from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import imageio.v2 as imageio

W, H = 1280, 720
WIDE = 1740          # scene width (pans to 1280)
FPS = 24
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")

ADDRESS = "412 Maple Court, Apt 3B"

# ---- fonts --------------------------------------------------------------------------
_FC = {}


def font(size, mono=False):
    k = (size, mono)
    if k in _FC:
        return _FC[k]
    cands = (["/System/Library/Fonts/Menlo.ttc"] if mono else
             ["/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial.ttf"])
    f = None
    for p in cands:
        try:
            f = ImageFont.truetype(p, size); break
        except Exception:
            pass
    if f is None:
        try:
            f = ImageFont.load_default(size=size)
        except TypeError:
            f = ImageFont.load_default()
    _FC[k] = f
    return f


def _rng(seed):
    return np.random.RandomState(abs(hash(seed)) % (2**31))


# ---- low-level texture helpers ------------------------------------------------------

def speckle(d, box, base, n, spread, seed):
    rng = _rng(seed)
    x0, y0, x1, y1 = box
    for _ in range(n):
        px = int(x0 + rng.rand() * (x1 - x0))
        py = int(y0 + rng.rand() * (y1 - y0))
        c = tuple(int(max(0, min(255, v + rng.randint(-spread, spread)))) for v in base)
        d.point((px, py), fill=c)


def vgrad(img, box, top, bottom):
    x0, y0, x1, y1 = box
    h = max(1, y1 - y0)
    d = ImageDraw.Draw(img)
    for i in range(h):
        t = i / h
        c = tuple(int(top[j] * (1 - t) + bottom[j] * t) for j in range(3))
        d.line([(x0, y0 + i), (x1, y0 + i)], fill=c)


# ---- room scene renderers (return a WIDE image) -------------------------------------

def _room_base(wall_top, wall_bottom, floor_col, seed, floor_y=470):
    img = Image.new("RGB", (WIDE, H), wall_top)
    vgrad(img, (0, 0, WIDE, floor_y), wall_top, wall_bottom)
    d = ImageDraw.Draw(img)
    speckle(d, (0, 0, WIDE, floor_y), wall_bottom, 2600, 8, seed + "wall")
    # baseboard
    d.rectangle([0, floor_y, WIDE, floor_y + 16], fill=tuple(int(c * 0.9) for c in wall_bottom))
    d.line([(0, floor_y), (WIDE, floor_y)], fill=(60, 60, 60), width=2)
    # floor
    d.rectangle([0, floor_y + 16, WIDE, H], fill=floor_col)
    speckle(d, (0, floor_y + 16, WIDE, H), floor_col, 5200, 16, seed + "floor")
    return img, d, floor_y


def scene_living(after=False):
    img, d, fy = _room_base((214, 210, 200), (196, 190, 178), (150, 120, 96), "living")
    # window with blinds
    wx0, wy0, wx1, wy1 = 980, 90, 1360, 380
    vgrad(img, (wx0, wy0, wx1, wy1), (176, 206, 232), (150, 188, 224))  # sky
    d.rectangle([wx0, wy0, wx1, wy1], outline=(120, 120, 120), width=8)
    for by in range(wy0 + 14, wy1 - 6, 20):            # blind slats
        d.line([(wx0 + 6, by), (wx1 - 6, by)], fill=(206, 206, 210), width=8)
    # one cracked/hanging slat (pre-existing, same before & after)
    d.line([(wx0 + 6, 250), (wx1 - 6, 262)], fill=(150, 150, 156), width=9)
    d.line([(1150, 246), (1180, 300)], fill=(120, 120, 126), width=6)
    # pre-existing carpet stain near the window
    cx, cy = 760, 600
    for r, col in ((70, (78, 60, 48)), (52, (66, 50, 40)), (32, (54, 40, 32))):
        d.ellipse([cx - r, cy - r // 2, cx + r, cy + r // 2], fill=col)
    if after:
        _traffic_path(d, 250, 560, 620, 660)           # normal wear: matted path
    return img, "Living room", [
        (cx, cy - 40, "Carpet stain — pre-existing" if not after else "Same stain (move-in)"),
        (1165, 275, "Blind slat cracked" if not after else "Same broken slat"),
    ]


def scene_kitchen(after=False):
    img, d, fy = _room_base((222, 218, 206), (204, 198, 184), (176, 152, 120), "kitchen")
    # counter hint
    d.rectangle([120, 360, 720, 400], fill=(120, 96, 74))
    d.rectangle([120, 400, 720, 470], fill=(150, 128, 104))
    # nail holes where a prior tenant's shelf was (pre-existing)
    hy = 250
    for hx in (900, 968, 1036, 1104):
        d.ellipse([hx - 4, hy - 4, hx + 4, hy + 4], fill=(70, 60, 50))
        d.ellipse([hx - 2, hy - 1, hx + 3, hy + 4], fill=(40, 34, 28))
    if after:
        for sx in (300, 430, 560):                     # minor scuffs (normal wear)
            d.line([(sx, 300), (sx + 26, 314)], fill=(170, 160, 148), width=3)
    return img, "Kitchen", [
        (1002, hy - 30, "Nail holes — prior tenant" if not after else "Same holes (move-in)"),
    ]


def scene_bath(after=False):
    img, d, fy = _room_base((214, 224, 222), (198, 210, 208), (206, 210, 210), "bath", floor_y=520)
    # tiled wall
    for gx in range(60, WIDE - 60, 96):
        d.line([(gx, 60), (gx, 470)], fill=(176, 188, 186), width=3)
    for gy in range(80, 470, 96):
        d.line([(60, gy), (WIDE - 60, gy)], fill=(176, 188, 186), width=3)
    # tub line + mildew along grout (pre-existing)
    d.rectangle([120, 430, 900, 470], fill=(150, 168, 166))
    rng = _rng("mildew")
    for _ in range(120):
        px = int(120 + rng.rand() * 760); py = int(452 + rng.rand() * 14)
        d.ellipse([px, py, px + 4, py + 4], fill=(64, 88, 66))
    return img, "Bathroom", [
        (500, 420, "Mildew on grout — pre-existing" if not after else "Same mildew (move-in)"),
    ]


def scene_bedroom(after=False):
    img, d, fy = _room_base((216, 210, 220), (200, 194, 206), (172, 150, 176), "bedroom")
    d.rectangle([980, 120, 1300, 360], outline=(120, 120, 124), width=8)  # plain window
    vgrad(img, (988, 128, 1292, 352), (188, 210, 232), (166, 194, 224))
    if after:
        _traffic_path(d, 300, 560, 900, 660)           # light wear only
    return img, "Bedroom", [
        (600, 560, "Carpet — good condition" if not after
         else "Light wear only (normal)"),
    ]


def _traffic_path(d, x0, y0, x1, y1):
    for i in range(0, x1 - x0, 6):
        a = 1 - abs(((i / (x1 - x0)) - 0.5) * 2)
        col = tuple(int(c * (1 - 0.10 * a)) for c in (150, 120, 96))
        d.line([(x0 + i, y0), (x0 + i, y1)], fill=col, width=6)


# ---- overlay (phone camera UI) ------------------------------------------------------

def _shadow_text(d, xy, s, f, fill=(255, 255, 255), anchor=None):
    x, y = xy
    d.text((x + 1, y + 1), s, font=f, fill=(0, 0, 0), anchor=anchor)
    d.text((x, y), s, font=f, fill=fill, anchor=anchor)


def overlay(frame, room, date_str, tsec, after):
    d = ImageDraw.Draw(frame)
    # REC indicator
    d.ellipse([28, 30, 46, 48], fill=(230, 40, 40))
    _shadow_text(d, (56, 28), "REC", font(22))
    mm, ss = divmod(int(tsec), 60)
    _shadow_text(d, (110, 28), f"{mm:01d}:{ss:02d}", font(22, mono=True))
    # phase pill
    label = "MOVE-OUT" if after else "MOVE-IN"
    pill = (200, 60, 60) if after else (40, 140, 90)
    f = font(20)
    tw = d.textlength(label, font=f)
    d.rounded_rectangle([W - tw - 250, 26, W - 168, 56], radius=999, fill=pill)
    _shadow_text(d, (W - tw - 238, 29), label, f)
    # timestamp
    _shadow_text(d, (W - 20, 28), date_str, font(22, mono=True), anchor="ra")
    # bottom: room + address
    _shadow_text(d, (28, H - 84), room, font(30))
    _shadow_text(d, (30, H - 48), ADDRESS, font(18), fill=(225, 225, 225))
    # honesty watermark
    d.text((W - 14, H - 22), "SAMPLE · synthetic render", font=font(13),
           fill=(235, 235, 235), anchor="rs")
    return frame


def annotate(frame, notes, pan_x, after):
    """Draw small callouts pointing at defects (scene coords -> screen coords)."""
    d = ImageDraw.Draw(frame)
    for sx, sy, text in notes:
        x = sx - pan_x
        if not (60 < x < W - 60):
            continue
        col = (235, 90, 90) if ("pre-existing" in text.lower() or "same" in text.lower()
                                or "holes" in text.lower() or "mildew" in text.lower()
                                or "stain" in text.lower() or "slat" in text.lower()) else (90, 200, 130)
        f = font(17)
        tw = d.textlength(text, font=f)
        bx0 = min(max(10, x - tw // 2 - 10), W - tw - 30)
        by0 = max(70, sy - 70)
        d.line([(x, sy), (bx0 + tw // 2 + 10, by0 + 28)], fill=col, width=2)
        d.ellipse([x - 5, sy - 5, x + 5, sy + 5], outline=col, width=3)
        d.rounded_rectangle([bx0, by0, bx0 + tw + 20, by0 + 30], radius=8,
                            fill=(20, 22, 26), outline=col, width=2)
        d.text((bx0 + 10, by0 + 6), text, font=f, fill=(240, 240, 240))
    return frame


# ---- cards --------------------------------------------------------------------------

def card(title, sub, after):
    img = Image.new("RGB", (W, H), (18, 20, 24))
    d = ImageDraw.Draw(img)
    accent = (200, 70, 70) if after else (46, 170, 110)
    d.rounded_rectangle([W // 2 - 120, 210, W // 2 + 120, 262], radius=999, fill=accent)
    d.text((W // 2, 236), "MOVE-OUT" if after else "MOVE-IN", font=font(24),
           fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, 330), title, font=font(40), fill=(245, 245, 245), anchor="ms")
    d.text((W // 2, 386), sub, font=font(22), fill=(150, 160, 170), anchor="ms")
    d.text((W // 2, 452), ADDRESS, font=font(20), fill=(120, 130, 140), anchor="ms")
    d.text((W - 14, H - 22), "SAMPLE · synthetic render", font=font(13),
           fill=(90, 100, 112), anchor="rs")
    return img


# ---- video writer -------------------------------------------------------------------

class Video:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.w = imageio.get_writer(path, fps=FPS, codec="libx264", quality=8,
                                    macro_block_size=16, ffmpeg_log_level="error")
        self.path = path
        self.t = 0.0  # elapsed seconds (for the REC timer)

    def _push(self, img):
        self.w.append_data(np.asarray(img.convert("RGB")))
        self.t += 1.0 / FPS

    def hold(self, img, secs, zoom=False):
        n = max(1, int(secs * FPS))
        for k in range(n):
            if zoom:
                z = 1.0 + 0.05 * (k / n)
                cw, ch = int(W / z), int(H / z)
                fr = img.crop(((W - cw) // 2, (H - ch) // 2,
                               (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H))
            else:
                fr = img
            self._push(fr)

    def crossfade(self, a, b, secs=0.35):
        n = max(1, int(secs * FPS))
        for i in range(n):
            self._push(Image.blend(a, b, (i + 1) / n))

    def shot(self, wide, room, date_str, secs, notes, after, prev_last=None):
        n = max(1, int(secs * FPS))
        max_pan = WIDE - W
        frames = []
        base_t = self.t
        for k in range(n):
            e = k / (n - 1)
            ease = 0.5 - 0.5 * np.cos(np.pi * e)      # ease in/out pan
            pan = int(max_pan * ease)
            fr = wide.crop((pan, 0, pan + W, H)).copy()
            annotate(fr, notes, pan, after)
            overlay(fr, room, date_str, base_t + k / FPS, after)
            frames.append(fr)
        if prev_last is not None:
            self.crossfade(prev_last, frames[0])
        for fr in frames:
            self._push(fr)
        return frames[-1]

    def close(self):
        self.w.close()
        print(f"  wrote {self.path} ({os.path.getsize(self.path)//1024} KB)")


def build(after: bool):
    name = "house_move_out_after.mp4" if after else "house_move_in_before.mp4"
    date_str = "2025-08-15" if after else "2023-08-01"
    v = Video(os.path.join(OUT_DIR, name))

    intro = card("Move-out condition walkthrough" if after else "Move-in condition walkthrough",
                 "Same defects as move-in — documented" if after
                 else "Documenting the unit's condition", after)
    v.hold(intro, 2.6, zoom=True)

    scenes = [scene_living(after), scene_kitchen(after),
              scene_bath(after), scene_bedroom(after)]
    last = intro
    first = True
    for wide, room, notes in scenes:
        last = v.shot(wide, room, date_str, 4.0, notes, after,
                      prev_last=(last if first else last))
        first = False

    outro = card("End of walkthrough" if not after else "Condition unchanged from move-in",
                 "Saved as dated video evidence", after)
    v.crossfade(last, outro, 0.4)
    v.hold(outro, 2.4, zoom=True)
    v.close()


if __name__ == "__main__":
    if "--frames" in sys.argv:
        os.makedirs(OUT_DIR, exist_ok=True)
        for after in (False, True):
            tag = "after" if after else "before"
            wide, room, notes = scene_living(after)
            fr = wide.crop((220, 0, 220 + W, H)).copy()
            annotate(fr, notes, 220, after)
            overlay(fr, room, "2025-08-15" if after else "2023-08-01", 3.0, after)
            fr.save(os.path.join(OUT_DIR, f"_qa_house_{tag}.png"))
            print("QA frame:", tag)
    else:
        print("Rendering house walkthrough videos (synthetic)...")
        build(after=False)
        build(after=True)
    print("Done.")
