# Documentation screenshots

These images show the actual app rendered with [the synthetic demo profile](../demo-profile.json). All account levels, ship builds, officer ranks and stats in that fixture are invented for illustration. They are not an imported player account or reliable in-game base values. Real public officer/ship names are used to demonstrate the interface. The recommendation example also uses manually entered target health of 300,000 and damage per round of 5,000; these are synthetic inputs, not measured Gorn Hunter stats.

Google Sheet syncing is disconnected during capture. There are no private sheet URLs, login details, browser account names or live player records in these images.

## Reproduce

From the repository root, using your development environment:

```sh
python -m pip install playwright
python -m playwright install chromium
python tools/capture_screenshots.py
```

The script launches its own server on an unused loopback port with a temporary data directory, captures six images, and shuts down that server. It also checks ship/account edits and mobile overflow using the temporary account. Your regular account and running app are unaffected. `STFC_SCREENSHOT_BROWSER` can point to an existing Chromium executable instead of downloading one.

| Image | View |
| --- | --- |
| `planner.png` | Mission planner and target briefing |
| `recommendations.png` | An actual generated recommendation using the demo values |
| `fleet.png` | Three illustrative owned ships |
| `roster.png` | Synthetic officer ranks and stats |
| `account.png` | Research controls and disconnected sheet syncing |
| `mobile-planner.png` | Mission planner at a 390-pixel mobile viewport |

Only these named images and this file are allowed through `.gitignore`. Review the rendered files before staging them; do not rename a private screenshot into the allowlist.
