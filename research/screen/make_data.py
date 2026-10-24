import argparse
import glob
import os
import sys
from multiprocessing import Pool
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import gen

W, H = 160, 320


def _init(pool_paths):
    gen.set_pool(pool_paths)


def _one(seed):
    rng = np.random.default_rng(seed)
    img, box, cls, name = gen.sample(rng)
    small = np.asarray(img.resize((W, H), Image.BILINEAR), dtype=np.uint8)
    return small, np.array(box, dtype=np.float32), cls, name


def build(n, seed0, pool_paths, out, workers=2):
    imgs = np.lib.format.open_memmap(out + "_x.npy", mode="w+", dtype=np.uint8, shape=(n, H, W, 3))
    boxes = np.zeros((n, 4), dtype=np.float32)
    cls = np.zeros(n, dtype=np.int64)
    names = []
    with Pool(workers, initializer=_init, initargs=(pool_paths,)) as p:
        for i, (im, b, c, name) in enumerate(p.imap(_one, range(seed0, seed0 + n), chunksize=16)):
            imgs[i] = im
            boxes[i] = b
            cls[i] = c
            names.append(name)
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{n}")
                sys.stdout.flush()
    imgs.flush()
    np.save(out + "_box.npy", boxes)
    np.save(out + "_cls.npy", cls)
    with open(out + "_tpl.txt", "w") as f:
        f.write("\n".join(names))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=8000)
    ap.add_argument("--val", type=int, default=800)
    ap.add_argument("--photos", default="../data/real", help="folder of real photos to use as media content")
    ap.add_argument("--out", default="/tmp/screen_data")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    pool = sorted(glob.glob(os.path.join(args.photos, "**", "*.*"), recursive=True))
    pool = [p for p in pool if p.lower().endswith((".jpg", ".jpeg", ".png"))]
    print(f"{len(pool)} photos in the content pool")
    build(args.train, 1_000, pool, os.path.join(args.out, "train"), args.workers)
    build(args.val, 9_000_000, pool, os.path.join(args.out, "val"), args.workers)
    print("done")


if __name__ == "__main__":
    main()
