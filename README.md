## Upgrading dependencies

### Python dependencies
Based on workflow from Ken Reitz ( [link](https://kenreitz.org/essays/a-better-pip-workflow) )
```python
# Upgrade core packages
pip install -r requirements-to-freeze.txt --upgrade

# Freeze dependencies to ensure consistent build in prod
pip freeze > requirements.txt
```