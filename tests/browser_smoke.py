"""Exercise the real UI + FastAPI, replacing only outbound Gemini and browser audio.

Run: python tests/browser_smoke.py
Install requirements-browser.txt and Chromium first (see README).
No real credential, microphone recording or paid API is used.
"""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import threading
import time

import httpx
from playwright.sync_api import sync_playwright, expect
import uvicorn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["GEMINI_API_KEY"] = "browser-test-not-a-real-credential"
os.environ["GEMINI_MODEL"] = "gemini-3.8-flash"
import app as backend  # noqa: E402 — test environment must be set before import


def gemini_response(request):
    """Mock the provider HTTP boundary, not our application API."""
    assert request.url.host == "generativelanguage.googleapis.com"
    assert "key=" not in str(request.url)
    assert request.headers["x-goog-api-key"] == "browser-test-not-a-real-credential"
    payload = json.loads(request.content)
    properties = payload["generationConfig"]["responseSchema"]["properties"]
    last = payload["contents"][-1]["parts"][0]["text"]
    if "simular limite" in last:
        return httpx.Response(429, json={"error": {"message": "provider details omitted"}})
    if "questions" in properties:
        result = {"questions": [
            {"question": question, "answer": "Una respuesta de ejemplo."}
            for question in ("¿Cómo te llamas?", "¿De dónde eres?", "¿Qué bebes?",
                             "¿Cómo estás?", "¿Qué te gusta comer?")
        ]}
    elif "correct" in properties:
        result = {"reply": "Boa tentativa! Em espanhol: Soy de Brasil.",
                  "speech": "Soy de Brasil.", "words": [],
                  "correct": json.loads(last)["student_answer"] != "incorrecto"}
    else:
        result = {"reply": f"Você escreveu: {last}\n¿Quieres un café?",
                  "speech": "¿Quieres un café?",
                  "words": [{"spanish": "café con leche", "portuguese": "café com leite"}]}
    return httpx.Response(200, json={"candidates": [{
        "finishReason": "STOP", "content": {"parts": [{"text": json.dumps(result)}]}
    }]})


api = backend.create_app()
original_lifespan = api.router.lifespan_context


@asynccontextmanager
async def test_lifespan(application):
    async with original_lifespan(application):
        async with httpx.AsyncClient(transport=httpx.MockTransport(gemini_response)) as client:
            application.state.gemini_http = client
            yield


api.router.lifespan_context = test_lifespan

AUDIO_STUB = """
window.__utterances = [];
window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } };
Object.defineProperty(window, 'speechSynthesis', {value: {
  getVoices: () => [{lang: 'es-ES', name: 'Test voice'}],
  speak: utterance => window.__utterances.push({text: utterance.text, lang: utterance.lang}),
  cancel: () => {}
}});
window.SpeechRecognition = class {
  start() {
    this.onstart?.();
    this.onresult?.({results: [[{transcript: 'Quiero un café.'}]]});
    this.onend?.();
  }
  stop() { this.onend?.(); }
  abort() { this.onend?.(); }
};
"""


def send(page, text):
    page.locator("#message-input").fill(text)
    page.locator("#send-button").click()
    expect(page.locator("#chat-form")).to_have_attribute("aria-busy", "false")


