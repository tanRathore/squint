# lab notes

Kept as they happened, so the next person knows which decisions were measured and which were
taste.

## constraints that shaped everything

Two CPU cores, 7 GB RAM, no GPU. No access to Hugging Face, Kaggle, Zenodo or Google storage.
GitHub reachable, including release assets and LFS. That ruled out every public deepfake
dataset and every hub-hosted checkpoint, and ruled in anything that lives in a git repo.

## data

`collect_github.py` sparse-clones repos and keeps images that survive three filters: minimum
side 224, aspect ≤ 2.2, and a diagram test (fewer than 120 quantised colours at 64×64, or more
than 60 % near-white → drop). Filename tokens like `canny`, `pose`, `mask`, `input`, `pipeline`
drop conditioning maps and figures. First pass with substring matching threw away most of the
synthetic set (`ui` matched `fruit`); token matching fixed it. Final: 2,102 real / 457 synthetic
across 40 sources.

Real photos are research-dataset photos (ImageNet samples, BSDS500, SR benchmarks). They are
small, JPEG, mundane. Synthetic showcase images are large, PNG, spectacular. Any detector trained
on this will be tempted to learn "spectacular = fake". The screenshot simulator is applied to
both classes precisely to destroy the format cues (size, compression, chrome); it cannot destroy
the content cues. That is the honest limit of v0 and the reason the detector enters the fusion
at 0.6 reliability and not 0.9.

### second collection pass

The second pass added ~50 repos and 930 images, and the contact sheet of the biggest new sources
was alarming: StarGAN v2's `assets/` are CelebA-HQ and AFHQ *inputs*, SadTalker's examples are
source portraits, DynamiCrafter's and I2VGen's are the still photos you animate, IC-Light's are
the people you relight. Twenty-one repos whose purpose is editing, animating or restyling an
input image were dropped from the list altogether (`collect_github.py` no longer has them),
including some that were in the first pass (IP-Adapter, InstantStyle, Versatile Diffusion,
Text2Video-Zero). A detector trained on those would have been taught that real portraits are
synthetic. The cleaned set is 542 synthetic images from 54 sources against 2,102 real photos;
smaller than before, and correctly labelled. Video models (AnimateDiff, VideoCrafter,
MotionDirector, Latte, Open-Sora, CogVideo, HunyuanVideo, Step-Video) contribute middle frames
of their demo GIFs, which is the closest this box gets to AI video.

## text model: does OCR noise matter?

Text reaches the server two ways: clean from the assistant's view tree, or from tesseract on
the screenshot. The question was whether the TF-IDF model, trained on clean prose, falls over on
OCR output, and whether training on noised copies helps or hurts.

Two tests. A simulator (`research/text/ocr_noise.py`) applies character confusions, dropped
characters, merged and split words at 3/6/10 %. And a real one: 240 held-out documents rendered
at 22–48 px in system fonts, downscaled to 40–85 %, JPEG 40–90, read back with tesseract.
Rendered at phone sizes tesseract is nearly perfect (character agreement ≈ 1.0); the damage comes
from the downscale and the compression, and it lands as a threshold shift, not a reordering.

| model          | clean  | noise 10 % | tesseract | ESL FPR (lang8 / ets) |
|----------------|--------|------------|-----------|-----------------------|
| clean-trained  | 98.4 % | 96.3 %     | 94.2 %    | 2.0 % / 0.1 %         |
| noise-trained  | 98.7 % | 98.5 %     | 95.4 %    | 2.1 % / 0.1 %         |

AUC is 0.998–0.999 for both on the simulated rows and 0.984 for both on tesseract. The first
shipping rule compared AUCs and would have kept the old model; the product thresholds at 0.5, so
the rule now compares accuracy at the operating point and requires no loss on clean text. The
noise-trained model ships. It is the one training-based change in this round that cost nothing.

## screen model

Generator first, model second. The generator went through two revisions: abstract-blob media
only, then real photos as media content 65 % of the time. The first version risked a model that
finds "blob texture"; the second finds "the big rectangle that isn't UI".

