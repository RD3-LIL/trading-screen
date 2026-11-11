#!/bin/bash
# Trading Screen daily updater.
# Fetches free FX, commodity, macro and rates data, rebuilds index.html.
# Push step is left manual: run the GitHub push from chat and it waits
# for Ron's approval tap, same as College Ratings.
# Schedule: 6:00 AM Chicago time, same as College Ratings.
# Usage: daily_update.sh [--no-push]
set -u
cd "$(dirname "$0")" || exit 1
export TZ=America/Chicago
echo "$(date -Iseconds) trading screen daily update"
python3 fetch.py || {
  echo "fetch failed, stopping (data/prices.json keeps last good values, labeled stale)"
  exit 1
}
python3 signals.py || {
  echo "signals failed, stopping (data/signals.json keeps last good values)"
  exit 1
}
python3 build_page.py || exit 1
echo "rebuilt index.html locally, push is manual"
# Manual push, do not automate here:
# /opt/hatch/bin/github push-files --owner RD3-LIL --repo trading-screen --branch main \
#   --message "Daily update: trading screen $(date +%Y-%m-%d)" \
#   --source-dir /home/hatch/workspace/trading-screen \
#   --paths-file /home/hatch/workspace/trading-screen-push-manifest.bin
