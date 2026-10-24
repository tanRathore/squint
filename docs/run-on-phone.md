# run it on your phone

Twenty minutes from clone to a buzz in your hand.

## 1. server

```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,onnx,text,heic]"
cp .env.example .env            # optional: HIVE key for real image verdicts, FACTCHECK key
squint doctor                   # tools, models, providers, a self test
squint serve                    # http://localhost:8080/dashboard
```

Your phone needs to reach it. On the same Wi-Fi, use your laptop's LAN address
(`http://192.168.x.x:8080`). From anywhere, put it behind a tunnel:

```bash
cloudflared tunnel --url http://localhost:8080     # or: ngrok http 8080
```

Set `SQUINT_SALT` to something random before anyone else's phone talks to it.

## 2. android

1. Open `android/` in Android Studio (Hedgehog or newer), let it sync, run on a device with
   Android 10+. `android:usesCleartextTraffic` is on, so a plain `http://` LAN address works
   for testing.
2. In the app: paste the server URL. Tap **Open assistant settings** → Default digital assistant
   app → squint. On the same screen turn on **Use screenshot** (wording varies by maker:
   "Use screenshot", "Allow screenshot", or under the assistant's gear icon).
3. Tap **Feel the three answers** once with the phone in your hand.
4. Open Instagram, long-press the power button on a post. Tick, then a buzz. With earbuds in,
   a sentence.
5. Press again on the same post within 45 seconds: two tiny taps, "Noted, thanks" — you just
   told the index it was wrong.

Samsung: if long-press power opens Bixby, Settings → Advanced features → Side button → Press and
hold → Power off menu, then use the Quick Settings tile ("squint") or the share sheet instead,
or set the double-press to the assistant. Pixel: Settings → System → Gestures → Press & hold
power button → Digital assistant.

Select any text anywhere → the selection toolbar has **Check with squint**.

## 3. iphone

1. Open `ios/README.md`; create the Xcode project with the three targets, set the App Group
   `group.app.squint`, deployment target iOS 17, run on a device (haptics don't exist in the
   simulator).
2. In the app, set the server URL. Tap **Feel the three answers**.
3. Shortcuts → new shortcut → **Take Screenshot** → **Check with squint** (image = Screenshot).
   Name it "Squint the screen".
4. Settings → Action Button → Shortcut → Squint the screen. Or Accessibility → Touch → Back Tap →
   Double Tap → Squint the screen.
5. Open anything, press the Action Button. Tick, buzz, sentence.

The share sheet works everywhere without the shortcut: any image, reel or voice note → **Check
with squint**.

## 4. bots

```bash
SQUINT_TELEGRAM_TOKEN=123:abc squint bot
```

Message the bot a photo. The verdict comes back with right / AI / human buttons.

## what you should see on the dashboard

Every press adds a fingerprint. Press the same post from two phones and the second answer says
"seen 2 times". Press five times and the quick path answers alone in 50 ms. Upload a Midjourney
PNG and it says so from the metadata; screenshot it and upload the screenshot and it still knows,
from the index.
