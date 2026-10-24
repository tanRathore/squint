# model cards

Three models ship in this repo. Both were trained in this session on two CPU cores, and both
come with the numbers that matter and the caveats that matter more.

## 1. screen model (`server/models/screen.onnx`, `android/.../assets/screen.onnx`)

**What it does.** Given a phone screenshot, predicts the bounding box of the primary media and
which kind it is: `photo`, `video`, `text` or `none`. Used before every detector so we analyse
the post, not the status bar, and so emails go down the text path instead of the image path.

**Architecture.** 1.23M-parameter plain CNN, 7 stride-2/stride-1 conv blocks, coordinate
channels, flatten → 256 → (4 sigmoid box, 4-way class). Input 160×320 RGB in [0,1]. 5 MB ONNX,
~55 ms on CPU including edge snapping, well under 20 ms on a phone NPU.

**Training data.** 10,000 procedurally generated screenshots (`research/screen/gen.py`):
sixteen app templates (feed, reel, story, chat, email, youtube, gallery, article, X, Reddit,
Telegram, a news app, TikTok with the comment sheet open, a Pinterest-style grid, landscape /
tablet, settings), light and dark themes, six phone widths, real UI fonts (Inter, Poppins,
DejaVu, Liberation), real photos as media content 65 % of the time (ImageNet samples, BSDS500,
SR benchmarks pulled from GitHub) and procedural textures the rest. JPEG recompression and blur
applied at generation. Grids are labelled *none*: a masonry page has no single media to check.

**Results** (`docs/screen_model_eval.json`, 600 fresh full-resolution screens across all
templates, unseen seeds, heuristic blending on; v1 re-scored on the same screens in
`docs/screen_model_v1_on_v2_templates.json`):

| metric                       | v2 (shipped) | v1     | heuristic crop |
|------------------------------|--------------|--------|----------------|
| mean IoU                     | 0.946        | 0.897  | 0.824          |
| boxes with IoU ≥ 0.75        | 98.0 %       | 85.0 % | 71.7 %         |
| region kind accuracy         | 91.8 %       | 84.4 % | n/a            |
| settings / grid screens flagged none | 100 % / 100 % | 100 % / 0 % | n/a    |
| latency, CPU                 | 50 ms        | 54 ms  | 16 ms          |

By template (v2 IoU, v1 in brackets): article 0.96 (0.96), chat 0.88 (0.87), email 0.97 (0.97),
feed 0.97 (0.97), gallery 0.98 (0.98), landscape 0.96 (0.69), news 0.95 (0.89), reddit 0.96
(0.95), reel 0.97 (0.97), story 0.88 (0.88), telegram 0.87 (0.55), tiktok+comments 0.92 (0.62),
x 0.97 (0.94), youtube 0.96 (0.96). v1 held up on anything shaped like a feed and fell over on
the layouts it never saw; the leave-template-out run (`docs/screen_model_lto.json`, lab notes)
says the same thing from the other direction. Telegram is the one template where the plain
heuristic still beats the blend (0.92 vs 0.87): an image bubble is exactly the dense block the
run-finder was built for, and the model's loose box doesn't agree with it closely enough to
defer. Chat-shaped apps remain the weakest family.

**Caveats.** The evaluation set comes from the same generator as the training set, with
different seeds. Real app screenshots will have layouts the generator never drew; the hold-out
experiment puts the expected cost of a brand-new layout anywhere between nothing (Reddit) and a
third of the boxes (Telegram). The server therefore keeps the heuristic crop as a tie-breaker:
when the two agree closely (IoU ≥ 0.8) the pixel-precise heuristic edges win, and when the
model's class confidence is under 0.75 the colour-statistics classifier decides photo vs text.
The first few thousand real presses, with the view-tree hints Android sends alongside, are the
dataset that retrains this.

## 2. text model (`server/models/text.joblib`)

**What it does.** Scores a block of text (an email read off the screen, a caption, a pasted
message) for "machine written". Enters the fusion as `squint_text` with reliability 0.5 for
120+ words, 0.38 for 60+, 0.25 below that, and never fires under 25 words.

