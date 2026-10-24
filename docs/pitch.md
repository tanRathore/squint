# squint — one page

**What.** An independent "is this real?" button that works on anything on your screen, in any
app, on any phone, with no screen of its own. Press a button you already have; feel the answer.
Behind it, a crowd-built index of synthetic media that gets smarter with every press.

**Why now.** Reported US fraud losses hit $15.9B in 2025, up from $12B; imposter scams were the
most reported category at $3.5B; text and social media are the top contact channels. Generators
are free and watermarks are optional. Google, Meta and Apple each ship detection for their own
content only, and each needs you to open their thing.

**The insight.** Detection is a commodity that decays. The platforms can't be neutral across each
other. The only durable asset is an index of what has been seen, where, when, and what people
said about it, and the only way to build that index is a button that lives in every app. The
button is the wedge, the index is the moat, same shape as Truecaller.

**Product.** Android: long-press power (we're the digital assistant, the OS hands us the
screenshot). iPhone: Action Button / Back Tap via Shortcut, share sheet, watch mode. WhatsApp and
Telegram bots for people who will never install anything. Output is a haptic pattern and one
whispered sentence, in four languages, that always carries its evidence and never says "real".
Known fakes answer in 50 ms from the index. Pressing again means "wrong", so correcting the
index costs nothing. No connection: the phone answers from the file's own metadata.

**Privacy as strategy.** Nothing runs until you press. Pixels are processed in memory; only a
perceptual hash, the verdict and the source app are kept. This is the one sentence Circle to
Search can't say, and it is what makes people willing to press on their own messages.

**Who pays.**
- B2B2C licensing: OEM pre-installs (Samsung, Xiaomi, Honor), antivirus suites, browsers, carriers.
- API: newsrooms, marketplaces, dating apps, insurers, brands fighting fake endorsements.
- Consumer family tier: protect your parents' phones. Small revenue, the data engine.

**Why we win.** Reality Defender, Sensity, GetReal sell forensics to banks and governments with no
consumer surface. McAfee and Norton need an app and a subscription. Google verifies Google. We own
the moment of doubt in every app and the dataset that only that moment produces: real
screenshots, real spread, real corrections.

**Why us.** Computer vision research background; the technical edge is models trained on the
screenshot distribution, which is the only input this product ever sees and the one published
detectors are worst at. Three already exist in this repo, trained on public data on two CPU
cores: a screen model that finds the media on any app screenshot (0.946 IoU across sixteen app
layouts, replaces a heuristic at 0.824, and measured on layouts it was never shown), a text
model that reads emails and captions (AUC 0.92–0.99 across unseen domains, 95 % accuracy after
a round trip through OCR, 2 % false positives on non-native English), and an image detector
fine-tuned on generator output from fifty model families and scored on families it never saw. The product's design problem (making a verdict
legible through a vibration, without false certainty) is a cognitive science problem, and the
haptic grammar is written down.

**Traction plan.** Ship both clients and the bots. Seed on campus and in the "is this AI?"
corners of Reddit and TikTok comments, where the question is already being asked daily. Three
numbers for the first raise: checks per user per week, 30-day retention, index growth. One
pilot conversation with an OEM or antivirus vendor in parallel.

**Risks we say out loud.** Accuracy decays (we're the aggregator and the index, not the model).
Consumers won't pay (we're not asking them to). Apple may change what Shortcuts can do (the share
sheet and the bots don't depend on it). False positives will annoy people (every verdict carries
evidence and a distinct "can't tell" buzz).

**Ask.** Pre-seed to put two engineers and a designer on it for twelve months, run the usage test
at a few thousand users, and land the first distribution partner.
