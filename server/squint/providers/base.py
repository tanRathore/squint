import asyncio
import logging
from dataclasses import dataclass, field

log = logging.getLogger("squint.providers")


@dataclass
class Signal:
    name: str
    score: float
    reliability: float
    note: str = ""
    raw: dict = field(default_factory=dict)


class Provider:
    name = "base"
    kinds = set()
    reliability = 0.5

    def __init__(self, settings):
        self.settings = settings

    def ready(self):
        return False

    async def check(self, kind, data, text="", client=None):
        return []


_classes = []


def register(cls):
    _classes.append(cls)
    return cls


def registry(settings):
    out = []
    for cls in _classes:
        try:
            p = cls(settings)
            if p.ready():
                out.append(p)
        except Exception as e:
            log.warning("provider %s failed to start: %s", cls.name, e)
    return out


async def run_all(providers, kind, data, text, client, timeout):
    picks = [p for p in providers if kind in p.kinds]
    if not picks:
        return []
    tasks = [asyncio.wait_for(p.check(kind, data, text, client), timeout) for p in picks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    signals = []
    for p, r in zip(picks, results):
        if isinstance(r, Exception):
            log.info("%s skipped: %s", p.name, r)
            continue
        signals.extend(r)
    return signals
