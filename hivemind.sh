#!/bin/sh
# Start Hivemind (backend :5001 + frontend :3000) on this Mac.
# Uses nvm's Node 22 because Vite 7 needs Node >= 20.19 and the default node here is 20.12.
set -e
cd "$(dirname "$0")"

NODE22="$(ls -d "$HOME"/.nvm/versions/node/v22.* 2>/dev/null | tail -1)"
[ -n "$NODE22" ] && PATH="$NODE22/bin:$PATH" && export PATH

if ! grep -q '^LLM_API_KEY=..*' .env 2>/dev/null || ! grep -q '^ZEP_API_KEY=..*' .env 2>/dev/null; then
  echo "Fill in LLM_API_KEY and ZEP_API_KEY in $(pwd)/.env first." >&2
  exit 1
fi

[ -d node_modules ] && [ -d frontend/node_modules ] || npm run setup
[ -d backend/.venv ] || (cd backend && uv sync)

echo "Hivemind: frontend http://localhost:3000  backend http://127.0.0.1:5001"
exec npm run dev
