## Running locally

### Frontend

The frontend uses gulp to watch the less files and compile them to css.

[gulp-less](https://github.com/gulp-community/gulp-less)

To run gulp:
`gulp`

### Backend

The backend is a Flask app.
Ensure the virtual environment is active, then run:
`flask --app project --debug`

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
