#!/usr/bin/env bash
set -euo pipefail

skip_openclaw_install=0
for arg in "$@"; do
  case "$arg" in
    --skip-openclaw-install)
      skip_openclaw_install=1
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: ./scripts/install.sh [--skip-openclaw-install]" >&2
      exit 2
      ;;
  esac
done

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "==> Install Python CLI"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
./.venv/bin/python -m pip install -e .
./.venv/bin/ci-defect-assistant init
./.venv/bin/ci-defect-assistant doctor

echo "==> Validate OpenClaw plugin"
(
  cd openclaw-plugin
  npm install
  npm run plugin:validate
)

if [ "$skip_openclaw_install" -eq 0 ]; then
  echo "==> Install OpenClaw plugin"
  openclaw plugins install --link ./openclaw-plugin --dangerously-force-unsafe-install
  openclaw gateway restart
  openclaw plugins inspect openclaw-ci-defect-assistant
  openclaw plugins doctor
fi

echo "==> Done"
