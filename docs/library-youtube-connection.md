# Library YouTube connection

Library is a single shared catalog. Every authenticated account can request an import, but only a site administrator can replace or revoke the shared YouTube connection. The connection requests only `youtube.readonly`. Imported playlists, including private playlist contents, are visible to the app's other signed-in accounts; choose the intended maintainer account.

## Reconnect

1. Open `https://www.keithriordan.com/oauth/` in a normal browser and sign in with the site's administrator account.
2. Select **Continue to Google**, choose the Google account that owns the desired playlists, and allow YouTube read access. A successful connection replaces the previous shared connection.
3. Back on the connection page, select **Check connection**. This makes a read-only YouTube request without importing the catalog.
4. Return to the installed mobile preview and select **Sync from YouTube**. The mobile app needs no Google token, browser cookie, or replacement build for this backend change.

If Google reports a redirect mismatch, its web OAuth client's authorized redirects must include exactly `https://www.keithriordan.com/oauth/oauth2callback`. If the consent screen is in Google's external **Testing** mode, a YouTube refresh token can expire after seven days; review the app's publishing status in Google Cloud. This is separate from the fixed Heroku file-persistence issue. Never paste access tokens, refresh tokens, or client secrets into chat, logs, or Git.

## Durable storage and deployment

The additive migration `f6a7b8c9d0e1` creates a singleton `youtube_connection` table; it does not change existing catalog rows. The refresh token is encrypted with Fernet. Its encryption key lives in the server's `YOUTUBE_CREDENTIALS_KEY` config, separately from the database. `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` remain in server config. `YOUTUBE_OAUTH_REDIRECT_URI` defaults to the canonical callback above and must be HTTPS.

Set `YOUTUBE_CREDENTIALS_KEY` once to a securely generated Fernet key through the deployment's secret/config mechanism. Do not print it, commit it, or regenerate it on restart. Retain it with restricted operator access: losing/replacing it makes the existing connection unreadable and requires another Google consent flow. Do not fall back to an unencrypted database value or a browser cookie. Reconnecting can replace an unreadable old record after the key is deliberately changed.

The old `project/data/youtube_token.json` and credential-bearing Flask session are no longer credential sources. API, website, and Flask CLI operations all read the shared database record. The connection page removes legacy session credentials on the administrator's next visit. Access tokens are short-lived in-memory values obtained through the saved refresh token. Neither Google token nor client secret is returned to the mobile app, rendered into HTML, or stored in the browser session. The authorization handshake stores only state, a PKCE verifier, the initiating site user, callback/client identifiers, and a ten-minute deadline in the signed session; callbacks are single-use.

Connection management uses admin checks, POST forms with CSRF protection, and private/no-store/no-referrer responses without analytics. **Revoke access and disconnect** explicitly revokes the Google grant and removes the saved credential, while retaining the catalog. It may also invalidate other tokens for the same Google grant. Ordinary website/API sync remains available to every signed-in account.

Deploy after the lockfile, migration, backend tests, and dependency audit pass. Keep the key stable across releases. Rolling the application back does not require dropping the new table; a downgrade deletes the saved connection. A successful deployment does not establish live OAuth consent or import success.

## Verification

- Regression coverage: real mocked Google authorization-code exchange with PKCE; rejected/missing/replayed/expired/cross-account state; admin and CSRF boundaries; denied consent and failed exchanges preserving the previous grant; encrypted storage; refresh after creating a fresh app; a second user's API sync using the shared connection; missing/wrong keys and client changes; read-only verification; revocation retaining catalog rows; and additive migration upgrade/downgrade/upgrade.
- After reconnecting, verify the connection from a fresh process or after a web-dyno restart, then test mobile sync and website visibility. Never inject authorization failures into the live shared catalog.
- Keep the [Library checklist](library-smoke-test.md) and all prior Grocery/Wishlist device checks open until individually verified. The existing 30-second mobile deadline still means completion is unknown if a long import outlasts the client wait; this repair does not add a background worker or import-status service.

References: [Heroku ephemeral filesystems](https://devcenter.heroku.com/articles/dyno-isolation), [Google token-storage guidance](https://developers.google.com/identity/protocols/oauth2/resources/best-practices), [Google offline authorization](https://developers.google.com/identity/protocols/oauth2/web-server), and [Fernet](https://cryptography.io/en/stable/fernet/).
