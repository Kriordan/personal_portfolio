# iPhone interval timer

**Latest iPhone preview:** [install version 1.0.0 (13)](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/df923f54-6209-4350-906a-5ef4c2eea9b5) in Safari on the registered iPhone. This November 14 build includes the timer, dependency security fixes, resolved lint errors, current Learning screens, and [preview updates](preview-updates.md). Open **Tools → Intervals** after installation.

Open **Tools → Intervals**. The first saved workout is Warm-up 5:00, Jog 2:00 / Walk 1:00 repeated eight times, then Cool down 5:00: 18 intervals, exactly 34 minutes. Workouts and cue volume live on this device and remain after sign-out. Sign-in uses the existing app session; no account-profile request is needed to read or play a workout offline.

Create named timed intervals and one-level repeat groups. Use a block's menu to edit, duplicate, move, or delete it. A workout supports up to 500 expanded intervals and four hours; the library supports 100 workouts. Changes save explicitly; failed saves retain the editor. The library is versioned JSON in Application Support, written serially and atomically. Corrupt or newer-format data is never replaced with the example. Deleting all workouts does not reseed it.

Start prepares audio before the clock begins. The first interval is announced immediately; subsequent names are spoken three seconds before their boundary, with a tone at the change. Overlong speech falls back to a tone; steps of three seconds or less omit the advance warning. A final chime has a 0.35-second audio tail outside the workout duration. Music/podcasts continue at their own volume. The app does not claim their lock-screen controls or use a microphone, push notifications, AI, GPS, or a server timer.

## Native architecture

`mobile/modules/interval-timer` is an autolinked local Expo module. Swift uses `AVSpeechSynthesizer.write` for local speech, then streams cues and quiet gaps through `AVAudioFile` into one AAC/M4A program. Only the latest successful render is cached. `AVAudioPlayer.currentTime` is the authoritative workout clock. Foreground status events update the display; JavaScript timers do not schedule cues. iOS `playback` + `mixWithOthers` and the `audio` background mode allow playback while locked, including with the silent switch enabled.

Pause freezes the audio timeline. Skip seeks to the next interval boundary, preserving a paused state. Phone/audio interruptions and headphone removal pause with manual resume. Backgrounding during preparation cancels it so audio cannot unexpectedly start later. Leaving the workout screen during playback is supported. Sign-out, account invalidation, End, and cancellation stop native work; generation guards prevent a late preparation from starting playback. Force-quitting ends a run; v1 has no history or interrupted-run restoration.

The module has no Android/web implementation. Those targets omit the Tools entry and show a supported-platform message for direct links. Old iPhone binaries show an update message without breaking other tools. A native rebuild is required; Metro reloads cannot install this module. Generated `ios/` remains ignored.

## Reproducible checks

From `mobile/`, use the pinned Node runtime and run:

```sh
npm test
npm run typecheck
npm run lint
npm run test:dependencies
npm run test:interval-audio
```

The last check requires macOS/Xcode and access to system audio services. It verifies actual encoded cue positions and quiet gaps, cancellation, full 34-minute file duration, real system speech buffers, and sample conversion. It is not a physical-iPhone background acceptance test. Existing CI continues to run pure TypeScript tests and all-platform exports.

For isolated simulator UI checks, run `poetry run python scripts/interval-preview-fixture.py` from the root and start Metro with `EXPO_PUBLIC_API_URL=http://127.0.0.1:5097`. The disposable login is `intervals@example.test` / `IntervalPreview123!`. The fixture uses a temporary database and removes it on exit. A fresh simulator prevents test workouts from touching an existing app installation.

## Acceptance record

