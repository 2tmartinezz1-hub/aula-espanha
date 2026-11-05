# Validação do Profe

Verificação concluída em 2026-11-05 no Python 3.12 e Chromium 155.

- `.venv/bin/python -m pytest -q`: **31 testes passaram**.
- `.venv/bin/python tests/browser_smoke.py`: **9 grupos de verificações passaram**
  usando a interface e o FastAPI reais, substituindo somente o HTTP do Gemini e
  as APIs de áudio do navegador.
- Fluxos: chat e níveis, persistência/deduplicação, ouvir/ditar, erro 429 e nova
  tentativa, texto seguro, cinco perguntas com pontuação, desktop/celular
  (390/320 px), remoção de palavras, preservação de 301 entradas após recarregar
  e funcionamento sem reconhecimento de voz.
- HTTP real sem chave: `/api/health` retornou 200 com `configured:false`; chat
  retornou 503 com orientação em português. `.env`, `.git/config` e `app.py`
  retornaram 404.
- `scripts/setup.sh --dev` foi executado a partir de outra pasta e repetido,
  preservando o `.env` existente.
- Revisão independente de código e segurança concluída. A perda silenciosa de
  palavras acima de 300 foi reproduzida e corrigida no commit `4f92497`; o teste
  de regressão falhou antes da correção e passou depois.
- `.env` ignorado desde o primeiro commit de implementação; chave vazia no
  `.env.example`; nenhuma credencial real identificada no código/histórico.

## Limites

A chave Gemini não foi fornecida. A conexão real com o provedor, qualidade das
respostas, disponibilidade do modelo e cota gratuita da conta não foram
verificadas. O modelo padrão segue o guia oficial do Google e pode ser trocado
em `GEMINI_MODEL`.

A lógica de voz passou com APIs simuladas. Microfone físico, áudio audível e
vozes instaladas precisam ser conferidos no navegador do usuário.

As instruções de instalação/inicialização e os domínios do Google foram salvos
no rascunho da nuvem. Isso não publica nem aplica a configuração: a publicação
e a restauração em uma nova tarefa não foram verificadas.
