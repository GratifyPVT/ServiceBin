#!/usr/bin/env bash
# Check GitHub for updates on service start. Pull only if remote is ahead.
# Exits 0 even on soft failures so dependent services still start.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REMOTE_NAME="${GRATIFY_GIT_REMOTE:-origin}"
BRANCH="${GRATIFY_GIT_BRANCH:-}"

cd "$REPO_ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "git not found — skipping update"
  exit 0
fi

if [[ ! -d .git ]]; then
  echo "Not a git repo — skipping update"
  exit 0
fi

if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
fi
if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
  BRANCH="main"
fi

echo "Checking GitHub for updates ($REMOTE_NAME/$BRANCH)..."

if ! git fetch --quiet "$REMOTE_NAME" "$BRANCH" 2>/tmp/gratify-git-fetch.err; then
  echo "Fetch failed — keeping current code"
  cat /tmp/gratify-git-fetch.err 2>/dev/null || true
  exit 0
fi

REMOTE_REF="$REMOTE_NAME/$BRANCH"
if ! git rev-parse --verify --quiet "$REMOTE_REF" >/dev/null; then
  echo "Remote branch $REMOTE_REF not found — skipping update"
  exit 0
fi

LOCAL_HASH="$(git rev-parse HEAD)"
REMOTE_HASH="$(git rev-parse "$REMOTE_REF")"

if [[ "$LOCAL_HASH" == "$REMOTE_HASH" ]]; then
  echo "Already up to date — no changes"
  exit 0
fi

# Only auto-update when we can fast-forward (local is ancestor of remote)
if ! git merge-base --is-ancestor HEAD "$REMOTE_REF"; then
  echo "Local branch has diverged from $REMOTE_REF — skipping auto-update"
  echo "  local:  $LOCAL_HASH"
  echo "  remote: $REMOTE_HASH"
  exit 0
fi

echo "Updates found — pulling..."
if git pull --ff-only "$REMOTE_NAME" "$BRANCH"; then
  echo "Updated to $(git rev-parse --short HEAD)"
else
  echo "Pull failed (dirty working tree or conflict) — keeping current code"
fi

exit 0
