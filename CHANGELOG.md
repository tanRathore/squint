# changelog

## 0.2.0

Measured before shipped. Every model change in this release came with the experiment that said
whether it was worth doing; the ones that lost are in `docs/research_notes.md` next to the ones
that won.

Models
- Screen model v2: sixteen app layouts (adds X, Reddit, Telegram, news, TikTok with comments,
  Pinterest-style grids, landscape/tablet). 0.946 mean IoU and 98.0 % of boxes over 0.75 on
  fresh screens; v1 scored 0.897 / 85.0 % on the same screens. A leave-template-out run first
  showed where an unseen layout costs nothing (Reddit) and where it costs a third of the boxes
  (Telegram). Grids are labelled "none": a masonry page has no single media to check.
- Text model v2: trained on each document clean and once through an OCR-noise simulator.
  98.7 % clean, 98.5 % at 10 % simulated noise, 95.4 % after a render-and-tesseract round trip
  (v1: 98.4 / 96.3 / 94.2); calibration error 0.039 (v1 0.057); ESL false positives unchanged.
- Detector v1: trained on the cleaned synthetic set (twenty-one repos whose example images were
  inputs rather than outputs removed; 54 families kept, video-model frames added) and scored on
  four generator families it never saw: AUC 0.859, 59 % recall, which is the number quoted from
  now on. Whole pipeline on the same split as v0: AUC 0.960 vs 0.912, 75 % vs 66 % of fakes
  flagged, 2.2 % vs 0.3 % of research-dataset photos flagged. Fitted fusion weights tied the
  hand-tuned ones under cross-validation, so none ship.
- Four alternative crop-blending rules tried and rejected with numbers.

Server
- Verdicts persist with their check row; `GET /v1/check/{id}` works after a restart and from any
  replica. Missing columns and indexes are added at boot.
- Sightings count devices, not requests; feedback is one vote per device per fingerprint, and a
  repeat press's "wrong" is read against the verdict it answers.
- Webhook URLs are vetted against private, loopback, link-local and reserved space, resolved
  again at delivery, and delivered to the vetted address with Host and SNI set; no redirects.
- Images over 80 megapixels are refused (413) or, for JPEGs, decoded at reduced size;
  undecodable files are a 415, not a traceback.
- The local detector scores three sampled frames of a video, not one.

Clients
- Tapping a recent check in either app fetches and shows the spoken line and evidence.
- Android: JVM unit tests for `PHash` (bit-for-bit against the server's hashes) and `MetaScan`,
  run in CI before the APK builds.

## 0.1.0

First complete system: Android assistant hook, iPhone App Intent and share extension, server
with fingerprint index, provenance, forensics, three bundled models, quick path, repeat-press
feedback, four languages, Telegram and WhatsApp bots, PWA share target, partner API and
webhooks, dashboard, model cards, threat model and privacy document.
