# architecture

```
          ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
          │ android       │    │ iphone        │    │ whatsapp /    │    │ partner api   │
          │ assistant     │    │ app intent    │    │ telegram bot  │    │ (X-Api-Key)   │
          │ share, qs tile│    │ share, watch  │    │ forward-to-   │    │ newsrooms,    │
          │               │    │               │    │ check         │    │ platforms     │
          └──────┬────────┘    └──────┬────────┘    └──────┬────────┘    └──────┬────────┘
                 │ jpeg/mp4/wav/text + source_app + trigger (+ hint, screen_text, local_p, lang, prev_*)
                 ▼
     ┌───────────────────────────────────────────────────────────────────────────────────┐
     │ POST /v1/quick   screen model crop → provenance → phash → index → decisive?        │
     │                  (~50 ms; answers alone when metadata, credentials or 5 agreeing    │
     │                   sightings settle it; press-again within 45 s files "wrong")      │
     │ POST /v1/check                                                                      │
     │                                                                                     │
     │  sniff ──► image ─► crop(hint|screen model|heuristic) ─► kind? ─text─► ocr ─┐       │
     │        ├─► video ─► frames (ffmpeg, in memory) + audio track     │                   │
     │        ├─► audio ─► decode 16k mono                              │                   │
     │        └─► text ◄────────────────────────────────────────────────┘                   │
     │                                                                                     │
     │  provenance (c2pa, iptc, generator metadata)   ──┐                                   │
     │  fingerprint (phash / frame phash / landmarks)  ─┤                                   │
     │  index lookup (bands → hamming, offset voting)  ─┼─► signals[] ─► fuse ─► tier       │
     │  local forensics (spectrum, residual, jpeg)     ─┤               │                   │
     │  providers in parallel (hive, sightengine, rd,  ─┤               ▼                   │
     │     gptzero, factcheck, squint_model,            │   haptic + say(lang) + evidence    │
     │     squint_text)                                 │                                   │
     │  history (prior verdicts, feedback)             ─┘                                   │
     │                                                                                     │
     │  record: items(phash, first/last seen, sightings, p_mean, apps, generator)          │
     │          audio_marks(hash, item, t)  checks(device_hash, app, tier, p, signals)      │
     │          feedback(check, label)       factchecks(item, publisher, rating, url)       │
     └───────────────────────────────────────────────────────────────────────────────────┘
```

## modules (server/squint)

| file               | job                                                                            |
|--------------------|--------------------------------------------------------------------------------|
| `app.py`           | FastAPI routes, rate limiting, partner keys, metrics, dashboard, whatsapp hooks |
| `pipeline.py`      | one class, one method per media kind, orchestrates everything below            |
| `crop.py`          | screen model (onnx) + heuristic crop + edge snapping; photo vs text fallback  |
| `lang.py`          | spoken lines and headlines in en/es/pt/hi, Accept-Language parsing            |
| `media.py`         | sniffing, ffmpeg frame/audio extraction (pipe first, temp file fallback), OCR  |
| `forensics.py`     | metadata/provenance scan, spectral + residual + jpeg signals                   |
| `fingerprint.py`   | pHash/dHash/wHash, banding, video signatures, audio landmark hashes + voting   |
| `index.py`         | SQLAlchemy core tables, banded hamming search, audio candidates, stats, purge  |
| `providers/*`      | one adapter per detector; `registry()` only loads ones with keys or bundled models |
| `push.py`          | APNs token auth + time-sensitive alerts for iPhone watch mode                 |
| `verdict.py`       | fusion, tiers, haptic patterns, spoken line, evidence ordering                 |
| `textsignals.py`   | stylometry, phishing patterns, text dedupe key                                 |
| `audiosignals.py`  | bandwidth cliff, pause regularity                                               |
| `bots/`            | telegram long-poll bot, whatsapp cloud api webhook, shared reply formatting   |
| `limits.py`        | token bucket per device, counters for /metrics                                 |
| `cli.py`           | `squint serve | check | bot | purge | stats`                                   |

## models in the path

`server/models/screen.onnx` (1.2M params) runs before anything else on a screenshot: box +
kind. `server/models/text.joblib` (TF-IDF + LR) scores text blocks. `research/runs/detector/
squint.onnx` (EfficientNet-B0) scores image crops when `SQUINT_LOCAL_MODEL` points at it. The
Android app bundles the screen model and can bundle the detector; both run through ONNX Runtime
on the phone, so the crop happens before upload and an offline press still gets an answer.
Cards with numbers and caveats: `docs/models.md`.

## the fusion, precisely

Each signal is `(name, score ∈ [0,1], reliability ∈ [0,1], note)`. Posterior:

