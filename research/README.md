# research

The published detectors are trained on clean generator output. Our button produces screenshots:
recompressed, rescaled to phone widths, wrapped in UI chrome, sometimes screen-recorded. That gap
is where models trained on *our* input distribution earn their place, and where the index's
feedback loop closes. Three models live here; all trained on two CPU cores in this repo's
history, all with their numbers in `docs/models.md`. Every training run in this folder is paired
with the experiment that says whether it was worth doing (`docs/research_notes.md`): a hold-out
switch on each trainer, and a shipping rule that compares against what is already shipped.

## layout

```
collect_github.py   pulls real photos and generator showcase images from public github repos
aug.py              screenshot simulator: phone frame, letterbox, screen-record, recompress
data.py             folder dataset, applies the simulator at train time
metrics.py          auc, eer, ece, per-source breakdown (numpy only)
train.py            detector: timm efficientnet_b0 (github-release weights), exports squint.onnx
                    --holdout a,b scores generator families it never trained on; --init warm-starts
eval.py             runs the whole server pipeline over a labelled folder and scores it
                    --dump writes per-image signals for calibrate.py; --weights evaluates a fit
calibrate.py        fits per-signal reliability weights from feedback or a dump -> weights.json
                    --cv 2 first checks the fit beats the hand-tuned weights on held-out folds
screen/gen.py       procedural phone screenshots with bbox + kind labels, 21 app templates
screen/make_data.py renders a dataset to memmapped arrays with 2 workers
screen/train_screen.py  1.2M-param cnn for media box + kind, exports screen.onnx; --exclude holds templates out
screen/eval_screen.py   model vs heuristic crop on fresh full-res screens, per template
text/train_text.py  tf-idf + logistic regression on Ghostbuster; --augment compares an OCR-noise-trained
                    copy and ships whichever wins at the operating point; --real-ocr N renders N held-out
                    docs and reads them back with tesseract
text/ocr_noise.py   the OCR damage simulator and the render-and-tesseract path
weights.example.json    what calibrate.py writes
```

## data

```
python collect_github.py --out data
```

Sparse-clones ~75 repos and keeps images that pass size, aspect and diagram filters. Repos
whose example images are the *inputs* to an editing or animation model (IP-Adapter, SadTalker,
DynamiCrafter and friends) are deliberately not on the list; see the lab notes for how that was
learned.

```
data/real/<source>/*.png        imagenet samples, bsds500, set5/set14/bsd100/urban100
data/synthetic/<generator>/*.png  sd, sdxl, comfyui, flux, sana, pixart, kolors, hunyuan, ...
```

Subfolder names become the per-source breakdown in every report. Add your own folders the
same way; the breakdown is how you find out which family you're blind to.

## screen model

```
cd screen
python make_data.py --train 10000 --val 1200 --photos ../data/real --out /tmp/screen_data
python train_screen.py --data /tmp/screen_data --epochs 16 --out runs/screen_lto --exclude reddit,telegram,news
python train_screen.py --data /tmp/screen_data --epochs 16 --out runs/screen
python eval_screen.py --model runs/screen/screen.onnx --n 600 --photos ../data/real
cp runs/screen/screen.onnx ../../server/models/   # the server picks it up automatically
cp runs/screen/screen.onnx ../../android/app/src/main/assets/
```

~25 minutes per run on two cores. The first run answers "does it generalise to an app it has
never seen" (per-template numbers in `val_report.json`); the second is the one you ship.
`gen.py` on its own writes labelled samples you can look at.

## detector

```
python train.py --data data --epochs 5 --batch 16 --holdout comfyui,motion_director,rudalle,stylegan3 --out runs/detector_lfo
python train.py --data data --epochs 3 --batch 16 --init runs/detector_lfo/best.pt --out runs/detector
python train.py --smoke        # 30 second sanity run on synthetic blobs
python eval.py --data data --degrade --model runs/detector/squint.onnx --dump runs/detector/val_signals.jsonl
```

The hold-out run prints an "unseen generators" AUC and recall every epoch; that is the number to
quote, because new generators arrive monthly and the per-source split only measures families
the model has met. Never run two trainings at once on a 7 GB box; the second one gets OOM-killed.

`--degrade` pushes every image through the screenshot simulator first, which is the number that
matters. Watch `unclear_rate` as much as AUC: a system that says "can't tell" on half of
everything is useless even if the other half is right. Point the server at the model with
`SQUINT_LOCAL_MODEL=runs/detector/squint.onnx`.

## close the loop

Every "wrong" (a second press, a button in telegram, the list in the app) lands in the
`feedback` table next to the signals that produced the verdict. Once there are a few hundred:

```
python calibrate.py --db ../server/squint.db --cv 2 --out ../server/weights.json
SQUINT_WEIGHTS_FILE=weights.json squint serve
```

`--cv 2` fits on half the rows and scores the other half against the hand-tuned reliabilities,
both ways round, and refuses to write a file unless the fit wins on every fold. The same works on
an `eval.py --dump` file for a labelled folder (`--jsonl`).

The fit is a plain L2 logistic regression on `logit(score)` per signal. Coefficients become the
reliability weights the fusion uses, so a provider that keeps being wrong on our screenshots
loses its vote without anyone editing code.
