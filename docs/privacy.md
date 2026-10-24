# privacy

The product only works if people are willing to press the button on anything, including their
own messages. So the rules are strict and simple.

## what the phone sends

Only when you press. Never in the background. The assistant screenshot hook on Android and the
Shortcut on iPhone are both user-initiated by the operating system's own rules; there is no
accessibility-service scraping and no screen recording service running.

By default the Android client crops to the media view it found before uploading, so the server
sees the photo, not your chat around it. You can turn that off if you want the context analysed.
On-screen text is sent only if the "include on-screen text" switch is on (default on, because
emails are a core use case). The iPhone Shortcut sends the full screenshot because Shortcuts
can't crop by view; the server crops.

Every request carries `X-Device`, a random UUID generated on the phone. There is a button to
rotate it. It is never tied to an account, a phone number or an ad id.

## what the server keeps

| kept                                                                       | not kept                       |
|----------------------------------------------------------------------------|--------------------------------|
| perceptual hash (64 bits) of the media region                              | the screenshot                 |
| up to 8 frame hashes for video, landmark hashes for audio                  | the video or audio             |
| sha256 of normalised text                                                  | the text                       |
| verdict, probability, which signals fired and their scores, the spoken line | provider raw responses         |
| source app package name, trigger type                                      | your account in that app       |
| sha256(salt + device id), truncated                                        | the device id itself, IP, UA   |
| timestamp of the check                                                     | location                       |
| fact-check publisher, rating, url for matched claims                       |                                |

`checks` rows are purged after `SQUINT_RETENTION_DAYS` (default 30). Each one carries the
verdict as served (`GET /v1/check/{id}`) so the phone can show the evidence later without the
media; the verdict is built from the signals above and names nothing that isn't in this table.
`items` (the fingerprints) are the product and are kept; they can't be turned back into the media.

`SQUINT_KEEP_MEDIA` exists for running evaluation on your own labelled set. It is false by
default and the production compose file does not set it.

## what leaves the server

The three bundled models (screen, text, detector) run in-process; ONNX Runtime's telemetry is
switched off explicitly. If you configure external detector providers, the cropped media is sent to them. That is the one place
pixels leave our process, and it is disclosed in the app. We send no identifiers to providers.
With no providers configured nothing leaves.

Fact-check lookups send the OCR'd caption text to Google's Fact Check Tools API. Same disclosure.

## what the user can do

- rotate the anonymous id at any time
- tap "wrong" on a recent check, which stores a label against the hash, nothing else
- turn off speech, turn off on-screen text, turn off cropping
- not press the button

## what we will never do

Sell the index per-user, correlate device ids across apps, store media "temporarily", or
ship an always-on mode. If a future version wants any of these, it needs a new document and a
new consent screen, not a config flag.
