# Dependency security review — October 5, 2026

Started from `origin/main` at `e4d94588a757cc1ea307422e03779845436d618b`, the merge of [PR #94](https://github.com/Kriordan/personal_portfolio/pull/94). The October 4 GitHub snapshot contained **27 open alerts**. This branch moves the locked packages outside the recorded affected ranges for **24**, with **3 remaining**. This is a lockfile/advisory comparison, not a claim that GitHub has closed alerts or that production has been updated. No alerts were dismissed; merging and deployment remain separate steps.

## Tested batches

| Batch | Changes | Captured GitHub alerts addressed |
| --- | --- | --- |
| Priority Python | PyJWT 2.13.0 → **2.15.1**, urllib3 2.7.0 → **2.8.0**; regression tests and backend CI | #229–239, #243–244; #240–242 (16 total) |
| Remaining Python | OAuthlib 3.3.1 → **4.0.0**; Click 8.3.1 → **8.3.3**; OAuth client test and pip-audit gate | #227–228; Click was an additional pip-audit finding |
| Web | DOMPurify 3.4.13 → **3.4.16**, both CDN URLs and SHA-384 hashes; brace-expansion 1.1.18 → **1.1.21** | #225–226 |
| Mobile | Every brace-expansion 1.x copy → **1.1.21** and 5.x copy → **5.0.12**; SDK compatibility and export CI | #217, #219, #221, #222 |

Python security floors are recorded in `pyproject.toml`; lockfiles retain existing unrelated package versions. Mobile keeps Expo **57.0.25**, React/React DOM **19.2.3**, React Native **0.86.3**, Reanimated **4.5.1**, and Worklets **0.10.1**. Its scoped `xcode` → `uuid@11.1.1` override remains covered by the existing dependency regression test.

## Exposure addressed

- **PyJWT:** API bearer-token authentication and Socket.IO both use Flask-JWT-Extended. Its preliminary unverified decode makes malformed, deeply nested token input relevant even without a valid signature. New API/Socket.IO tests verify rejection of nested headers/payloads, expired tokens, and tokens signed with the wrong key. Existing login, refresh, and socket interoperability tests pass. The repository uses the default HS256 application-secret configuration, with no PyJWKClient/JWKS fetch path or public-key input configured. The public-key confusion/JWKS advisories therefore have different preconditions from the active authentication path. Stateless logout still has no server-side revocation; dependency updates do not add that feature.
- **PyJWT #244:** [GHSA-gvp8-978c-rx2q](https://github.com/advisories/GHSA-gvp8-978c-rx2q) has no `first_patched_version` and records an affected range through 2.13.0. We independently verified that 2.15.1 preserves caller options in both `decode` and `decode_complete`, and that re-enabling signature verification still rejects an expired token. CI preserves that regression test. The app does not itself reuse an unverified options dictionary across verification modes.
- **urllib3:** Requests and botocore bring this into server runtime. `Job.render_screenshot` streams an HTTPS screenshot response into S3; outbound response parsing is a real integration boundary. The destination is the configured screenshot service, so exploiting a hostile response requires control of that response path, rather than merely submitting an HTTP request to Flask. Tests exercise valid chunked input, rejection of oversized chunk-size lines, and fragmented deflate streams with a subprocess timeout. No custom HTTPS proxy/TLS override is configured in repository code; environment-provided proxies were not inspected. Proxy behavior was not independently integration-tested. See the [2.8.0 release notes](https://github.com/urllib3/urllib3/releases/tag/2.8.0) before deploying with custom proxy certificates.
- **OAuthlib:** Used as an OAuth client through Google Auth/requests-oauthlib, not as the application's authorization server. The PKCE verifier comparison and JSONP revocation endpoint findings do not map to server endpoints implemented here. The 4.0 server-side breaking changes are compatible with this client use; the new test performs the real client authorization-code parsing/exchange against a mocked HTTP response and checks state mismatch rejection. See [OAuthlib 4.0.0](https://github.com/oauthlib/oauthlib/releases/tag/v4.0.0).
- **Click:** The additional `PYSEC-2026-2132` / `GHSA-47fr-3ffg-hgmw` finding concerns `click.edit()`. No such call exists in application code. We still installed the minimal fixed patch, 8.3.3, and reran the application suite.
- **DOMPurify:** The learning renderer sanitizes Markdown-derived HTML strings. The particular [#226 advisory](https://github.com/advisories/GHSA-p98j-92pf-mc4p) needs `IN_PLACE` plus node-removing hooks, neither of which this renderer uses. Both templates now load 3.4.16 with matching SRI. The downloaded jsDelivr response matched the installed npm browser bundle byte-for-byte. CI verifies all template references against the package version and bytes, and executes the real renderer's XSS/fallback checks in Chrome.

## Remaining alerts and additional npm exposure

| Alert / advisory | Dependency path and actual exposure | Resolution condition |
| --- | --- | --- |
| [#186](https://github.com/Kriordan/personal_portfolio/security/dependabot/186), [GHSA-vcc3-ghjq-m6fr](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr) | `expo-router@57.0.23` → `query-string@7.1.3` → `decode-uri-component@0.2.2`. Router uses query-string when parsing navigation paths. Malformed attacker-supplied deep links/query input can consume CPU in the app or web client; this remains an availability risk. | Decoder 0.5.0 is ESM-only; query-string 7 calls its CommonJS import as a function. Published Router 57.0.24 still requests `query-string ^7.1.3`. Use a compatible upstream Router fix or a separately maintained and tested adapter/backport; no override or mitigation is claimed here. |
| [#246](https://github.com/Kriordan/personal_portfolio/security/dependabot/246), [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) | Mobile Metro/file-map tooling → `micromatch` → `braces@3.0.3`. Fresh npm audit also finds the same advisory in root Gulp/BrowserSync's glob/watch tree. Deeply nested attacker-controlled glob patterns can exhaust the build process stack. We found build/configuration use, not an application endpoint accepting globs; repository/configuration inputs still need to be trusted. npm labels some mobile tooling as runtime because Expo depends on it. | No patched release is published. `brace-expansion` is a different package and its update does not fix `braces`. Do not apply npm's suggested downgrade to old Gulp/BrowserSync. Revisit the upstream glob stack when a patch is available. |
| [#245](https://github.com/Kriordan/personal_portfolio/security/dependabot/245), [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv) | Expo CLI / `@expo/code-signing-certificates` → `node-forge@1.4.0`. Its certificate tooling contains real signature-verification calls, and the CLI uses forge for iOS provisioning. Crafted RSA PKCS#1 v1.5 signatures are a build/signing trust-boundary risk if untrusted signing material reaches these tools. No application import was found; this is not evidence that the tooling issue is harmless. | No patched release is published. Keep the alert open; update the Expo-compatible tooling once a fix exists, with certificate-validation regression coverage. |

Fresh scan results: Python **0 known vulnerabilities**; root npm **9 high entries**, all propagation of the single braces advisory; mobile npm **22 entries (19 high, 3 moderate)** representing the three underlying advisories above. Root `npm audit --omit=dev` is clean. Counts of affected parents are not counts of distinct vulnerabilities.

The narrow exceptions in `npm-audit-exceptions.json` expire after **November 5, 2026**. The gate checks advisory ID, package, installed lockfile version, and severity. It fails for new findings (including new advisories on these packages), expired/stale exceptions, changed versions/severity, and unavailable or malformed audit responses. No blanket severity threshold, `continue-on-error`, alert dismissal, or `npm audit fix --force` is used. Updating an exception requires another exposure review.

## PR disposition and prevention

- [#92](https://github.com/Kriordan/personal_portfolio/pull/92) and [#93](https://github.com/Kriordan/personal_portfolio/pull/93) are superseded by the tested PyJWT/urllib3 batch. Although #92's title says 2.15.0, its current diff already targets 2.15.1.
- [#71](https://github.com/Kriordan/personal_portfolio/pull/71) and [#73](https://github.com/Kriordan/personal_portfolio/pull/73) are already superseded on main (DOMPurify 3.4.13 and nanoid 3.3.18). [#85](https://github.com/Kriordan/personal_portfolio/pull/85) targets DOMPurify 3.4.15, which remains affected; this batch includes 3.4.16 and the CDN changes missing from a package-only bump.
- [#95](https://github.com/Kriordan/personal_portfolio/pull/95), [#96](https://github.com/Kriordan/personal_portfolio/pull/96), and [#97](https://github.com/Kriordan/personal_portfolio/pull/97) propose React/React DOM 19.3 and Worklets 0.13 independently of Expo. They are incompatible with the retained SDK matrix and should not be merged. Dependabot now ignores independent minor/major version updates for SDK-managed package families; security advisories remain tracked. Patch PRs still have to pass the installed Expo bundle's compatibility ranges. [Expo 57 reference](https://docs.expo.dev/versions/v57.0.0/).
- [#86](https://github.com/Kriordan/personal_portfolio/pull/86) (Flask-JWT-Extended) and [#88](https://github.com/Kriordan/personal_portfolio/pull/88) (Google API client) remain separate routine version reviews. Neither is required to resolve this alert snapshot.

## Validation and reproduction

- Python 3.13.11 / Poetry 2.4.3, isolated `/tmp` environment: `poetry check --lock`, dependency consistency, **114 unittest tests**, and pip-audit 2.10.1 pass. Test execution disables dotenv and cloud metadata access and supplies no production credentials. The unchanged source-only Flask-APScheduler dependency is installed by Poetry; this run is not described as a wheels-only supply-chain audit.
- Node 24.14.0 / npm 11.9.0: both `npm ci --ignore-scripts` installations pass. Web: **4 audit-gate tests**, CDN integrity check, **13 browser checks**, and Sass compilation pass. Stable Chrome timed out locally; Chrome Canary completed the same headless runner. CI uses Ubuntu's Google Chrome. Existing Sass deprecation warnings remain.
- Mobile: **18 tests**, the SDK/XML/UUID/Metro compatibility script, TypeScript, ESLint, and production JavaScript/Hermes exports for **web, iOS, and Android** pass. No Xcode/Gradle native build, device test, or deployment was performed.
- Three read-only GitHub Actions workflows run on PRs and pushes to main: backend tests/audit; web audit/CDN/browser/Sass checks; and mobile audit/compatibility/tests/all-platform export/typecheck/lint. Action revisions are pinned. Repository branch-protection settings were not changed.

```bash
# Python: use a disposable environment; disable local dotenv during tests.
poetry check --lock
poetry sync --no-interaction
poetry run pip check
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python -m unittest discover -s tests
# Install pip-audit==2.10.1 in a separate tool environment, then audit the app's
# site-packages with pip-audit --path /path/to/app/env/lib/python3.13/site-packages.

npm ci --ignore-scripts
npm test
npm run audit:security
npm run test:browser  # CHROME_BIN can select a Chrome executable.
npm run sass

cd mobile
npm ci --ignore-scripts
node ../scripts/check-npm-audit.cjs mobile
npm run test:dependencies
npm test
EXPO_NO_DOTENV=1 EXPO_PUBLIC_API_URL=https://api.example.com EAS_BUILD_PROFILE=production npx --no-install expo export --platform all
npm run typecheck
EXPO_NO_DOTENV=1 npm run lint
```
