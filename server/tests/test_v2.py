import asyncio
import json
import time
import pytest
from httpx import ASGITransport, AsyncClient
from squint.app import build
from squint.index import Index_
from squint.pipeline import Pipeline
from squint import lang as L
from squint.providers.base import Provider, Signal
from conftest import noisy_photo, phone_screenshot, to_bytes, png_with_text


class Hot(Provider):
    name = "hive"
    kinds = {"image"}

    def __init__(self):
        pass

    def ready(self):
        return True

    async def check(self, kind, data, text="", client=None):
        return [Signal("hive", 0.92, 0.8, "hive puts it at 92% synthetic")]


@pytest.fixture
async def client(settings):
    settings.rate_per_minute = 500
    settings.partner_keys = "pk-1"
    idx = Index_(settings.db_url, settings.salt)
    app = build(settings, idx, Pipeline(settings, idx, providers=[]))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            c.index = idx
            yield c


def test_language_pick():
    assert L.pick("es-MX,es;q=0.9,en;q=0.8") == "es"
    assert L.pick("fr-FR") == "en"
    assert L.pick("fr", explicit="hi") == "hi"
    assert L.pick("", "pt-BR") == "pt"


def test_every_language_covers_every_tier():
    from squint.verdict import TIERS
    for code, table in L.LANGS.items():
        for t in TIERS:
            assert table[t] and table["headlines"][t], (code, t)


async def test_quick_is_fast_and_honest(client):
    shot, truth = phone_screenshot(noisy_photo(21))
    r = await client.post("/v1/quick", files={"file": ("Screenshot.png", to_bytes(shot), "image/png")}, data={"trigger": "assistant", "source_app": "ig"}, headers={"X-Device": "q1"})
    assert r.status_code == 200
    v = r.json()
    assert v["quick"] is True and v["decisive"] is False and v["tier"] == "unclear"
    assert len(v["phash"]) == 16
    assert v["ms"] < 1500


async def test_quick_is_decisive_on_generator_metadata(client):
    data = png_with_text(noisy_photo(22), "parameters", "Steps: 20, Model: sd_xl")
    r = await client.post("/v1/quick", files={"file": ("x.png", data, "image/png")}, data={"trigger": "share"}, headers={"X-Device": "q2"})
    v = r.json()
    assert v["decisive"] is True and v["tier"] == "likely_synthetic"


async def test_quick_becomes_decisive_once_index_knows(settings, index):
    pipe = Pipeline(settings, index, providers=[Hot()])
    data = to_bytes(noisy_photo(23), "JPEG")
    for i in range(5):
        v = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", f"d{i}")
        assert v.tier == "likely_synthetic"
    quick = Pipeline(settings, index, providers=[])
    v = await quick.quick(data, "a.jpg", "ig", "share", "d9")
    assert v.quick and v.decisive and v.tier in ("likely_synthetic", "leaning_synthetic")
    assert v.seen_before["sightings"] >= 5
    assert v.ms < 500


async def test_press_again_records_feedback(client):
    shot, _ = phone_screenshot(noisy_photo(24))
    data = to_bytes(shot)
    r = await client.post("/v1/check", files={"file": ("Screenshot.png", data, "image/png")}, data={"trigger": "assistant"}, headers={"X-Device": "again-1"})
    v = r.json()
    r2 = await client.post("/v1/check", files={"file": ("Screenshot.png", data, "image/png")}, data={"trigger": "assistant", "prev_check": v["check_id"], "prev_phash": v["phash"], "prev_ts": str(time.time() - 5)}, headers={"X-Device": "again-1"})
    v2 = r2.json()
    assert v2["feedback_recorded"] is True
    assert v2["say"] == "Noted, thanks."
    assert client.index.stats()["feedback"] == {"unsure": 1}


