# Profe · espanhol, um pouquinho por dia

App web local para brasileiros que estão começando a aprender espanhol. Backend
em Python/FastAPI, interface em um único `index.html` e professor com Google
Gemini. Sem cadastro, banco de dados ou etapa de build do frontend.

- Conversa com explicações em português e prática em espanhol, nos níveis A1, A2 e B1.
- Quiz de cinco perguntas, uma por vez, com correção e pontuação.
- Botão para ouvir em espanhol e microfone para ditar uma mensagem.
- Caderno de palavras com tradução, salvo neste navegador.
- Mensagem clara quando a cota gratuita é atingida.

## Rodar no seu computador

Requer Python 3.10 ou superior (validado com Python 3.12) e conexão com a internet
para conversar com o Gemini. Abra o terminal na pasta do projeto.

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Também é possível usar `bash scripts/setup.sh`, que instala as dependências e
cria o `.env` somente se ele não existir.

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

### Configurar o Gemini

Crie uma chave no [Google AI Studio](https://aistudio.google.com/apikey). Abra o
arquivo **`.env` local** e preencha `GEMINI_API_KEY`. O arquivo de exemplo tem a
chave vazia de propósito. Não coloque a chave em `index.html`, mensagens de chat,
commits ou arquivos compartilhados.

O modelo padrão é `gemini-3.8-flash`, recomendado no
[guia oficial do Google](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_Generate_Content.ipynb);
você pode trocá-lo em `GEMINI_MODEL`. Escolha
um modelo Flash disponível na coluna gratuita da
[tabela oficial de preços](https://ai.google.dev/gemini-api/docs/pricing).
A oferta gratuita, disponibilidade regional e cotas são definidas pelo Google e
podem mudar. Reinicie o servidor depois de editar o `.env`.

O `.env` já é ignorado pelo Git. Variáveis de ambiente existentes têm prioridade
sobre o arquivo. O backend usa a chave apenas no cabeçalho HTTPS enviado ao Google;
o navegador recebe somente as respostas da aplicação.

### Iniciar

Linux/macOS, com o ambiente virtual ativado:

```bash
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Abra `http://localhost:8000` no navegador. Não abra o HTML diretamente pelo
gerenciador de arquivos: ele precisa do backend. Use `Ctrl+C` para encerrar.

## Como estudar

Escolha o nível, escreva uma mensagem ou use uma sugestão de conversa. O professor
explica em português, corrige seu espanhol e termina com uma pergunta para praticar.
As palavras ensinadas vão para o caderno. Elas ficam neste navegador e podem ser
removidas; limpar os dados do site também apaga o caderno.

O botão **Quiz** começa cinco perguntas. O nível fica fixo durante a atividade.
Responda uma por vez para receber a correção. O progresso do quiz fica na memória
do servidor por até uma hora de inatividade; use apenas um worker do Uvicorn.
Reiniciar o servidor ou deixar a sessão expirar exige iniciar outro.
O histórico da conversa fica na memória da página e desaparece ao recarregar.

## Voz

O botão **Ouvir** lê a parte em espanhol da resposta com `speechSynthesis`.
Escolha/instale uma voz espanhola nas configurações do sistema se necessário.
O botão pode interromper a leitura. Não é usada uma API paga de áudio.

O **microfone** usa `SpeechRecognition`/`webkitSpeechRecognition`, com idioma
espanhol. Permita o acesso ao microfone; a transcrição vai ao campo para você
revisar e enviar. Chrome/Edge costumam oferecer esse recurso; o suporte varia
por navegador, versão e sistema. O app informa quando não há suporte.

O microfone precisa de contexto seguro: `localhost` no computador ou HTTPS.
Abrir um endereço HTTP da rede local no celular pode bloquear esse recurso. A
interface se adapta ao celular, mas o servidor deve ser disponibilizado em HTTPS
para usar o microfone fora do computador. Este projeto é configurado para uso
local; não inclui autenticação ou publicação na internet.

Alguns navegadores enviam áudio ao serviço de reconhecimento do próprio
fornecedor e precisam de internet. O backend do Profe não recebe áudio; recebe
apenas a transcrição quando você clica em enviar.

## Verificação e testes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes do backend simulam a API Gemini para validar o contrato, sequência do
quiz, falhas e proteção da chave sem consumir cota. Não substituem uma chamada
real com a sua chave. O endpoint `GET /api/health` indica se a chave está presente;
ele não verifica se a chave é válida ou se há cota.

Para testar a interface integrada ao FastAPI em um Chromium automatizado:

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python tests/browser_smoke.py
```

Esse teste usa o backend real, substitui apenas a chamada HTTPS ao Gemini e
simula as APIs de áudio do navegador. Verifica chat, cinco perguntas, erros,
caderno, texto seguro e layout em desktop/celular. Não grava áudio e não comprova
o funcionamento de um microfone físico. Usa Chromium do sistema quando disponível;
`PROFE_BROWSER_PATH` permite indicar outro executável. As capturas ficam em
`test-results/` (ignorado pelo Git).

Em caso de HTTP 429, a interface mostra exatamente:

> Limite gratuito atingido, tente de novo em alguns minutos.

Se a configuração estiver ausente, o app orienta a preencher `.env`. Se o modelo
ou a chave forem rejeitados, confira ambos no AI Studio. Erros do provedor são
convertidos em mensagens seguras em português.

Em ambientes de nuvem com saída de rede restrita, autorize
`generativelanguage.googleapis.com` para chamadas Gemini. A instalação usa
`pypi.org` e `files.pythonhosted.org`.

## Estrutura

```text
app.py                  API, configuração e comunicação com o Gemini
index.html              interface, voz e caderno local
.env.example            nomes das configurações, sem chave
requirements.txt        dependências da aplicação
requirements-dev.txt    dependências dos testes
requirements-browser.txt  dependências opcionais dos testes de navegador
scripts/setup.sh        instalação repetível em Linux/macOS
tests/                  testes do backend
docs/API.md             contrato JSON das rotas
docs/PLAN.md             brainstorming e plano de trabalho
```

Apenas o `index.html` é servido como arquivo. `.env`, código Python e metadados Git
não são disponibilizados pelo servidor HTTP.
