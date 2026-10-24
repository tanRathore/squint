import argparse
import asyncio
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="squint")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the api")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--reload", action="store_true")

    c = sub.add_parser("check", help="check a file from the command line")
    c.add_argument("path")
    c.add_argument("--app", default="cli")
    c.add_argument("--trigger", default="")
    c.add_argument("--json", action="store_true")

    sub.add_parser("bot", help="run the telegram bot (needs SQUINT_TELEGRAM_TOKEN)")
    sub.add_parser("purge", help="drop check rows older than the retention window")
    sub.add_parser("stats", help="print index stats")
    sub.add_parser("doctor", help="check tools, models, providers and run a self test")

    args = ap.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("squint.app:app", host=args.host, port=args.port, reload=args.reload)
        return

    from .config import settings
    from .index import Index_
    from .pipeline import Pipeline

    st = settings()

    if args.cmd == "doctor":
        doctor(st)
        return

    idx = Index_(st.db_url, st.salt)

    if args.cmd == "purge":
        n = idx.purge(st.retention_days)
        print(f"dropped {n} rows")
        return
    if args.cmd == "stats":
        print(json.dumps(idx.stats(), indent=2))
        return

    pipe = Pipeline(st, idx)

    if args.cmd == "bot":
        if not st.telegram_token:
            print("set SQUINT_TELEGRAM_TOKEN first")
            sys.exit(1)
        from .bots.telegram import TelegramBot
        asyncio.run(TelegramBot(st.telegram_token, pipe, idx).run())
        return

    if args.cmd == "check":
        p = Path(args.path)
        data = p.read_bytes()
        v = asyncio.run(pipe.check(data, p.name, "", args.app, args.trigger, "cli"))
        asyncio.run(pipe.aclose())
        if args.json:
            print(v.model_dump_json(indent=2))
            return
        print(f"{v.headline}  (p={v.p}, {v.confidence} confidence, {v.ms} ms)")
        print(f"  buzz: {v.haptic.label}")
        print(f"  say:  {v.say}")
        for e in v.evidence:
            print(f"  - {e}")


def doctor(st):
    import io
    import struct
    import zlib
    from PIL import Image
    from . import media
    from .index import Index_
    from .pipeline import Pipeline

    def row(ok, label, detail=""):
        print(f"  {'ok ' if ok else '-- '} {label}" + (f"  ({detail})" if detail else ""))

    print("tools")
    row(media.FFMPEG is not None, "ffmpeg", media.FFMPEG or "install it for video and audio")
    row(media.TESSERACT is not None, "tesseract", media.TESSERACT or "install it to read emails off the screen")
    row(media.HEIC, "heic", "pillow-heif" if media.HEIC else "pip install -e '.[heic]' for iphone originals")
    try:
        import onnxruntime
        row(True, "onnxruntime", onnxruntime.__version__)
    except ImportError:
        row(False, "onnxruntime", "pip install -e '.[onnx]' to run the bundled models")
    print("database")
    try:
        idx = Index_(st.db_url, st.salt)
        row(True, st.db_url.split("://")[0], f"{idx.stats()['items']} fingerprints")
    except Exception as e:
        row(False, st.db_url, str(e)[:80])
        return
    pipe = Pipeline(st, idx)
    print("models")
    row(pipe.screen.ready, "screen model", getattr(pipe.screen, "path", "") or "server/models/screen.onnx missing, heuristic crop in use")
    names = pipe.provider_names()
    row("squint_text" in names, "text model", "" if "squint_text" in names else "server/models/text.joblib missing or scikit-learn not installed")
    row("squint_model" in names, "image detector", "" if "squint_model" in names else "optional: SQUINT_LOCAL_MODEL or server/models/detector.onnx")
    print("providers")
    for n in ("hive", "sightengine", "realitydefender", "gptzero", "factcheck"):
        row(n in names, n, "" if n in names else "no key")
    if st.salt == "dev-salt":
        print("warning: SQUINT_SALT is the default, set it before real devices talk to this server")
    print("self test")
    img = Image.new("RGB", (320, 240), (90, 120, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    body = b"parameters\x00Steps: 20, Model: sd_xl"
    chunk = struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body) & 0xFFFFFFFF)
    data = data[:33] + chunk + data[33:]
    v = asyncio.run(pipe.check(data, "doctor.png", "image/png", "doctor", "share", "doctor"))
    asyncio.run(pipe.aclose())
    row(v.tier == "likely_synthetic", "generator metadata is caught", f"{v.tier}, {v.ms} ms")
    print("done")


if __name__ == "__main__":
    main()