async def test_press_again_ignored_when_stale_or_different(client):
    shot, _ = phone_screenshot(noisy_photo(25))
    data = to_bytes(shot)
    r = await client.post("/v1/check", files={"file": ("Screenshot.png", data, "image/png")}, data={"trigger": "assistant"}, headers={"X-Device": "again-2"})
    v = r.json()
    r2 = await client.post("/v1/check", files={"file": ("Screenshot.png", data, "image/png")}, data={"trigger": "assistant", "prev_check": v["check_id"], "prev_phash": v["phash"], "prev_ts": str(time.time() - 600)}, headers={"X-Device": "again-2"})
    assert r2.json()["feedback_recorded"] is False
    other, _ = phone_screenshot(noisy_photo(26).rotate(90, expand=True))
    r3 = await client.post("/v1/check", files={"file": ("Screenshot.png", to_bytes(other), "image/png")}, data={"trigger": "assistant", "prev_check": v["check_id"], "prev_phash": v["phash"], "prev_ts": str(time.time())}, headers={"X-Device": "again-2"})
    assert r3.json()["feedback_recorded"] is False


async def test_spoken_line_follows_accept_language(client):
    data = png_with_text(noisy_photo(27), "parameters", "Steps: 20, Model: sd_xl")
    r = await client.post("/v1/check", files={"file": ("x.png", data, "image/png")}, headers={"X-Device": "es-1", "Accept-Language": "es-ES,es;q=0.9"})
    v = r.json()
    assert v["lang"] == "es" and v["say"].startswith("Probablemente")
    assert v["headline"] == "Probablemente IA"
    r = await client.post("/v1/check", files={"file": ("x.png", data, "image/png")}, data={"lang": "hi"}, headers={"X-Device": "hi-1"})
    assert r.json()["say"].startswith("शायद")


async def test_stats_has_trending_timeline_health(client):
    data = to_bytes(noisy_photo(28), "JPEG")
    for d in ("t1", "t2", "t3"):
        await client.post("/v1/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Device": d})
    s = (await client.get("/v1/stats")).json()
    assert s["trending"] and s["trending"][0]["recent"] == 3
    assert len(s["timeline"]) == 48 and sum(b["total"] for b in s["timeline"]) >= 3
    assert "providers" in s
    h = (await client.get("/healthz")).json()
    assert "provider_health" in h and "screen_model" in h
    r = await client.get("/v1/partner/trending", headers={"X-Api-Key": "pk-1"})
    assert r.status_code == 200 and r.json()[0]["sightings"] == 3


async def test_provider_health_counts_failures(settings, index):
    class Flaky(Provider):
        name = "flaky"
        kinds = {"image"}

        def __init__(self):
            self.n = 0

        def ready(self):
            return True

        async def check(self, *a, **k):
            self.n += 1
            if self.n % 2:
                raise RuntimeError("down")
            return [Signal("flaky", 0.5, 0.3, "meh")]

    pipe = Pipeline(settings, index, providers=[Flaky()])
    for i in range(4):
        await pipe.check(to_bytes(noisy_photo(30 + i), "JPEG"), "a.jpg", "image/jpeg", "x", "share", "d")
    h = pipe.health.snapshot()["flaky"]
    assert h["calls"] == 4 and h["failures"] == 2


async def test_cached_verdict(settings, index):
    pipe = Pipeline(settings, index, providers=[])
    data = to_bytes(noisy_photo(40), "JPEG")
    v = await pipe.check(data, "a.jpg", "image/jpeg", "x", "share", "dev")
    assert pipe.cached("dev", v.phash).check_id == v.check_id
    assert pipe.cached("other", v.phash) is None


