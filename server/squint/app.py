import asyncio
import hmac
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from . import __version__
from . import lang as L
from .config import settings as get_settings
from .index import Index_
from .limits import Bucket, Counters
from .pipeline import Pipeline
from .schemas import Feedback, PushRegistration, TextCheck, Verdict
from .bots import whatsapp
from .push import Apns, maybe_alert
from . import hooks, media

log = logging.getLogger("squint")
HERE = Path(__file__).parent


def parse_hint(raw):
    if not raw:
        return None
    try:
        parts = [int(float(x)) for x in raw.replace(" ", "").split(",")]
        return tuple(parts) if len(parts) == 4 else None
    except ValueError:
        return None


def parse_prev(prev_check, prev_phash, prev_ts):
    if prev_check and prev_phash:
        return (prev_check, prev_phash, prev_ts)
    return None


def build(settings=None, index=None, pipeline=None):
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings
        app.state.index = index or Index_(settings.db_url, settings.salt)
        app.state.pipeline = pipeline or Pipeline(settings, app.state.index)
        app.state.bucket = Bucket(settings.rate_per_minute)
        app.state.counters = Counters()
        app.state.apns = Apns(settings, app.state.pipeline.client)
        log.info("squint %s up, providers: %s, screen model: %s", __version__, ", ".join(app.state.pipeline.provider_names()) or "none (local signals only)", "yes" if app.state.pipeline.screen.ready else "heuristic")
        task = asyncio.create_task(_housekeeping(app))
        try:
            yield
        finally:
            task.cancel()
            await app.state.pipeline.aclose()

    app = FastAPI(title="squint", version=__version__, lifespan=lifespan)

    async def _housekeeping(app):
        while True:
            await asyncio.sleep(3600)
            try:
                n = app.state.index.purge(app.state.settings.retention_days)
                app.state.bucket.sweep()
                if n:
                    log.info("purged %d old check rows", n)
            except Exception as e:
                log.warning("housekeeping hiccup: %s", e)

    def _gate(request, device):
        key = device or (request.client.host if request.client else "anon")
        if not request.app.state.bucket.allow(key):
            request.app.state.counters.hit("rate_limited")
            raise HTTPException(429, "slow down a little")

    def _partner(request, api_key):
        keys = request.app.state.settings.partner_key_set
        if not keys or not any(hmac.compare_digest(api_key, k) for k in keys):
            raise HTTPException(401, "bad api key")

    async def _read(request, file):
        limit = request.app.state.settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"keep uploads under {request.app.state.settings.max_upload_mb} MB")
        if not data:
            raise HTTPException(400, "empty upload")
        return data

    def _lang(request, explicit):
        return L.pick(request.headers.get("accept-language", ""), explicit)

    async def _run(request, data, filename, content_type, source_app, trigger, device, hint, text="", screen_text="", local_p=None, lang="en", prev=None, quick=False):
        counters = request.app.state.counters
        pipe = request.app.state.pipeline
        t0 = time.time()
        try:
            if quick:
                v = await pipe.quick(data, filename, source_app, trigger, device, parse_hint(hint), lang, prev)
            else:
                v = await pipe.check(data, filename, content_type, source_app, trigger, device, parse_hint(hint), text, screen_text, local_p, lang, prev)
        except media.TooLarge as e:
            counters.hit("bad_input")
            raise HTTPException(413, str(e))
        except ValueError as e:
            counters.hit("bad_input")
            raise HTTPException(415, str(e))
        counters.hit("quick" if quick else "checks")
        if not v.feedback_recorded:
            counters.hit(f"tier_{v.tier}")
            counters.hit(f"kind_{v.kind}")
        counters.observe("quick" if quick else "check", int((time.time() - t0) * 1000))
        if trigger == "watch" and device and not quick:
            asyncio.create_task(maybe_alert(request.app, device, v))
        if v.seen_before and not v.feedback_recorded:
            due = hooks.crossed(request.app.state.index.list_webhooks(), v.seen_before["sightings"])
            if due:
                item = request.app.state.index.get(request.app.state.index.near(v.phash, 10, v.kind)[0]["id"]) if v.phash else None
                if item:
                    asyncio.create_task(hooks.fire(pipe.client, due, hooks.payload(item, v)))
        return v

    @app.get("/healthz")
    async def healthz(request: Request):
        pipe = request.app.state.pipeline
        return {"ok": True, "version": __version__, "providers": pipe.provider_names(), "screen_model": pipe.screen.ready, "provider_health": pipe.health.snapshot()}

    @app.post("/v1/check", response_model=Verdict)
    async def check(
        request: Request,
        file: UploadFile = File(...),
        source_app: str = Form(""),
        trigger: str = Form(""),
        hint: str = Form(""),
        screen_text: str = Form(""),
        local_p: str = Form(""),
        lang: str = Form(""),
        prev_check: str = Form(""),
        prev_phash: str = Form(""),
        prev_ts: str = Form(""),
        x_device: str = Header("", alias="X-Device"),
    ):
        _gate(request, x_device)
        data = await _read(request, file)
        lp = None
        if local_p:
            try:
                lp = float(local_p)
            except ValueError:
                lp = None
        return await _run(request, data, file.filename or "", file.content_type or "", source_app, trigger, x_device, hint, "", screen_text[:8000], lp, _lang(request, lang), parse_prev(prev_check, prev_phash, prev_ts))

    @app.post("/v1/quick", response_model=Verdict)
    async def quick(
        request: Request,
        file: UploadFile = File(...),
        source_app: str = Form(""),
        trigger: str = Form(""),
        hint: str = Form(""),
        lang: str = Form(""),
        prev_check: str = Form(""),
        prev_phash: str = Form(""),
        prev_ts: str = Form(""),
        x_device: str = Header("", alias="X-Device"),
    ):
        _gate(request, x_device)
        data = await _read(request, file)
        return await _run(request, data, file.filename or "", file.content_type or "", source_app, trigger, x_device, hint, lang=_lang(request, lang), prev=parse_prev(prev_check, prev_phash, prev_ts), quick=True)

    @app.post("/v1/check/text", response_model=Verdict)
    async def check_text(request: Request, body: TextCheck, x_device: str = Header("", alias="X-Device")):
        _gate(request, x_device or body.device)
        if len(body.text.strip()) < 20:
            raise HTTPException(400, "need a bit more text than that")
        return await _run(request, b"", "", "text/plain", body.source_app, "text", x_device or body.device, "", body.text, lang=_lang(request, body.lang))

    @app.post("/v1/feedback")
    async def feedback(request: Request, body: Feedback):
        if body.label not in ("ai", "human", "unsure"):
            raise HTTPException(400, "label should be ai, human or unsure")
        ok = request.app.state.index.add_feedback(body.check_id, body.label)
        if not ok:
            raise HTTPException(404, "no such check")
        request.app.state.counters.hit("feedback")
        return {"ok": True}

    @app.post("/v1/push/register")
    async def push_register(request: Request, body: PushRegistration, x_device: str = Header("", alias="X-Device")):
        device = x_device or body.device
        if not device:
            raise HTTPException(400, "need a device id")
        if not request.app.state.index.save_push_token(device, body.platform, body.token):
            raise HTTPException(400, "bad token")
        return {"ok": True, "push_configured": request.app.state.apns.ready()}

    @app.get("/v1/lookup")
    async def lookup(request: Request, phash: str, kind: str = "image"):
        if len(phash) != 16:
            raise HTTPException(400, "phash should be 16 hex chars")
        hit = request.app.state.index.near(phash, threshold=10, kind=kind)
        if not hit or hit[0]["sightings"] < 2:
            return {"found": False}
        item, d = hit
        return {
            "found": True, "distance": d, "sightings": item["sightings"], "first_seen": item["first_seen"].isoformat(),
            "tier": item["tier"], "p_mean": round(item["p_mean"], 3), "generator": item["generator"], "apps": json.loads(item["apps"] or "{}"),
            "factchecks": request.app.state.index.factchecks_for(item["id"]),
        }

    @app.get("/v1/stats")
    async def stats(request: Request):
        idx = request.app.state.index
        out = idx.stats()
        out["trending"] = idx.trending()
        out["timeline"] = idx.timeline()
        out["providers"] = request.app.state.pipeline.health.snapshot()
        out["screen_model"] = request.app.state.pipeline.screen.ready
        return out

    @app.post("/v1/partner/check")
    async def partner_check(
        request: Request,
        file: UploadFile = File(...),
        source_app: str = Form(""),
        x_api_key: str = Header("", alias="X-Api-Key"),
    ):
        _partner(request, x_api_key)
        data = await _read(request, file)
        v = await _run(request, data, file.filename or "", file.content_type or "", source_app, "partner", "partner:" + x_api_key[:6], "")
        request.app.state.counters.hit("partner_checks")
        return v

    @app.get("/v1/partner/recent")
    async def partner_recent(request: Request, x_api_key: str = Header("", alias="X-Api-Key")):
        _partner(request, x_api_key)
        return request.app.state.index.recent(100)

    @app.get("/v1/partner/trending")
    async def partner_trending(request: Request, hours: int = 24, x_api_key: str = Header("", alias="X-Api-Key")):
        _partner(request, x_api_key)
        return request.app.state.index.trending(hours=max(1, min(hours, 168)), limit=50)

    @app.post("/v1/partner/webhooks")
    async def add_webhook(request: Request, body: dict, x_api_key: str = Header("", alias="X-Api-Key")):
        _partner(request, x_api_key)
        url = str(body.get("url", ""))[:2000]
        problem = await hooks.unsafe(url)
        if problem:
            raise HTTPException(400, problem)
        wid = request.app.state.index.add_webhook(x_api_key[:16], url, body.get("threshold", 25))
        return {"id": wid, "url": url, "threshold": max(2, int(body.get("threshold", 25)))}

    @app.get("/v1/partner/webhooks")
    async def list_webhooks(request: Request, x_api_key: str = Header("", alias="X-Api-Key")):
        _partner(request, x_api_key)
        return request.app.state.index.list_webhooks(x_api_key[:16])

    @app.delete("/v1/partner/webhooks/{wid}")
    async def remove_webhook(request: Request, wid: str, x_api_key: str = Header("", alias="X-Api-Key")):
        _partner(request, x_api_key)
        if not request.app.state.index.remove_webhook(x_api_key[:16], wid):
            raise HTTPException(404, "no such webhook")
        return {"ok": True}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics(request: Request):
        return request.app.state.counters.render()

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        return (HERE / "dashboard.html").read_text()

    @app.get("/try", response_class=HTMLResponse)
    async def try_page():
        return (HERE / "static" / "try.html").read_text()

    @app.get("/manifest.webmanifest")
    async def manifest():
        return FileResponse(HERE / "static" / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/sw.js")
    async def service_worker():
        return FileResponse(HERE / "static" / "sw.js", media_type="application/javascript")

    @app.get("/icon.svg")
    async def icon():
        return FileResponse(HERE / "static" / "icon.svg", media_type="image/svg+xml")

    @app.post("/share-target")
    async def share_target(request: Request, file: UploadFile = File(None), text: str = Form(""), url: str = Form(""), title: str = Form("")):
        device = request.cookies.get("squint-device") or ("web-" + request.client.host if request.client else "web")
        _gate(request, device)
        lang = _lang(request, "")
        if file is not None and file.filename:
            data = await _read(request, file)
            v = await _run(request, data, file.filename or "", file.content_type or "", "web-share", "share", device, "", lang=lang)
        else:
            body = " ".join(x for x in (title, text, url) if x).strip()
            if len(body) < 20:
                return RedirectResponse("/try", status_code=303)
            v = await _run(request, b"", "", "text/plain", "web-share", "share", device, "", body, lang=lang)
        return RedirectResponse(f"/try?c={v.check_id}", status_code=303)

    @app.get("/v1/check/{check_id}")
    @app.get("/v1/result/{check_id}", include_in_schema=False)
    async def get_check(request: Request, check_id: str):
        if len(check_id) != 36:
            raise HTTPException(404, "no such check")
        hit = request.app.state.index.get_check(check_id)
        if not hit:
            raise HTTPException(404, "no such check, or it has been purged")
        return hit

    @app.get("/hooks/whatsapp")
    async def wa_verify(request: Request):
        return whatsapp.verify(request)

    @app.post("/hooks/whatsapp")
    async def wa_inbound(request: Request):
        body = await request.json()
        asyncio.create_task(whatsapp.handle(request.app, body))
        return JSONResponse({"ok": True})

    return app


app = build()
