#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -x "$repo_root/.venv/bin/uvicorn" ]]; then
  echo "尚未安装本地API依赖。请先按README执行一次安装命令。"
  exit 1
fi

if [[ ! -d "$repo_root/apps/web/node_modules" ]]; then
  echo "尚未安装页面依赖。请先按README执行一次安装命令。"
  exit 1
fi

cleanup() {
  [[ -n "${api_pid:-}" ]] && kill "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$repo_root"
uvicorn_args=(services.api.app.main:app --port 8000)
if [[ -f "$repo_root/.env" ]]; then
  uvicorn_args+=(--env-file "$repo_root/.env")
fi
"$repo_root/.venv/bin/uvicorn" "${uvicorn_args[@]}" &
api_pid=$!

cd "$repo_root/apps/web"
npm run dev