def run_browser(url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("PROFE_BROWSER_PATH") or shutil.which("chromium"),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        context.add_init_script(AUDIO_STUB)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto(url)
        expect(page.locator("#status-text")).to_have_text("Pronto para uma boa conversa")
        page.locator("#level-select").select_option("B1")
        send(page, "Hola")
        expect(page.locator(".message.assistant").last).to_contain_text("¿Quieres un café?")
        expect(page.locator(".word-card")).to_have_count(1)
        send(page, "Más café")
        expect(page.locator(".word-card")).to_have_count(1)
        page.reload()
        expect(page.locator(".word-card")).to_have_count(1)
        print("PASS chat, nível, deduplicação e persistência do caderno")

        send(page, "Hola de nuevo")
        page.locator(".listen-button").last.click()
        utterance = page.evaluate("window.__utterances.at(-1)")
        assert utterance == {"text": "¿Quieres un café?", "lang": "es-ES"}
        expect(page.locator(".listen-button").last).to_contain_text("Parar áudio")
        page.locator(".listen-button").last.click()
        count = page.locator(".message.user").count()
        page.locator("#mic-button").click()
        expect(page.locator("#message-input")).to_have_value("Quiero un café.")
        assert page.locator(".message.user").count() == count
        print("PASS controles de voz com APIs simuladas; ditado sem envio automático")

        send(page, "simular limite")
        expect(page.locator("#error-text")).to_have_text(
            "Limite gratuito atingido, tente de novo em alguns minutos.")
        expect(page.locator("#message-input")).to_have_value("simular limite")
        assert page.locator(".message.user").count() == count
        send(page, "Agora posso tentar")
        expect(page.locator("#error-banner")).to_be_hidden()
        print("PASS 429, preservação do rascunho e nova tentativa")

        malicious = '<img src=x onerror="window.__xss=true">'
        send(page, malicious)
        expect(page.locator(".message.assistant").last).to_contain_text(malicious)
        assert page.locator("#messages img").count() == 0
        assert not page.evaluate("Boolean(window.__xss)")
        print("PASS conteúdo do usuário/modelo tratado como texto")

        page.locator("#quiz-button").click()
        expect(page.locator("#quiz-title")).to_have_text("Pergunta 1 de 5")
        expect(page.locator("#level-select")).to_be_disabled()
        send(page, "simular limite")
        expect(page.locator("#quiz-title")).to_have_text("Pergunta 1 de 5")
        for index in range(5):
            send(page, "incorrecto" if index == 2 else "Soy de Brasil")
            expect(page.locator("#quiz-title")).to_have_text(
                "¡Muy bien! Você concluiu o quiz." if index == 4
                else f"Pergunta {index + 2} de 5")
        expect(page.locator("#quiz-subtitle")).to_contain_text("4 de 5 acertos")
        expect(page.locator("#level-select")).to_be_enabled()
        print("PASS quiz integrado: cinco perguntas, correção, placar e erro sem avançar")

        page.locator("#new-chat").click()
        expect(page.locator(".message")).to_have_count(0)
        expect(page.locator(".word-card")).to_have_count(1)
        outputs = ROOT / "test-results"
        outputs.mkdir(exist_ok=True)
        page.screenshot(path=str(outputs / "desktop.png"), full_page=True)
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#open-words").click()
            expect(page.locator("#sidebar")).to_have_attribute("aria-modal", "true")
            page.keyboard.press("Escape")
            expect(page.locator("#open-words")).to_be_focused()
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_function("document.querySelector('#sidebar').getBoundingClientRect().right <= 1")
        page.screenshot(path=str(outputs / "mobile.png"), full_page=True)
        print("PASS desktop e celular (390/320 px), caderno e teclado")

        # localStorage is untrusted too, including data from older app versions.
        page.evaluate("word => localStorage.setItem('profe.words.v1', JSON.stringify([word]))",
                      {"spanish": malicious, "portuguese": "palavra de teste"})
        page.reload()
        assert page.locator("#words-list img").count() == 0
        assert not page.evaluate("Boolean(window.__xss)")
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator(".word-delete").click()
        page.reload()
        expect(page.locator(".word-card")).to_have_count(0)
        print("PASS caderno seguro e remoção persistente")

        vocabulary = [{"spanish": f"palabra {number}", "portuguese": f"palavra {number}"}
                      for number in range(300)]
        page.evaluate("words => localStorage.setItem('profe.words.v1', JSON.stringify(words))", vocabulary)
        page.reload()
        send(page, "Uma palavra nova")
        expect(page.locator(".word-card")).to_have_count(301)
        page.reload()
        expect(page.locator(".word-card")).to_have_count(301)
        saved = page.evaluate("JSON.parse(localStorage.getItem('profe.words.v1'))")
        assert all(word in saved for word in vocabulary)
        print("PASS caderno preserva palavras antigas ao ultrapassar 300 entradas")

        fallback = browser.new_context()
        fallback.add_init_script("window.SpeechRecognition=undefined; window.webkitSpeechRecognition=undefined;")
        fallback_page = fallback.new_page()
        fallback_page.goto(url)
        expect(fallback_page.locator("#mic-button")).to_be_disabled()
        expect(fallback_page.locator("#voice-note")).to_contain_text("Microfone indisponível")
        send(fallback_page, "Posso digitar")
        expect(fallback_page.locator(".message.assistant").last).to_contain_text("¿Quieres un café?")
        print("PASS chat funcional em navegador sem reconhecimento de voz")
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(api, log_level="error"))
    worker = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline or not worker.is_alive():
                raise RuntimeError("Servidor de teste não iniciou")
            time.sleep(0.05)
        run_browser(f"http://127.0.0.1:{port}")
    finally:
        server.should_exit = True
        worker.join(timeout=5)
        listener.close()
