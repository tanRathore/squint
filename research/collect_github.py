import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import numpy as np
from PIL import Image

REAL = [
    ("imagenet", "https://github.com/EliSchwartz/imagenet-sample-images", ["/*.JPEG"]),
    ("bsds500", "https://github.com/BIDS/BSDS500", ["/BSDS500/data/images/**"]),
    ("sr_benchmarks", "https://github.com/jbhuang0604/SelfExSR", ["/data/**"]),
]

SYNTHETIC = [
    ("sd1", "https://github.com/CompVis/stable-diffusion", ["/assets/**"]),
    ("sd2", "https://github.com/Stability-AI/stablediffusion", ["/assets/**"]),
    ("sdxl", "https://github.com/Stability-AI/generative-models", ["/assets/**"]),
    ("comfyui", "https://github.com/comfyanonymous/ComfyUI_examples", ["/**"]),
    ("flux", "https://github.com/black-forest-labs/flux", ["/assets/**"]),
    ("xflux", "https://github.com/XLabs-AI/x-flux", ["/assets/**"]),
    ("sana", "https://github.com/NVlabs/Sana", ["/asset/**"]),
    ("pixart", "https://github.com/PixArt-alpha/PixArt-alpha", ["/asset/**"]),
    ("pixart_sigma", "https://github.com/PixArt-alpha/PixArt-sigma", ["/asset/**"]),
    ("kolors", "https://github.com/Kwai-Kolors/Kolors", ["/imgs/**"]),
    ("hunyuan", "https://github.com/Tencent/HunyuanDiT", ["/asset/**"]),
    ("kandinsky3", "https://github.com/ai-forever/Kandinsky-3", ["/assets/**"]),
    ("kandinsky2", "https://github.com/ai-forever/Kandinsky-2", ["/content/**"]),
    ("janus", "https://github.com/deepseek-ai/Janus", ["/images/**"]),
    ("instantid", "https://github.com/InstantX/InstantID", ["/assets/**"]),
    ("infinity", "https://github.com/FoundationVision/Infinity", ["/assets/**"]),
    ("var", "https://github.com/FoundationVision/VAR", ["/assets/**"]),
    ("lumina", "https://github.com/Alpha-VLLM/Lumina-T2X", ["/assets/**"]),
    ("hart", "https://github.com/mit-han-lab/hart", ["/assets/**"]),
    ("deepfloyd", "https://github.com/deep-floyd/IF", ["/pics/**"]),
    ("cogview", "https://github.com/THUDM/CogView4", ["/resources/**"]),
    ("latent_diffusion", "https://github.com/CompVis/latent-diffusion", ["/assets/**"]),
    ("taming", "https://github.com/CompVis/taming-transformers", ["/assets/**"]),
    ("stable_cascade", "https://github.com/Stability-AI/StableCascade", ["/figures/**"]),
    ("t2i_adapter", "https://github.com/TencentARC/T2I-Adapter", ["/assets/**"]),
    ("ipadapter_plus", "https://github.com/cubiq/ComfyUI_IPAdapter_plus", ["/examples/**"]),
    ("freeu", "https://github.com/ChenyangSi/FreeU", ["/**"]),
    ("unidiffuser", "https://github.com/thu-ml/unidiffuser", ["/assets/**"]),
    ("omost", "https://github.com/lllyasviel/Omost", ["/**"]),
    ("wuerstchen", "https://github.com/dome272/Wuerstchen", ["/figures/**"]),
    ("nunchaku", "https://github.com/mit-han-lab/nunchaku", ["/assets/**"]),
    ("vqgan_clip", "https://github.com/nerdyrodent/VQGAN-CLIP", ["/samples/**"]),
    ("dalle_mini", "https://github.com/borisdayma/dalle-mini", ["/img/**"]),
    ("rudalle", "https://github.com/ai-forever/ru-dalle", ["/pics/**"]),
    ("cogview2", "https://github.com/THUDM/CogView2", ["/resources/**"]),
    ("stylegan2ada", "https://github.com/NVlabs/stylegan2-ada-pytorch", ["/docs/**"]),
    ("stylegan3", "https://github.com/NVlabs/stylegan3", ["/docs/**"]),
    ("pggan", "https://github.com/tkarras/progressive_growing_of_gans", ["/**"]),
    ("streamdiffusion", "https://github.com/cumulo-autumn/StreamDiffusion", ["/assets/**"]),
    ("lumina2", "https://github.com/Alpha-VLLM/Lumina-Image-2.0", ["/assets/**"]),
    ("sd35", "https://github.com/Stability-AI/sd3.5", ["/assets/**"]),
    ("hidream", "https://github.com/HiDream-ai/HiDream-I1", ["/assets/**"]),
    ("kolors2", "https://github.com/Kwai-Kolors/Kolors", ["/**"]),
    ("hunyuan2", "https://github.com/Tencent-Hunyuan/HunyuanImage-2.1", ["/assets/**"]),
    ("qwen_image", "https://github.com/QwenLM/Qwen-Image", ["/assets/**"]),
    ("bagel", "https://github.com/ByteDance-Seed/Bagel", ["/assets/**"]),
    ("show_o", "https://github.com/showlab/Show-o", ["/docs/**"]),
    ("animatediff", "https://github.com/guoyww/AnimateDiff", ["/__assets__/**"]),
    ("open_sora", "https://github.com/hpcaitech/Open-Sora", ["/assets/**"]),
    ("open_sora_plan", "https://github.com/PKU-YuanGroup/Open-Sora-Plan", ["/assets/**"]),
    ("latte", "https://github.com/Vchitect/Latte", ["/visuals/**"]),
    ("videocrafter", "https://github.com/AILab-CVC/VideoCrafter", ["/assets/**"]),
    ("cogvideo", "https://github.com/THUDM/CogVideo", ["/resources/**"]),
    ("pyramid_flow", "https://github.com/jy0205/Pyramid-Flow", ["/assets/**"]),
    ("hunyuan_video", "https://github.com/Tencent/HunyuanVideo", ["/assets/**"]),
    ("ltx_video", "https://github.com/Lightricks/LTX-Video", ["/docs/**"]),
    ("wan", "https://github.com/Wan-Video/Wan2.1", ["/assets/**"]),
    ("step_video", "https://github.com/stepfun-ai/Step-Video-T2V", ["/assets/**"]),
    ("karlo", "https://github.com/kakaobrain/karlo", ["/assets/**"]),
    ("mindalle", "https://github.com/kakaobrain/minDALL-E", ["/assets/**"]),
    ("parti", "https://github.com/google-research/parti", ["/images/**"]),
    ("min_dalle", "https://github.com/kuprel/min-dalle", ["/examples/**"]),
    ("interfacegan", "https://github.com/genforce/interfacegan", ["/docs/**"]),
    ("anycost_gan", "https://github.com/mit-han-lab/anycost-gan", ["/assets/**"]),
    ("pytorch_gan", "https://github.com/eriklindernoren/PyTorch-GAN", ["/assets/**"]),
    ("keras_gan", "https://github.com/eriklindernoren/Keras-GAN", ["/images/**", "/assets/**"]),
    ("singan", "https://github.com/tamarott/SinGAN", ["/imgs/**"]),
    ("biggan", "https://github.com/ajbrock/BigGAN-PyTorch", ["/imgs/**"]),
    ("pix2pixhd", "https://github.com/NVIDIA/pix2pixHD", ["/imgs/**"]),
    ("spade", "https://github.com/NVlabs/SPADE", ["/docs/**"]),
    ("prompt_to_prompt", "https://github.com/google/prompt-to-prompt", ["/docs/**"]),
    ("eg3d", "https://github.com/NVlabs/eg3d", ["/docs/**"]),
    ("stylegan_t", "https://github.com/autonomousvision/stylegan-t", ["/media/**"]),
    ("stylegan_xl", "https://github.com/autonomousvision/stylegan-xl", ["/media/**"]),
    ("dreamfusion", "https://github.com/ashawkey/stable-dreamfusion", ["/assets/**"]),
    ("net2net", "https://github.com/CompVis/net2net", ["/assets/**"]),
    ("streaming_t2v", "https://github.com/Picsart-AI-Research/StreamingT2V", ["/__assets__/**"]),
    ("motion_director", "https://github.com/showlab/MotionDirector", ["/assets/**"]),
    ("janus_pro", "https://github.com/deepseek-ai/Janus", ["/**"]),
]

