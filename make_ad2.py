#!/usr/bin/env python3
"""Ad #2 (hook-first, fast): "3 words you'll use every day". Uses the channel's own scenes, characters and edge-tts voices.

  python make_ad2.py --lang jp --repo jp --out out/tiny-japanese-ad2.mp4
  python make_ad2.py --lang fr --repo fr --out out/tiny-french-ad2.mp4
--dummy-audio = tones instead of voices (look test), --stills = a few PNG frames only.
"""
import argparse, math, os, random, subprocess, sys, tempfile, wave, functools
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_ad import make_audio, icon, fit_text  # noqa: E402  (music, icons, text fitting from ad #1)

CFG = {
    "jp": dict(
        module="tinyvideo", scene="sakura", left="Mika", right="Alex", rate="-15%", weather="petals", kind="JAPANESE",
        title="3 words you'll use every day!",
        hook=["WAIT!", "3 JAPANESE WORDS", "you'll use every day"],
        hook_say="Wait! Do you know these three Japanese words?",
        words=[("Mika", "ありがとう", "arigatō", "Thank you!"), ("Alex", "すみません", "sumimasen", "Excuse me! Or: sorry."), ("Mika", "おいしい！", "oishii", "Delicious!")],
        cta_say="Want more? Learn Japanese free with Mika and Alex. Follow Tiny Japanese and visit our website!",
        cta_tag="Learn free!",
        cta=[("yt", "Watch on YouTube", "@tinyjapanese"), ("web", "Free lessons - link in bio", "tiny-japanese.sabagh1.workers.dev"), ("ig", "Follow on Instagram", "@tinyjapanes")],
        cols=[(236, 96, 126), (96, 150, 112), (240, 160, 60)], dark=(52, 40, 44), accent=(222, 110, 134), root=2, seed=11,
    ),
    "fr": dict(
        module="small", scene="park", left="Adrien", right="Marinette", rate="-15%", weather=None, kind="FRENCH",
        title="3 words you'll use every day!",
        hook=["WAIT!", "3 FRENCH WORDS", "you'll use every day"],
        hook_say="Wait! Do you know these three French words?",
        words=[("Marinette", "Merci !", "mehr-SEE", "Thank you!"), ("Adrien", "Excusez-moi !", "ex-kew-ZAY mwah", "Excuse me!"), ("Marinette", "C'est délicieux !", "say day-lee-SYUH", "It's delicious!")],
        cta_say="Want more? Learn French free with Adrien and Marinette. Follow Tiny French and visit our website!",
        cta_tag="Learn free!",
        cta=[("yt", "Watch on YouTube", "@tinyfrench9"), ("web", "Visit our website - link in bio", "tiny-french.sabagh1.workers.dev"), ("ig", "Follow on Instagram", "@tiny.french")],
        cols=[(70, 104, 196), (222, 84, 98), (236, 168, 56)], dark=(40, 44, 70), accent=(122, 150, 204), root=-1, seed=13,
    ),
}


