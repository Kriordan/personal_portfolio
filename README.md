## Upgrading dependencies

### Python dependencies
Based on workflow from Ken Reitz ( [link](https://kenreitz.org/essays/a-better-pip-workflow) )
```python
# Upgrade core packages
pip install -r requirements-to-freeze.txt --upgrade

# Freeze dependencies to ensure consistent build in prod
pip freeze > requirements.txt
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