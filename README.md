## Upgrading dependencies
```python
# Upgrade core packages
pip install -r requirements-to-freeze.txt --upgrade

# Freeze dependencies to ensure consistent build in prod
pip freeze > requirements.txt
```