**Architecture.** TF-IDF over character 3–5-grams (80k features) and word 1–2-grams (40k)
→ logistic regression. 1.6 MB, scores in under 5 ms. `research/text/train_text.py`.

**Training data.** The Ghostbuster dataset (Verma, Fleisig, Tomlin, Klein 2023; CC BY 3.0):
human-written essays, Reuters articles and r/WritingPrompts stories alongside ChatGPT and Claude
versions of the same prompts. 8,909 documents, balanced per domain, 85/15 split. The shipped
model (v2) is trained on each document twice: once clean and once through
`research/text/ocr_noise.py`, which applies 1–8 % character-level OCR damage (l/1/I, rn/m, O/0,
dropped apostrophes, merged and split words, wrap hyphens).

**Results** (`docs/text_model_eval.json`; the same 15 % split for both models):

| test                                   | v1 (clean-trained) | v2 (shipped) |
|----------------------------------------|--------------------|--------------|
| in-domain held-out, AUC / accuracy     | 0.999 / 98.4 %     | 0.999 / 98.7 % |
| expected calibration error             | 0.057              | 0.039        |
| simulated OCR noise 3 %                | 97.9 %             | 98.5 %       |
| simulated OCR noise 6 %                | 97.2 %             | 98.4 %       |
| simulated OCR noise 10 %               | 96.3 %             | 98.5 %       |
| rendered to a phone-like screen and read back with tesseract (240 docs) | AUC 0.984 / 94.2 % | AUC 0.984 / 95.4 % |
| only the first 40 / 80 / 150 words     | 83.5 / 91.2 / 95.9 % | 83.5 / 91.5 / 96.0 % |
| essays / news / fiction held out entirely (v1) | AUC 0.916 / 0.964 / 0.975 | unchanged recipe |

False-positive rate on **non-native English** human writing, the classic failure of text
detectors: 2.1 % on Lang-8, 0.1 % on ETS essays (v1: 2.0 % / 0.1 %).

The tesseract row is the one that matters for the product: text arrives from the screen either
through the assistant's view tree (clean) or through OCR of the screenshot. Rendering the held-out
documents at 22–48 px, downscaling to 40–85 %, JPEG 40–90 and reading them back costs about four
points of accuracy for the clean-trained model and under three for v2. AUC is identical, so the
noise moves scores across the threshold rather than reordering documents; training on noised
copies fixes the threshold, which is why the shipping rule compares accuracy at 0.5 and not AUC.

**Caveats.** The machine side is 2023-era ChatGPT and Claude; newer models write differently
and the cross-domain numbers are the honest ones. It is a signal with reliability 0.5, so on
its own it can reach "leaning", never "likely".

## 3. detector v1 (`server/models/detector.onnx`)

**What it does.** Scores an image crop for "synthetic". Enters the fusion as `squint_model`
with reliability 0.6 and appears in evidence as "our screenshot model: N % synthetic". For
video it scores three sampled frames and reports the mean.

**Architecture.** timm EfficientNet-B0, ImageNet weights from the timm GitHub release,
2-way head, fine-tuned end to end at 224 px. 16 MB ONNX.

**Training data.** Collected by `research/collect_github.py` from public GitHub repositories:
2,102 real photos (ImageNet sample images, BSDS500, Set5/Set14/BSD100/Urban100) and 542
generator output images across 54 families: SD 1/2/XL, ComfyUI examples, FLUX and x-flux, Sana,
PixArt α/Σ, Kolors 1/2, HunyuanDiT/2, Kandinsky 2/3, Infinity, Lumina 1/2, DeepFloyd IF,
CogView, UniDiffuser, VQGAN-CLIP, ruDALL-E, min-DALL-E, Show-o, HART, BAGEL, Qwen-Image,
HiDream, StreamDiffusion, Stable Cascade, SPADE, pix2pixHD, InterFaceGAN, EG3D, StyleGAN3/XL,
PGGAN, BigGAN, SinGAN, Taming Transformers, Latent Diffusion, and middle frames from the demo
clips of AnimateDiff, VideoCrafter, MotionDirector, Latte, Open-Sora, CogVideo, HunyuanVideo,
Pyramid Flow and Step-Video. Twenty-one repos whose example images are *inputs* to an editing
or animation model were removed from the v0 list (see the lab notes); v0 had been training on
real portraits labelled synthetic. Every training image, both classes, goes through the
screenshot simulator (phone frame, letterbox, screen-record, recompress) 85 % of the time so the
model never sees a clean PNG. Validation holds out 15 % of every source.

