#!/usr/bin/env python3
"""
make_demo_video.py — build a NARRATED demo video from REAL screenshots of the running app.

Unlike the synthetic previews, this uses genuine screenshots of the live Streamlit website
(captured via Playwright + your system Chrome), wraps them in a browser-chrome frame, pans
down each page like a real scroll, and adds a spoken voiceover generated with macOS `say`,
muxed into the mp4 with ffmpeg. The result looks like the actual website and has sound.

Prereq: capture the screenshots first (see the capture step / README), so these exist:
    media/shots/01_home.png  02_evidence.png  03_results.png  04_letter.png

Run:
    ./venv/bin/python scripts/make_demo_video.py
Output:
    media/demo_walkthrough.mp4   (narrated, ~55s, real website)
"""

from __future__ import annotations

import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import imageio.v2 as imageio
import imageio_ffmpeg

W, H = 1280, 720
FPS = 24
CHROME_H = 46                      # fake browser toolbar height
CONTENT_H = H - CHROME_H
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "media")
SHOTS = os.path.join(OUT_DIR, "shots")
TMP = os.path.join(OUT_DIR, "_tmp_audio")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Preferred voice: Kokoro neural TTS (most natural) -> Piper -> macOS `say`.
KOKORO_ONNX = os.path.join(ROOT, "models", "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(ROOT, "models", "voices-v1.0.bin")
KOKORO_VOICE = "af_heart"
USE_KOKORO = os.path.exists(KOKORO_ONNX) and os.path.exists(KOKORO_VOICES)
_KOKORO = None

PIPER_MODEL = os.path.join(ROOT, "models", "en_US-amy-medium.onnx")
if not os.path.exists(PIPER_MODEL):
    PIPER_MODEL = None


def _kokoro_synth(text, out_wav):
    global _KOKORO
    if _KOKORO is None:
        from kokoro_onnx import Kokoro
        _KOKORO = Kokoro(KOKORO_ONNX, KOKORO_VOICES)
    import soundfile as sf
    samples, sr = _KOKORO.create(text, voice=KOKORO_VOICE, speed=1.0, lang="en-us")
    sf.write(out_wav, samples, sr)

BG = (14, 17, 23)
BLUE = (102, 178, 255)


def _pick_voice():
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    except Exception:
        return None
    names = [ln.split("  ")[0].strip() for ln in out.splitlines()]
    for pref in ("Samantha", "Alex", "Ava", "Allison", "Tom", "Nicky", "Fred"):
        for n in names:
            if n.startswith(pref):
                return n
    return None


VOICE = _pick_voice()

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


# ---- audio via macOS `say` ----------------------------------------------------------

def _synth_raw(text, idx):
    """Synthesize raw audio for one segment (Kokoro -> Piper -> macOS `say`)."""
    os.makedirs(TMP, exist_ok=True)
    if USE_KOKORO:
        raw = os.path.join(TMP, f"seg{idx}_raw.wav")
        _kokoro_synth(text, raw)
        return raw
    if PIPER_MODEL:
        raw = os.path.join(TMP, f"seg{idx}_raw.wav")
        subprocess.run([sys.executable, "-m", "piper", "-m", PIPER_MODEL,
                        "--length-scale", "1.05", "-f", raw],
                       input=text, text=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return raw
    aiff = os.path.join(TMP, f"seg{idx}.aiff")
    cmd = ["say", "-o", aiff]
    if VOICE:
        cmd += ["-v", VOICE]
    cmd += ["-r", "180", text]
    subprocess.run(cmd, check=True)
    return aiff


def tts(text, idx):
    """Render one narration segment to a normalized wav; return (path, seconds)."""
    raw = _synth_raw(text, idx)
    wav = os.path.join(TMP, f"seg{idx}.wav")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", raw,
                    "-ar", "44100", "-ac", "1", "-sample_fmt", "s16", wav], check=True)
    with wave.open(wav) as w:
        secs = w.getnframes() / w.getframerate()
    return wav, secs


def concat_audio(segments, pads, out_path):
    """Concatenate segment wavs, each followed by `pad` seconds of silence."""
    sr = 44100
    with wave.open(out_path, "w") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sr)
        for (wav, _), pad in zip(segments, pads):
            with wave.open(wav) as w:
                out.writeframes(w.readframes(w.getnframes()))
            out.writeframes(b"\x00\x00" * int(sr * pad))


# ---- visual frame helpers -----------------------------------------------------------

def browser_chrome(base=None):
    img = base or Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, CHROME_H], fill=(32, 36, 44))
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        d.ellipse([20 + i * 22, 16, 34 + i * 22, 30], fill=c)
    d.rounded_rectangle([100, 10, W - 20, 36], radius=13, fill=(20, 23, 29))
    d.text((118, 15), "🔒", font=font(14))
    d.text((140, 15), "localhost:8501  —  Rental Deposit Shield · Streamlit",
           font=font(14), fill=(150, 160, 172))
    return img, d


def page_frame(shot_img, pan_t):
    """Compose one frame: browser chrome + a vertically-panned view of the screenshot."""
    img, _ = browser_chrome()
    scaled_w = W
    scaled_h = int(shot_img.height * (W / shot_img.width))
    view = shot_img.resize((scaled_w, scaled_h))
    if scaled_h <= CONTENT_H:
        y = (CONTENT_H - scaled_h) // 2
        img.paste(view, (0, CHROME_H + y))
    else:
        top = int((scaled_h - CONTENT_H) * pan_t)
        img.paste(view.crop((0, top, W, top + CONTENT_H)), (0, CHROME_H))
    return img


