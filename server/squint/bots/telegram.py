import asyncio
import logging
import httpx
from .reply import format_reply

log = logging.getLogger("squint.telegram")

KEYBOARD = {"inline_keyboard": [[{"text": "👍 right", "callback_data": "ok"}, {"text": "🤖 it's AI", "callback_data": "ai"}, {"text": "🧑 it's human", "callback_data": "human"}]]}


class TelegramBot:
    def __init__(self, token, pipeline, index):
        self.base = f"https://api.telegram.org/bot{token}"
        self.file_base = f"https://api.telegram.org/file/bot{token}"
        self.pipe = pipeline
        self.index = index
        self.client = httpx.AsyncClient(timeout=60)
        self.offset = 0
        self.last = {}

    async def send(self, chat, text, keyboard=None, reply_to=None):
        body = {"chat_id": chat, "text": text}
        if keyboard:
            body["reply_markup"] = keyboard
        if reply_to:
            body["reply_to_message_id"] = reply_to
        r = await self.client.post(f"{self.base}/sendMessage", json=body)
        try:
            return r.json()["result"]["message_id"]
        except Exception:
            return None

    async def fetch(self, file_id):
        r = await self.client.get(f"{self.base}/getFile", params={"file_id": file_id})
        r.raise_for_status()
        path = r.json()["result"]["file_path"]
        r = await self.client.get(f"{self.file_base}/{path}")
        r.raise_for_status()
        return r.content, path

    async def handle_callback(self, cb):
        data = cb.get("data", "")
        msg = cb.get("message") or {}
        chat = msg.get("chat", {}).get("id")
        key = (chat, msg.get("message_id"))
        check_id = self.last.get(key)
        label = {"ai": "ai", "human": "human", "ok": None}.get(data, None)
        if check_id and label:
            self.index.add_feedback(check_id, label)
            note = "noted, the index learns from this"
        elif check_id:
            note = "thanks"
        else:
            note = "that one's expired"
        await self.client.post(f"{self.base}/answerCallbackQuery", json={"callback_query_id": cb["id"], "text": note})
        if chat and msg.get("message_id"):
            await self.client.post(f"{self.base}/editMessageReplyMarkup", json={"chat_id": chat, "message_id": msg["message_id"], "reply_markup": {"inline_keyboard": []}})

    async def handle(self, msg):
        chat = msg["chat"]["id"]
        who = f"tg:{chat}"
        lang = (msg.get("from") or {}).get("language_code", "en")
        if "text" in msg:
            text = msg["text"].strip()
            if text.startswith("/start"):
                await self.send(chat, "send me a photo, video, voice note or paste some text. i'll tell you whether it looks machine made and whether we've seen it before. tap the buttons under a verdict to teach me.")
                return
            if len(text) < 40:
                await self.send(chat, "that's a bit short to judge. paste a paragraph or send media.")
                return
            v = await self.pipe.text(text, source_app="telegram", trigger="bot", device=who, lang=lang[:2])
        else:
            file_id, name = None, ""
            if "photo" in msg:
                file_id = msg["photo"][-1]["file_id"]
            elif "video" in msg:
                file_id = msg["video"]["file_id"]
            elif "video_note" in msg:
                file_id = msg["video_note"]["file_id"]
            elif "voice" in msg:
                file_id = msg["voice"]["file_id"]
            elif "audio" in msg:
                file_id = msg["audio"]["file_id"]
            elif "document" in msg:
                file_id = msg["document"]["file_id"]
                name = msg["document"].get("file_name", "")
            if not file_id:
                return
            data, path = await self.fetch(file_id)
            v = await self.pipe.check(data, name or path, "", source_app="telegram", trigger="bot", device=who, lang=lang[:2])
        mid = await self.send(chat, format_reply(v), KEYBOARD, reply_to=msg.get("message_id"))
        if mid:
            self.last[(chat, mid)] = v.check_id
            if len(self.last) > 2000:
                for k in list(self.last)[:500]:
                    del self.last[k]

    async def run(self):
        log.info("telegram bot polling")
        while True:
            try:
                r = await self.client.get(f"{self.base}/getUpdates", params={"offset": self.offset, "timeout": 30, "allowed_updates": ["message", "callback_query"]})
                for upd in r.json().get("result", []):
                    self.offset = upd["update_id"] + 1
                    if "callback_query" in upd:
                        try:
                            await self.handle_callback(upd["callback_query"])
                        except Exception as e:
                            log.warning("callback failed: %s", e)
                        continue
                    msg = upd.get("message")
                    if msg:
                        try:
                            await self.handle(msg)
                        except Exception as e:
                            log.warning("message failed: %s", e)
                            await self.send(msg["chat"]["id"], "something went wrong on my end, try again in a bit")
            except Exception as e:
                log.warning("poll failed: %s", e)
                await asyncio.sleep(3)
