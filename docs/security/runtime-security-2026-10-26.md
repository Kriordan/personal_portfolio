# October 2026 runtime security update

The portfolio now selects Node 24.22.1 for local work, CI, and every Expo EAS
build profile, and Python 3.13.18 for the backend and CI. The existing
certifi 2026.10.19 fix is retained with an explicit minimum requirement.
No locked dependency version or integrity hash changes.

Node installs require `>=24.22.1 <25`. npm scripts invoke the runtime guard
directly because this repository disables lifecycle hooks with
`ignore-scripts=true`; a preinstall/pretest hook alone would not enforce it.
`.nvmrc` is the CI source of truth, while EAS requires its own explicit
`node` value. Normal npm commands reject the old Node executable even with
existing node_modules.

## Existing work preserved

- Reused the already-installed Node 24.22.1 from the Pocketroads remediation.
  Pocketroads and Theglades files, runtime installations, and deployments were
  not changed. The shared nvm default remains unchanged.
- Worked in an isolated worktree and rebased onto the merged monitoring work
  at `0c177bd`. Its dependency additions, preview auto-increment, monitoring
  configuration, and application behavior are retained.
- Python 3.13.18 was compiled from the official release with the checksum in
  pyenv's published build definition, under /tmp for testing, then installed
  alongside the existing pyenv versions using the same verified source download.
  Shared defaults and other projects' Python environments were not modified.

## Validation

- Clean locked npm installs with lifecycle scripts disabled.
- Old Node 24.14.0 rejected by installation and test commands in both npm projects.
- 13 root Node tests and CDN integrity checks pass; Sass compiles.
- Browser checks pass: 18 sanitizer checks and nine extraction DOM checks.
- 104 mobile tests, dependency compatibility, TypeScript, ESLint, and
  iOS/Android/web JavaScript exports pass on Node 24.22.1.
- EAS's own schema/profile resolver confirms Node 24.22.1 for all three profiles
  on both iOS and Android. No cloud native build or OTA publication was needed
  for this build-runtime configuration change; future builds must verify the
  selected Node version in their logs.
- Python 3.13.18: Poetry lock validation, dependency consistency, and the full
  backend suite pass (259 tests; one Linux-only parent-death check skipped on
  macOS). PostgreSQL integration tests ran against an isolated UTF-8 PostgreSQL
  18 cluster, which was stopped and removed afterward.
- Python pip-audit reports no known vulnerabilities. Both npm audit gates pass
  with the same three documented mobile exceptions and November 5 review date.
  Runtime fixes do not resolve those separate dependency advisories.
- The offline certificate regression checks the actual CA bundles used by
  Requests, httplib2, and Botocore for the removed emSign G3 root fingerprint.
- All 12 anonymous TLS checks pass on the isolated Python 3.13.18 environment.

## Deployed release check

**October 27 update:** the runtime update is deployed. Heroku v160, source/release `5f1e887`, reports Python **3.13.18** and retains enabled production Sentry. The [deployment record](../assets/recovery-validation-2026-10-27/html-error-status-deployment.json) verifies that version and live HTTP smoke checks. The older v154 probe below remains evidence for its original release; a retained result of all 12 TLS trust checks on the newer runtime is still needed before closing that narrower follow-up. See the [current validation ledger](../validation-status.md).

A short-lived Heroku dyno using the current deployed release (v154, application
source `d12dccca`) reported Python 3.13.11 and certifi 2026.10.19 on October 26.
The app has only the Python buildpack; it does not serve requests through Node.
The probe did not load the application, access its database, send email, or
change configuration.

The system SSL context, Requests, httplib2 (Google), and Botocore (AWS) each
accepted the normal Python.org HTTPS control and rejected both compromised
certificate test endpoints listed in Render's advisory: all 12 checks passed.
This confirms those deployed trust paths, not the newer Python runtime update.

The live homepage and login returned 200; anonymous requests to the protected
current-user and lists APIs returned 401. No authenticated data was read.

Python 3.13.18 deployment/version verification is now complete. To record the
remaining deployed trust-path check on that runtime, verify the release and run:

```sh
heroku run --app keithriordan --no-tty --exit-code -- \
  python -B scripts/check-tls-trust.py
```

Require Python 3.13.18, certifi >=2026.10.19, and all 12 passes. Inconclusive
network errors fail the probe. The read-only site/API smoke checks passed on
v160; do not treat the earlier v154 TLS results as a new-runtime rerun.

For local development, select Node with `nvm use`. Install/select Python 3.13.18
with the local Python manager, point Poetry at that interpreter, and run
`poetry sync`; an existing Poetry environment does not change interpreters
merely because `.python-version` changed.

## Sources

- [Node October 21 security release](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)
- [Render certificate advisory and test endpoints](https://render.com/docs/advisory-emudhra)
- [Python 3.13.18 security release](https://www.python.org/downloads/release/python-31318/)
- [Heroku runtime availability](https://devcenter.heroku.com/changelog)
- [EAS Node configuration](https://docs.expo.dev/eas/json/)
