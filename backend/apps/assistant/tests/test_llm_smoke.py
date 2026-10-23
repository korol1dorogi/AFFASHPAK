"""AI19: the provider smoke against a fake OpenAI-compatible server (no network, no key)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from apps.assistant.llm import smoke

KEY = "fake-key-for-the-smoke-test"


def _server(behaviour: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get("Authorization") != f"Bearer {KEY}":
                return self._send(401, {"error": {"message": "invalid key"}})
            self._send(200, {"data": [{"id": "good"}, {"id": "chatty"}, {"id": "limited"}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            behaviour.setdefault("requests", []).append(body)
            model = body["model"]
            if model == "limited":
                return self._send(429, {"error": {"message": "rate limit"}})
            if model == "chatty":
                message = {"role": "assistant", "content": "Платёж около 94 тысяч."}
            else:
                arguments = {"principal": "1000000", "annual_rate": "0.24", "term_months": 12}
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "calc_payment",
                                # arguments as a string, as the API sends them
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            self._send(200, {"choices": [{"index": 0, "message": message}]})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def fake():
    behaviour: dict = {}
    server = _server(behaviour)
    behaviour["url"] = f"http://127.0.0.1:{server.server_address[1]}/v1"
    yield behaviour
    server.shutdown()


def _run(env: dict) -> tuple[int, str]:
    lines: list[str] = []
    code = smoke.run(env, out=lines.append)
    return code, "\n".join(lines)


def test_a_working_model_is_ready(fake):
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_BASE_URL": fake["url"],
        "LLM_API_KEY": KEY,
        "LLM_MODEL": "good",
    }
    code, output = _run(env)
    assert code == 0, output
    assert "✓ good" in output and "готово" in output
    assert KEY not in output  # the key is never printed
    request = fake["requests"][0]
    assert request["tools"][0]["function"]["name"] == "calc_payment"


def test_each_model_is_checked_and_problems_are_named(fake):
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_BASE_URL": fake["url"] + "/",
        "LLM_API_KEY": KEY,
        "LLM_MODEL": "good, chatty, limited",
    }
    code, output = _run(env)
    assert code == 1, output
    assert "✗ chatty: модель ответила текстом и не вызвала инструмент" in output
    assert "✗ limited: лимит запросов" in output
    assert "частично: работают 1 из 3" in output


def test_a_wrong_key_stops_at_once(fake):
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_BASE_URL": fake["url"],
        "LLM_API_KEY": "wrong",
        "LLM_MODEL": "good",
    }
    code, output = _run(env)
    assert code == 2
    assert "ключ не подходит" in output
    assert "wrong" not in output


def test_nothing_configured_says_what_to_set():
    code, output = _run({})
    assert code == 2
    assert "LLM_BASE_URL и LLM_MODEL" in output


def test_an_unreachable_provider_is_named():
    env = {"LLM_BASE_URL": "http://127.0.0.1:9/v1", "LLM_MODEL": "x", "LLM_TIMEOUT_SECONDS": "2"}
    code, output = _run(env)
    assert code == 2
    assert "не удалось подключиться" in output
    assert "заглушкой" in output  # LLM_PROVIDER is not openai
