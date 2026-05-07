# RESTORE INSTRUCTIONS

This folder contains a stable version of the Trading Analyzer (v3.5) created on 2026-04-24.

To restore:
1. Delete the current `app.py` in the root directory.
2. Copy `backups/app_stable_v3_5.py` to the root directory and rename it to `app.py`.
3. If dependencies changed, run: `pip install -r backups/requirements_backup.txt`

Current features in this version:
- Fixed yfinance 429 errors (Batch Fetch & Retries)
- Fixed AI analysis JSON parsing & Manual Key Override
- Fixed UI/CSS to original stable design
- Market Status Indicators (Header)
