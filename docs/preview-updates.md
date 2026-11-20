# iPhone preview updates

**Current standalone preview:** [iPhone preview 1.0.0 (15)](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/ca355617-b873-443d-a246-328086d973c4).
Released November 20 from `a8b7499`, it adds Learning responses and focused recall
while retaining the Lotto/Home changes, interval timer, and native update client.
See the [release record](engineering-learning-milestone-2.md#approved-2d-release--november-20).
Install this build for 2d; no OTA was published for that checkpoint.
**Latest preview update:** [Lotto and compact Home — November 19](https://expo.dev/accounts/kriordan/projects/personal-portfolio/updates/de7f5743-ce1e-4e7a-9b31-c74907a72409),
published from `7cf2b5e` on `preview` for iOS. It combines the lottery tools, starts
scratch-off listings with three choices, simplifies Home to one upcoming drawing
and one latest result across both games, adds the Monday popup, and removes
“Ready for your next shop.” It matches build 14's native runtime; no new native
installation is required for that Lotto update. Build 15 already includes it.
Backend deployment, live drawing-data refresh, runtime
compatibility, and Sentry source-map upload passed. See the
[release record](scratch-offs.md#november-19-lotto-and-home-preview).

EAS Update is configured for the `preview` build profile and channel. The manual
workflow in `mobile/.eas/workflows/preview-update.yml` publishes only iOS. Existing
builds through version 1.0.0 (12) do not contain expo-updates and cannot receive an
update that installs it; an update-enabled native preview must be installed once.

## Delivery and compatibility

The app starts immediately from its cached or embedded bundle, checks at launch,
and downloads a compatible update in the background. A downloaded update runs on
the next restart. No application code invokes `reloadAsync`, so an update cannot
interrupt an active interval workout. Keep the embedded bundle and Expo's default
error recovery enabled. Offline startup continues to use the available bundle.

The runtime uses Expo's `fingerprint` policy. Native dependencies, local Swift
modules, config plugins, permissions, and other native configuration remain in the
hash. `fingerprint.config.js` excludes version/build counters and the `extra`
section, which currently contains only EAS project metadata and the JavaScript
monitoring commit. Those values must not force a native rebuild for every commit.
If a future plugin consumes `extra` to configure native behavior, revisit this
exclusion before releasing it.

The publication hook computes the managed iOS fingerprint and requires a finished
internal iPhone preview on the `preview` channel with that runtime. It fails with
an actionable message if a fresh native build is needed. It does not create a
build automatically. Development and production profiles keep updates disabled;
there are no push-triggered publication jobs.

## Environment and monitoring

The Expo project `kriordan/personal-portfolio` uses its existing `preview`
environment. `APP_VARIANT=preview` and
`EXPO_PUBLIC_API_URL=https://keithriordan.herokuapp.com` are plain-text project
variables. This avoids relying on `eas.json` build-only variables or a developer's
local `.env` when publishing. The existing Sentry DSN, enable flag, environment,
organization, project, and secret upload token are reused.

The workflow runs on Node 24.22.1 with `upload_sentry_sourcemaps: true`; a failed
symbol upload fails the job. The upload token stays on Expo. Do not use a bare
local `eas update` as the normal release command: it cannot read the secret upload
token. Sentry retains errors-only reporting and the existing privacy scrubber.
Only a validated update UUID and an `embedded`/`ota` source tag are added, so errors
can be associated with the active JavaScript update.

## Publish

Run the normal mobile tests, lint, TypeScript, dependency compatibility, audit,
and export checks after a change. From `mobile/`:

```sh
npx eas-cli workflow:run .eas/workflows/preview-update.yml --input 'message=Describe the tested change' --wait
```

This uploads the current local working tree. It does not require committing or
pushing first. Check that the update and Sentry upload both succeeded. On the
iPhone, launch while online, allow the download to finish, then close and reopen
the app. Do this between workouts. The update remains available offline after it
has downloaded. Native changes still use the existing preview build command.

The workflow uses a small amount of separately billed Linux workflow time; it
does not spend an iOS cloud build credit. Update downloads use the plan's MAU and
bandwidth allowances. A new native build still incurs the usual build charge.

## Recovery

For a faulty published update, target the affected runtime explicitly:

```sh
npx eas-cli update:roll-back-to-embedded --channel preview --platform ios --runtime-version RUNTIME_HASH --message 'Restore the installed preview bundle' --non-interactive
```

Get `RUNTIME_HASH` from the affected build/update details. This publishes a rollback
directive for that runtime; devices need connectivity to receive it. Alternatively,
use `eas update:republish` to restore a known good update. A failed workflow may
already have published the update before its Sentry upload failed: inspect the
update group and restore or repair it rather than assuming nothing was published.

## Validation

The dated preview/build evidence below was collected on the broader Learning
branch. [PR #149](https://github.com/Kriordan/personal_portfolio/pull/149) isolates
the interval timer, security fixes, and update setup on `main`; its mobile suite
has 146 tests. The published previews are not exact builds of that focused PR.

- 196 mobile tests pass, including preview environment parity, rejected local API
  origins during publication, production/development isolation, and bounded Sentry
  update tags.
- ESLint, TypeScript, Expo dependency compatibility, both audit gates with zero
  findings/exceptions, and all-platform exports pass.
- In an isolated source copy, changing JavaScript, the monitoring commit, and the
  iOS build number preserved the runtime hash; changing the interval module's
  Swift source changed it.
- Expo's server validates the workflow configuration.
- Build 13 finished November 14 at 4:15 p.m. Eastern. Its IPA passes strict/deep
  signature verification and includes the registered iPhone, native interval
  module, background audio, production API, and `preview` update channel. The
  native runtime is `77b0440fdf8c270adcb7939e8c162f453f8e5ad4`.
- The [publication workflow](https://expo.dev/accounts/kriordan/projects/personal-portfolio/workflows/01a1dbee-ad4d-7346-958a-b8501011b5cd)
  passed the matching-build guard, published iOS update
  `01a1dbf0-391e-7ad2-b155-f56be07607f2`, and completed the required Sentry upload.
  A first attempt stopped before publication because its hook assumed a global
  EAS CLI; the hook now invokes pinned CLI 27.10.0 through npx. No second native
  build was necessary.
- An isolated iPhone 18 Pro / iOS 27 Release simulator host used the same native
  runtime. Its update database recorded two successful embedded launches while
  the published update downloaded and remained ready with zero launches. After
  restarting, the published update recorded one successful launch and zero failed
  launches. This verifies download and activation without a forced reload.
- The local simulator host skipped Sentry symbol upload only for its local build;
  the distributed IPA and published update both completed their Sentry uploads.
  Their debug ID matches the Hermes bundle. Physical iPhone installation and
  workout acceptance remain pending. [Verification receipt](assets/preview-updates-2026-11-14.json).

References: [Expo 57 updates](https://docs.expo.dev/versions/v57.0.0/sdk/updates/),
[workflow update jobs](https://docs.expo.dev/eas/workflows/pre-packaged-jobs/#update),
[Sentry and updates](https://docs.expo.dev/guides/using-sentry/#usage-with-expo-update).
