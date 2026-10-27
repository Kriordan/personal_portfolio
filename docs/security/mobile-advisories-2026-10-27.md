# Mobile dependency remediation — October 27, 2026

Based on `main` at `ab8a02e`, including the merged runtime security, lottery,
account isolation, and Jobwizard recovery work. Python 3.13.18, Node 24.22.1,
certifi 2026.10.19, EAS runtime settings, application code, migrations, and the
backend deployment are unchanged.

## Remediation

| Advisory | Change |
| --- | --- |
| [node-forge / CVE-2026-85393](https://github.com/advisories/GHSA-86w9-cpqp-85rv) | Both Expo CLI and its signing-certificate helper resolve **1.4.2**. The [October 27 upstream release](https://github.com/digitalbazaar/forge/blob/7928054627d93ab8c0216b756246e8ca8d62a93e/CHANGELOG.md) fixes nested DigestAlgorithm verification and includes the subsequent PEM Buffer-input compatibility correction. |
| [decode-uri-component](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr) | Router 57 retains query-string 7, with a three-line CommonJS adapter returning the default export of unmodified, integrity-locked **0.5.1**. No older decoder remains in the dependency tree. |
| [Zod](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5) | ESLint's React Hooks plugin uses fixed **4.6.7** directly. Expo CLI retains the Zod 3 interface through a local backport applied to 4.6.7's legacy `v3` export. The backport rejects oversized constrained collections before visiting elements; a shared 1,000-entry validation budget also bounds Expo's unconstrained plugin collections, nested inputs, and union attempts. |

The upstream Zod package's version does **not** establish that its legacy v3
export is safe: a control test shows that unwrapped export still visits elements
after a size check fails. The local backport, its integrity-locked dependency,
and the behavioral regressions are therefore essential. This is a maintained
compatibility fix, not a claim that upstream published a patched Zod 3 release.
Its collection budget affects CLI plugin input/output, not application lists.

The adapters are explicit local dependencies, selected by scoped overrides.
Clean `npm ci --ignore-scripts` installs them without postinstall hooks or
modifying node_modules. Expo, Router, React, React Native, and unrelated locked
package versions stay unchanged. Maintenance/removal conditions are in
[the adapter README](../../mobile/security-compat/README.md).

All three audit exceptions were removed. The audit gate is unchanged; no
advisory was dismissed or suppressed. After the merge, GitHub marked alerts
#186, #245, and #251 fixed at 21:22 UTC on October 27. The subsequent
default-branch check reports zero open dependency alerts.

## Validation

- Clean locked installation succeeds, and `npm ls` resolves the intended
  libraries through the actual Router, Expo CLI, signing, and ESLint consumers.
- Root and mobile audit gates pass with **zero findings and zero exceptions**.
- **129 mobile tests** pass, including seven new dependency-security tests.
- Normal query values, Unicode, repeated parameters, malformed escapes, and
  query round-trips work. Large malformed inputs complete inside a bounded
  subprocess; the old 0.2.2 decoder fails the same isolated control.
- Zod tests cover early rejection, ordinary transformations, async parsing,
  nested collection budgets, union/catch contexts, fresh budgets across parses,
  and real Expo plugin/MCP schemas retaining the Zod 3 interface.
- Real RSA tests accept valid signatures and reject extra nested
  DigestAlgorithm elements using both Expo consumers. The same regression fails
  against old node-forge 1.4.0. The constrained-collection regression also fails
  against old Zod 3.25.76, confirming the tests detect the original behavior.
- Expo SDK compatibility, TypeScript, ESLint, and iOS/Android/web exports pass.
  All existing application, account isolation, lottery, and recovery tests are
  retained. Root runtime/audit-policy/CDN tests also pass.

## Delivery status

[PR #134](https://github.com/Kriordan/personal_portfolio/pull/134) was merged as
`977c9d122d1a5ff22b8a9ca05e24ba3e75e99b67`. All post-merge backend, mobile,
web, and CodeQL checks passed.

The authorized [iPhone preview 7](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/d1f95c3f-6cbe-4763-bd3d-2ff4925359a0)
finished at **5:31 p.m. EDT on October 27, 2026**, directly from that merged
commit. The downloaded app passes macOS signature verification, identifies
itself as version 1.0.0 (7), contains the expected source commit and production
API origin, and uses the existing signing certificate and registered iPhone.
Its application screens, source, and settings match accepted preview 6;
changes are confined to dependency security, regression tests, and documentation.
The cloud dependency install reports zero vulnerabilities. Sentry's successful
source-map upload report has the same debug ID as the signed app.

Cloud Expo Doctor passed 20 of 21 checks. Its latest-SDK-patch check reports
exactly the same ten older patch versions as accepted preview 6; no new
mismatch or suppression was introduced. The build succeeded with the existing
Expo 57 dependency set. This cloud check is distinct from the passing repository
SDK compatibility checks.

The [verification receipt](../assets/security/iphone-preview-build-7.json)
records the app checksum, signing and source-map evidence, and build identifiers.
No backend deployment, credential change, OTA publication, production data write,
or other project modification was performed for this mobile release. The
previous Python, Node, certifi, lottery, account-isolation, and recovery fixes
remain preserved.

## Closeout — October 27, 2026

The user installed preview 7 on the physical iPhone and confirmed:
“I’ve installed preview 7 and it looks good.” This records overall device
acceptance of the signed security build. Individual adversarial, accessibility,
Android, and concurrency scenarios were not separately reported.

The requested runtime and three mobile dependency security updates are closed:
PR #129's deployed runtime/TLS evidence is retained in the
[runtime security record](runtime-security-2026-10-26.md), PR #134 is merged,
and preview 7 is installed and accepted. GitHub was rechecked at closeout:
alerts #186, #245, and #251 remain fixed, with zero open dependency alerts.
Both audit-exception lists are empty, so their November 5 review follow-up is
complete. No advisory was dismissed or suppressed. Ongoing adapter maintenance
and unrelated feature, accessibility, credential, and platform follow-ups retain
their existing scope in the [validation ledger](../validation-status.md).