def ease_out(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3


def pop(t, t0, dur=0.35):
    x = (t - t0) / dur
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


# ------------------------------------------------------------------ sound effects
def sfx_track(total, events, sr=44100):
    n = int(sr * total); out = np.zeros(n)
    rnd = np.random.RandomState(4)

    def add(t0, x, v):
        i0 = int(t0 * sr)
        if i0 >= n: return
        x = x[: n - i0]; out[i0:i0 + len(x)] += v * x

    for kind, t0 in events:
        if kind == "boom":
            tt = np.arange(int(sr * .7)) / sr; f = 38 + 120 * np.exp(-tt * 9)
            add(t0, np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 5) + 0.25 * rnd.randn(len(tt)) * np.exp(-tt * 18), 0.9)
        elif kind == "whoosh":
            tt = np.arange(int(sr * .45)) / sr; f = 250 + 2600 * (tt / .45) ** 2
            add(t0, (np.sin(2 * np.pi * np.cumsum(f) / sr) * .35 + rnd.randn(len(tt)) * .25) * np.sin(np.pi * tt / .45) ** 1.5, 0.35)
        elif kind == "ding":
            tt = np.arange(int(sr * 1.1)) / sr; f0 = 988
            add(t0, sum(a * np.sin(2 * np.pi * f0 * r * tt) for a, r in ((1, 1), (.5, 2.76), (.25, 5.4))) * np.exp(-tt * 4.5), 0.35)
        elif kind == "pop":
            tt = np.arange(int(sr * .18)) / sr
            add(t0, np.sin(2 * np.pi * (500 + 900 * tt / .18) * tt) * np.exp(-tt * 22), 0.4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["jp", "fr"])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dummy-audio", action="store_true")
    ap.add_argument("--stills", action="store_true")
    a = ap.parse_args()
    c = CFG[a.lang]
    sys.path.insert(0, os.path.abspath(a.repo))
    import importlib
    m = importlib.import_module(c["module"])
    W, H, FPS, SR = m.W, m.H, m.FPS, m.SR
    jp = a.lang == "jp"; L, R = c["left"], c["right"]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    # ---------- voice + timeline ----------
    tmp = tempfile.mkdtemp()
    chunks, t = [np.zeros(int(0.12 * SR), np.float32)], 0.12
    talk = []

    def say(text, speaker=None, rate=None, narrator=False):
        nonlocal t
        wav = os.path.join(tmp, f"v{len(chunks)}.wav")
        if narrator:
            nrate = rate or "+8%"
            if jp: m.synth(text, "Narrator", wav, nrate, a.dummy_audio, voice="en-US-AriaNeural", lang="en")
            else: m.synth(text, "en-US-AriaNeural", wav, nrate, a.dummy_audio, lang="en")
        else:
            if jp: m.synth(text, speaker, wav, rate or c["rate"], a.dummy_audio)
            else: m.synth(text, m.CHARS[speaker]["voice"], wav, rate or c["rate"], a.dummy_audio)
        x = m.read_wav(wav); s, e = t, t + len(x) / SR
        chunks.extend([x, np.zeros(int(0.3 * SR), np.float32)]); t = e + 0.3
        if not narrator: talk.append(dict(speaker=speaker, start=s, end=e))
        return s, e

    hs, he = say(c["hook_say"], narrator=True, rate="+12%")
    hook_end = he + 0.25
    segs = []
    for (sp, word, pron, mean) in c["words"]:
        w1s, w1e = say(word, sp)
        ms, me = say(mean, narrator=True)
        w2s, w2e = say(word, sp)
        segs.append(dict(sp=sp, word=word, pron=pron, mean=mean, start=w1s - 0.12, w1=(w1s, w1e), m=(ms, me), end=w2e + 0.25))
    cs, ce = say(c["cta_say"], narrator=True, rate="+4%")
    cta_start = segs[-1]["end"]
    total = ce + 1.3
    chunks.append(np.zeros(int((total - t) * SR) + SR, np.float32))
    audio = np.concatenate(chunks); audio = audio / max(0.01, np.abs(audio).max()) * 0.9
    n = int(total * FPS); mouth = m.mouth_levels(audio, n)
    print(f"hook {hs:.1f}-{he:.1f}; segs {[(round(s['start'],1), round(s['end'],1)) for s in segs]}; cta {cta_start:.1f}-{ce:.1f}; total {total:.1f}s")
    beats = [0.0] + [s["start"] for s in segs] + [cta_start]   # punch / flash moments

    # ---------- visuals ----------
    bg, fg = m.make_scene(c["scene"], {"title": c["title"], "episode": ""})
    wx = wxp = None
    if c["weather"]: wx = c["weather"]; wxp = m.make_weather(wx, c["scene"])
    dark, cols = c["dark"], c["cols"]

    @functools.lru_cache(None)
    def outlined(txt, size, fill, stroke, scol):
        f = m.font(size, True); d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        b = d0.textbbox((0, 0), txt, font=f, stroke_width=stroke); pad = stroke + 6
        im = Image.new("RGBA", (b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad - b[0], pad - b[1]), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=scol)
        return im

    def fit_outlined(txt, size, fill, stroke, scol, maxw):
        while size > 24:
            im = outlined(txt, size, fill, stroke, scol)
            if im.width <= maxw: return im
            size -= 4
        return outlined(txt, size, fill, stroke, scol)

    def put(base, im, cx, cy, scale=1.0, alpha=1.0):
        if scale <= 0.02 or alpha <= 0.02: return
        if abs(scale - 1) > 0.004: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
        if alpha < 0.99:
            im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
        base.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)

    @functools.lru_cache(None)
    def panel(word, pron, ci):
        col = cols[ci]; w, h = 940, 520; S = 2
        im = Image.new("RGBA", ((w + 40) * S, (h + 40) * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((26 * S, 34 * S, (w + 26) * S, (h + 34) * S), radius=70 * S, fill=(0, 0, 0, 60))
        d.rounded_rectangle((20 * S, 20 * S, (w + 20) * S, (h + 20) * S), radius=70 * S, fill=(255, 253, 250, 255), outline=col, width=12 * S)
        im = im.resize((w + 40, h + 40), Image.LANCZOS)
        wi = fit_outlined(word, 190 if jp else 150, dark, 0, dark, 820); im.paste(wi, ((im.width - wi.width) // 2, 70), wi)
        pi_ = fit_outlined(pron, 58, col, 0, col, 820); im.paste(pi_, ((im.width - pi_.width) // 2, 70 + wi.height + 6), pi_)
        return im

    @functools.lru_cache(None)
    def band(mean, ci):
        col = cols[ci]; w, h = 860, 130
        im = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((10, 16, w + 10, h + 16), radius=65, fill=(0, 0, 0, 60)); d.rounded_rectangle((10, 10, w + 10, h + 10), radius=65, fill=col)
        ti = fit_outlined("= " + mean, 66, (255, 255, 255), 0, col, w - 70); im.paste(ti, ((im.width - ti.width) // 2, (im.height - ti.height) // 2), ti)
        return im

    # speed lines overlay for the hook (two jitter variants)
    def rays(seed):
        r = random.Random(seed); im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); cx, cy = W // 2, 640
        for _ in range(46):
            ang = r.uniform(0, 2 * math.pi); wd = r.uniform(0.02, 0.06); r0 = r.uniform(260, 420); r1 = 1800
            d.polygon([(cx + r0 * math.cos(ang - wd), cy + r0 * math.sin(ang - wd)), (cx + r1 * math.cos(ang - wd * .2), cy + r1 * math.sin(ang - wd * .2)),
                       (cx + r1 * math.cos(ang + wd * .2), cy + r1 * math.sin(ang + wd * .2)), (cx + r0 * math.cos(ang + wd), cy + r0 * math.sin(ang + wd))], fill=(255, 255, 255, 120))
        return im
    rays_v = [rays(1), rays(2)]

    # CTA card (same family as ad #1 but bigger headline)
    ctab = m.card_image(c["cta_tag"], c["cols"][0], [("", None, None, 3 * 134)], min_h=380)
    ctab_y0 = 40 + 56 + int((ctab.height - 80 - 56 - 36 - 3 * 134) / 2)
    for i, (kind, label, sub) in enumerate(c["cta"]):
        y = ctab_y0 + i * 134
        ic = icon(kind, 92, cols[0] if kind != "web" else cols[1]); ctab.paste(ic, (100, y + 20), ic)
        lab = fit_text(m, label, 40, True, dark, 700); ctab.paste(lab, (212, y + 6), lab)
        sb = fit_text(m, sub, 34, False, cols[0], 700); ctab.paste(sb, (212, y + 62), sb)

    pills = {(nm, aa): m.pill(nm if not jp else m.CHARS[nm]["label"], m.CHARS[nm]["accent"] if aa else (226, 214, 206), (255, 255, 255) if aa else (130, 112, 108))
             for nm in (L, R) for aa in (0, 1)}

    def scene_frame(i, tt, excited):
        fr = bg.copy()
        if wx: fr.alpha_composite(m.wx_layer(wx, wxp, tt, False), (0, m.WX_Y0))
        cur = next((k for k, l in enumerate(talk) if l["start"] - 0.02 <= tt <= l["end"] + 0.1), None)
        for nm in (L, R):
            cc = m.CHARS[nm]; sp = cur is not None and talk[cur]["speaker"] == nm
            lvl = int(mouth[min(i, n - 1)])
            mo = (1 + int(tt * 9) % 2) if excited else (lvl if sp else 0)
            bob = 6 * abs(math.sin(tt * 7)) if (sp or excited) else 2 * math.sin(tt * 2 + (0 if nm == L else 1.7))
            blink = (not excited) and ((i + (0 if nm == L else 41)) % 97) < 4
            s = m.sprite(nm, mo, blink); fr.paste(s, (cc["x"], int(m.CHAR_Y - bob)), s)
            p = pills[(nm, int(sp))]; fr.paste(p, (cc["x"] + s.width // 2 - p.width // 2, 330), p)
        fr.paste(fg, (0, m.TABLE_TOP - 55), fg)
        if wx: fr.alpha_composite(m.wx_layer(wx, wxp, tt, True), (0, m.WX_Y0))
        return fr.convert("RGB")

    def camera(img, z, cx, cy, dx=0, dy=0):
        if z <= 1.001 and not dx and not dy: return img
        w, h = W / z, H / z
        x0 = min(max(cx - w / 2 + dx, 0), W - w); y0 = min(max(cy - h / 2 + dy, 0), H - h)
        return img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))

    def confetti(d, tt, t0, cx, cy, ci):
        if tt < t0 or tt > t0 + 1.1: return
        r = random.Random(int(t0 * 100)); e = tt - t0
        for k in range(34):
            ang = r.uniform(-math.pi, 0) if k % 3 else r.uniform(0, math.pi); sp = r.uniform(380, 900); sz = r.uniform(12, 26)
            x = cx + math.cos(ang) * sp * e; y = cy + math.sin(ang) * sp * e + 900 * e * e
            col = r.choice([cols[0], cols[1], cols[2], (255, 255, 255)]); a = r.uniform(0, 6.28) + e * r.uniform(-8, 8)
            d.polygon([(x + sz * math.cos(a + q * 1.5708), y + sz * .6 * math.sin(a + q * 1.5708)) for q in range(4)], fill=col)

    def frame(i):
        tt = i / FPS
        in_hook = tt < hook_end
        fr = scene_frame(i, tt, in_hook)
        # camera: slow push in on the hook, small punch on every beat
        punch = max((math.exp(-(tt - b) * 7) for b in beats if tt >= b), default=0)
        z = 1.0 + 0.07 * punch
        cx, cy, dx, dy = W / 2, 620, 0, 0
        if in_hook:
            z = 1.0 + 0.14 * ease_out(tt / 0.5) + 0.04 * punch; cy = 560
            dec = math.exp(-tt * 3); dx, dy = 16 * dec * math.sin(tt * 55), 12 * dec * math.cos(tt * 47)
        fr = camera(fr, z, cx, cy, dx, dy)
        d = ImageDraw.Draw(fr, "RGBA")

        if in_hook:
            fr.paste(Image.new("RGB", (W, H), cols[0]), (0, 0), rays_v[int(tt * 12) % 2].getchannel("A").point(lambda v: int(v * 0.55)))
            for k, (txt, size, y0, delay) in enumerate(((c["hook"][0], 230, 1040, 0.0), (c["hook"][1], 92, 1250, 0.35), (c["hook"][2], 62, 1350, 0.6))):
                s_ = pop(tt, delay + 0.05)
                if s_ > 0:
                    jit = 6 * math.sin(tt * 40 + k)
                    put(fr, fit_outlined(txt, size, (255, 255, 255), 16 if k == 0 else 10, dark, 980), 540 + jit, y0 + (0 if k else jit), s_)
        else:
            # progress pills
            cur_seg = max((k for k, s in enumerate(segs) if tt >= s["start"]), default=-1)
            if tt < cta_start:
                for k in range(3):
                    x0 = 540 + (k - 1) * 150
                    d.rounded_rectangle((x0 - 60, 272, x0 + 60, 290), radius=9, fill=cols[k] if k <= cur_seg else (255, 255, 255, 170))
            for k, s in enumerate(segs):
                if s["start"] <= tt < s["end"]:
                    e = tt - s["start"]
                    put(fr, panel(s["word"], s["pron"], k), 540, 1230, pop(tt, s["start"] + 0.02, 0.4))
                    if tt >= s["m"][0] - 0.05:
                        put(fr, band(s["mean"], k), 540, 1130 + 300, pop(tt, s["m"][0] - 0.05, 0.35))
                    confetti(d, tt, s["m"][0] - 0.05, 540, 1390, k)
            if tt >= cta_start:
                e = tt - cta_start; pulse = 1 + 0.025 * math.sin(tt * 8)
                cardimg = ctab
                put(fr, cardimg, 540, m.CARD_Y - 40 + cardimg.height // 2 - 10 + (1 - ease_out(e / 0.4)) * 700, pulse)
        # flash on each beat
        fl = max((max(0.0, 1 - (tt - b) * 9) for b in beats if tt >= b), default=0)
        if fl > 0.02: fr.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), Image.new("L", (W, H), int(150 * fl)))
        return fr

    if a.stills:
        base = os.path.splitext(a.out)[0]
        for tt in (0.08, 0.5, hook_end - 0.2, segs[0]["start"] + 0.6, segs[0]["m"][0] + 0.5, segs[2]["m"][0] + 0.3, cta_start + 1.2):
            frame(int(tt * FPS)).save(f"{base}_still_{tt:04.1f}.png")
        return

    # ---------- audio: voice + music + sfx ----------
    voice_wav = os.path.join(tmp, "voice.wav"); m.write_wav(voice_wav, audio)
    music = os.path.join(tmp, "music.wav"); make_audio(music, total * 1.25, root=c["root"], seed=c["seed"], vol=0.5)
    ev = [("boom", 0.0), ("whoosh", 0.0)]
    for s in segs: ev += [("whoosh", s["start"] - 0.05), ("pop", s["start"] + 0.02), ("ding", s["m"][0] - 0.05)]
    ev += [("whoosh", cta_start - 0.05), ("ding", cta_start + 0.2)]
    sfx = sfx_track(total, ev); sfx_wav = os.path.join(tmp, "sfx.wav")
    with wave.open(sfx_wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100); wf.writeframes((np.clip(sfx, -1, 1) * 32767).astype("<i2").tobytes())
    pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", voice_wav, "-i", music, "-i", sfx_wav,
                           "-filter_complex", "[1:a]aresample=44100[v];[2:a]atempo=1.2,volume=0.26[mu];[3:a]volume=0.8[fx];"
                                              "[v][mu][fx]amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.95[a]",
                           "-map", "0:v", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    for i in range(n): pr.stdin.write(frame(i).tobytes())
    pr.stdin.close(); pr.wait()
    print("wrote", a.out, f"{total:.1f}s")


if __name__ == "__main__":
    main()