- Preview 13 adds EAS Update and supersedes preview 12. Its signature, registered iPhone, timer module, background audio, and Sentry source-map match are verified. An initial iOS update downloaded and activated after restart in an isolated Release simulator with the same native runtime; there are no forced mid-workout reloads. [Update verification](assets/preview-updates-2026-11-14.json). This does not close the physical workout checks below.
- November 14 preview 12 finished at 9:40 a.m. Eastern. The downloaded IPA passes strict/deep signature verification, includes the existing registered iPhone, embeds the production API, and contains the IntervalTimer native module with background audio enabled. The Sentry source-map upload completed for release `com.kriordan.personalportfolio@1.0.0+12`; its debug ID matches the signed Hermes bundle. [Artifact verification](assets/interval-preview-2026-11-14.json).
- The inspected upload archive matched 177 required source files, including every mobile source file, the native timer, and patched lockfile. Environment secrets, credentials, databases, generated native projects, and local editor files were excluded. EAS metadata records HEAD `9923253`; the uploaded working tree also contains the uncommitted interval and security changes. Existing signing credentials were reused without modification.
- The pre-build checks passed: 192 mobile tests, 13 root tests, CDN integrity, TypeScript, ESLint, Expo dependency compatibility, both audit gates with zero findings/exceptions, all-platform exports (36 web routes), and native interval audio checks. Cloud Expo Doctor passed 20/21 checks and recommended newer SDK 57 patches for 11 packages; the tested dependency versions were retained. The cloud native build succeeded. Physical-device and accessibility items below remain pending.
- Passed: nine model/storage/session tests, including the exact preset, limits, serialized saves, disk failure, duplicate Start, immutable running definitions, cancellation/logout races, and starting again after sound preview.
- Passed: native audio checks including actual speech synthesis, encoded cue placement, cancellation, and the complete 34-minute duration.
- Passed: full mobile suite (138 tests), TypeScript, ESLint, Expo dependency compatibility, all-platform exports, and an iOS simulator native build.
- Passed in an isolated iPhone 18 Pro / iOS 27 simulator: fixture sign-in, Tools entry, default preset rendering, start, pause, skip while paused, resume, navigation away/back, a simulated screen lock spanning the Jog → Walk transition, and confirmed End. Creating a second workout with a repeat group saved its names and durations correctly (Jog 0:08 / Walk 0:05 × 2 = 0:26).
- That 26-second circuit also ran to automatic completion, showing the correct duration and 100% progress. Simulator signing must be enabled (ad-hoc identity `-` works); an unsigned build cannot read the existing SecureStore keychain and stalls at session restoration.
- Passed after terminating the disposable API and cold-restarting the simulator app: the existing sign-in opened Tools despite failed account/network requests, both saved workouts remained, and the 26-second circuit started from local storage/audio. This verifies API-independent playback, not a physical-device airplane-mode test.
- The initial November 12 validation failed the mobile audit on the expired `deepmerge@4.3.1` exception. The November 13 [dependency follow-up](security/deepmerge-2026-11-13.md) removes deepmerge through an upstream Expo patch and clears both audit gates with zero findings and zero exceptions. Preview 8 predates these dependency changes.
- [Internal iPhone preview, version 1.0.0 (8)](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/3201a4af-e7e5-4dea-9620-a119cf229b76) finished November 12, 2026 at 10:02 p.m. Eastern. It uses the existing registered-device signing profile and production API origin. The upload archive matched the new native/route/model source and excluded environment files, credentials, databases, generated native projects, and local editor files. EAS metadata references the prior Git HEAD; the uploaded working tree contains this implementation. Later validation-note edits do not alter app code. No backend deployment or App Store/TestFlight submission was performed.
- Pending physical iPhone: full locked 34-minute run with music/podcasts, silent mode, offline cold launch with retained sign-in, Bluetooth disconnect/reconnect, calls, and return-to-app timing. Verify both music-start orders and manual resume after interruption.
- The completed preview's IPA artifact returned HTTP 200. The disposable API, Metro server, and isolated simulator were stopped after validation; existing simulator sessions were left running.
- Pending accessibility/device matrix: VoiceOver, largest Dynamic Type, a small iPhone, light/dark rendering, and low-storage preparation failure. Do not treat build success as completion of these checks.