First network was depthwise-separable (MobileNet style). On this CPU in PyTorch it ran 11.5 s
per batch of 32. Plain 3×3 convs with early stride-2 ran 2.4 s with the same parameter count.
Depthwise convs are a GPU/NPU optimisation; on a two-core CPU they are a trap.

Training on 8,000 pre-rendered samples (memmapped uint8) instead of generating on the fly was
the other speed decision: rendering a screen costs ~100 ms, a training step ~1 s, so on-the-fly
generation with one worker would have been generation-bound.

Validation IoU by epoch: 0.76, 0.80, 0.83, 0.86, 0.88, 0.82, 0.90, 0.81, 0.91, 0.93, 0.94,
0.93, 0.94, 0.94. The dips at 6 and 8 are OneCycle at peak learning rate. Fourteen epochs,
20 minutes.

### combining with the heuristic

The heuristic crop (busy-row / busy-column runs) is pixel-precise when it's right and wrong by
a whole caption block when it's wrong. The model is right about *what* the region is but its
edges are off by a few percent. Three rules were tried on 300 fresh full-res screens:

| rule                                              | mean IoU | ≥ 0.75 |
|---------------------------------------------------|----------|--------|
| heuristic only                                    | 0.786    | 65.6 % |
| model + edge snapping (±3 %)                      | 0.940    | 97.4 % |
| model, take heuristic box if IoU(model, heur) ≥ 0.5 | 0.878  | 78.0 % |
| model, take heuristic box if IoU ≥ 0.8, else snap ±6 % | **0.945** | **97.8 %** |

The 0.5 rule looked sensible and cost six points: the heuristic agrees "roughly" exactly when
it has swallowed a caption. Only near-identical agreement is worth trusting.

Class confidence under 0.75 hands the photo/text decision back to the colour-statistics rule.
This matters for the crude test screenshots in the suite (bitmap font on white), which look
like nothing the generator draws.

### does the model generalise to apps it has never seen?

Seven templates were added to the generator for v2 (X, Reddit, Telegram, a news app, TikTok
with the comment sheet open, a Pinterest-style grid, landscape/tablet), and v1's screen model
had never seen any of them. Rather than retrain and hope, the first run held three of the new
templates out of training entirely (Reddit, Telegram, news) and reported them separately
(`docs/screen_model_lto.json`, 160×320 model input, no heuristic blending):

| template (never trained on) | mean IoU | ≥ 0.75 | kind acc |
|-----------------------------|----------|--------|----------|
| reddit                      | 0.937    | 98 %   | 95 %     |
| news                        | 0.855    | 86 %   | 84 %     |
| telegram                    | 0.637    | 33 %   | 53 %     |

Layouts that look like layouts it knows (a feed post, an article) transfer almost for free.
Telegram does not: image bubbles sit at arbitrary positions and widths, and the nearest trained
template (chat) is itself the weakest family at 0.84. So the retrain on all 21 templates is
worth its 25 minutes for the chat-shaped apps specifically, and the LTO numbers above are the
honest expectation for the next app nobody drew a template for.

The grid template was a labelling mistake, caught by the same run: "the largest tile" is not a
thing a model can find in a masonry grid of similar tiles (IoU 0.217 even when trained on it).
A grid has no single media to check. It is now labelled *none*, so a press on an explore page
says nothing was found rather than checking a random tile.

The retrain on all templates (v2, 16 epochs, 24 minutes) against the same validation set:

| template | LTO IoU | v2 IoU | LTO kind | v2 kind |
|----------|---------|--------|----------|---------|
| telegram | 0.637   | 0.820  | 53 %     | 76 %    |
| news     | 0.855   | 0.946  | 84 %     | 94 %    |
| reddit   | 0.937   | 0.955  | 95 %     | 95 %    |
| chat     | 0.844   | 0.863  | 81 %     | 92 %    |
| all      | 0.880   | 0.939  | 89 %     | 93 %    |

