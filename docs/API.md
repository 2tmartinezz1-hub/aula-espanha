# Contrato da API — Profe (v1)

Mesma origem: o FastAPI serve `GET /` (somente `index.html`) e `/api/*`. Todas as
rotas POST recebem e retornam JSON. Nunca enviar uma chave ao navegador. Não
publicar o diretório do repositório como arquivos estáticos.

## Saúde

`GET /api/health` → 200:

```json
{"status":"ok","configured":false,"model":"gemini-2.5-flash"}
```

`configured` indica apenas presença da chave no servidor, sem validar acesso.

## Conversa

`POST /api/chat`:

```json
{"level":"A1","messages":[{"role":"user","content":"Como peço um café?"}]}
```

Níveis: `A1`, `A2`, `B1`. Histórico de 1 a 30 mensagens; roles `user` e `assistant`;
última mensagem deve ser do usuário. Cada conteúdo tem 1 a 2000 caracteres úteis.
O frontend corta o histórico antigo preservando o turno atual. O backend mantém
o system prompt fixo, fora do histórico fornecido pelo cliente.

Resposta comum (200):

```json
{
  "reply":"Diga: Un café, por favor.\n¿Lo quieres con leche?",
  "speech":"Un café, por favor. ¿Lo quieres con leche?",
  "words":[{"spanish":"café con leche","portuguese":"café com leite"}],
  "quiz":null
}
```

`reply` é texto simples, com até seis linhas. `speech` é texto em espanhol para
síntese de voz, sem SSML ou HTML. `words` tem até cinco palavras/expressões novas
com tradução. O cliente usa textContent, nunca HTML retornado pelo modelo.

## Quiz

`POST /api/quiz/start` com `{"level":"A1"}` inicia um quiz independente na memória
do servidor. Retorna a resposta comum e:

```json
{"id":"uuid-opaco","question_number":1,"total":5,"complete":false,"score":0}
```

Esse objeto vai no campo `quiz`; `reply` contém a primeira pergunta. As próximas
perguntas aparecem apenas depois de corrigir a resposta anterior. O nível fica
fixo durante o quiz; o frontend desabilita a troca até concluir ou sair do quiz.

`POST /api/quiz/answer`:

```json
{"quiz_id":"uuid-opaco","question_number":1,"answer":"Un café, por favor."}
```

Retorna correção curta e a próxima pergunta em `reply`; incrementa
`question_number`. Após a quinta resposta retorna `complete:true`,
`question_number:5` e `score` final (0–5), sem sexta pergunta avaliativa. O
backend valida a posição esperada (409 em repetição/atraso), aplica expiração e
limite de sessões e não avança o estado se o Gemini falhar. Quiz desaparece ao
reiniciar o servidor. Respostas têm 1 a 2000 caracteres úteis.

## Erros

Formato uniforme:

```json
{"error":{"code":"rate_limited","message":"Limite gratuito atingido, tente de novo em alguns minutos."}}
```

Status/códigos: `422 invalid_request`; `503 missing_api_key`; `429 rate_limited`;
`502 provider_error` ou `invalid_response`; `504 provider_timeout`;
`404 quiz_not_found`; `409 quiz_conflict`; `503 quiz_capacity`.

Erros nunca devolvem corpos brutos do provedor, cabeçalhos, URLs com credenciais
ou exceções. O cliente mantém o rascunho em falhas, permite tentar novamente e
anuncia o erro em português. Não há retentativa automática que consuma a cota.

## Voz e armazenamento

Síntese: SpeechSynthesisUtterance com `lang=es-ES`, botão ouvir/parar por resposta.
Reconhecimento: SpeechRecognition ou webkitSpeechRecognition com `lang=es-ES`;
transcrição vai ao campo, sem envio automático. A voz depende do suporte do
navegador, permissão do microfone e contexto localhost/HTTPS. Sem suporte, mostrar
explicação e manter chat digitado operacional.

Palavras são persistidas via localStorage com deduplicação sem diferença entre
maiúsculas/minúsculas, remoção individual e estado vazio. Falhas de armazenamento
não devem impedir a conversa. Nenhuma credencial é armazenada no navegador.
