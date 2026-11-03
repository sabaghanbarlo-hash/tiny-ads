#!/usr/bin/env python3
"""Tiny Japanese / Tiny French ad (1080x1920, Instagram Reel) built with the channels' own
scenes, characters (sprites), cards and edge-tts voices.

  python make_ad.py --lang jp --repo jp --out out/tiny-japanese-ad.mp4
  python make_ad.py --lang fr --repo fr --out out/tiny-french-ad.mp4
Add --dummy-audio for a local look-only test (tones instead of voices), --stills for PNG frames only.
"""
import argparse, math, os, subprocess, sys, tempfile, random, wave
import numpy as np
from PIL import Image, ImageDraw

def make_audio(path, total, root=0, seed=1, vol=0.5):
    """Soft pentatonic background music (no samples needed)."""
    sr = 44100; n = int(sr * total); out = np.zeros(n); rnd = random.Random(seed)
    beat = 60 / 104; base = 261.63 * 2 ** (root / 12); scale = [0, 2, 4, 7, 9, 12, 14, 16]

    def note(t0, f, d, v, harm=(1, .4, .15)):
        i0 = int(t0 * sr)
        if i0 >= n: return
        mm = min(int(d * sr), n - i0); tt = np.arange(mm) / sr
        env = np.minimum(1, tt / 0.01) * np.exp(-tt * (3.2 / max(d, .2)))
        out[i0:i0 + mm] += v * env * sum(a * np.sin(2 * np.pi * f * (k + 1) * tt) for k, a in enumerate(harm))
    chords = [(0, 4, 7), (9, 12, 16), (5, 9, 12), (7, 11, 14)]; bar = beat * 4; t = 0.0; bi = 0
    while t < total:
        ch = chords[bi % 4]
        for s_ in ch: note(t, base / 2 * 2 ** (s_ / 12), bar * 0.95, 0.05, harm=(1, .25))
        note(t, base / 4 * 2 ** (ch[0] / 12), beat * 1.8, 0.13, harm=(1, .3)); note(t + 2 * beat, base / 4 * 2 ** (ch[0] / 12), beat * 1.8, 0.1, harm=(1, .3))
        for q in range(8):
            if rnd.random() < 0.78:
                note(t + q * beat / 2, base * 2 ** (scale[rnd.choice([0, 1, 2, 3, 4, 5]) if q % 4 else rnd.choice([0, 2, 3, 4])] / 12), beat * 0.9, 0.085)
        t += bar; bi += 1
    idx = np.arange(n); out *= np.minimum(1, np.minimum(idx / (sr * .3), (n - idx) / (sr * 1.2)))
    out = out / (np.max(np.abs(out)) + 1e-9) * vol
    st = np.stack([out, out], 1); dl = int(sr * 0.012); st[dl:, 1] = out[:-dl] * 0.95
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes((st * 32767).astype("<i2").tobytes())


def icon(kind, size, bg):
    S = 3; s = size * S; im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im); w = (255, 255, 255); lw = int(s * .055)
    if kind == "yt":
        d.rounded_rectangle((0, s * .16, s, s * .84), radius=s * .22, fill=(235, 30, 30)); d.polygon([(s * .40, s * .34), (s * .40, s * .66), (s * .68, s * .5)], fill=w)
    elif kind == "web":
        d.ellipse((s * .04, s * .04, s * .96, s * .96), fill=bg); d.ellipse((s * .2, s * .2, s * .8, s * .8), outline=w, width=lw)
        d.ellipse((s * .38, s * .2, s * .62, s * .8), outline=w, width=lw); d.line((s * .2, s * .5, s * .8, s * .5), fill=w, width=lw)
    else:
        d.rounded_rectangle((s * .04, s * .04, s * .96, s * .96), radius=s * .26, fill=(214, 62, 140))
        d.rounded_rectangle((s * .22, s * .22, s * .78, s * .78), radius=s * .17, outline=w, width=lw); d.ellipse((s * .36, s * .36, s * .64, s * .64), outline=w, width=lw)
        d.ellipse((s * .64, s * .27, s * .72, s * .35), fill=w)
    return im.resize((size, size), Image.LANCZOS)


def fit_text(m, txt, size, bold, fill, maxw):
    while size > 16:
        f = m.font(size, bold); b = f.getbbox(txt)
        if b[2] - b[0] <= maxw: break
        size -= 2
    f = m.font(size, bold); b = f.getbbox(txt)
    im = Image.new("RGBA", (b[2] - b[0] + 8, b[3] - b[1] + 8), (0, 0, 0, 0)); ImageDraw.Draw(im).text((4 - b[0], 4 - b[1]), txt, font=f, fill=fill)
    return im

