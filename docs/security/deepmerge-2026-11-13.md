# Dependency security follow-up — November 13, 2026

The user requested fixing the expired deepmerge audit issue and rerunning the
checks. Expo config 57.0.11 replaces the vulnerable dependency with its upstream
merge helper. No local deepmerge fork or extended audit exception is needed.

## Remediation

The [deepmerge advisory](https://github.com/advisories/GHSA-gcqx-w48m-w2h4)
still lists no patched deepmerge release. npm also reports 4.3.1 as latest.
Updating its consumer, `@expo/config` from 57.0.9 to 57.0.11, removes it entirely.
The upstream helper excludes `__proto__` from both target and source keys,
including recursively cloned arrays and config-plugin options.

A regression using Expo's real `modifyConfigAsync` API failed on the old
dependency: a nested null placeholder acquired an attacker-controlled returned
prototype. It passes after the update, along with target-key, primitive,
array-element, and plugin-option cases. Ordinary nested config and plugin
merges also pass. Tests reject a reintroduced deepmerge dependency in the lockfile.
The audit gate itself is unchanged; both exception lists are empty.

Fresh registry scans also found additional advisories. The dependency changes
resolve these as part of making the audit checks pass:

| Dependency | Resolution |
| --- | --- |
| glob | Expo 57 CLI/config/plugin/Metro patches use 14.0.6, covering [cancellation bypass](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4). |
| minimatch | 11.0.8 fixes [pattern amplification](https://github.com/advisories/GHSA-g3hv-75wg-m249). Two scoped overrides cover fingerprint and TypeScript parser consumers that still request 10.x. Legacy ESLint consumers retain their unaffected 3.1.5 API. |
| node-forge | Existing pin moves from 1.4.2 to 1.4.3, covering the [upstream security fixes](https://github.com/digitalbazaar/forge/blob/main/CHANGELOG.md#143---2026-11-03). |
| follow-redirects | Root development dependency moves from 1.16.1 to 1.16.3, covering [cross-realm sensitive header leakage](https://github.com/advisories/GHSA-mrwp-f3q8-3g9p). |

Expo remains 57.0.25 and React Native remains 0.86.3. The toolchain update also
selects compatible transitive patches, including expo-constants 57.0.24 and
autolinking 57.0.18. Expo CLI 57.0.34 removes its Zod 3 dependency in favor of JSON
Schema; the retired local Zod adapter is deleted and its tests now exercise the
new upstream API. Xcode 4.0.0 removes the need for the UUID override. The URL
decoder compatibility package and fixed Zod 4 lint dependency remain.

## Validation

- Clean `npm ci --ignore-scripts` installations pass in both npm projects.
- Root and mobile audit gates pass with zero findings and zero exceptions.
- The full mobile suite passes (165 tests at this run), including the new config-poisoning regression,
  normal config/plugin merging, fixed Ed25519 verification, fingerprint ignore
  behavior, and bounded matcher execution. Root runtime/audit-policy/browserless
  tests (13 tests) and CDN integrity checks pass.
- TypeScript and Expo dependency compatibility checks pass. Local
  generated route declarations were refreshed as concurrent Learning screen
  edits added routes; no Learning feature source was modified for this fix.
- The November 13 lint run found two `react-hooks/set-state-in-effect` errors
  in the concurrently added Discuss screen. The subsequent Learning changes
  resolved them; the November 14 verification below closes this blocker.
- Android/iOS JavaScript exports and web static rendering pass (32 routes).
- Native interval audio checks pass, including actual speech, encoded cue
  placement, cancellation, and the exact 34-minute workout duration.
- iOS project generation, CocoaPods installation, and the signed simulator
  native build pass with the updated tooling. The app retains the local
  IntervalTimer module and audio background mode. Generated iOS files remain
  ignored. This is build validation, not another physical-device acceptance run.

Preview 8 was built before this update. This follow-up does not publish a new
cloud build, deploy a backend, or close the outstanding physical iPhone and
accessibility acceptance items in the [interval timer record](../interval-timer.md).

## Lint follow-up — November 14, 2026

Both reported effects were already removed by the newer Learning implementation
when this follow-up began. Discuss reads pending message text or the subscribed
draft store directly. A confirmed send clears only the matching stored draft;
existing regressions cover recovery, storage failures, and preserving newer edits.
No additional application source change or lint suppression was necessary.

Refreshed the local generated route declarations for the existing Build screen,
then reran the checks:

- Full mobile ESLint and TypeScript pass.
- All 192 mobile tests and 13 root tests pass, along with CDN integrity checks.
- Expo dependency compatibility checks pass.
- Both security audit gates pass with zero findings and zero exceptions.
- iOS/Android exports and web static rendering pass (36 routes).
- Native interval audio checks pass, including real speech synthesis and the
  complete 34-minute encoded workout.
- `git diff --check` passes. The previous native simulator build result remains
  above; this lint follow-up did not require a new native or cloud build.

## Updated iPhone preview — November 14, 2026

The user subsequently requested a new installable preview. [Version 1.0.0 (12)](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/28622d1b-c763-4fc6-bd87-ee35638538e7)
finished at 9:40 a.m. Eastern and includes this remediation, the interval timer,
and the current Learning implementation. The source archive contains the patched
lockfile with no deepmerge package. The signed IPA, registered-device profile,
native timer, background audio, production API, and matching Sentry upload debug
ID were verified. [Artifact receipt](../assets/interval-preview-2026-11-14.json).

Cloud Expo Doctor passed 20 of 21 checks; its remaining recommendation is to
update 11 packages to newer SDK 57 patches. This is separate from the resolved
audit findings. The validated dependency set was retained, and the native build
succeeded. Physical iPhone playback and accessibility acceptance remain pending.

## PR audit follow-up — November 14, 2026

The fresh backend audit on [PR #149](https://github.com/Kriordan/personal_portfolio/pull/149)
reported six advisories in the existing Python lockfile. Apply the audited patch
releases and enforce their minimum versions in `pyproject.toml`:

- [dnspython 2.9.2](https://pypi.org/project/dnspython/2.9.2/) fixes CVE-2026-128089.
- [oauthlib 4.0.1](https://pypi.org/project/oauthlib/4.0.1/) fixes CVE-2026-49272.
- [pyasn1 0.6.5](https://pypi.org/project/pyasn1/0.6.5/) fixes CVE-2026-119194,
  CVE-2026-119195, CVE-2026-119196, and CVE-2026-119197.

Only these three resolved Python package versions changed. A fresh Python 3.13.18
installation passes the lockfile check, `pip check`, and `pip-audit` with no known
vulnerabilities. The GitHub audit gate remains unchanged. This updates the PR's
source dependencies; it does not deploy the backend or alter an installed preview.
