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
  pyenv's published build definition, under /tmp for testing. Other projects'
  Python environments were not modified.

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

A short-lived Heroku dyno using the current deployed release (v154, application
source `d12dccca`) reported Python 3.13.11 and certifi 2026.10.19 on October 26.
The app has only the Python buildpack; it does not serve requests through Node.
The probe did not load the application, access its database, send email, or
change configuration.

The system SSL context, Requests, httplib2 (Google), and Botocore (AWS) each
accepted the normal Python.org HTTPS control and rejected both compromised
certificate test endpoints listed in Render's advisory: all 12 checks passed.
This confirms those deployed trust paths, not the newer Python runtime update.

Python 3.13.18 still requires a rebuild/deployment. Heroku and GitHub Actions
publish this version. After deployment, verify the release revision and run:

```sh
heroku run --app keithriordan --no-tty --exit-code -- \
  python -B scripts/check-tls-trust.py
```

Require Python 3.13.18, certifi >=2026.10.19, and all 12 passes. Inconclusive
network errors fail the probe. Then perform the existing read-only site/API
smoke checks. A redeployment and its resulting runtime have not yet been
verified by this change.

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
