#!/bin/sh
# Start Hivemind (backend :5001 + frontend :3000) on this Mac.
# Uses nvm's Node 22 because Vite 7 needs Node >= 20.19 and the default node here is 20.12.
set -e
cd "$(dirname "$0")"

NODE22="$(ls -d "$HOME"/.nvm/versions/node/v22.* 2>/dev/null | tail -1)"
[ -n "$NODE22" ] && PATH="$NODE22/bin:$PATH" && export PATH

# First run: create .env from the template so there is one obvious file to edit.
[ -f .env ] || cp .env.example .env

if grep -q -E '^(LLM_API_KEY|ZEP_API_KEY)=(your_.*)?$' .env; then
  cat >&2 <<EOF
Hivemind needs two keys before it can run. Open $(pwd)/.env and set:

  LLM_API_KEY   your Anthropic key   https://console.anthropic.com/  (API keys)
  ZEP_API_KEY   your Zep Cloud key   https://app.getzep.com/         (free tier is enough)

Then run ./hivemind.sh again. .env is gitignored; your keys are never committed.
EOF
  exit 1
fi

[ -d node_modules ] && [ -d frontend/node_modules ] || npm run setup
[ -d backend/.venv ] || (cd backend && uv sync)

echo "Hivemind: frontend http://localhost:3000  backend http://127.0.0.1:5001"
exec npm run dev