**How it was trained.** First with four families held out entirely (ComfyUI, MotionDirector,
ruDALL-E, StyleGAN3; 130 images), five epochs, to measure what happens on a generator the model
has never met. Then three more epochs at a quarter of the learning rate with the four families
put back. The hold-out checkpoint is `docs/detector_lfo.json`; the shipped one is the fine-tune.

**Results on generators it had never seen** (hold-out checkpoint, 130 synthetic images vs the
314 held-out real photos, all degraded):

| | value |
|---|---|
| AUC                                       | 0.859 |
| synthetic recall at 0.5                   | 59.2 % |
| ComfyUI / MotionDirector frames / ruDALL-E recall | 65.6 % / 19.0 % / 90.0 % |

**Results on held-out images of trained-on sources** (shipped checkpoint, `docs/detector_val.json`,
382 images, degraded): AUC 0.954, accuracy at 0.5 90.6 %, equal error rate 11.8 %, ECE 0.062.

**Whole pipeline, v1 against v0 on the same 382 images**, degraded, no external providers
(`docs/detector_pipeline_eval.json`, `docs/detector_v0_pipeline_eval_same_split.json`):

| | v0 | v1 (shipped) |
|---|----|----|
| AUC                                                  | 0.912 | 0.960 |
| equal error rate                                     | 13.5 % | 10.2 % |
| synthetic (68) reaching *likely* or *leaning synthetic* | 66 % | 75 % |
| synthetic missed as *leaning human*                  | 29 % | 15 % |
| real photos (314) called *likely* or *leaning synthetic* | 0.3 % | 2.2 % |
| real photos left *unclear*                           | 1.6 % | 4.1 % |
| synthetic recall at a fixed 1 % / 2 % / 5 % real false-positive rate | 70.6 / 72.1 / 79.4 % | 69.1 / 70.6 / 85.3 % |

Read the last row carefully: at a strict 1–2 % false-positive budget the two models catch the
same share of fakes; v1's gain is in ranking (AUC, EER) and in the 5 % region, and at the
default fusion settings it answers more often and is wrong on real photos more often. The seven
real photos v1 calls synthetic are low-resolution research-dataset JPEGs the model scores at
0.90–0.98. Three of them reach *likely*. v1 ships because the ranking is better, the labels
behind it are right, and its behaviour on unseen generators is measured; the operating point is a
fusion parameter (`reliability`, `prior`) and the index pulls it back toward *human* as real
photos accumulate sightings.

**Fusion weights.** `calibrate.py --cv 2` on the 382 validation rows: fitted per-signal weights
tie the hand-tuned reliabilities on both folds (AUC 0.982 vs 0.981, 0.940 vs 0.940;
`docs/fusion_calibration_cv.json`), so no `weights.json` ships. The hand-set numbers stay until
real feedback says otherwise.

**Caveats, in order of importance.**
1. 542 synthetic images is small. The real-photo set is narrow in style (research datasets), and
   that is where v1's new false positives come from.
2. Showcase images are curated: high quality, often fantastical, frequently 1024 px. Natural
   photos in ImageNet are mundane and small. A model can learn *content* instead of *generation
   artefacts*. The screenshot simulator and random crops blunt this but do not remove it.
3. On a generator it has never seen it catches six in ten. On AI video frames from an unfamiliar
   model, two in ten. No deepfakes of faces, no phone-camera photos from the last five years.
4. It is one signal among several with reliability 0.6, never a verdict by itself; the fusion
   requires a raw score of 0.98 before the detector alone can say "likely".

The point of shipping it is the loop, not the number: real presses → corrections →
`calibrate.py` → reliability weights; real screenshots → `train.py` → the next version.
