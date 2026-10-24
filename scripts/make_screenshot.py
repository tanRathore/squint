import argparse
import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "research", "screen"))
import gen


def main():
    ap = argparse.ArgumentParser(description="wrap any image in a fake phone app screenshot, for demos and tests")
    ap.add_argument("image")
    ap.add_argument("--app", default="feed", choices=["feed", "reel", "story", "chat", "email", "youtube", "gallery", "article"])
    ap.add_argument("--out", default="")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    gen.set_pool([args.image])
    gen.CANVAS_WIDTHS[:] = [1080]
    rng = np.random.default_rng(args.seed)
    tpl = getattr(gen, f"t_{args.app}")
    orig = gen.fake_photo

    def only_this(r, w, h):
        return gen.pooled_photo(r, w, h) or orig(r, w, h)

    gen.fake_photo = only_this
    img, box, cls = tpl(rng)
    out = args.out or f"Screenshot_{args.app}_{os.path.basename(args.image)}.png"
    img.save(out)
    print(f"{out}  media at {box}  ({cls})")


if __name__ == "__main__":
    main()
