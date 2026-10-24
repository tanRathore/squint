# demo script

Three minutes, no slides until the end.

**0:00** Phone in hand, Instagram open on a reel that looks slightly off. "I'm not going to open
anything." Long-press power. The phone gives a tiny tick (acknowledged), then one long buzz.
Earbud: *"Likely AI. Seen 2,300 times since Tuesday."* Keep scrolling.

**0:30** Gmail. An urgent email from "your bank". Long-press power. Three quick taps. Earbud:
*"Can't tell if it's machine written. It does read like a scam message."* "It won't guess, and it
still told me the thing that matters."

**1:00** Photos app. A real photo you took this morning. Share → Check with squint. Two short
buzzes. *"Nothing here points to AI."* If the phone saved content credentials: short then long,
*"Camera verified by content credentials."*

**1:30** iPhone. Same reel in WhatsApp. Double-tap the back of the phone. Same long buzz, same
line. "Two platforms, one index: it already knew."

**2:00** Laptop. `/dashboard`: fingerprints indexed, zero images stored, the verdict distribution,
where checks come from. Drop a Midjourney PNG on it: "Likely AI-made, metadata names midjourney."
Drop the screenshot of the same image: still likely, now via the index. "Metadata dies on the
first screenshot. The index doesn't."

**2:30** Telegram. Forward a voice note to the bot. It comes back in a second with the verdict
and "seen before" if it has. "That's the billion-people version. No app."

**2:50** One slide: the index growth curve from the test group, checks per user per week,
retention. Then the ask.

## setup checklist

- server running with at least one image provider key (Hive is the easiest to get)
- `SQUINT_FACTCHECK_KEY` set so a debunked viral image shows a publisher name
- pre-seed the index: run the reel and the Midjourney image through once from another device so
  "seen before" fires live
- Android: squint set as assistant, "use screenshot" on, earbuds paired, speak on
- iPhone: shortcut on Back Tap, speak on
- Telegram bot running (`squint bot`)
- airplane mode off, obviously