async def test_webhook_fires_when_threshold_crossed(settings, index, monkeypatch):
    import httpx
    from squint.app import build
    received = []

    async def catcher(request):
        received.append(json.loads(request.content))
        return httpx.Response(200)

    from squint import hooks

    async def public(host, port):
        return ["93.184.216.34"]

    monkeypatch.setattr(hooks, "_resolve", public)
    settings.partner_keys = "pk-hook"
    settings.rate_per_minute = 500
    pipe = Pipeline(settings, index, providers=[], client=httpx.AsyncClient(transport=httpx.MockTransport(catcher)))
    seen_urls = []

    async def catcher(request):
        seen_urls.append((str(request.url), request.headers.get("host"), request.extensions.get("sni_hostname")))
        received.append(json.loads(request.content))
        return httpx.Response(200)

    pipe = Pipeline(settings, index, providers=[], client=httpx.AsyncClient(transport=httpx.MockTransport(catcher)))
    app = build(settings, index, pipe)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/v1/partner/webhooks", json={"url": "https://newsroom.example/hook", "threshold": 3}, headers={"X-Api-Key": "pk-hook"})
            assert r.status_code == 200 and r.json()["threshold"] == 3
            assert len((await c.get("/v1/partner/webhooks", headers={"X-Api-Key": "pk-hook"})).json()) == 1
            data = to_bytes(noisy_photo(61), "JPEG")
            for d in ("h1", "h2", "h3", "h4"):
                await c.post("/v1/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Device": d})
            await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0]["event"] == "item.spreading" and received[0]["sightings"] == 3
    assert seen_urls[0] == ("https://93.184.216.34/hook", "newsroom.example", "newsroom.example")


async def test_webhooks_cannot_point_inside(client, monkeypatch):
    from squint import hooks
    for url in ("http://localhost:8000/x", "http://127.0.0.1/x", "http://10.0.0.4/hook", "http://[::1]/x", "http://169.254.169.254/latest/meta-data", "ftp://example.org/x", "http://user:pw@example.org/x", "http://example.org:99999/x", "http://a..b/x", "http://[::ffff:10.0.0.4]/x"):
        r = await client.post("/v1/partner/webhooks", json={"url": url, "threshold": 3}, headers={"X-Api-Key": "pk-1"})
        assert r.status_code == 400, url

    async def rebinder(host, port):
        return ["93.184.216.34", "10.1.2.3"]

    monkeypatch.setattr(hooks, "_resolve", rebinder)
    r = await client.post("/v1/partner/webhooks", json={"url": "https://sneaky.example/hook", "threshold": 3}, headers={"X-Api-Key": "pk-1"})
    assert r.status_code == 400
    assert (await client.get("/v1/partner/webhooks", headers={"X-Api-Key": "pk-1"})).json() == []


async def test_verdicts_survive_a_restart(settings):
    idx = Index_(settings.db_url, settings.salt)
    app = build(settings, idx, Pipeline(settings, idx, providers=[]))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/v1/check", files={"file": ("a.jpg", to_bytes(noisy_photo(71), "JPEG"), "image/jpeg")}, headers={"X-Device": "p1"})
            first = r.json()
    idx2 = Index_(settings.db_url, settings.salt)
    app2 = build(settings, idx2, Pipeline(settings, idx2, providers=[]))
    async with app2.router.lifespan_context(app2):
        async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://t") as c:
            again = (await c.get(f"/v1/check/{first['check_id']}")).json()
            assert again["tier"] == first["tier"] and again["say"] == first["say"] and again["signals"] == first["signals"]
            assert (await c.get("/v1/check/" + "0" * 36)).status_code == 404
            assert (await c.get("/v1/check/short")).status_code == 404


def test_old_databases_pick_up_new_columns(settings):
    import sqlalchemy as sa
    eng = sa.create_engine(settings.db_url)
    with eng.begin() as c:
        c.execute(sa.text("CREATE TABLE checks (id VARCHAR(36) PRIMARY KEY, item_id VARCHAR(36), device VARCHAR(64), source_app VARCHAR(80), trigger VARCHAR(32), kind VARCHAR(12), tier VARCHAR(24), p FLOAT, signals TEXT, ms INTEGER, created DATETIME NOT NULL)"))
    eng.dispose()
    idx = Index_(settings.db_url, settings.salt)
    cid = idx.log_check(None, "d", "app", "share", "image", "unclear", 0.5, [], 12, payload='{"tier": "unclear"}')
    assert idx.get_check(cid) == {"tier": "unclear"}


