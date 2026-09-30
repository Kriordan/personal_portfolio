## Project layout

- Flask backend and web UI live in `project/`; the JSON API for external clients is under `/api/v1/` (`project/api/`).
- The Expo mobile client lives in `mobile/` (see `mobile/README.md`).
- For backend setup, test commands, and API smoke checks, see `docs/verification-runbook.md`.

## Running locally

### Frontend

Install dependencies
`npm ci`

The project disables automatic npm lifecycle scripts in `.npmrc`. Review any
package that requires an installation script before explicitly enabling it.

The frontend uses gulp to watch the less files and compile them to css.

[gulp-less](https://github.com/gulp-community/gulp-less)

To run gulp:
`npm run dev`

### Backend

The backend is a Flask app.
Ensure the virtual environment is active, then run:
`flask --app project run --port 5001 --debug`

## User Management

### Creating a user from the command line

To create a new user, use the `create-user` command. The command will interactively prompt for credentials:

```bash
flask --app project create-user
```

You can also provide the credentials directly via command-line options:

```bash
flask --app project create-user --email user@example.com --username myuser --password mypassword
```

**Note:** When using the interactive prompt, the password input will be hidden and you'll be asked to confirm it.

### Resetting a user's password

To reset the password for an existing user, use the `reset-password` command:

```bash
flask --app project reset-password
```

You can also provide the email and password directly:

```bash
flask --app project reset-password --email user@example.com --password newpassword
```

## Upgrading dependencies

### Python dependencies

```python
# Check for outdated packages
poetry show -o
```

### JavaScript dependencies

```bash
# Find outdated packages and known vulnerabilities (also run in mobile/).
npm outdated
npm audit

# After selecting and reviewing a fixed version, prepare a lockfile-only change.
# Replace PACKAGE and VERSION with the reviewed package and version.
npm install PACKAGE@VERSION --save-exact --package-lock-only --ignore-scripts

# Review the manifest/lockfile diff before installing in a temporary environment.
npm ci --ignore-scripts
npm audit signatures
```

Semver-compatible does not mean security-reviewed. Check release notes, package
sources, new dependencies, and lifecycle scripts; avoid blanket `npm audit fix
--force` updates. Installation scripts being disabled does not sandbox commands
such as `npm run`, builds, tests, or `npx`.

Dependabot checks for routine version updates in both npm projects and Poetry weekly. These updates
have a seven-day cooldown; security updates require prompt individual review and
are not delayed by that cooldown. This configuration does not enable GitHub's
security-update setting or enforce branch protection, and it does not enable
automatic merging. Run the checks in [the verification runbook](docs/verification-runbook.md)
before merging. See [the September 2026 dependency review](docs/security/dependabot-2026-09-16.md)
for the current fixes and remaining alerts.

## Utilities

### Collect playlist IDs on playlists page

```javascript
const playlistLinks = document.querySelectorAll('a[href^="/playlist?list="]');
const playlistIds = [];

playlistLinks.forEach((link) => {
  const href = link.getAttribute("href");

  const id = href.split("list=")[1];

  if (id) {
    playlistIds.push(id);
  }
});

console.log(playlistIds);
```

## Troubleshooting

### HTTPS redirect error

Secure Connection Failed

An error occurred during a connection to 127.0.0.1:5000. SSL received a record that exceeded the maximum permissible length.

Error code: SSL_ERROR_RX_RECORD_TOO_LONG

Ensure debug mode in on for local development to prevent redirecting to https

`flask --app project run --debug`
