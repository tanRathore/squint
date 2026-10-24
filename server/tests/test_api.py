import pytest
from httpx import ASGITransport, AsyncClient
from squint.app import build
from squint.index import Index_
from squint.pipeline import Pipeline
from conftest import noisy_photo, to_bytes, png_with_text


@pytest.fixture
async def client(settings):
    settings.partner_keys = "pk-test"
    settings.rate_per_minute = 5
    idx = Index_(settings.db_url, settings.salt)
    app = build(settings, idx, Pipeline(settings, idx, providers=[]))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            yield c


async def test_health(client):
    r = await client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"]


async def test_check_image(client):
    data = png_with_text(noisy_photo(1), "parameters", "Steps: 20, Model: sd_xl")
    r = await client.post("/v1/check", files={"file": ("x.png", data, "image/png")}, data={"source_app": "test", "trigger": "share"}, headers={"X-Device": "dev-1"})
    assert r.status_code == 200
    j = r.json()
    assert j["tier"] == "likely_synthetic"
    assert j["haptic"]["pattern"] and j["say"] and j["check_id"]


async def test_feedback_and_lookup(client):
    data = to_bytes(noisy_photo(2), "JPEG")
    r = await client.post("/v1/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Device": "dev-2"})
    cid = r.json()["check_id"]
    r = await client.post("/v1/feedback", json={"check_id": cid, "label": "ai"})
    assert r.status_code == 200
    r = await client.post("/v1/feedback", json={"check_id": "zzz", "label": "ai"})
    assert r.status_code == 404
    r = await client.post("/v1/feedback", json={"check_id": cid, "label": "maybe"})
    assert r.status_code == 400
    from squint.fingerprint import image_prints
    ph = image_prints(noisy_photo(2))["phash"]
    r = await client.get("/v1/lookup", params={"phash": ph})
    assert r.json()["found"] is False
    await client.post("/v1/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Device": "dev-2b"})
    r = await client.get("/v1/lookup", params={"phash": ph})
    assert r.json()["found"] and r.json()["sightings"] == 2


async def test_text_endpoint(client):
    r = await client.post("/v1/check/text", json={"text": "short"}, headers={"X-Device": "dev-3"})
    assert r.status_code == 400
    r = await client.post("/v1/check/text", json={"text": "a " * 60, "source_app": "gmail"}, headers={"X-Device": "dev-3"})
    assert r.status_code == 200 and r.json()["kind"] == "text"


async def test_rate_limit(client):
    data = to_bytes(noisy_photo(3), "JPEG")
    codes = []
    for _ in range(7):
        r = await client.post("/v1/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Device": "spammy"})
        codes.append(r.status_code)
    assert 429 in codes


async def test_partner_requires_key(client):
    data = to_bytes(noisy_photo(4), "JPEG")
    r = await client.post("/v1/partner/check", files={"file": ("a.jpg", data, "image/jpeg")})
    assert r.status_code == 401
    r = await client.post("/v1/partner/check", files={"file": ("a.jpg", data, "image/jpeg")}, headers={"X-Api-Key": "pk-test"})
    assert r.status_code == 200
    r = await client.get("/v1/partner/recent", headers={"X-Api-Key": "pk-test"})
    assert r.status_code == 200 and len(r.json()) >= 1


async def test_rejects_garbage(client):
    r = await client.post("/v1/check", files={"file": ("a.bin", b"\x00\x01\x02" * 50, "application/octet-stream")}, headers={"X-Device": "dev-9"})
    assert r.status_code == 415


async def test_stats_metrics_dashboard(client):
    r = await client.get("/v1/stats")
    assert r.status_code == 200 and "checks" in r.json()
    r = await client.get("/metrics")
    assert r.status_code == 200
    r = await client.get("/dashboard")
    assert r.status_code == 200 and "squint" in r.text


async def test_whatsapp_verify(client):
    r = await client.get("/hooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "squint", "hub.challenge": "abc"})
    assert r.status_code == 200 and r.text == "abc"
    r = await client.get("/hooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "abc"})
    assert r.status_code == 403


async def test_pwa_share_target_round_trip(client):
    r = await client.get("/try")
    assert r.status_code == 200 and "share sheet" in r.text
    r = await client.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.json()["share_target"]["action"] == "/share-target"
    assert (await client.get("/sw.js")).status_code == 200
    data = png_with_text(noisy_photo(5), "parameters", "Steps: 20, Model: sd_xl")
    r = await client.post("/share-target", files={"file": ("x.png", data, "image/png")})
    assert r.status_code == 303 and r.headers["location"].startswith("/try?c=")
    cid = r.headers["location"].split("c=")[1]
    v = (await client.get(f"/v1/result/{cid}")).json()
    assert v["tier"] == "likely_synthetic"
    r = await client.post("/share-target", data={"text": "x " * 40, "title": "hello"})
    assert r.status_code == 303
    assert (await client.get("/v1/result/nope")).status_code == 404
