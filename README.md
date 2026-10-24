# squint

Press a button your phone already has. Feel the answer.

squint is an on-demand check for synthetic media that never shows you a screen. You're looking
at a reel, a photo in a group chat, an email, a voice note. You long-press power (Android), hit
the Action Button or double-tap the back of the phone (iPhone), or share it from anywhere. The
phone gives squint a screenshot of that moment, squint answers through your hand:

| buzz                | meaning                                  |
|---------------------|------------------------------------------|
| one long            | likely machine made                      |
| long, then short    | leaning machine made, not certain        |
| three quick taps    | can't tell from this                     |
| two short           | nothing points to AI                     |
| short, then long    | camera-verified capture (content credentials) |

If you've got earbuds in, it also whispers one sentence: *"Likely AI. Seen 4,000 times since
Tuesday, Reuters rated it false."* It never says "real". It says what it saw and how sure it is.
In English, Spanish, Portuguese or Hindi, from the phone's locale.

Press again on the same screen within 45 seconds and you've told it it was wrong. No button, no
typing. That second press is how the index learns.

Nothing runs until you press. Nothing is stored except a perceptual fingerprint and the verdict.
No connection? The phone scans the file's own metadata and says so.

No app store? Open `/try` in Chrome on Android, add it to the home screen, and "squint" is in
every share sheet, vibrating verdicts through the browser.

## why this is a company and not a feature

Google will verify Google's watermarks. Meta labels Meta. Apple will check Apple. None of them
will tell you a TikTok in your WhatsApp is a Midjourney render, and none of them covers Gmail,
Instagram, YouTube and iMessage with one answer on one button. squint is the neutral layer.

The detector is deliberately a commodity: we aggregate Hive, Sightengine, Reality Defender,
GPTZero and our own model, and swap them as they rot. The thing that compounds is the **index**:
every press adds a fingerprint, a timestamp, the app it came from, and later a correction. Six
months in we know when something first appeared, how fast it's spreading, whether it's been
debunked, and which detectors keep getting it wrong on real screenshots. Nobody else has a button
in every app, so nobody else can collect that.

## what's here

```
server/     fastapi service: pipeline, hash-only index, provider adapters, fusion, api, bots
server/models/screen.onnx   trained screen model, finds the media on any screenshot (0.94 IoU)
android/    the assistant app: long-press power -> screenshot -> buzz. share target, qs tile,
            on-device crop + metadata scan + verdict cache, offline fallback, 4 languages
ios/        app intents (action button / back tap), share extension, replaykit watch mode,
            offline metadata scan, earcons
research/   data collection from github, screenshot simulator, two trained models, calibration
docs/       architecture, haptic grammar, model cards, privacy, threat model, api, pitch, demo
scripts/    demo.py (end to end, no keys needed), bench.py, make_screenshot.py, dev.sh, check.sh
```

## run it on a phone

`docs/run-on-phone.md`: server + tunnel, Android Studio, Xcode, bots. `squint doctor` tells you
what's missing.

## run it in two minutes

```bash
cd server
pip install -e ".[dev]"
cp .env.example .env            # add provider keys if you have them, works without
squint serve                    # http://localhost:8080/dashboard
```

```bash
python scripts/demo.py          # five checks through the real pipeline, prints verdicts
scripts/check.sh some_image.jpg # curl one file
squint check path/to/reel.mp4   # same thing without a server running
```

Tests: `pytest server/tests` (70 tests, covers ffmpeg video + audio round trips, OCR, the quick
path, press-again feedback, four languages and the bundled screen model) and
`pytest research/test_research.py`.

Docker: `cd server && docker compose up` gives you the api, the telegram bot and postgres.

## how a press becomes a buzz

0. **Tick.** The phone acknowledges the press within a frame. If nothing has answered after
   1.6 s it gives a faint double tap so you know it's still working.
1. **Trigger.** Android: squint is the device's digital assistant, so the OS hands the session a
   screenshot plus the view tree on long-press power. We find the largest media view, crop to it
   by default, and read the on-screen text for emails and captions. iPhone: a Shortcut takes the
   screenshot and hands it to our App Intent. Both: the share sheet works everywhere.
