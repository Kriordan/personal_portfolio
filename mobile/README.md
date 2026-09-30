# Mobile (Expo)

Expo client for the Flask API in the repo root. Uses [Expo Router](https://docs.expo.dev/router/introduction/) for navigation, [TanStack Query](https://tanstack.com/query) for server state, and `expo-secure-store` for token storage.

## Prerequisites

- Node 22.13+ (SDK 57 minimum; this change was verified with Node 24)
- The Flask API running locally (see `docs/verification-runbook.md` in the repo root):

```bash
flask --app project run --host 0.0.0.0 --port 5001 --debug
```

`--host 0.0.0.0` matters for physical devices because the iPhone must reach the Flask server over the LAN. `--debug` matters because outside debug mode Talisman redirects to HTTPS, which breaks plain-HTTP requests from simulators/devices.

## Setup

```bash
cd mobile
npm install
npm start
```

Then press `i` (iOS simulator), `a` (Android emulator), or `w` (web).

After installing or updating native packages, rebuild the development client with `npm run ios` or `npm run android`. Native projects remain generated and ignored. SDK 57 is deliberately retained: `expo-build-properties` enables the scene lifecycle required by Xcode 27. When an existing generated project predates the setting, back up any manual native changes and run `npx expo prebuild --platform ios` before rebuilding.

The product targets iOS first and supports Android. Expo web is a development convenience, not a production web-authentication or UI-parity commitment. The Flask website remains independent.

### Local Android development on macOS

Complete Android Studio's SDK setup and create an ARM64 virtual phone in **More Actions → Virtual Device Manager** on Apple Silicon. SDK 57 compiles against Android API 36; the Android Studio wizard may install a newer platform instead. Gradle can download the required platform and NDK when the corresponding SDK licenses have already been accepted. Review any additional emulator-image license in Android Studio.

With the emulator running, use a terminal with Java 17 and the Android SDK configured:

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
export PATH="$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$PATH"
cd mobile
EXPO_PUBLIC_API_URL=http://10.0.2.2:5001 npm run android
```

The first native build downloads Gradle, Maven dependencies, and missing SDK components. Later JavaScript edits use Metro without rebuilding; changes to native packages or app configuration require another native build. The explicit API URL above overrides an iOS-oriented `.env` value: Android's `10.0.2.2` reaches the Mac hosting Flask. Use your actual local Flask port if it differs from 5001.

Keep Android Studio's **Running Devices** tool window in **Dock Pinned** mode when using computer-assisted emulator testing. To exercise the software keyboard while a hardware keyboard is connected, enable **Show on-screen keyboard** in the emulator's **Settings → System → Keyboard → On-screen keyboard → Gboard → Physical keyboard**. After a connectivity test, use the development menu's **Reload** if Fast Refresh has stopped applying edits.

## API base URL

The API base URL is resolved in `src/lib/config.ts`:

1. `EXPO_PUBLIC_API_URL` if set (copy `.env.example` to `.env` and fill it in)
2. Otherwise a platform default: `http://127.0.0.1:5001` (iOS simulator/web) or `http://10.0.2.2:5001` (Android emulator)

For a physical device, set `EXPO_PUBLIC_API_URL` to your machine's LAN IP, e.g. `http://192.168.1.20:5001`, and make sure the device is on the same network. A quick way to verify the right IP is to match the host shown in Metro's dev-client URL. After changing `.env`, fully reload the development build so Expo re-inlines the value into the JavaScript bundle.

Set `EXPO_PUBLIC_API_URL` in the EAS **production** environment before a production build. `app.config.ts` rejects a missing, non-HTTPS, or loopback production URL. It does not provision or verify remote EAS environment values; confirm those before releasing. Development, preview, and production build profiles are retained; no EAS Update configuration is added.

### Installable iPhone preview

The `preview` profile in `eas.json` embeds `https://keithriordan.herokuapp.com` as its public API origin. This standalone build uses the deployed account and data, including writes shared with the website. It runs without Metro or a local Flask server. Preview builds also reject a missing, non-HTTPS, or loopback API URL.

```bash
cd mobile
npx eas-cli build --platform ios --profile preview
```

Reuse the registered iPhone and existing signing credentials when prompted. Open the completed build's Expo install page in Safari on that iPhone and tap **Install**. Only devices included in the provisioning profile can install it. If the phone has changed, register it with `npx eas-cli device:create` and include it when rebuilding. This is internal distribution; no App Store submission or TestFlight setup is required.

If iOS asks for Developer Mode, follow **Settings → Privacy & Security → Developer Mode**, enable it, restart, and confirm **Turn On** after unlocking. This is a one-time device setup for internal builds; see [Expo's instructions](https://docs.expo.dev/guides/ios-developer-mode/). Sign in with the existing website account, then verify a small grocery change appears in both clients.

## Physical iPhone development build (EAS)

The app is linked to `@kriordan/personal-portfolio` on Expo, with bundle identifier `com.kriordan.personalportfolio`. The `development` profile in `eas.json` builds an internally distributed app containing `expo-dev-client`. Building for a physical iPhone through EAS requires an Apple Developer Program membership; Xcode and a local signing certificate are not required for this cloud build workflow.

### Build or replace the installed app

From `mobile/`:

```bash
npm ci
npx eas-cli@latest login --browser
npx eas-cli@latest whoami
npx eas-cli@latest build:list --platform ios --limit 3
npx eas-cli@latest device:list
```

Use the `kriordan` Expo account and the existing Apple team. If the iPhone is already registered, reuse it. For a new phone, run `npx eas-cli@latest device:create`, choose website registration, and open the generated link in Safari on the iPhone to complete registration. Include that phone when the build command selects devices.

```bash
npx eas-cli@latest build --platform ios --profile development
```

Reuse the existing EAS-managed signing credentials when offered. Apple sign-in may be needed to create or refresh credentials or update the device list. When the build finishes, open its Expo build page in Safari on the iPhone and install the app. Enable Developer Mode under Settings → Privacy & Security if prompted, completing the restart and confirmation.

Adding a native dependency requires another native build and installation. For example, `Cannot find native module 'ExpoCrypto'` means the installed app lacks the native module used by the current JavaScript. Installing npm dependencies or restarting Metro alone cannot add it to the phone. JavaScript-only changes normally need only a reload.

### Connect the phone to this Mac

1. Find the Mac's Wi-Fi address with `ipconfig getifaddr en0` (or check Network settings if Wi-Fi uses another interface).
2. Set `EXPO_PUBLIC_API_URL=http://<MAC_LAN_IP>:5001` in `mobile/.env`; update it when switching Macs or networks.
3. In a terminal at the repository root, start the API:

   ```bash
   poetry run flask --app project run --host 0.0.0.0 --port 5001 --debug --no-debugger --no-reload
   ```

4. In another terminal at `mobile/`, start Metro:

   ```bash
   npm start -- --dev-client --lan
   ```

5. Keep the phone on the same Wi-Fi, allow the app Local Network access, and select the development server. If discovery does not find it, enter `http://<MAC_LAN_IP>:8081` manually in the app's launcher.
6. Sign in, open Lists, check the Live badge, then open Learning and its review screen. Close and reopen the app to verify session restoration.

The two ports serve different purposes: `8081` loads the app's JavaScript; `5001` serves the Flask API. On the iPhone, opening `http://<MAC_LAN_IP>:5001/api/v1/auth/me` in Safari should return a JSON authentication error (HTTP 401), confirming API reachability without signing in. A JavaScript error screen confirms Metro was reached, but does not confirm API connectivity.

This development workflow requires Metro and the API to keep running. The separate `preview` profile bundles JavaScript for standalone testing, but still needs a reachable backend and an API URL configured for the EAS build. The gitignored local `.env` is not uploaded to EAS.

### Moving to another Mac

- Restore the root `.env` and recreate `mobile/.env` with the new LAN address. Install Python/Poetry and Node dependencies from their lockfiles.
- Sign in to Expo to reuse hosted builds and signing credentials. Local `node_modules`, generated `ios/` and `android/` folders, and build caches can be regenerated.
- Check the database separately: Git and EAS do not carry local users, lists, gifts, or other database records. Preserve an old database backup if that data is needed, even if the new database's migrations are current.
- For YouTube sync, check the ignored `client_secret.json`, `project/data/youtube_token.json`, and `project/data/jsonfiles/` inputs. OAuth credentials can be restored or authorization repeated as appropriate.
- For optional integrations, check the credentials listed in `docs/verification-runbook.md`, including `APILEAP_ACCESS_KEY` for job screenshots and AWS access for uploads. Keep secrets out of Git.

References: [Expo iPhone builds](https://docs.expo.dev/tutorial/eas/ios-development-build-for-devices/), [managed signing credentials](https://docs.expo.dev/app-signing/managed-credentials/), and [development builds and native dependency changes](https://docs.expo.dev/develop/development-builds/introduction/).

### New Mac verification — 2026-09-14

- [iPhone development build](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/1e1b51ee-8adc-4200-b1b0-ee516b7e8f4b) completed using existing EAS-managed signing credentials and the previously registered iPhone.
- Xcode's build log confirmed `ExpoCrypto` compiled and the archive succeeded. TypeScript, lint, and iOS JavaScript export checks also passed locally.
- After installing the replacement build, the user confirmed successful login and navigation between app sections using Metro and Flask on the new Mac.
- Old database completeness and optional external integration flows were not verified by this check.

## Project structure

| Path | Purpose |
|------|---------|
| `src/app/` | Root native stack, shared providers and centralized `Stack.Protected` authentication; feature URLs stay unchanged |
| `src/app/(tabs)/` | Home / Tools / Me shell; SDK 57 native tabs isolated in `_layout.tsx` |
| `src/app/lists/` | Lists overview and detail: owned + shared lists, categories, items, live sync badge |
| `src/app/learning/` | Learning notes index, note detail, and spaced-repetition review screen |
| `src/app/wishlist/` | Wishlist gift list, create/edit forms (optional image upload), detail |
| `src/app/library/` | Library playlist browsing, playlist detail with videos, sync trigger |
| `src/app/jobwizard/` | Job list, create form, and job detail |
| `src/lib/config.ts` | Environment/API URL configuration |
| `src/lib/api-client.ts` | Fetch wrapper with JWT attachment, 401 refresh-and-retry, auth endpoints |
| `src/lib/lists-api.ts` | Typed list endpoints (`/api/v1/lists/...`) and TanStack Query keys |
| `src/hooks/use-lists.ts` | Grocery queries, authoritative mutations, and focused-screen room subscription |
| `src/lib/lists-cache.ts` | Shared cache updates, reconnect invalidation, and completed-item sections |
| `src/lib/query-lifecycle.tsx` | Native app-focus and network integration for TanStack Query |
| `src/components/native-form.tsx` | Expo UI fields and sheets; explicit `RNHostView` boundary gives forms their sheet height |
| `src/components/screen.tsx` | Small shared screen compositions and semantic feedback states |
| `src/lib/learning-api.ts` | Typed learning endpoints (`/api/v1/learning/...`) |
| `src/lib/wishlist-api.ts` | Typed wishlist endpoints (`/api/v1/wishlist/...`) |
| `src/lib/library-api.ts` | Typed library endpoints (`/api/v1/library/...`) |
| `src/lib/jobwizard-api.ts` | Typed jobwizard endpoints (`/api/v1/jobwizard/...`) |
| `src/lib/list-socket.ts` | Socket.IO client: JWT connect auth, `useListRoom` hook, post-mutation emits |
| `src/lib/token-storage.ts` | Secure token persistence (`expo-secure-store`, localStorage fallback on web) |
| `src/lib/query-client.ts` | Shared TanStack Query client |
| `src/lib/auth-context.tsx` | Auth state provider: sign-in, sign-out, session restoration |

## Auth flow

- `POST /api/v1/auth/login` returns `access_token` (15 min), `refresh_token` (30 days), and the `user` object; both tokens are stored in secure storage.
- On app launch, a stored refresh token restores the session immediately; a TanStack Query request to `GET /api/v1/auth/me` then repopulates the `user` object and validates the session (an unrecoverable 401/404 signs the user out; network errors keep the session and recover on focus/reconnect).
- Requests attach `Authorization: Bearer <access_token>`. On a 401 the client refreshes via `POST /api/v1/auth/refresh` (using the refresh token) and retries once; concurrent 401s share a single refresh.
- If refresh also fails, tokens are cleared and the app redirects to the login screen.
- Logout calls `POST /api/v1/auth/logout` (stateless server-side) and clears local tokens and the query cache.

## Lists and realtime

- The overview screen (`/lists`) shows owned and shared lists via `GET /api/v1/lists/` and creates lists via `POST /api/v1/lists/`.
- The detail screen (`/lists/[id]`) loads the full list (`GET /api/v1/lists/:id`), toggles items, and adds items/categories through the REST API.
- Realtime sync uses Socket.IO against the same base URL as the API:
  - The connection authenticates by passing a JWT access token in the Socket.IO `auth` payload; the server validates it in the connect handler (`project/sockets.py`). A fresh token is fetched before each connection attempt.
  - After connecting, the client joins the `list_<id>` room via `join_list` and re-joins automatically on reconnect (each rejoin also refetches the list to catch missed events).
  - Incoming `item_toggled`, `item_added`, and `category_added` events patch the cached list in place; `items_reordered`, `categories_reordered`, and `settings_updated` trigger a refetch.
  - After a successful local mutation the client emits the matching event so other clients (including the web UI) update live — same protocol as `project/static/js/lists.js`.
  - The connection status describes **live updates**, separately from REST availability. A room is live only after a successful join acknowledgement. Socket disconnection alone does not disable REST. Known device disconnection fails a mutation immediately; mutations are never queued or automatically retried. A failed toggle prompts a refresh before trying again because its response could have been lost after persistence.
- Signing out disconnects the socket and clears the query cache.

Grocery uses `SectionList`, preserving category/item ordering and all three server `completed_display_mode` settings: inline bottom, completed sections per category, and one global completed section. Rows expose checkbox roles and checked/busy states. Forms retain drafts on errors and guard against duplicate submission before the next React render. Native fields own their live text; keyboard submission consumes the native event value.

## UI verification

```bash
npm run typecheck
npm run lint
npm test
npx expo install --check
```

Mobile regressions use Node's built-in test runner and TypeScript stripping, without introducing a mobile test framework. They exercise real TanStack Query cache/mutation behavior, including duplicate events, stale in-flight responses, reconnect recovery, display modes, and offline/lost-response toggle handling.

See `docs/mobile-ui-validation.md` in the repository root for the completed first slice, device evidence, and remaining native/release checks. Migrate Wishlist, Library, Learning, and Jobwizard individually after the Grocery controls pass the native-platform gate.

## Dev login

Create a local user via the Flask CLI if you don't have one:

```bash
flask --app project create-user --email test@example.com --username testuser --password password123
```
