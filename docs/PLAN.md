# Profe — plano de implementação

## Brainstorming

Um brasileiro iniciante precisa praticar sem ser sobrecarregado. O Profe será uma
conversa acolhedora: português para explicar, espanhol para praticar. A tela tem
fundo claro, detalhes em terracota e verde, tipografia legível, atalhos para temas
do cotidiano e controles grandes no celular. O caderno guarda palavras no próprio
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

Os plugins Adobe, GitHub, Canva, Superpowers e Writing Style não estão disponíveis
nesta sessão. O trabalho usa Git local e o fluxo descrito acima. Sem uma chave
Gemini configurada, as chamadas ao provedor são simuladas nos testes; o app real
informa a configuração ausente. Nenhuma resposta simulada entra no produto.

