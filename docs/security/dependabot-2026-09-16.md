# Dependency security review — September 16, 2026

Prepared on branch `dependabot-fixes-9-16-2026`. These are local changes; no alerts have been dismissed and nothing has been pushed, merged, or deployed. Existing mobile run-script and README edits were preserved.

## Result

Of the 101 open alerts retrieved from GitHub, the selected lockfiles are outside the affected version ranges for **100**. The remaining alert is **#186**, the mobile URL decoder. Counts are a comparison with the captured advisory snapshot, not a claim that GitHub has already closed the alerts.

| Area | Original alerts | Addressed by selected versions | Remaining |
| --- | ---: | ---: | ---: |
| Portfolio npm | 36 | 36 | 0 |
| Python backend | 25 | 25 | 0 |
| Mobile npm | 40 | 39 | 1 |

Fresh npm scans also found brace-expansion advisories beyond the initial snapshot. Version **1.1.18** covers those as well. Final web npm audit: **0 findings**. Final mobile npm audit: **0 high/critical, 3 moderate entries**—the decoder plus its `query-string` and `expo-router` parents, all representing the same underlying issue.

## Remaining mobile issue

- [Alert #186](https://github.com/Kriordan/personal_portfolio/security/dependabot/186): `expo-router` → `query-string@7.1.3` → `decode-uri-component@0.2.2`. Malformed percent-encoded input can cause excessive CPU usage. Treat attacker-supplied deep links as an open availability risk.
- The fixed decoder, 0.5.0, is ESM-only. The current query-string calls its CommonJS import as a function. Blindly overriding the decoder would break that contract. Published Expo Router 57 releases through 57.0.21 still depend on query-string 7.1.3.
- Keep the alert open. The next mobile change should use an upstream-compatible update or an explicitly maintained, tested compatibility adapter/backport, with malformed deep-link and native/web routing regression tests. No such mitigation is claimed in this batch.

## Important implementation choices

- DOMPurify is pinned to 3.4.13 in npm and in both learning templates. The npm browser bundle matched the official GitHub release and jsDelivr response byte-for-byte. Both script tags include a SHA-384 integrity hash and `crossorigin="anonymous"`.
- The unpatched-metadata DOMPurify alert #139 describes live DOM nodes with `IN_PLACE`. The app passes strings, without that option. The selected version is also outside its recorded affected range.
- Flask-SocketIO 5.6.1 accompanies Flask 3.1.3. This is necessary for the session API change; the existing socket tests caught the incompatibility with 5.6.0. [Maintainer changelog](https://github.com/miguelgrinberg/Flask-SocketIO/blob/v5.6.1/CHANGES.md).
- Expo-compatible `@expo/metro@56.0.2` selects the Metro 0.84.5 family. This removes `image-size` and its unused `queue` dependency. No Expo SDK, React, or React Native upgrade was made.
- The sole persistent npm override is scoped to `xcode` → `uuid@11.1.1`. This supported CommonJS release fixes the alert. Xcode only uses `v4()`; a regression script verifies identifier generation and project parse/write behavior. Remove the override when xcode adopts a fixed compatible UUID version itself.

## Supply-chain precautions

- Resolved lockfiles in temporary directories before installing. Reviewed changed package identities, registry origins, release dates, dependencies, and lifecycle scripts; verified downloaded npm archive hashes against lockfile integrity values.
- Installed npm dependencies with lifecycle scripts disabled. Verified registry signatures for **283 web** and **836 mobile** packages; **16 web** and **174 mobile** packages also had verified provenance attestations.
- Most selected releases are weeks or months old. The newest changed web package was published September 3; the newest mobile transitive release is yaml 2.9.1, published September 11. Release age and valid signatures are supporting evidence, not proof that code is harmless.
- The 14 changed Python packages were installed as wheels into a temporary virtual environment. The unchanged Flask-APScheduler 1.13.1 has no wheel; its already-installed files were copied from the existing environment for verification instead of running its source-build script. No active project environment was updated.
- Tests ran from temporary source copies with a clean environment and credentials excluded. The browser test used a fresh Chrome profile. This was a dependency review and regression test, not a comprehensive malware or application security audit.
- Added project-local `.npmrc` files to disable automatic lifecycle scripts in both npm projects. Explicit commands such as `npm run` and `npx` still execute code.
- Added weekly Dependabot version-update configuration for both npm projects and Poetry with a seven-day cooldown and three open version PRs per entry. Security updates are not delayed by cooldown. Repository security-update settings and branch protection are separate; no automatic merge or remote settings were enabled.

## Validation

- Backend: **87/87 tests pass** in the temporary Python environment. Python dependency consistency check passed.
- Flashcard browser regression: **13/13 checks pass**, including Markdown rendering, XSS payloads, and plain-text fallback when sanitization is unavailable.
- Web: Sass compilation passes (existing Sass deprecation warnings remain).
- Mobile: TypeScript and ESLint pass; static production web export generates **17 routes**. The generated Expo type reference was included in the temporary test copy.
- Mobile dependency regression: both plist parsers round-trip; Xcode generates 100 valid unique identifiers and parses/writes a project; Metro reads PNG dimensions and rejects unsupported or disguised malformed image data.
- Production iOS and Android JavaScript/Hermes exports both pass with the patched Metro tree. No Xcode/Gradle native build, simulator/device smoke test, or production deployment has been performed.

## Reproduce after reviewing the changes

Use Node 24.14.0/npm 11.9.0 and Python 3.13.11/Poetry 2.4.3 (the versions used for the final checks). Install and test in a disposable environment without production credentials.

```bash
npm ci --ignore-scripts
npm audit
npm audit signatures
npm run sass
# Open tests/browser/flashcards-security.html; expect PASS: 13 checks.

cd mobile
npm ci --ignore-scripts
npm audit  # Expected to retain the documented decoder finding.
npm audit signatures
npm run test:dependencies
npx --no-install tsc --noEmit
npm run lint
npx --no-install expo export --platform web
```

For Python, install the reviewed Poetry lockfile in an isolated environment, then run `poetry run python -m unittest discover -s tests`. Source-only packages require explicit review; do not silently relax a wheels-only policy. The [verification runbook](../verification-runbook.md) covers application smoke tests.

## Alert package versions

### package-lock.json

| Package | Before | After | Original alerts |
| --- | --- | --- | ---: |
| `brace-expansion` | 1.1.12 | 1.1.18 | 1 |
| `dompurify` | 3.3.1 | 3.4.13 | 18 |
| `engine.io` | 6.6.5 | 6.6.10 | 2 |
| `follow-redirects` | 1.15.11 | 1.16.0 | 1 |
| `immutable` | 3.8.2, 5.1.4 | 3.8.4, 5.1.9 | 6 |
| `lodash` | 4.17.21 | 4.18.1 | 3 |
| `minimatch` | 3.1.2 | 3.1.5 | 1 |
| `picomatch` | 2.3.1, 4.0.3 | 2.3.2, 4.0.7 | 2 |
| `socket.io-parser` | 4.2.5 | 4.2.7 | 1 |
| `ws` | 8.18.3 | 8.21.3 | 1 |

### poetry.lock

| Package | Before | After | Original alerts |
| --- | --- | --- | ---: |
| `flask` | 3.1.2 | 3.1.3 | 1 |
| `httplib2` | 0.31.1 | 0.32.0 | 1 |
| `idna` | 3.11 | 3.15 | 1 |
| `mako` | 1.3.10 | 1.3.12 | 2 |
| `protobuf` | 6.33.4 | 6.33.5 | 1 |
| `pyasn1` | 0.6.1 | 0.6.4 | 5 |
| `pyjwt` | 2.11.0 | 2.13.0 | 6 |
| `python-dotenv` | 1.2.1 | 1.2.2 | 1 |
| `python-engineio` | 4.13.0 | 4.13.2 | 2 |
| `python-socketio` | 5.16.0 | 5.16.2 | 1 |
| `requests` | 2.32.5 | 2.33.0 | 1 |
| `urllib3` | 2.6.3 | 2.7.0 | 2 |
| `werkzeug` | 3.1.5 | 3.1.6 | 1 |

### mobile/package-lock.json

| Package | Before | After | Original alerts |
| --- | --- | --- | ---: |
| `@xmldom/xmldom` | 0.8.13, 0.9.10 | 0.8.15, 0.9.12 | 23 |
| `baseline-browser-mapping` | 2.10.42 | 2.11.0 | 1 |
| `brace-expansion` | 1.1.15, 5.0.7 | 1.1.18, 5.0.9 | 3 |
| `browserslist` | 4.28.5 | 4.28.7 | 2 |
| `decode-uri-component` | 0.2.2 | 0.2.2 | 1 |
| `image-size` | 1.2.1 | removed | 2 |
| `js-yaml` | 4.3.0 | 4.3.2 | 2 |
| `nanoid` | 3.3.15 | 3.3.18 | 2 |
| `postcss` | 8.5.16 | 8.5.23 | 2 |
| `socket.io-parser` | 4.2.6 | 4.2.7 | 1 |
| `uuid` | 7.0.3 | 11.1.1 | 1 |
