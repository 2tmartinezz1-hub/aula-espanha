#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "${1:-}" != "" && "${1:-}" != "--dev" ]]; then
  echo "Uso: bash scripts/setup.sh [--dev]" >&2
  exit 2
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
requirements=requirements.txt
if [[ "${1:-}" == "--dev" ]]; then
  requirements=requirements-dev.txt
fi
.venv/bin/python -m pip install --disable-pip-version-check -r "$requirements"
.venv/bin/python - <<'PY'
from pathlib import Path

target = Path('.env')
if not target.exists():
    with target.open('x', encoding='utf-8') as stream:
        stream.write(Path('.env.example').read_text(encoding='utf-8'))
    target.chmod(0o600)
    print('.env criado com chave vazia. Preencha GEMINI_API_KEY localmente.')
else:
    print('.env existente preservado.')
PY
echo "Instalação concluída. Inicie: .venv/bin/python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000"
