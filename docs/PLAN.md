# Profe — plano de implementação

## Brainstorming

Um brasileiro iniciante precisa praticar sem ser sobrecarregado. O Profe será uma
conversa acolhedora: português para explicar, espanhol para praticar. A referência
visual enviada pelo usuário em `Tela principal-html.zip` foi aprovada: fundo
escuro, destaques amarelos, verdes, corais e roxos, tipografia legível e controles
grandes no celular. O layout tem navegação, conversa e caderno; no celular, o
caderno abre em um painel. O HTML exportado serve de referência visual, sem
adicionar seu runtime React à aplicação. O caderno guarda palavras no próprio
navegador; nenhuma conta é necessária.

A voz usa apenas as APIs gratuitas do navegador. A síntese lê uma versão em
espanhol da resposta; o reconhecimento preenche a caixa de mensagem e permite
revisar antes de enviar. A disponibilidade depende do navegador e das vozes do
sistema. O quiz apresenta cinco perguntas curtas, uma de cada vez, com correção e
progresso controlado no servidor.

## Plano curto e responsabilidades

1. Fixar `docs/API.md` e criar `.gitignore` antes do primeiro commit de trabalho.
2. Backend: agente em `feature/profe-backend`, worktree independente, FastAPI,
   Gemini via HTTPS, configuração `.env`, quiz e testes de erros/segurança.
3. Frontend: agente em `feature/profe-frontend`, worktree independente, único
   `index.html` com CSS/JS, chat, níveis, quiz, voz e palavras no localStorage.
4. Integrar, exercitar HTTP e navegador em desktop/celular e pedir revisão a um
   terceiro agente. Corrigir problemas, conferir segredos e fazer commit local.

## Limites de validação

Adobe, GitHub, Canva e Writing Style não foram expostos no catálogo da sessão.
As skills Superpowers ficaram disponíveis aos agentes delegados e foram usadas
para orientar testes e verificação. O trabalho usa Git local. Sem uma chave
Gemini configurada, as chamadas ao provedor são simuladas nos testes; o app real
informa a configuração ausente. Nenhuma resposta simulada entra no produto.

O modelo padrão foi atualizado para `gemini-3.8-flash` após consulta ao
[guia oficial do Google](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_Generate_Content.ipynb).
A tabela de preços requer acesso a `ai.google.dev`, salvo no rascunho da rede.
O modelo permanece configurável em `.env`; nenhuma cota real foi consumida.

