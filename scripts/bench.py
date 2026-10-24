import argparse
import asyncio
import io
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw


def sample(seed):
    rng = np.random.default_rng(seed)
    a = rng.normal(128, 30, (1080, 1080, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(a)
    d = ImageDraw.Draw(img)
    for _ in range(5):
        x, y = rng.integers(0, 900, 2)
        d.ellipse([x, y, x + 150, y + 150], fill=tuple(int(c) for c in rng.integers(0, 255, 3)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


async def one(client, server, data, i):
    t0 = time.perf_counter()
    r = await client.post(f"{server}/v1/check", files={"file": (f"s{i}.jpg", data, "image/jpeg")}, data={"source_app": "bench", "trigger": "share"}, headers={"X-Device": f"bench-{i % 50}"})
    return (time.perf_counter() - t0) * 1000, r.status_code


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:8080")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    samples = [sample(i) for i in range(20)]
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(timeout=60) as client:
        async def guarded(i):
            async with sem:
                return await one(client, args.server, samples[i % len(samples)], i)
        t0 = time.perf_counter()
        results = await asyncio.gather(*(guarded(i) for i in range(args.n)))
        wall = time.perf_counter() - t0

    lat = sorted(ms for ms, _ in results)
    codes = {}
    for _, c in results:
        codes[c] = codes.get(c, 0) + 1
    print(f"{args.n} checks, concurrency {args.concurrency}, {wall:.1f}s wall, {args.n / wall:.1f} req/s")
    print(f"latency ms  p50 {lat[len(lat) // 2]:.0f}  p95 {lat[int(len(lat) * 0.95) - 1]:.0f}  max {lat[-1]:.0f}")
    print(f"status codes {codes}")


if __name__ == "__main__":
    asyncio.run(main())
