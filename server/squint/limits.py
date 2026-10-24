import time
from collections import defaultdict


class Bucket:
    def __init__(self, per_minute):
        self.rate = per_minute / 60.0
        self.cap = float(per_minute)
        self.state = defaultdict(lambda: [self.cap, time.monotonic()])

    def allow(self, key):
        tokens, last = self.state[key]
        now = time.monotonic()
        tokens = min(self.cap, tokens + (now - last) * self.rate)
        if tokens < 1:
            self.state[key] = [tokens, now]
            return False
        self.state[key] = [tokens - 1, now]
        return True

    def sweep(self, older_than=600):
        now = time.monotonic()
        for k in [k for k, (_, t) in self.state.items() if now - t > older_than]:
            del self.state[k]


class Counters:
    def __init__(self):
        self.c = defaultdict(int)
        self.latency = defaultdict(list)

    def hit(self, name, n=1):
        self.c[name] += n

    def observe(self, name, ms):
        arr = self.latency[name]
        arr.append(ms)
        if len(arr) > 500:
            del arr[: len(arr) - 500]

    def render(self):
        lines = []
        for k, v in sorted(self.c.items()):
            lines.append(f"squint_{k} {v}")
        for k, arr in self.latency.items():
            if arr:
                s = sorted(arr)
                lines.append(f"squint_latency_ms_p50{{stage=\"{k}\"}} {s[len(s) // 2]}")
                lines.append(f"squint_latency_ms_p95{{stage=\"{k}\"}} {s[int(len(s) * 0.95) - 1 if len(s) > 1 else 0]}")
        return "\n".join(lines) + "\n"
