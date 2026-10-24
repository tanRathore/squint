# squint the screen (iPhone shortcut)

The iPhone has no equivalent of Android's assistant screenshot hook, so the invisible trigger
is a Shortcut. The app ships an App Intent called **Check with squint**; the shortcut takes the
screenshot and hands it over. Assign it to the Action Button or Back Tap and the whole thing is:
press, buzz.

## Build it once in the Shortcuts app

1. New shortcut, name it `Squint the screen`.
2. Add **Take Screenshot**.
3. Add **Check with squint** (from the squint app). Image = Screenshot.
4. Optional: **Show Result** off, keep **Speak** off (the intent already whispers).

The intent itself vibrates with the verdict pattern and speaks the one-line result at low volume,
so the shortcut needs nothing else. It never shows a screen.

## Hook it to a button you already have

- Settings → Action Button → Shortcut → `Squint the screen` (iPhone 15 Pro and later)
- Settings → Accessibility → Touch → Back Tap → Double Tap → `Squint the screen` (any iPhone 8+)
- Or long-press the screenshot thumbnail → Share → **Check with squint**

## Without the app installed (pure Shortcut)

If you only want to try the server, this version calls the API directly:

1. **Take Screenshot**
2. **Get Contents of URL**
   - URL: `https://YOUR-SERVER/v1/check`
   - Method: POST, Request Body: Form
   - `file` = Screenshot (File), `trigger` = `back_tap`, `source_app` = `shortcut`
   - Header `X-Device` = any random string you keep stable
3. **Get Dictionary Value** `tier` from Contents of URL
4. **If** tier is `likely_synthetic` → **Vibrate Device** (once)
   **Otherwise If** tier is `unclear` → Vibrate, Vibrate, Vibrate
   **Otherwise** → Vibrate, Vibrate
5. **Get Dictionary Value** `say` → **Speak Text** (rate 1.05, volume low)

The Vibrate action only does one fixed buzz, which is why the app's Core Haptics patterns are
nicer. The logic is the same.

## Audio and video

Share a reel or voice note from any app → **Check with squint**. The share extension fingerprints
the clip and the server matches it against everything it has heard before.
