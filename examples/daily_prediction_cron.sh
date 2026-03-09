#!/bin/bash
# Cron wrapper: generate predictions, commit, and push to GitHub

REPO_DIR="/mnt/raid/michael/findata"
PYTHON="$REPO_DIR/findata-env/bin/python3"
SCRIPT="$REPO_DIR/examples/daily_prediction.py"
PREDICTIONS_DIR="$REPO_DIR/predictions"

cd "$REPO_DIR"

$PYTHON "$SCRIPT" "$PREDICTIONS_DIR"

DATE=$(date -u +%Y-%m-%d)
git add "predictions/$DATE/"
git commit -m "prediction: $DATE daily market report"
git push
