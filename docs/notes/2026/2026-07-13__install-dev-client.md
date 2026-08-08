# Install expo-dev-client and Link EAS Project (`install-dev-client`)

Date: 2026-07-13
Todo ID: `install-dev-client`

## Objective

Install `expo-dev-client` and link the mobile app to an EAS project so the app can be built as a development build on EAS, replacing the Expo Go workflow (App Store Expo Go is stuck on SDK 54 while the project uses SDK 57).

## Scope Delivered

- Installed `expo-dev-client@~57.0.5` into `mobile/` via `npx expo install expo-dev-client` (SDK 57-compatible version resolved automatically).
- Created the EAS project `@kriordan/personal-portfolio` (https://expo.dev/accounts/kriordan/projects/personal-portfolio) via `eas init --non-interactive --force`.
- Linked the project: `extra.eas.projectId` (`02007b1c-386b-4348-8e84-7cc98d6ae38d`) and `owner: "kriordan"` written into `mobile/app.json`.

## Prior Art / Context

This is Step 2 of the "Move to EAS Development Builds" plan. Step 1 (renaming the app to "Personal Portfolio" / slug `personal-portfolio` / bundle ID `com.kriordan.personalportfolio`) was already complete in `mobile/app.json`, and `mobile/eas.json` already had a correct `development` profile (`developmentClient: true`, `distribution: "internal"`). The user was already logged in to EAS as `kriordan`.

## Architecture and Design Choices

### 1) `npx expo install` instead of plain `npm install`

- Used `npx expo install expo-dev-client` so Expo pins the version compatible with SDK 57 (`~57.0.5`) rather than latest.

### 2) Non-interactive `eas init`

- Ran `npx eas-cli@latest init --non-interactive --force` (eas-cli 21.0.0) since the shell can't answer interactive prompts. `--force` accepts the default of creating `@kriordan/personal-portfolio` under the logged-in account, matching what the interactive prompt would have offered.

### 3) Reverted incidental `eas init` edits to `app.json`

- `eas init` (via prebuild config resolution) also injected `android.permissions: ["android.permission.RECORD_AUDIO"]` and `extra.router: {}` into `app.json`. Both were reverted: the app doesn't record audio, and `extra.router` was an empty artifact. Only `extra.eas.projectId` and `owner` were kept.

## Files Created

- N/A — no new source files; `expo-dev-client` and its 6 transitive packages were added to `mobile/node_modules`.

## Files Modified

- `mobile/package.json` — added `"expo-dev-client": "~57.0.5"` to dependencies.
- `mobile/package-lock.json` — lockfile entries for the new packages.
- `mobile/app.json` — added `extra.eas.projectId` and `owner: "kriordan"`.

## API Contract

N/A — no endpoints or public interfaces added.

## Validation and Verification

1. `npm install` output confirmed 7 packages added with no errors; `mobile/node_modules/expo-dev-client/package.json` reports version 57.0.5.
2. `npx eas-cli whoami` confirmed the logged-in account (`kriordan`) before project creation.
3. `eas init` reported "Project successfully linked (ID: 02007b1c-386b-4348-8e84-7cc98d6ae38d)".
4. `npx expo config --type public` (run from `mobile/`) resolves cleanly and shows `name: 'Personal Portfolio'`, `slug: 'personal-portfolio'`, `owner: 'kriordan'`, and the correct `projectId` — confirming the reverted edits didn't break config resolution.

## Known Gaps / Follow-ups

- Step 3 of the plan is next: `eas device:create` to register the iPhone, then `eas build --platform ios --profile development` (first build prompts for Apple Developer sign-in).
- Steps 4-5 (LAN `EXPO_PUBLIC_API_URL` in `mobile/.env`, Flask bound to `0.0.0.0`, README update, optional TestFlight) remain.
- `npm audit` reports 11 moderate vulnerabilities in the dependency tree (pre-existing, not introduced by this change).

## How to Run (Current)

1. `cd mobile`
2. `eas device:create` — open the URL/QR on the iPhone to install the provisioning profile.
3. `eas build --platform ios --profile development` — build the development client on EAS (~10-20 min), then install it on the phone from the build link.
4. After install: `npx expo start` — with `expo-dev-client` present, the bundler targets the development build automatically.
