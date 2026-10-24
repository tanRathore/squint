# squint for iPhone

Three targets, one Xcode project (create it with File → New → Project → App, then add the two
extension targets and drop these sources in):

| target        | what it is                                              | files                                |
|---------------|---------------------------------------------------------|--------------------------------------|
| `Squint`      | the app: settings screen + App Intents                  | `Squint/*.swift`                     |
| `SquintShare` | share extension, "Check with squint" in any share sheet | `SquintShare/*`                      |
| `SquintWatch` | ReplayKit broadcast extension, watches a video you play | `SquintWatch/SampleHandler.swift`    |

Settings:

- App Group `group.app.squint` on all three targets (shared UserDefaults for server + device id).
- Add `Settings.swift`, `Verdict.swift`, `SquintClient.swift`, `Haptics.swift`, `Whisper.swift`,
  `Earcons.swift`, `MetaScan.swift`, `Offline.swift` and the `Deliver` enum from `Intents.swift`
  to the extension targets too (target membership).
- Deployment target iOS 17 (App Intents with `IntentFile`, `onChange(of:)` two-arg form).
- The app target needs no special entitlements. Speech and haptics work from intents without the
  app opening (`openAppWhenRun = false`).

What the client does on a press: ack tick → `/v1/quick` (index + provenance, ~50 ms; if the
index already knows, that's the answer) → `/v1/check` (full detectors) → buzz + whisper. A second
press on the same screen within 45 s files "wrong" with no UI. If the server is unreachable, the
file's own metadata is scanned on the phone and the whisper says so.

What runs where:

- **Action Button / Back Tap** → Shortcut (`Shortcuts/README.md`) → `CheckImageIntent` → buzz + whisper.
- **Share sheet** → `ShareViewController` → same client, same buzz.
- **Screenshot → visual intelligence (iOS 26)** → `VisualIntelligence.swift` registers an
  `IntentValueQuery`, so after any screenshot the visual-intelligence panel can hand the pixels
  to squint with one tap; the verdict buzzes and whispers and shows as an entity. Compiled only
  when the Visual Intelligence framework is present (Xcode 26+), guarded by `#if canImport`.
- **Watch mode** → start a broadcast from Control Center while a video plays. Every ~8 s a frame
  goes through the server with `trigger=watch`. A broadcast extension can't post notifications
  itself, so the alert comes back as a time-sensitive push from the server (APNs settings in
  `server/.env.example`, `pip install -e ".[push]"`). The app registers the token on first launch
  and needs the Push Notifications + Time Sensitive Notifications capabilities.

Nothing here keeps the screenshot. The server keeps a perceptual hash and a verdict, that's it.
