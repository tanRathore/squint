# the next ninety days

What is built is a working system with three trained models and an index that learns. What it
is not yet is a product with users. The order below is the order that produces the three
numbers an investor will ask for: checks per user per week, 30-day retention, index growth.

## weeks 1–2: real phones

- Build the Android APK and the iOS targets, sideload to ten phones across the team.
- Hosted server with Hive and the fact-check key, Postgres, the dashboard behind basic auth.
- Instrument: press-to-buzz latency p50/p95 per trigger, quick-path hit rate, press-again rate,
  share of "unclear". These four are the product's vitals.
- Fix what the first hundred real presses break. The screen model has only seen generated
  screens; every real press with a view-tree hint is a free labelled example. Store the hint
  box and the model box (no pixels) and retrain the screen model on week two.

## weeks 3–6: the first thousand

- Campus first, then the "is this AI?" corners of Reddit and TikTok comments, where the
  question is asked daily and nobody has a button.
- Telegram and WhatsApp bots as the install-free on-ramp; measure conversion to the app.
- Detector v1: replace the GitHub showcase set with real screenshots from the index that got
  decisive verdicts from provenance or strong provider agreement (weak labels), plus every
  correction. Retrain weekly. Calibrate reliability weights from corrections (`calibrate.py`)
  the moment there are 200 of them.
- Audio: the only modality without our own model. Collect voice-note presses; evaluate Hive and
  Resemble on them; decide whether to train.

## weeks 7–12: the index becomes the product

- Trending feed for partners (webhooks are built); first newsroom pilot, free, in exchange for
  labelled outcomes.
- OEM / antivirus conversation with the usage numbers in hand. The pitch is the index, not the
  detector: "N fingerprints, M corrections, first-seen timestamps across these apps".
- Privacy review by someone outside the team against `privacy.md`; publish the result.
- Wear OS / watchOS haptic relay: the phone checks, the wrist buzzes. The most invisible
  version of the interface and a cheap build on top of what exists.

## things to decide, not build

- Whether to charge consumers at all. The data engine argues no; a family tier for parents'
  phones argues a little.
- Whether to open the index API publicly at k-anonymity ≥ 2 (built) or keep it partner-only.
- Whether a C2PA-signing partnership (camera makers) is worth pursuing early: "camera-verified"
  is the one verdict users love and the one we can't produce without the ecosystem.