2. **Segment.** Without a view-tree hint, a 1.2M-parameter screen model trained on 10,000
   procedurally generated app screenshots (sixteen app layouts, from Instagram to Telegram to a
   tablet in landscape) finds the media box and says whether it's a photo, a video, a text block
   or nothing at all (0.946 mean IoU on fresh screens, 98 % of boxes over 0.75, against 0.824 /
   72 % for the row/column heuristic it replaced; the heuristic stays as a tie-breaker). The
   same model runs on the phone so the crop happens before anything is uploaded.
2b. **Quick path.** `/v1/quick` answers from provenance and the index alone in ~50 ms. If the
   index already has five agreeing sightings, that's the verdict and the full check is skipped:
   known fakes answer instantly, and the more people press, the faster it gets.
3. **Provenance first.** C2PA / Content Credentials, IPTC digital source type, generator metadata
   (SD prompt blocks, Midjourney/DALL·E/Firefly tags). Decisive when present, usually absent on
   screenshots, which is why the next steps exist.
4. **Fingerprint and look up.** pHash for images, sampled-frame pHash for video, Shazam-style
   landmark hashes for audio. Multi-index banding makes hamming lookup fast in SQLite/Postgres.
   A hit brings back first-seen, sighting count, prior verdicts, feedback and any fact-checks.
5. **Detectors.** Whatever's configured runs in parallel with a timeout, and anything that fails is
   skipped, never fatal. Our own classical signals (spectrum, residual noise, JPEG tables) carry
   low weight and say so. Text goes through stylometry plus phishing patterns plus providers.
6. **Fuse.** Weighted log-odds with per-signal reliability, hard overrides for camera provenance
   and generator metadata, and an honest *unclear* when total reliability is too low. Weights are
   refit from real feedback (`research/calibrate.py`), so a detector that keeps being wrong on our
   screenshots loses its vote.
7. **Answer.** Tier → haptic waveform + one spoken line + evidence list. Log the hash, the
   verdict, the source app and a salted device hash. Drop the pixels.

See `docs/architecture.md` for the long version and `docs/privacy.md` for exactly what is kept.

## the three models

| model | what | trained on | result |
|---|---|---|---|
| screen model v2 | media box + kind on a screenshot | 10,000 generated screens, 16 app layouts, real fonts, real photos | 0.946 IoU, 98.0 % ≥ 0.75, 92 % kind; v1 scored 0.897 / 85 % on the same screens |
| text model v2 | machine-written vs human text | Ghostbuster: 8,909 human / GPT / Claude docs (CC-BY), each seen clean and OCR-noised | 98.7 % in-domain, 95.4 % after render + tesseract, 0.92–0.98 AUC on unseen domains, 2 % FPR on non-native English |
| detector v1 | synthetic vs real crop | 2,102 real photos + 542 generator images from 54 families on public GitHub, all pushed through the screenshot simulator | AUC 0.954 on held-out images of trained-on sources; AUC 0.859 / 59 % recall on four generator families it never saw; whole pipeline AUC 0.960 vs 0.912 for v0 on the same split |

All three have model cards with the caveats spelled out in `docs/models.md` and ship bundled in
`server/models/`. The detector is one weighted signal among many; the screen model is
load-bearing.

## numbers on two cpu cores

- quick path on a 1080×2340 screenshot (screen model + hash + index): p50 163 ms, p90 288 ms
- full check with all three bundled models, no external providers: p50 596 ms, p95 752 ms,
  13.4 req/s at concurrency 8 on one two-core process (`scripts/bench.py`, 0.2.0 models)
- external providers add 1–3 s when configured; they run in parallel with a timeout

## honesty about accuracy

No detector is conclusive and we don't pretend otherwise. With the bundled models and no provider
keys, the pipeline commits to an answer on about 97 % of held-out images at 94 % accuracy, and
says *unclear* for the rest. Provenance and metadata always win when present. With Hive or
Reality Defender configured on top, the fusion gets a second independent vote.
The research folder exists because published detectors degrade badly on screenshots, which is the
only thing this product ever sees, and that gap is ours to close.

## licence

MIT.
