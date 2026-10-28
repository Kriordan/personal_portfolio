# Expo 57 security compatibility

These private local packages bridge upstream security fixes into the retained
Expo 57 stack. They are installed through explicit dependencies and scoped npm
overrides, including on clean installs with `ignore-scripts=true`. They require
no postinstall patching, generated vendor files, or changes to installed packages.

## URL decoding

`query-string@7.1.3` requires a callable CommonJS export. The decoder adapter
returns the default export of the unmodified, integrity-locked upstream
`decode-uri-component@0.5.1`. Node 24 supports the synchronous ESM import;
Metro transforms the same dependency for the native and web bundles.

Remove the adapter when a compatible Expo Router dependency uses the fixed
decoder directly. Keep malformed-percent regression tests on the actual
Router dependency path.

## Expo CLI schemas

Expo CLI 57.0.27 still requires the Zod 3 interface, including the schema shape
consumed by MCP tooling. The adapter uses the `v3` compatibility export in
the exact `zod@4.6.7` package and patches its collection parsers at module load.
The upstream package version alone does **not** fix that legacy export.

The local backport rejects an oversized array/set before parsing its elements
when `.max()` or `.length()` already rules it out, following the upstream
[size-gate fix](https://github.com/colinhacks/zod/commit/a0ebf970f2d752e5f58527cd2942ff48be4f46bd).
Expo also has unconstrained plugin arrays, so a separate **1,000-entry total
collection budget per parse** bounds nested arrays, sets, maps, and attempted
union branches. Over-budget tooling input returns a validation error. This
limit applies to CLI plugin configuration/output, not application lists or APIs.

The backport deliberately retains Zod 3 constructors, errors, schema metadata,
and ordinary validation/transforms. It depends on pinned Zod internals; do not
update the aliased upstream package without rerunning the early-rejection,
async, nested-budget, real Expo plugin, and MCP schema tests. The CLI override
is version-scoped so a CLI upgrade cannot silently inherit an unreviewed bridge.
ESLint's React Hooks plugin already supports Zod 4 and uses unmodified 4.6.7.

Remove this adapter when Expo supports fixed collection validation upstream.
Do not replace it with a plain `zod/v3` re-export: that would restore the issue.
An audit without findings is not proof of this local backport; the behavioral
regressions in `tests/dependency-security.test.mjs` are required in CI.
