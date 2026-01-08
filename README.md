## Running locally

### Frontend

Install dependencies
`npm i`

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

```javascript
// Find outdated packages
npm outdated

// Update to 'safe' versions of all packages
npm update

// Update to latest version of a package
npm install <packagename>@latest
```

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
