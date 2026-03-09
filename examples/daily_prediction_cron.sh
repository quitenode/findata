#!/bin/bash
# Cron wrapper: generate predictions, update dashboard, commit, and push

REPO_DIR="/mnt/raid/michael/findata"
PYTHON="$REPO_DIR/findata-env/bin/python3"
PREDICTIONS_DIR="$REPO_DIR/predictions"

cd "$REPO_DIR"

# Generate prediction reports (EN/CN markdown + PDF)
$PYTHON "$REPO_DIR/examples/daily_prediction.py" "$PREDICTIONS_DIR"

# Update GitHub Pages dashboard (data.json + sync markdowns)
$PYTHON "$REPO_DIR/examples/update_dashboard.py"

# Commit and push
DATE=$(date -u +%Y-%m-%d)
git add predictions/ docs/
git commit -m "prediction: $DATE daily market report"
git push