async def test_huge_images_are_refused_politely(client):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("L", (12000, 9000)).save(buf, format="PNG", compress_level=9)
    r = await client.post("/v1/check", files={"file": ("bomb.png", buf.getvalue(), "image/png")}, headers={"X-Device": "b1"})
    assert r.status_code == 413
    r = await client.post("/v1/check", files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"garbage" * 40, "image/png")}, headers={"X-Device": "b1"})
    assert r.status_code == 415


async def test_one_device_cannot_inflate_sightings(client):
    data = to_bytes(noisy_photo(81), "JPEG")
    for _ in range(4):
        v = (await client.post("/v1/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Device": "same"})).json()
    assert v["seen_before"] is None
    v = (await client.post("/v1/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Device": "other"})).json()
    assert v["seen_before"]["sightings"] == 2
    s = (await client.get("/v1/stats")).json()
    assert not s["trending"] or s["trending"][0]["recent"] == 2


async def test_feedback_counts_once_and_press_again_votes_against_the_verdict(settings, index):
    pipe = Pipeline(settings, index, providers=[Hot()])
    data = to_bytes(noisy_photo(82), "JPEG")
    v = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "f1")
    assert v.tier == "likely_synthetic"
    item_id = index.near(v.phash)[0]["id"]
    for _ in range(3):
        assert index.add_feedback(v.check_id, "unsure")
    it = index.get(item_id)
    assert (it["feedback_ai"], it["feedback_human"]) == (0, 1)
    assert index.add_feedback(v.check_id, "ai")
    it = index.get(item_id)
    assert (it["feedback_ai"], it["feedback_human"]) == (1, 0)
    assert index.stats()["feedback"] == {"ai": 1}
    assert not index.add_feedback("no-such-check", "ai")
    v2 = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "f1")
    assert index.add_feedback(v2.check_id, "human")
    it = index.get(item_id)
    assert (it["feedback_ai"], it["feedback_human"]) == (0, 1)
    v3 = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "f2")
    assert index.add_feedback(v3.check_id, "human")
    it = index.get(item_id)
    assert (it["feedback_ai"], it["feedback_human"]) == (0, 2)
    await pipe.aclose()


async def test_quick_then_full_from_a_new_phone_counts_once(settings, index):
    pipe = Pipeline(settings, index, providers=[])
    data = to_bytes(noisy_photo(91), "JPEG")
    await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "p1")
    q = await pipe.quick(data, "a.jpg", "ig", "share", "p2")
    assert not q.decisive
    v = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "p2")
    assert v.seen_before and v.seen_before["sightings"] == 2
    v = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "p2")
    assert v.seen_before["sightings"] == 2
    await pipe.aclose()


async def test_a_second_wrong_on_the_opposite_verdict_flips_the_vote(settings, index):
    pipe = Pipeline(settings, index, providers=[])
    data = to_bytes(noisy_photo(92), "JPEG")
    v = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "w1")
    item_id = index.near(v.phash)[0]["id"]
    assert v.tier in ("leaning_human", "no_ai_signals", "unclear")
    index.add_feedback(v.check_id, "unsure")
    it = index.get(item_id)
    expect_ai = 1 if v.tier != "unclear" else 0
    assert (it["feedback_ai"], it["feedback_human"]) == (expect_ai, 0)
    v2 = await pipe.check(data, "a.jpg", "image/jpeg", "ig", "share", "w1")
    with index.engine.begin() as c:
        from sqlalchemy import text
        c.execute(text("update checks set tier='likely_synthetic' where id=:i"), {"i": v2.check_id})
    index.add_feedback(v2.check_id, "unsure")
    it = index.get(item_id)
    assert (it["feedback_ai"], it["feedback_human"]) == (0, 1)
    assert index.stats()["feedback"] == {"unsure": 1}
    await pipe.aclose()
