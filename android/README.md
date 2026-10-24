# squint for android

Open this folder in Android Studio, run on a device with Android 10+. `docs/run-on-phone.md`
has the setup steps (default assistant, screenshot permission, the haptic tutorial).

What's in the box:

- `SquintInteractionService` / `SquintSession`: the digital-assistant hook. Long-press power →
  the OS hands us the screenshot and the view tree → crop → `/v1/quick` → `/v1/check` → buzz.
- `device/`: on-device pieces. `ScreenModel` (bundled `assets/screen.onnx`) finds the media when
  the view tree gives no hint; `MetaScan` reads generator metadata and content credentials;
  `PHash` + `VerdictCache` answer repeat presses instantly; `Offline` builds a verdict with no
  network and says so.
- `LocalScorer`: runs the image detector on the phone if you drop `research/runs/detector/
  squint.onnx` into `app/src/main/assets/squint.onnx` (16 MB, not committed). Its score rides
  along to the server as `local_p` and powers offline verdicts.
- `Haptics`, `Earcons`, `Whisper`: the three output channels. Patterns come from the server.
- `ShareActivity`: share sheet and text-selection toolbar entry. `QuickTile`: Quick Settings.
- `SetupActivity`: live setup checks, haptic tutorial, privacy switches, recent checks with a
  "wrong" button.

Strings in English, Spanish, Portuguese and Hindi.

`gradle testDebugUnitTest` runs the JVM tests: `PHash` is checked bit-for-bit against the
server's hashes on fixed 32×32 grids (so a phone and the index agree on what "same image" means),
and `MetaScan` against hand-built PNG/JPEG byte streams. CI runs them before building the APK.
