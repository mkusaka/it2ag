#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Syncing release dependencies"
uv sync --group release --locked

echo "==> Building app directory"
rm -rf ./build/it2ag ./dist/it2ag
uv run pyinstaller --clean --noconfirm it2ag.spec

echo "==> Running smoke tests"
test -x ./dist/it2ag/it2ag
test -d ./dist/it2ag/_internal
./dist/it2ag/it2ag --help >/dev/null
./dist/it2ag/it2ag --version

echo "==> Built app directory: $ROOT_DIR/dist/it2ag"
