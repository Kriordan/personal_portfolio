# Expo 57 security compatibility

The private URL decoder package bridges an upstream security fix into the
retained Expo 57 stack. It is installed through an explicit dependency and a
scoped npm override, including on clean installs with `ignore-scripts=true`.
It requires no postinstall patching or changes to installed packages.

## URL decoding

`query-string@7.1.3` requires a callable CommonJS export. The decoder adapter
returns the default export of the unmodified, integrity-locked upstream
`decode-uri-component@0.5.1`. Node 24 supports the synchronous ESM import;
Metro transforms the same dependency for the native and web bundles.

Remove the adapter when a compatible Expo Router dependency uses the fixed
decoder directly. Keep malformed-percent regression tests on the actual
Router dependency path.

## Upstream tooling fixes — November 13, 2026

Expo config 57.0.11 removes `deepmerge` and filters `__proto__` in both merge
inputs. The expired audit exception is removed. Tests exercise the real
`modifyConfigAsync` API with malicious config/plugin options and ordinary
nested settings; no local merge implementation is needed.

Expo CLI 57.0.34 uses JSON Schema for plugin validation and accepts a schema
library from an optional MCP provider. It no longer installs Zod 3. The old
Zod 3 adapter and its scoped override have been removed. Its 1,000-entry budget
was specific to that removed parser; it is not a limit of the new JSON Schema
validator. Tests now exercise the actual upstream plugin/output schemas,
early `maxItems` rejection, and MCP schema construction with fixed Zod 4.
ESLint's React Hooks plugin continues to use unmodified Zod 4.6.7.

The updated Expo tools use patched glob 14.0.6. Two consumers still request
minimatch 10: `@expo/fingerprint` and `@typescript-eslint/typescript-estree`.
Scoped overrides select 11.0.8. Those consumers use the retained matching API,
not the removed `makeRe()`/AST API. Tests verify fingerprint ignore/negation
behavior, parser-style path matching, the installed versions, and bounded
rejection of amplification patterns. Re-review the overrides when those
consumers change; remove them when their declared dependencies are fixed.

The node-forge pin is 1.4.3. RSA and Ed25519 regressions exercise Expo's installed
signing libraries. Xcode 4.0.0 no longer needs the UUID override; its project
read/write and identifier checks remain in `npm run test:dependencies`.

See the [security validation record](../../docs/security/deepmerge-2026-11-13.md).