```
z = logit(0.35) + Σ reliability_i · clip(logit(score_i), −4, 4)
p = σ(z)
```

`reliability` is the provider's default unless `SQUINT_WEIGHTS_FILE` overrides it (fit by
`research/calibrate.py` from feedback). Then:

- `provenance` ≤ 0.1 (camera-signed C2PA) and no strong detector disagreement → `verified_capture`
- `metadata` ≥ 0.9 (generator named, or IPTC trainedAlgorithmicMedia) → `likely_synthetic`
- Σ reliability < 0.45 → `unclear` regardless of p (we refuse to guess on thin evidence)
- otherwise p ≥ .8 likely_synthetic · ≥ .62 leaning_synthetic · > .38 unclear · > .2 leaning_human · else no_ai_signals

Screenshots multiply the classical forensic signals by 0.6 because recompression wrecks them.
History from the index enters as a signal whose reliability grows with √n and jumps when there
are ≥3 human corrections.

## the index

Images: 64-bit pHash split into four 16-bit bands, each indexed. A query fetches rows sharing
any band (≤400), then exact hamming ≤10. Video: up to 8 evenly sampled frame hashes, each stored
as a `video` item pointing at the parent; a match needs ≥40% of query frames to hit the same
parent. Audio: Shazam-style (f1, f2, Δt) landmark hashes with time offsets; candidates are
fetched by hash and votes are counted per (item, offset) so a clip shifted by half a second
still matches.

Text: sha256 of the normalised text, exact match only.

Items accumulate `sightings`, `p_mean`, `apps` (which app each sighting came from), `generator`
hints and feedback counts. That is the dataset. A sighting is one device seeing one fingerprint
in one day: the check row records whether it counted, and a device that already counted is a
repeat (it still gets an answer, it just doesn't move the numbers). Feedback is one vote per
device per fingerprint, replaced rather than added when it changes.

## clients

**Android** registers as the device's `VoiceInteractionService`. On a press: tick → view-tree
hint or on-device screen model → crop → `/v1/quick` (decisive? buzz, done) → `/v1/check` →
buzz + whisper. A faint double tap at 1.6 s if still working. Verdicts are cached by perceptual
hash for six hours so a repeat press on the same thing answers instantly even offline; with no
network the phone scans the file's own metadata and says "checked on the phone only". On long-press power the system
calls `onHandleAssist(AssistState)` with the foreground app's view tree and `onHandleScreenshot(Bitmap)`
with the pixels (the user enables "use screenshot" once). We pick the largest
Image/Video/Surface/TextureView as the crop hint, collect visible text, crop on-device by default,
POST, hide the (already invisible) session, and deliver the verdict through `VibrationEffect.createWaveform`
and TTS at low volume on the accessibility stream. A Quick Settings tile and the share sheet are
secondary triggers. If `assets/squint.onnx` exists, ONNX Runtime scores the crop first and the
score rides along as `local_p`.

**iPhone** has no third-party assist hook, so the invisible trigger is a Shortcut: Take Screenshot →
Check with squint (our `AppIntent`, `openAppWhenRun = false`). Assigned to the Action Button or
Back Tap it is press → buzz, with Core Haptics playing the server's pattern and `AVSpeechSynthesizer`
whispering. The share extension covers reels and voice notes. A ReplayKit broadcast extension
samples a frame every 8 s while a video plays and posts a time-sensitive notification only when it
leans synthetic.

**Bots** are for the billion people who won't install anything: forward it to a number, get a
line back.

## scaling notes

SQLite is fine to ~10M items for a single node; the compose file runs Postgres and the band
indexes carry over. Provider calls are the latency floor (1–3 s); local signals and index lookups
are ~50 ms. Media never touches disk except ffmpeg's temp-file fallback for MP4s with a trailing
moov atom, which is deleted immediately. Horizontal scaling is stateless behind the DB: verdicts
are stored with their check row, so any replica can answer `GET /v1/check/{id}`. The only
in-memory state left is the per-device rate limiter and the 2-minute repeat-press cache; both are
per-process, so with several uvicorn workers the effective rate limit is `workers ×
SQUINT_RATE_PER_MINUTE` and a repeat press that lands on a different worker recomputes instead
of short-circuiting. Neither is a correctness problem, and both move to Redis before a second
replica goes live (`limits.Bucket` and `Pipeline.recent` are the two seams).

Schema changes: `Index_` creates missing tables and then adds any column that exists in the
model but not in the database, so a new column is a one-line change to `index.py` and old
databases pick it up on the next boot. Dropping or retyping a column still wants a real migration.
