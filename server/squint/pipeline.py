import asyncio
import json
import logging
import time
import uuid
import httpx
from PIL import Image

from . import media, forensics, fingerprint as fp, verdict as vd, textsignals, audiosignals, lang as L
from .crop import ScreenModel, find_media, region_kind
from .providers import registry
from .providers.base import Signal, run_all
from .schemas import Verdict, Haptic

log = logging.getLogger("squint.pipeline")

SCREEN_TRIGGERS = {"assistant", "screenshot", "back_tap", "action_button", "quick_tile", "power", "watch"}
AGAIN_WINDOW = 45.0
AGAIN_DISTANCE = 8


def _sig(name, score, rel, note):
    return Signal(name, float(score), float(rel), note)


class Health:
    def __init__(self):
        self.stats = {}

    def note(self, name, ok, ms):
        d = self.stats.setdefault(name, {"calls": 0, "failures": 0, "ms_total": 0})
        d["calls"] += 1
        d["ms_total"] += int(ms)
        if not ok:
            d["failures"] += 1

    def snapshot(self):
        out = {}
        for k, d in self.stats.items():
            out[k] = {"calls": d["calls"], "failures": d["failures"], "avg_ms": int(d["ms_total"] / d["calls"]) if d["calls"] else 0}
        return out


class Pipeline:
    def __init__(self, settings, index, providers=None, client=None):
        self.settings = settings
        self.index = index
        self.providers = providers if providers is not None else registry(settings)
        self.client = client or httpx.AsyncClient(timeout=settings.provider_timeout)
        self.weights = vd.load_weights(settings.weights_file)
        self.screen = ScreenModel(getattr(settings, "screen_model", ""))
        self.health = Health()
        self.recent = {}

    def provider_names(self):
        return [p.name for p in self.providers]

    async def aclose(self):
        await self.client.aclose()

    async def _providers(self, kind, data, text="", skip=()):
        picks = [p for p in self.providers if kind in p.kinds and p.name not in skip]
        if not picks:
            return []
        out = []

        async def one(p):
            t0 = time.time()
            try:
                r = await asyncio.wait_for(p.check(kind, data, text, self.client), self.settings.provider_timeout)
                self.health.note(p.name, True, (time.time() - t0) * 1000)
                return r
            except Exception as e:
                self.health.note(p.name, False, (time.time() - t0) * 1000)
                log.info("%s skipped: %s", p.name, e)
                return []

        for r in await asyncio.gather(*(one(p) for p in picks)):
            out.extend(r)
        return out

    async def _frames_through_model(self, frames):
        local = next((p for p in self.providers if p.name == "squint_model"), None)
        if local is None or not frames:
            return []
        scores = []
        for f in frames:
            try:
                got = await asyncio.wait_for(local.check("image", media.jpeg_bytes(Image.fromarray(f), 92), "", self.client), self.settings.provider_timeout)
                scores.extend(s.score for s in got)
            except Exception as e:
                log.info("frame skipped by local model: %s", e)
        if not scores:
            return []
        mean = sum(scores) / len(scores)
        spread = max(scores) - min(scores)
        note = f"our model across {len(scores)} frames: {mean:.0%} synthetic"
        if spread > 0.5:
            note += ", frames disagree"
        return [_sig("squint_model", mean, local.reliability * (0.8 if spread > 0.5 else 1.0), note)]

    def _history_signals(self, item):
        if not item or item.get("p_n", 0) < 1 or item.get("sightings", 1) < 2:
            return []
        n = item["p_n"]
        fb_ai, fb_h = item.get("feedback_ai", 0), item.get("feedback_human", 0)
        p = item["p_mean"]
        rel = min(0.5, 0.12 * (n ** 0.5))
        if fb_ai + fb_h >= 3:
            p = 0.5 * p + 0.5 * (fb_ai / (fb_ai + fb_h))
            rel = min(0.7, rel + 0.2)
        return [_sig("history", p, rel, f"checked {n} times before, averaging {p:.0%} synthetic")]

    def _consensus_signal(self, item):
        if not item or item.get("p_n", 0) < 3:
            return self._history_signals(item)
        n = item["p_n"]
        fb_ai, fb_h = item.get("feedback_ai", 0), item.get("feedback_human", 0)
        p = item["p_mean"]
        if fb_ai + fb_h >= 3:
            p = 0.5 * p + 0.5 * (fb_ai / (fb_ai + fb_h))
        rel = min(0.9, 0.4 * (n ** 0.5))
        return [_sig("history", p, rel, f"{n} earlier checks agree at {p:.0%} synthetic")]

    def _again(self, device, phash, prev_check, prev_phash, prev_ts):
        if not (device and prev_check and prev_phash and phash):
            return False
        try:
            age = time.time() - float(prev_ts or 0)
        except ValueError:
            return False
        if age > AGAIN_WINDOW or len(prev_phash) != 16:
            return False
        try:
            if fp.hamming(prev_phash, phash) > AGAIN_DISTANCE:
                return False
        except ValueError:
            return False
        return self.index.add_feedback(prev_check, "unsure")

    def _noted(self, prev_check, kind, lang, started):
        h = {"pattern": [0, 40, 60, 40], "amplitudes": [0, 120, 0, 120], "label": "two tiny taps"}
        return Verdict(
            check_id=prev_check, kind=kind, tier="unclear", p=0.5, confidence="low", haptic=Haptic(**h),
            say=L.t(lang, "noted"), headline=L.t(lang, "noted").rstrip("."), evidence=["flagged as wrong, thanks"], signals=[],
            lang=lang, feedback_recorded=True, decisive=True, ms=int((time.time() - started) * 1000),
        )

    def _finish(self, kind, signals, item, factchecks, device, source_app, trigger, started, region=None, rkind=None, screenshot=False, lang="en", phash=None, quick=False, decisive=True, say=None, counted=False):
        p, rel_total = vd.fuse(signals, self.weights)
        tier = vd.tier_for(p, rel_total, signals)
        say = say or vd.say_line(tier, signals, item, factchecks, kind, screenshot, lang, rkind)
        ms = int((time.time() - started) * 1000)
        sig_dump = [{"name": s.name, "score": round(s.score, 3), "reliability": round(s.reliability, 2), "note": s.note} for s in signals]
        cid = str(uuid.uuid4())
        seen = None
        if item and item.get("sightings", 1) > 1:
            fs = item["first_seen"]
            seen = {"sightings": item["sightings"], "first_seen": fs.isoformat() if hasattr(fs, "isoformat") else str(fs), "apps": json.loads(item.get("apps") or "{}")}
        h = vd.HAPTICS[tier]
        v = Verdict(
            check_id=cid, kind=kind, tier=tier, p=round(p, 3), confidence=vd.confidence_for(rel_total),
            haptic=Haptic(**h), say=say, headline=L.headline(lang, tier),
            evidence=vd.evidence_lines(signals, item, factchecks),
            signals=sig_dump,
            seen_before=seen, factchecks=factchecks or [], region=list(region) if region else None, region_kind=rkind,
            phash=phash, lang=lang, quick=quick, decisive=decisive, ms=ms,
        )
        self.index.log_check(item["id"] if item else None, device, source_app, trigger + (":quick" if quick else ""), kind, tier, p, sig_dump, ms, cid=cid, payload=v.model_dump_json(), counted=counted and item is not None)
        if device and phash:
            self.recent[(device, phash)] = (time.time(), v)
            if len(self.recent) > 5000:
                cutoff = time.time() - 300
                self.recent = {k: val for k, val in self.recent.items() if val[0] > cutoff}
        return v

    def cached(self, device, phash, max_age=120):
        hit = self.recent.get((device, phash))
        if hit and time.time() - hit[0] < max_age:
            return hit[1]
        return None

    async def check(self, data, filename="", content_type="", source_app="", trigger="", device="", hint=None, text="", screen_text="", local_p=None, lang="en", prev=None):
        kind = media.sniff(data, filename, content_type) if data else "text"
        if kind == "image":
            return await self.image(data, filename, source_app, trigger, device, hint, screen_text, local_p, lang, prev)
        if kind == "video":
            return await self.video(data, source_app, trigger, device, lang)
        if kind == "audio":
            return await self.audio(data, source_app, trigger, device, lang)
        if kind == "text":
            return await self.text(text or data.decode("utf-8", "replace"), source_app, trigger, device, lang=lang)
        raise ValueError("couldn't tell what kind of file that is")

    def _image_prep(self, data, screenshot, hint, screen_text, full=True):
        img = media.open_image(data)
        region, box, kind, caption = img, None, "photo", screen_text or ""
        if screenshot:
            box, _conf, mkind = find_media(img, hint, self.screen)
            region = img.crop(box)
            kind = mkind or region_kind(region)
            if kind == "none":
                txt = screen_text if len((screen_text or "").split()) >= 30 else (media.ocr(img) if full else "")
                if len(txt.split()) >= 8:
                    return {"text": txt, "box": box}
                return {"nothing": True, "box": box}
            if kind == "text":
                txt = screen_text if len((screen_text or "").split()) >= 30 else (media.ocr(region) if full else "")
                if len(txt.split()) >= 8:
                    return {"text": txt, "box": box}
                kind = "photo"
            elif full and not caption:
                caption = media.ocr(img) if media.TESSERACT else ""
        prints = fp.image_prints(region)
        local, meta = forensics.inspect_image(data, region) if full else ([], forensics.metadata_scan(data))
        return {
            "region": region, "box": box, "kind": kind, "caption": caption, "local": local, "meta": meta, "prints": prints,
            "payload": media.jpeg_bytes(region, 92) if screenshot else data,
        }

    def _nothing(self, kind, device, source_app, trigger, started, box, lang, quick=False):
        signals = [_sig("screen", 0.5, 0.0, "no photo, video or text block found on screen")]
        return self._finish(kind, signals, None, [], device, source_app, trigger, started, box, "none", True, lang, None, quick, decisive=True, say=L.t(lang, "nothing"))

    async def quick(self, data, filename="", source_app="", trigger="", device="", hint=None, lang="en", prev=None):
        started = time.time()
        screenshot = trigger in SCREEN_TRIGGERS or bool(hint) or (filename or "").lower().startswith("screenshot")
        prep = await asyncio.to_thread(self._image_prep, data, screenshot, hint, "", False)
        if prep.get("nothing"):
            return self._nothing("image", device, source_app, trigger, started, prep["box"], lang, quick=True)
        if prep.get("text"):
            v = await self.text(prep["text"], source_app, trigger, device, started=started, from_screen=True, lang=lang)
            v.quick = True
            return v
        prints, meta = prep["prints"], prep["meta"]
        if prev and self._again(device, prints["phash"], *prev):
            return self._noted(prev[0], "image", lang, started)
        signals = []
        if meta["generator"] or meta["source_type"] == "trainedalgorithmicmedia":
            signals.append(_sig("metadata", 0.97, 0.95, "; ".join(meta["notes"])))
        elif meta["c2pa"] and (meta["camera"] or meta["source_type"] == "digitalcapture"):
            signals.append(_sig("provenance", 0.05, 0.9, "content credentials from a camera capture"))
        hit = self.index.near(prints["phash"], threshold=10, kind="image")
        item = hit[0] if hit else None
        signals.extend(self._consensus_signal(item))
        factchecks = self.index.factchecks_for(item["id"]) if item else []
        if factchecks:
            signals.append(_sig("factcheck", 0.85, 0.75, f"{factchecks[0]['publisher']} rated a matching claim {factchecks[0]['rating'].lower()}"))
        p, rel = vd.fuse(signals, self.weights)
        tier = vd.tier_for(p, rel, signals)
        agreeing = item["p_n"] if item else 0
        decisive = tier in ("likely_synthetic", "no_ai_signals", "verified_capture") or (tier in ("leaning_synthetic", "leaning_human") and agreeing >= 5)
        counted = False
        if decisive:
            item, counted = self.index.record("image", prints=prints, p=p, tier=tier, generator=meta.get("generator", ""), source_app=source_app, match=item, device=device)
        return self._finish("image", signals, item, factchecks, device, source_app, trigger, started, prep["box"], prep["kind"], screenshot, lang, prints["phash"], quick=True, decisive=decisive, counted=counted)

    async def image(self, data, filename="", source_app="", trigger="", device="", hint=None, screen_text="", local_p=None, lang="en", prev=None):
        started = time.time()
        screenshot = trigger in SCREEN_TRIGGERS or (filename or "").lower().startswith(("screenshot", "img_screen")) or bool(hint)
        prep = await asyncio.to_thread(self._image_prep, data, screenshot, hint, screen_text, True)
        if prep.get("nothing"):
            return self._nothing("image", device, source_app, trigger, started, prep["box"], lang)
        if prep.get("text"):
            v = await self.text(prep["text"], source_app, trigger, device, started=started, from_screen=True, lang=lang)
            v.region = list(prep["box"])
            v.region_kind = "text"
            return v
        region, region_box, rkind, caption, local, meta, prints, payload = (prep[k] for k in ("region", "box", "kind", "caption", "local", "meta", "prints", "payload"))
        if prev and self._again(device, prints["phash"], *prev):
            return self._noted(prev[0], "image", lang, started)

        signals = [_sig(*s) for s in local]
        if local_p is not None and 0.0 <= local_p <= 1.0:
            signals.append(_sig("device_model", local_p, 0.45, f"on-device model: {local_p:.0%} synthetic"))
        if screenshot:
            for s in signals:
                if s.name in ("spectrum", "residual", "jpeg"):
                    s.reliability = round(s.reliability * 0.6, 3)
                    s.note += " (screenshot, weak)"
        hit = self.index.near(prints["phash"], threshold=10, kind="image")
        item = hit[0] if hit else None
        signals.extend(self._history_signals(item))

        signals.extend(await self._providers("image", payload, caption))
        factchecks = []
        for s in signals:
            if s.name == "factcheck" and s.raw.get("claims"):
                factchecks = s.raw["claims"][:3]
        if item:
            factchecks = factchecks or self.index.factchecks_for(item["id"])

        p, _ = vd.fuse(signals, self.weights)
        item, counted = self.index.record("image", prints=prints, p=p, tier=vd.tier_for(p, sum(s.reliability for s in signals), signals), generator=meta.get("generator", ""), source_app=source_app, match=item, device=device)
        if factchecks:
            self.index.add_factchecks(item["id"], factchecks)
        return self._finish("image", signals, item, factchecks, device, source_app, trigger, started, region_box, rkind, screenshot, lang, prints["phash"], counted=counted)

    async def video(self, data, source_app="", trigger="", device="", lang="en"):
        started = time.time()
        frames = await asyncio.to_thread(media.video_frames, data)
        signals = []
        if not frames:
            signals.append(_sig("decode", 0.5, 0.0, "couldn't decode the video"))
            return self._finish("video", signals, None, [], device, source_app, trigger, started, lang=lang)
        sig = fp.video_signature(frames)
        hit = self.index.near_video(sig)
        item = hit[0] if hit else None
        signals.extend(self._history_signals(item))

        picks = frames[:: max(1, len(frames) // 3)][:3]
        spec = [forensics.spectral_score(Image.fromarray(f)) for f in picks]
        s_mean = sum(s for s, _ in spec) / len(spec)
        signals.append(_sig("spectrum", s_mean, 0.15, spec[0][1] + " across sampled frames"))

        samples, sr = await asyncio.to_thread(media.video_audio, data, 16000)
        marks = []
        if samples is not None and len(samples) > 16000:
            marks = await asyncio.to_thread(fp.audio_marks, samples, sr)
            a_item, a_score = fp.audio_match(marks, self.index.audio_candidates(marks))
            if a_item and a_score > 0.2 and (not item or a_item != item["id"]):
                other = self.index.get(a_item)
                if other and other.get("kind") == "video":
                    signals.append(_sig("audio_reuse", 0.62, 0.35, "soundtrack matches a different video we've seen"))
            for name, score, rel, note in audiosignals.inspect_audio(samples, sr):
                signals.append(_sig(name, score, rel, note))

        if len(data) <= 20_000_000:
            signals.extend(await self._providers("video", data))
        signals.extend(await self._frames_through_model(picks))
        if not any(s.name in ("hive", "realitydefender") for s in signals):
            mid = Image.fromarray(frames[len(frames) // 2])
            signals.extend(await self._providers("image", media.jpeg_bytes(mid, 92), skip=("squint_model",)))

        p, _ = vd.fuse(signals, self.weights)
        tier = vd.tier_for(p, sum(s.reliability for s in signals), signals)
        if item:
            item, counted = self.index.record("video", p=p, tier=tier, source_app=source_app, match=item, device=device)
        else:
            item, counted = self.index.record("video", prints={"phash": sig[0]} if sig else None, frames=sig, audio=marks, p=p, tier=tier, source_app=source_app)
            if len(sig) > 1:
                self.index.record_frames(sig[1:], item["id"])
        return self._finish("video", signals, item, [], device, source_app, trigger, started, lang=lang, phash=sig[0] if sig else None, counted=counted)

    async def audio(self, data, source_app="", trigger="", device="", lang="en"):
        started = time.time()
        samples, sr = await asyncio.to_thread(media.decode_audio, data, 16000)
        signals = []
        if samples is None:
            signals.append(_sig("decode", 0.5, 0.0, "couldn't decode the audio"))
            return self._finish("audio", signals, None, [], device, source_app, trigger, started, lang=lang)
        marks = await asyncio.to_thread(fp.audio_marks, samples, sr)
        a_item, a_score = fp.audio_match(marks, self.index.audio_candidates(marks))
        item = self.index.get(a_item) if a_item and a_score > 0.2 else None
        signals.extend(self._history_signals(item))
        for name, score, rel, note in audiosignals.inspect_audio(samples, sr):
            signals.append(_sig(name, score, rel, note))
        wav = media.to_wav(samples, sr)
        signals.extend(await self._providers("audio", wav))
        p, _ = vd.fuse(signals, self.weights)
        tier = vd.tier_for(p, sum(s.reliability for s in signals), signals)
        if item:
            item, counted = self.index.record("audio", p=p, tier=tier, source_app=source_app, match=item, device=device)
        else:
            item, counted = self.index.record("audio", audio=marks, p=p, tier=tier, source_app=source_app)
        return self._finish("audio", signals, item, [], device, source_app, trigger, started, lang=lang, counted=counted)

    async def text(self, text, source_app="", trigger="", device="", started=None, from_screen=False, lang="en"):
        started = started or time.time()
        text = textsignals.clean(text)
        signals = []
        s, note = textsignals.stylometry(text)
        if s is not None:
            signals.append(_sig("style", s, 0.15, note))
        key = textsignals.text_key(text)
        hit = self.index.near(key, threshold=0, kind="text")
        item = hit[0] if hit else None
        signals.extend(self._history_signals(item))
        signals.extend(await self._providers("text", b"", text))
        factchecks = []
        for sg in signals:
            if sg.name == "factcheck" and sg.raw.get("claims"):
                factchecks = sg.raw["claims"][:3]
        for n in textsignals.phishing_notes(text):
            signals.append(_sig("phishing", 0.5, 0.0, n))
        p, _ = vd.fuse(signals, self.weights)
        tier = vd.tier_for(p, sum(sg.reliability for sg in signals), signals)
        item, counted = self.index.record("text", prints={"phash": key}, p=p, tier=tier, source_app=source_app, match=item, device=device)
        if factchecks:
            self.index.add_factchecks(item["id"], factchecks)
        return self._finish("text", signals, item, factchecks, device, source_app, trigger, started, screenshot=from_screen, lang=lang, phash=key, counted=counted)
