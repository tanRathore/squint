from .base import Provider, Signal, register

SYNC = "https://api.thehive.ai/api/v2/task/sync"


def _walk_classes(payload):
    found = {}
    stack = [payload]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if "class" in cur and "score" in cur:
                found[cur["class"]] = max(found.get(cur["class"], 0.0), float(cur["score"]))
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return found


@register
class Hive(Provider):
    name = "hive"
    kinds = {"image", "video", "audio", "text"}
    reliability = 0.8

    def ready(self):
        return bool(self.settings.hive_key)

    async def check(self, kind, data, text="", client=None):
        headers = {"authorization": f"token {self.settings.hive_key}", "accept": "application/json"}
        if kind == "text":
            r = await client.post(SYNC, headers=headers, data={"text_data": text[:20000]})
        else:
            ext = {"image": "jpg", "video": "mp4", "audio": "wav"}[kind]
            r = await client.post(SYNC, headers=headers, files={"media": (f"check.{ext}", data)})
        r.raise_for_status()
        classes = _walk_classes(r.json())
        ai = classes.get("ai_generated")
        if ai is None:
            return []
        rel = self.reliability if kind in ("image", "video") else 0.65
        top = max(((k, v) for k, v in classes.items() if k not in ("ai_generated", "not_ai_generated", "none")), key=lambda kv: kv[1], default=None)
        note = f"hive puts it at {ai:.0%} synthetic"
        if top and top[1] > 0.4:
            note += f", closest generator {top[0]}"
        return [Signal(self.name, ai, rel, note, {"classes": classes})]