def shield(d, cx, cy, s, color=BLUE):
    w, h = s, int(s * 1.15)
    d.polygon([(cx - w // 2, cy - h // 2), (cx + w // 2, cy - h // 2),
               (cx + w // 2, cy + h // 6), (cx, cy + h // 2), (cx - w // 2, cy + h // 6)],
              fill=color)
    d.line([(cx - w // 5, cy), (cx - w // 30, cy + h // 6), (cx + w // 4, cy - h // 6)],
           fill=BG, width=max(3, s // 12), joint="curve")


def card(title, sub):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    shield(d, W // 2, 250, 84)
    d.text((W // 2, 340), title, font=font(46), fill=(245, 245, 245), anchor="ms")
    d.text((W // 2, 392), sub, font=font(22), fill=(150, 160, 172), anchor="ms")
    badges = [("Everyday Agents Track", BLUE, (19, 47, 76)),
              ("For renters anywhere", (120, 220, 160), (16, 46, 30))]
    f = font(16)
    widths = [d.textlength(t, font=f) + 24 for t, _, _ in badges]
    total = sum(widths) + 12 * (len(badges) - 1)
    x0 = W // 2 - total // 2
    for (t, fg, bg), wd in zip(badges, widths):
        d.rounded_rectangle([x0, 430, x0 + wd, 462], radius=999, fill=bg)
        d.text((x0 + 12, 436), t, font=f, fill=fg)
        x0 += wd + 12
    d.text((W - 14, H - 22), "Demo · AI voiceover", font=font(13),
           fill=(90, 100, 112), anchor="rs")
    return img


# ---- build --------------------------------------------------------------------------

NARRATION = [
    ("card:Rental Deposit Shield:An AWS Strands AI agent that gets your deposit back",
     "Renters everywhere lose part of their deposit to unfair deductions. Rental Deposit "
     "Shield is an A.I. agent, built on the A.W.S. Strands S.D.K., that helps them get it "
     "back."),
    ("01_home",
     "It's a web app. You enter your case: the tenant, the landlord, and the amount withheld. "
     "The agent applies the tenant-protection rules for your location, whether it's a "
     "long-term lease or a short-term stay like Airbnb. In this walkthrough, the landlord "
     "withheld 2,365 dollars."),
    ("02_evidence",
     "You upload your move-in walkthrough video, and the agent pulls out screenshots as "
     "evidence. Red means the condition was already there when you moved in, so it is "
     "disputable."),
    ("03_results",
     "The Strands agent then runs three tools. It reconciles your evidence against the claim, "
     "looks up the applicable tenant law, and flags normal wear and tear. The verdict: "
     "2,165 dollars is recoverable, and it concedes the one fair charge in good faith."),
    ("04_letter",
     "Nothing goes out without you. After you approve, it drafts a formal demand letter that "
     "cites your photos and the law, ready to download and send."),
    ("card:Rental Deposit Shield:Your deposit back — with a human in the loop",
     "Rental Deposit Shield. Your deposit back, with a human in the loop."),
]

PAD = 0.5          # trailing silence after each narration segment
LEAD_PAN = 0.15    # fraction of segment spent static before panning


def load_visual(spec):
    if spec.startswith("card:"):
        _, title, sub = spec.split(":", 2)
        return card(title, sub)
    return Image.open(os.path.join(SHOTS, spec + ".png")).convert("RGB")


def main():
    for spec, _ in NARRATION:
        if not spec.startswith("card:"):
            p = os.path.join(SHOTS, spec + ".png")
            if not os.path.exists(p):
                sys.exit(f"Missing screenshot: {p}\nCapture the live app first (see README).")

    print("Voice:", (f"Kokoro {KOKORO_VOICE}" if USE_KOKORO else
                      ("Piper en_US-amy-medium" if PIPER_MODEL else (VOICE or "system default"))))
    print("Rendering narration audio...")
    segs = [tts(text, i) for i, (_, text) in enumerate(NARRATION)]
    durs = [s for _, s in segs]

    # video segment durations = narration + trailing pad
    seg_video = [d + PAD for d in durs]

    tmp_video = os.path.join(OUT_DIR, "_demo_silent.mp4")
    writer = imageio.get_writer(tmp_video, fps=FPS, codec="libx264", quality=8,
                                macro_block_size=16, ffmpeg_log_level="error")
    print("Rendering video frames...")
    for (spec, _), vdur in zip(NARRATION, seg_video):
        vis = load_visual(spec)
        is_card = spec.startswith("card:")
        n = max(1, int(vdur * FPS))
        for k in range(n):
            if is_card:
                z = 1.0 + 0.04 * (k / n)
                cw, ch = int(W / z), int(H / z)
                fr = vis.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw,
                               (H - ch) // 2 + ch)).resize((W, H))
            else:
                e = max(0.0, (k / n - LEAD_PAN) / (1 - LEAD_PAN))
                pan = 0.5 - 0.5 * np.cos(np.pi * min(1.0, e))   # ease in/out
                fr = page_frame(vis, pan)
            writer.append_data(np.asarray(fr))
    writer.close()

    print("Muxing audio...")
    audio = os.path.join(OUT_DIR, "_demo_audio.wav")
    concat_audio(segs, [PAD] * len(segs), audio)
    out = os.path.join(OUT_DIR, "demo_walkthrough.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", tmp_video, "-i", audio,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out],
                   check=True)
    os.remove(tmp_video); os.remove(audio)
    print(f"  wrote {out} ({os.path.getsize(out)//1024} KB)")


if __name__ == "__main__":
    main()
