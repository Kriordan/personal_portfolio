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

## Deployment verification

**October 27 update:** Heroku **v162**, source/release `96b909f`, reports Python **3.13.18**, certifi **2026.10.19**, dnspython **2.9.0** and enabled production Sentry. All **12 TLS trust checks** passed on that release: system SSL, Requests, httplib2 and Botocore each accepted the control and rejected both compromised-certificate endpoints. The [retained deployment record](../assets/recovery-validation-2026-10-27/pr131-deployment.json) includes every result and live HTTP smoke checks, closing the newer-runtime trust follow-up. The older v154 probe below remains historical evidence. See the [current validation ledger](../validation-status.md).

### Initial coordinated rollout

[PR #129](https://github.com/Kriordan/personal_portfolio/pull/129) merged as
`12558b2f0074f02ebaa48c8b9ce5a588e911e812`. The user approved the merge and
coordinated rollout. Production already included the separate lottery branch,
so the security merge was integrated onto its tip `19ccf7b`, retaining its
release notes and every application, migration, and native source file.
The combined commit is `8754d28a37a8ca52a82647f75ac97f74c8131ab8` and is retained
on `feature/scratch-off-picks` for future work. Its draft PR #128 remains open.

The combined source passed 284 backend tests (283 passed and one Linux-only
skip on macOS), including the isolated PostgreSQL suite, 107 mobile tests,
TypeScript, lint, and the root web checks. All seven GitHub checks passed on
that exact commit, including mobile exports and CodeQL; its open code-scanning
alert list was empty.

Heroku **v156**, released **2026-10-27 at 03:28:02 UTC** (October 26 at 11:28 p.m.
EDT), runs that combined commit. The build discarded the old Python cache and
installed **Python 3.13.18** with the existing locked **certifi 2026.10.19**.
The app still has only the Python buildpack; it does not serve requests through
Node. A fresh dyno running the deployed probe confirmed both package versions
and that httplib2 and Botocore use certifi's bundle.

All **12 deployed TLS checks passed**: the system SSL context, Requests,
httplib2 (Google), and Botocore (AWS) each accepted the Python.org HTTPS control
and rejected both compromised certificate test endpoints in Render's advisory.
The TLS probe did not import the application or access its database.

Live homepage/login checks returned 200, and anonymous current-user, lists,
scratch-offs, and draw APIs returned 401. A separate read-only check confirmed
the authenticated private Home card, saved rankings and details for 32 NY and
22 CT games, draw responses, and existing migration `a4b5c6d7e8f9`. It made zero
lottery-source HTTP requests. No data import, configuration change, or Scheduler
change was performed. The existing 13:00 UTC schedule and its separately
queued first-run verification remain with the lottery task.

Earlier v154 and v155 probes already rejected the compromised certificates
using certifi 2026.10.19, but still ran Python 3.13.11. The v156 probe verifies
the additional Python runtime update is now deployed.

### Repeating the verification

To repeat the deployed trust check:

```sh
heroku run --app keithriordan --no-tty --exit-code -- \
  python -B scripts/check-tls-trust.py
```

Require Python 3.13.18 or a later supported security patch,
certifi >=2026.10.19, and all 12 passes. Inconclusive network errors fail the
probe. Then perform the existing read-only site/API smoke checks.

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
