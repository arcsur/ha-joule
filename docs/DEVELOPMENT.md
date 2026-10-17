# ha-joule Developer Guide

This document outlines local development, testing workflows, release processes, and debugging for the `ha-joule` Home Assistant integration.

---

## 1. Local Testing Environment

Tests use `pytest-homeassistant-custom-component` with Python 3.12:

```bash
uv run --python 3.12 \
  --with pytest \
  --with pytest-asyncio \
  --with pytest-homeassistant-custom-component \
  --with pyserial \
  --with pyserial-asyncio \
  python -m pytest tests/ -v
```

---

## 2. Release & Deployment via HACS

When changes are made to `ha-joule`:

1. Update the dependency requirement in `custom_components/joule/manifest.json` if a new version of `joule-ble` is required:
   ```json
   "requirements": ["joule-ble>=0.1.0a15"]
   ```
2. Bump the `"version"` field in `manifest.json`.
3. Commit and push changes to `main`.
4. Create a tagged release via GitHub CLI:
   ```bash
   gh release create v0.1.13 --title "v0.1.13" --notes "Release notes here..."
   ```
5. In Home Assistant, refresh repository information and update via HACS:
   - Call HACS update information: `ha_manage_hacs(action="update_information", repository_id="arcsur/ha-joule")`
   - Download the new release: `ha_manage_hacs(action="download", repository_id="arcsur/ha-joule", version="v0.1.13")`
   - Restart Home Assistant: `ha_restart(confirm=True)`

---

## 3. Debugging Live Bluetooth Traffic

To view detailed stream exchanges and Protobuf message bytes in Home Assistant logs:

```yaml
# In Home Assistant configuration.yaml or via service call logger.set_level:
logger:
  default: warning
  logs:
    custom_components.joule: debug
    joule_ble: debug
```
