import logging
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse
from .reply import format_reply

log = logging.getLogger("squint.whatsapp")
GRAPH = "https://graph.facebook.com/v20.0"
last_check = {}


def verify(request):
    s = request.app.state.settings
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == s.whatsapp_verify:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "verify token mismatch")


async def _send(app, to, text):
    s = app.state.settings
    if not (s.whatsapp_token and s.whatsapp_phone_id):
        log.info("would send to %s: %s", to, text)
        return
    await app.state.pipeline.client.post(
        f"{GRAPH}/{s.whatsapp_phone_id}/messages",
        headers={"Authorization": f"Bearer {s.whatsapp_token}"},
        json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}},
    )


async def _download(app, media_id):
    s = app.state.settings
    client = app.state.pipeline.client
    r = await client.get(f"{GRAPH}/{media_id}", headers={"Authorization": f"Bearer {s.whatsapp_token}"})
    r.raise_for_status()
    url = r.json()["url"]
    r = await client.get(url, headers={"Authorization": f"Bearer {s.whatsapp_token}"})
    r.raise_for_status()
    return r.content, r.headers.get("content-type", "")


async def handle(app, body):
    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                for msg in change.get("value", {}).get("messages", []) or []:
                    await _one(app, msg)
    except Exception as e:
        log.warning("whatsapp handling failed: %s", e)


async def _one(app, msg):
    sender = msg.get("from", "")
    kind = msg.get("type")
    pipe = app.state.pipeline
    if kind == "text":
        text = msg["text"]["body"].strip()
        if text.lower() in ("wrong", "nope", "incorrect") and sender in last_check:
            app.state.index.add_feedback(last_check[sender], "unsure")
            await _send(app, sender, "noted, thanks. the index learns from this.")
            return
        if len(text) < 40:
            await _send(app, sender, "forward me an image, video, voice note or a chunk of text and i'll tell you what i can.")
            return
        v = await pipe.text(text, source_app="whatsapp", trigger="bot", device="wa:" + sender)
    elif kind in ("image", "video", "audio", "voice", "document"):
        media_id = msg[kind]["id"]
        data, ctype = await _download(app, media_id)
        v = await pipe.check(data, msg[kind].get("filename", ""), ctype, source_app="whatsapp", trigger="bot", device="wa:" + sender)
    else:
        return
    last_check[sender] = v.check_id
    await _send(app, sender, format_reply(v, hint=True))