On 600 fresh full-resolution screens with the heuristic blend, v2 scores 0.946 mean IoU and
98.0 % of boxes over 0.75, against 0.897 / 85.0 % for v1 on the same screens (v1 had never
seen seven of the templates). v2 ships. One more lesson from the per-template table: on
Telegram the heuristic alone (0.92) beats the blend (0.87), because the model's loose box
never agrees with the heuristic's tight one closely enough to defer to it. Four alternative
blends were tried offline on the same 600 screens (`research/screen/blend_study.py`,
`docs/screen_blend_study.json`): a looser agreement threshold (0.6), deferring to the heuristic
when its box sits inside the model's, deferring when the model's kind confidence is low, and
averaging the two boxes. Every one of them lifts Telegram (up to 0.94) and chat (up to 0.91) and
every one of them loses more elsewhere; the best alternative is 0.944 / 96.9 % against the
shipped rule's 0.946 / 98.0 %. The shipped rule stays. The fix for chat-shaped apps is a better
box from the model, not a cleverer merge.

## detector: what happens on a generator it has never seen

v0's validation split held out 15 % of every source, so every number it produced was about
generator families the model had trained on. New generators ship monthly; that is the wrong
question. v1 was trained with four families removed from training entirely, chosen to be unlike
each other: ComfyUI example outputs (96 images, the modern diffusion workflows people actually
run), MotionDirector video frames (21), ruDALL-E (10, VQ-token decoder) and StyleGAN3 (3).
Five epochs, batch 16, 52 minutes (`docs/detector_lfo.json`):

| | AUC | accuracy / recall at 0.5 |
|---|-----|---------------------------|
| held-out 15 % of trained-on sources (364 images) | 0.928 | 90.9 % |
| the four unseen families (130 synthetic vs the same real photos) | 0.859 | 59.2 % recall |
| ComfyUI alone | | 65.6 % recall |
| MotionDirector frames alone | | 19.0 % recall |
| ruDALL-E alone | | 90.0 % recall |

So: a generator this model has never met gets caught about six times in ten at the default
threshold, and AI *video* frames from an unfamiliar model mostly get through. That is the number
to put in front of anyone who asks "how good is the detector", and it is why the detector enters
the fusion at reliability 0.6 behind provenance, metadata and the index, and why the product's
moat is the fingerprint index and not this network. The in-distribution AUC (0.928) is lower than
v0's 0.955, which was measured on a validation set that contained the mislabelled input photos
and lacked the video-model frames; the two numbers are not comparable, and v1's is the honest one.

The shipped v1 is the hold-out checkpoint fine-tuned for three more epochs at a quarter of the
learning rate with the four families put back. Its in-distribution numbers are in `docs/models.md`;
its unseen-generator number is, by construction, unmeasured, and the 0.859 / 59 % above is the
best available estimate of it.

Was v1 worth shipping over v0? Both were run through the whole pipeline on the same 382
degraded validation images with per-image signals dumped (`eval.py --dump`). At a fixed 1 % or
2 % false-positive rate on real photos the two catch the same share of fakes (≈ 70 %); at 5 %
v1 catches 85 % to v0's 79 %; AUC 0.960 vs 0.912. At the default fusion settings v1 flags 75 %
of fakes (v0: 66 %) and 2.2 % of real photos (v0: 0.3 %). That is not a clean win at the strict
operating point, and the model card says so. v1 ships for the ranking, the labels and the
measured unseen-generator behaviour; the operating point is tunable in the fusion without
retraining. The fitted fusion weights (`calibrate.py --cv 2`) tied the hand-tuned ones on both
folds, so the hand-tuned ones stay: a second "did nothing, kept nothing" result for the round.

## quick path

The index-only answer needed its own fusion rule. With the normal history signal (reliability
0.12·√n, capped 0.5) three agreeing prior checks at 0.9 fuse to p = 0.46: the prior at 0.35
wins and nothing is ever decisive. The quick path uses a consensus signal (0.4·√n, capped 0.9)
and requires five agreeing sightings before a "leaning" verdict counts as decisive. Three
sightings → leaning, not decisive, full check still runs (cheap). Five → answered in 50 ms.

## things that were cut

- A per-detector haptic pattern. Nobody wants to learn eight rhythms.
- Always-on watch mode on Android. The OS allows it through MediaProjection; the privacy story
  doesn't survive it.
- Local notifications from the iOS broadcast extension. Extensions can't post them; the server
  pushes instead.
- Hamming search via BK-tree. Four 16-bit bands over indexed columns was simpler and is fine
  past a million rows.