SKIP_TOKENS = {
    "diagram", "arch", "architecture", "pipeline", "logo", "framework", "overview", "method", "table", "chart", "plot", "curve",
    "benchmark", "workflow", "screenshot", "ui", "gui", "canny", "depth", "pose", "openpose", "seg", "segmentation", "scribble",
    "hed", "mlsd", "normal", "sketch", "mask", "cond", "condition", "control", "input", "source", "ref", "reference", "banner",
    "icon", "badge", "qr", "wechat", "group", "lineart", "edge", "edges", "softedge", "tile", "shuffle", "fig", "figure",
}
EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def skip_name(stem):
    tokens = re.split(r"[^a-zA-Z0-9]+", stem.lower())
    return any(t in SKIP_TOKENS for t in tokens if t)


def looks_like_diagram(im):
    small = im.convert("RGB").resize((64, 64))
    q = (np.asarray(small) // 16).reshape(-1, 3)
    colours = len(np.unique(q, axis=0))
    white = (np.asarray(small).mean(axis=2) > 245).mean()
    return colours < 120 or white > 0.6


def sparse_clone(url, patterns, dest):
    if dest.exists():
        shutil.rmtree(dest)
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", url, str(dest)], check=True, env=env, timeout=600, capture_output=True)
    subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone", *patterns], check=True, env=env, timeout=600, capture_output=True)


def harvest(src, label, out, min_side, max_side, keep_skipwords):
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(src.rglob("*")):
        if p.suffix.lower() not in EXT or ".git" in p.parts:
            continue
        if not keep_skipwords and skip_name(p.stem):
            continue
        try:
            with Image.open(p) as im:
                frames = getattr(im, "n_frames", 1)
                if frames > 1:
                    im.seek(min(frames - 1, max(0, frames // 2)))
                im.load()
                w, h = im.size
                if min(w, h) < min_side or max(w, h) / max(1, min(w, h)) > 2.2:
                    continue
                if im.mode in ("P", "LA", "RGBA", "L", "I;16", "I"):
                    im = im.convert("RGB")
                if not keep_skipwords and looks_like_diagram(im):
                    continue
                if max(w, h) > max_side:
                    s = max_side / max(w, h)
                    im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
                name = re.sub(r"[^a-zA-Z0-9_-]", "_", p.stem)[:60]
                im.convert("RGB").save(out / f"{name}_{n}.png")
                n += 1
        except Exception:
            continue
    return n


def main():
    ap = argparse.ArgumentParser(description="pull public real photos and generator showcase images from github")
    ap.add_argument("--out", default="data")
    ap.add_argument("--tmp", default="/tmp/squint_collect")
    ap.add_argument("--min-side", type=int, default=224)
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--only", default="", help="comma separated source names")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}
    tmp = Path(args.tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    totals = {"real": 0, "synthetic": 0}
    for label, sources in (("real", REAL), ("synthetic", SYNTHETIC)):
        for name, url, patterns in sources:
            if only and name not in only:
                continue
            dest = tmp / name
            try:
                sparse_clone(url, patterns, dest)
            except Exception as e:
                print(f"{name}: clone failed ({str(e)[:80]})")
                continue
            n = harvest(dest, label, Path(args.out) / label / name, args.min_side, args.max_side, keep_skipwords=(label == "real"))
            totals[label] += n
            print(f"{name}: {n} {label} images")
            shutil.rmtree(dest, ignore_errors=True)
            sys.stdout.flush()
    print(f"\n{totals['real']} real, {totals['synthetic']} synthetic under {args.out}/")


if __name__ == "__main__":
    main()