CFG = {
    "jp": dict(
        module="tinyvideo", scene="sakura", left="Mika", right="Alex", rate="-10%", weather="petals",
        title="Come learn with us!",
        ink=(52, 40, 44), soft=(176, 110, 128), accent=(222, 110, 134), accent2=(96, 150, 112),
        lines=[
            ("Mika", dict(jp="こんにちは！ にほんご、いっしょに！", romaji="Konnichiwa! Nihongo, issho ni!", en="Hello! Japanese, together!")),
            ("Alex", dict(jp="うん、たのしみ！", romaji="Un, tanoshimi!", en="Yes! I'm excited!")),
        ],
        spoken=["こんにちは！ にほんご、いっしょに！", "うん、たのしみ！"],
        n1="Short stories, everyday phrases, and free lessons, made for beginners.",
        feats=[("Tiny story lessons", "with Mika & Alex"), ("Useful everyday phrases", "beginner-friendly Japanese"), ("Free lessons", "on our website")],
        feat_tag="Why learn with us",
        n2="Watch us on YouTube, visit our website, and follow us on Instagram. The link is in our bio!",
        cta=[("yt", "Watch on YouTube", "@tinyjapanese"), ("web", "Free lessons - link in bio", "tiny-japanese.sabagh1.workers.dev"), ("ig", "Follow on Instagram", "@tinyjapanes")],
        cta_tag="Join us!",
    ),
    "fr": dict(
        module="small", scene="park", left="Adrien", right="Marinette", rate="-12%", weather=None,
        title="Come learn with us!",
        ink=(46, 48, 60), soft=(128, 152, 204), accent=(122, 150, 204), accent2=(228, 140, 152),
        lines=[
            ("Adrien", dict(fr="Bonjour ! On apprend le français ?", pron="bon-ZHOOR ! on a-PRON luh fron-SAY ?", en="Hello! Shall we learn French?")),
            ("Marinette", dict(fr="Oui ! Ensemble !", pron="WEE ! on-SON-bluh", en="Yes! Together!")),
        ],
        spoken=["Bonjour ! On apprend le français ?", "Oui ! Ensemble !"],
        n1="Short stories, simple vocabulary, and grammar, made for beginners.",
        feats=[("Tiny stories", "with Adrien & Marinette"), ("Vocabulary & grammar", "simple French for beginners"), ("Small steps", "a little French every day")],
        feat_tag="Why learn with us",
        n2="Watch us on YouTube, visit our website, and follow us on Instagram. The link is in our bio!",
        cta=[("yt", "Watch on YouTube", "@tinyfrench9"), ("web", "Visit our website - link in bio", "tiny-french.sabagh1.workers.dev"), ("ig", "Follow on Instagram", "@tiny.french")],
        cta_tag="Join us!",
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["jp", "fr"])
    ap.add_argument("--repo", required=True, help="folder holding the channel's renderer (tinyvideo.py or small.py)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dummy-audio", action="store_true")
    ap.add_argument("--stills", action="store_true")
    a = ap.parse_args()
    c = CFG[a.lang]
    sys.path.insert(0, os.path.abspath(a.repo))
    import importlib
    m = importlib.import_module(c["module"])
    W, H, FPS, SR = m.W, m.H, m.FPS, m.SR
    jp = a.lang == "jp"
    L, R = c["left"], c["right"]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    # ---------- voice track + timeline ----------
    tmp = tempfile.mkdtemp()
    chunks, t = [np.zeros(int(0.6 * SR), np.float32)], 0.6
    talk, cardlines = [], []

    def say(text, speaker, narrator=False):
        nonlocal t
        wav = os.path.join(tmp, f"v{len(chunks)}.wav")
        if narrator:
            if jp: m.synth(text, "Narrator", wav, "+0%", a.dummy_audio, voice="en-US-AriaNeural", lang="en")
            else: m.synth(text, "en-US-AriaNeural", wav, "+0%", a.dummy_audio, lang="en")
        else:
            if jp: m.synth(text, speaker, wav, c["rate"], a.dummy_audio)
            else: m.synth(text, m.CHARS[speaker]["voice"], wav, c["rate"], a.dummy_audio)
        x = m.read_wav(wav)
        s, e = t, t + len(x) / SR
        chunks.extend([x, np.zeros(int(0.5 * SR), np.float32)]); t = e + 0.5
        return s, e

    for (sp, ln), spoken in zip(c["lines"], c["spoken"]):
        s, e = say(spoken, sp)
        ln = dict(ln, speaker=sp); ln["start"], ln["end"] = s, e
        cardlines.append(ln); talk.append(dict(speaker=sp, start=s, end=e))
    n1s, n1e = say(c["n1"], None, narrator=True)
    n2s, n2e = say(c["n2"], None, narrator=True)
    total = n2e + 1.6
    chunks.append(np.zeros(int((total - t) * SR) + SR, np.float32))
    audio = np.concatenate(chunks); audio = audio / max(0.01, np.abs(audio).max()) * 0.9
    n = int(total * FPS); mouth = m.mouth_levels(audio, n)
    print(f"timeline: lines {[(round(l['start'],1), round(l['end'],1)) for l in cardlines]}, n1 {n1s:.1f}-{n1e:.1f}, n2 {n2s:.1f}-{n2e:.1f}, total {total:.1f}s")

    # ---------- visuals ----------
    meta = {"title": c["title"], "episode": ""}
    bg, fg = m.make_scene(c["scene"], meta)
    wx = wxp = None
    if c["weather"]:
        wx = c["weather"]; wxp = m.make_weather(wx, c["scene"])
    ink, soft, acc = c["ink"], c["soft"], c["accent"]
    cards = [m.line_card(l) for l in cardlines]

    def feat_card(k):
        parts = []
        for i, (ti, su) in enumerate(c["feats"]):
            show = i < k
            parts += [(ti, m.font(54) if show else None, ink, 66), (su, m.font(36, False) if show else None, soft, 52), ("", None, None, 26)]
        return m.card_image(c["feat_tag"], acc, parts, min_h=420)
    fcards = [feat_card(k) for k in (1, 2, 3)]

    ctab = m.card_image(c["cta_tag"], acc, [("", None, None, 3 * 134)], min_h=380)
    d = ImageDraw.Draw(ctab)
    ctab_y0 = 40 + 56 + int((ctab.height - 80 - 56 - 36 - 3 * 134) / 2)
    for i, (kind, label, sub) in enumerate(c["cta"]):
        y = ctab_y0 + i * 134
        ic = icon(kind, 92, acc if kind != "web" else c["accent2"]); ctab.paste(ic, (100, y + 20), ic)
        lab = fit_text(m, label, 40, True, ink, 700); ctab.paste(lab, (212, y + 6), lab)
        sb = fit_text(m, sub, 34, False, soft if jp else (84, 110, 176), 700); ctab.paste(sb, (212, y + 62), sb)
    ctab_d = ctab

    pills = {(nm, aa): m.pill(nm if not jp else m.CHARS[nm]["label"], m.CHARS[nm]["accent"] if aa else (226, 214, 206),
                              (255, 255, 255) if aa else (130, 112, 108)) for nm in (L, R) for aa in (0, 1)}

    # whole-ad progress: which card is on screen at time tt
    def pick_card(tt):
        if tt >= n2s - 0.05: return ctab_d, n2s - 0.05
        if tt >= n1s - 0.05:
            k = 0 if tt < n1s + (n1e - n1s) * 0.30 else (1 if tt < n1s + (n1e - n1s) * 0.62 else 2)
            return fcards[k], (n1s - 0.05 if k == 0 else n1s + (n1e - n1s) * (0.30 if k == 1 else 0.62))
        k = max((k for k, l in enumerate(cardlines) if tt >= l["start"] - 0.02), default=None)
        return (cards[k], cardlines[k]["start"] - 0.02) if k is not None else (None, 0)

    def frame(i):
        tt = i / FPS; fr = bg.copy()
        if wx: fr.alpha_composite(m.wx_layer(wx, wxp, tt, False), (0, m.WX_Y0))
        cur = next((k for k, l in enumerate(talk) if l["start"] - 0.02 <= tt <= l["end"] + 0.1), None)
        for nm in (L, R):
            cc = m.CHARS[nm]
            sp = cur is not None and talk[cur]["speaker"] == nm
            bob = 6 * abs(math.sin(tt * 7)) if sp and mouth[min(i, n - 1)] else 2 * math.sin(tt * 2 + (0 if nm == L else 1.7))
            blink = ((i + (0 if nm == L else 41)) % 97) < 4
            s = m.sprite(nm, int(mouth[min(i, n - 1)]) if sp else 0, blink)
            fr.paste(s, (cc["x"], int(m.CHAR_Y - bob)), s)
            p = pills[(nm, int(sp))]; fr.paste(p, (cc["x"] + s.width // 2 - p.width // 2, 330), p)
        fr.paste(fg, (0, m.TABLE_TOP - 55), fg)
        if wx: fr.alpha_composite(m.wx_layer(wx, wxp, tt, True), (0, m.WX_Y0))
        card, t0 = pick_card(tt)
        if card is not None:
            f = min(1, (tt - t0) / 0.2); dy = int(24 * (1 - f))
            if f < 1:
                card = card.copy(); card.putalpha(card.getchannel("A").point(lambda v: int(v * max(f, 0))))
            fr.alpha_composite(card, (20, m.CARD_Y - 40 + dy)) if fr.mode == "RGBA" else fr.paste(card, (20, m.CARD_Y - 40 + dy), card)
        return fr.convert("RGB")

    if a.stills:
        base = os.path.splitext(a.out)[0]
        for tt in (0.9, (cardlines[1]["start"] + cardlines[1]["end"]) / 2, n1s + (n1e - n1s) * 0.85, n2s + 1.5, total - 0.5):
            frame(int(tt * FPS)).save(f"{base}_still_{tt:04.1f}.png")
        return

    # ---------- audio mix + encode ----------
    voice_wav = os.path.join(tmp, "voice.wav"); m.write_wav(voice_wav, audio)
    music = os.path.join(tmp, "music.wav"); make_audio(music, total, root=0 if jp else -3, seed=3 if jp else 5)
    pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", voice_wav, "-i", music,
                           "-filter_complex", "[1:a]aresample=44100,volume=1.0[v];[2:a]volume=0.30[mu];[v][mu]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]",
                           "-map", "0:v", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    for i in range(n):
        pr.stdin.write(frame(i).tobytes())
    pr.stdin.close(); pr.wait()
    print("wrote", a.out, f"{total:.1f}s")


if __name__ == "__main__":
    main()
