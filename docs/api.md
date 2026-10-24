# api

Base URL is wherever you run it. All responses are JSON. Media is never logged.

## POST /v1/check

multipart/form-data

| field         | type   | notes                                                                 |
|---------------|--------|-----------------------------------------------------------------------|
| `file`        | file   | image, video, audio or text. ≤ `SQUINT_MAX_UPLOAD_MB` (25)            |
| `source_app`  | string | package / bundle id or a label (`com.instagram.android`, `whatsapp`)  |
| `trigger`     | string | `assistant` `screenshot` `back_tap` `action_button` `quick_tile` `share` `bot` `upload` — screen triggers turn on cropping |
| `hint`        | string | `x0,y0,x1,y1` media bounds from the client's view tree, optional     |
| `screen_text` | string | visible text from the client's view tree, optional, ≤ 8000 chars     |
| `local_p`     | float  | on-device model score, optional                                       |
| `lang`        | string | `en` `es` `pt` `hi` for the spoken line; falls back to `Accept-Language` |
| `prev_check`, `prev_phash`, `prev_ts` | string | the previous verdict's id, `phash` and unix time. If the new screenshot matches it within 45 s, the server files "wrong" and answers with `feedback_recorded: true` instead of re-checking |

Header `X-Device`: a stable random id per install. Rate limited to `SQUINT_RATE_PER_MINUTE` (30).

Response:

```json
{
  "check_id": "d4b0…",
  "kind": "image",
  "tier": "likely_synthetic",
  "p": 0.93,
  "confidence": "high",
  "haptic": {"pattern": [0, 650], "amplitudes": [0, 255], "label": "one long buzz"},
  "say": "Likely AI. Hive puts it at 94% synthetic. Seen 312 times, first 3 days ago.",
  "headline": "Likely AI-made",
  "evidence": ["hive puts it at 94% synthetic, closest generator midjourney", "seen 312 times, first 3 days ago"],
  "signals": [{"name": "hive", "score": 0.94, "reliability": 0.8, "note": "…"}, …],
  "seen_before": {"sightings": 312, "first_seen": "2026-10-21T08:11:02", "apps": {"com.instagram.android": 290, "whatsapp": 22}},
  "factchecks": [{"publisher": "Reuters", "rating": "False", "url": "https://…"}],
  "region": [0, 193, 1080, 1287],
  "region_kind": "photo",
  "phash": "a4ad67d2d80b27f0",
  "lang": "en",
  "quick": false,
  "decisive": true,
  "feedback_recorded": false,
  "ms": 1840
}
```

`haptic.pattern` is a vibration waveform in ms (off, on, off, on…), `amplitudes` 0–255 aligned
to it. Play it as-is on Android with `VibrationEffect.createWaveform`; on iPhone map to Core
Haptics continuous events (see `ios/Squint/Haptics.swift`).

Tiers: `verified_capture` `no_ai_signals` `leaning_human` `unclear` `leaning_synthetic` `likely_synthetic`.

Errors: 400 empty, 413 too big (over `SQUINT_MAX_UPLOAD_MB`, or more than 80 megapixels when it
isn't a JPEG we can decode at reduced size), 415 unknown file type or undecodable image, 429 slow down.

## GET /v1/check/{check_id}

The verdict exactly as it was served, for as long as the check row lives (`SQUINT_RETENTION_DAYS`,
30 by default). Ids are random UUIDs; there is no listing endpoint. The phone uses this when a
press was answered by haptics but the user opens the app later to read the evidence; the web
client uses it after a share-sheet redirect. 404 once purged.

## POST /v1/quick

Same fields as `/v1/check` (no `screen_text`/`local_p`). Runs only the parts that take tens of
milliseconds: screen model crop, provenance scan, perceptual hash, index lookup, stored
fact-checks. Returns the same shape with `quick: true`. `decisive` is true when the answer can
stand on its own: generator metadata, camera-signed credentials, or five or more earlier checks
of the same fingerprint that agree. Clients buzz immediately on a decisive quick answer and skip
`/v1/check`; otherwise they go on to the full check. Typical latency 40–150 ms.

## POST /v1/check/text

```json
{"text": "…", "source_app": "com.google.android.gm", "lang": "es"}
```
Same response shape, `kind: "text"`.

## POST /v1/feedback

```json
{"check_id": "d4b0…", "label": "ai" | "human" | "unsure"}
```

One label per check: posting again replaces the earlier one. `unsure` is what a repeat press
sends and means "that was wrong"; the server reads it against the verdict it answers (a wrong
*likely synthetic* becomes one human vote, a wrong *leaning human* one AI vote, a wrong
*unclear* nothing). Votes feed the `history` signal only after three of them agree on a
fingerprint, and only from distinct devices.

## GET /v1/lookup?phash=&lt;16 hex&gt;&kind=image

Aggregate facts about a fingerprint you already hold: sightings, first seen, tier, generator
hint, apps, fact-checks. Nothing enumerable.

## GET /v1/stats

Counts by tier, kind and source app. Powers `/dashboard`.

## POST /v1/push/register

```json
{"token": "<apns device token hex>", "platform": "ios"}
```
With `X-Device`. Lets the server send a time-sensitive push when a `trigger=watch` check leans
synthetic (the iPhone broadcast extension can't notify on its own). Needs the APNs settings.

## partner

`POST /v1/partner/check` and `GET /v1/partner/recent` with header `X-Api-Key` from
`SQUINT_PARTNER_KEYS`. Same payload as `/v1/check`, no per-device rate limit, full signal detail.

### webhooks

`POST /v1/partner/webhooks` `{"url": "https://…", "threshold": 25}` registers a URL that
receives `{"event": "item.spreading", "item", "kind", "sightings", "tier", "p_mean",
"first_seen", "apps", "generator", "factchecks"}` the moment a fingerprint's sighting count
reaches the threshold. `GET` lists yours, `DELETE /v1/partner/webhooks/{id}` removes one. This is
how a newsroom hears about a fake while it is still spreading, without polling.

URLs must be public http(s) without credentials: anything that resolves to a loopback, private,
link-local or reserved address is refused at registration (400). At delivery time the host is
resolved again, the connection is pinned to the address that passed (Host header and TLS SNI
still carry your hostname, so certificates verify as usual), and redirects are not followed. A
hook can't be pointed at the metadata service or a sibling container, and a DNS answer that
changes between the check and the connect doesn't help either.

## no-install web client

`GET /try` is a small page that checks a picked file and answers with `navigator.vibrate` and
speech synthesis. It ships a manifest with a Web Share Target, so once installed from Chrome on
Android it appears in every app's share sheet as "squint": share a reel → the server runs the
check → the page opens already buzzing. `POST /share-target` is the endpoint the share sheet
hits; it redirects to `/try?c=<check_id>` and the page reads the verdict back from
`GET /v1/check/{check_id}` (`/v1/result/{id}` is the same route under its old name).

## ops

`GET /healthz` · `GET /metrics` (plain text counters + p50/p95 latency) · `GET /dashboard`

## bots

`GET|POST /hooks/whatsapp` is the Meta Cloud API webhook (`SQUINT_WHATSAPP_VERIFY`,
`SQUINT_WHATSAPP_TOKEN`, `SQUINT_WHATSAPP_PHONE_ID`). Telegram runs as `squint bot` with
`SQUINT_TELEGRAM_TOKEN`.
