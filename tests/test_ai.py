"""Tests for the AI director: Gemini request shape, recipe validation, error mapping.

The real Gemini API is never called — a local mock stands in for it, so these
tests run offline and deterministically:

    python3 -m unittest discover -s tests -v
"""

import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai  # noqa: E402
import server  # noqa: E402

GOOD_RECIPE = {
    "reply": "Взял тёмный синтвейв в ми миноре.",
    "title": "Ночная поездка",
    "apply": True,
    "seed": "night-drive",
    "style": "synthwave",
    "mood": "dark",
    "key": 9,
    "scale": "minor",
    "bpm": 100,
    "duration": 90,
    "harmonicRhythm": 1,
    "progressionA": [0, 5, 2, 6],
    "progressionB": [0, 3, 4, 0],
    "notes": "i–VI–III–VII",
}

SCALES = ["major", "minor", "harmonic", "dorian", "phrygian", "lydian", "mixolydian"]


def gemini_body(recipe=None):
    """Wrap a recipe the way the REST API does."""
    payload = recipe if recipe is not None else GOOD_RECIPE
    return {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]},
             "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 80},
    }


class MockGemini:
    """A tiny stand-in for generativelanguage.googleapis.com."""

    def __init__(self, handler=None):
        self.calls = []
        self.model_list = [{"name": "models/gemini-test-flash",
                            "supportedGenerationMethods": ["generateContent"]}]
        self.handler = handler or (lambda path, body, n: (200, gemini_body()))
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                outer.calls.append(("GET", self.path, None))
                self._json(200, {"models": outer.model_list})

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.calls.append(("POST", self.path, body))
                status, payload = outer.handler(self.path, body, len(outer.calls))
                self._json(status, payload)

            def _json(self, status, payload):
                raw = json.dumps(payload, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}/v1beta"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class GeminiTestBase(unittest.TestCase):
    def setUp(self):
        self.gemini = MockGemini()
        self.addCleanup(self.gemini.stop)

    def config(self, **overrides):
        env = {"GEMINI_API_KEY": "test-key", "GEMINI_BASE_URL": self.gemini.base_url,
               "GEMINI_MODEL": "gemini-test"}
        env.update(overrides)
        return ai.Config(env=env)

    def ask(self, text="тёмный синтвейв, ми миноре", current=None, config=None):
        return ai.chat([{"role": "user", "text": text}], current, config or self.config())


class TestRecipeNormalisation(unittest.TestCase):
    def test_clean_recipe_passes_through(self):
        r = ai.normalise_recipe(GOOD_RECIPE)
        self.assertEqual(r["style"], "synthwave")
        self.assertEqual(r["key"], 9)
        self.assertEqual(r["bpm"], 100)
        self.assertEqual(r["progressionA"], [0, 5, 2, 6])
        self.assertTrue(r["apply"])

    def test_clamps_out_of_range_values(self):
        r = ai.normalise_recipe({**GOOD_RECIPE, "key": 99, "bpm": 5000, "duration": 40})
        self.assertEqual(r["key"], 3)            # 99 % 12
        self.assertEqual(r["bpm"], 150)          # capped
        self.assertEqual(r["duration"], 30)      # nearest allowed

    def test_rejects_unknown_enums_and_bad_progressions(self):
        r = ai.normalise_recipe({
            **GOOD_RECIPE,
            "style": "dub",
            "mood": "melancholic",
            "scale": "blues",
            "progressionA": [0, 9, 42],
            "progressionB": "i-VI",
        })
        self.assertEqual(r["style"], "lofi")
        self.assertEqual(r["mood"], "dreamy")
        self.assertIn(r["scale"], SCALES)
        self.assertTrue(all(0 <= d <= 6 for d in r["progressionA"]))
        self.assertTrue(all(0 <= d <= 6 for d in r["progressionB"]))

    def test_bpm_zero_means_auto(self):
        self.assertEqual(ai.normalise_recipe({**GOOD_RECIPE, "bpm": 0})["bpm"], 0)

    def test_identical_progressions_are_differentiated(self):
        r = ai.normalise_recipe({**GOOD_RECIPE, "progressionA": [0, 5, 2, 6],
                                 "progressionB": [0, 5, 2, 6]})
        self.assertNotEqual(r["progressionA"], r["progressionB"])

    def test_inherits_from_current_when_field_missing(self):
        current = {"recipe": {"style": "techno", "mood": "epic", "scale": "phrygian",
                              "key": 4, "bpm": 132, "duration": 60, "seed": "old"}}
        r = ai.normalise_recipe({"reply": "ок"}, current)
        self.assertEqual(r["style"], "techno")
        self.assertEqual(r["scale"], "phrygian")
        self.assertEqual(r["seed"], "old")

    def test_garbage_input_still_yields_a_valid_recipe(self):
        r = ai.normalise_recipe("not a dict")
        self.assertIn(r["style"], ai.STYLES)
        self.assertIn(r["scale"], SCALES)
        self.assertTrue(r["progressionA"])


class TestGeminiCall(GeminiTestBase):
    def test_returns_recipe_and_usage(self):
        res = self.ask()
        self.assertEqual(res["recipe"]["title"], "Ночная поездка")
        self.assertEqual(res["model"], "gemini-test")
        self.assertEqual(res["usage"]["outputTokens"], 80)

    def test_request_shape(self):
        self.ask()
        method, path, body = self.gemini.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("models/gemini-test:generateContent", path)
        self.assertIn("key=test-key", path)
        self.assertIn("systemInstruction", body)
        self.assertIn("дирижёр", body["systemInstruction"]["parts"][0]["text"])
        gen = body["generationConfig"]
        self.assertEqual(gen["responseMimeType"], "application/json")
        self.assertEqual(gen["responseSchema"]["type"], "OBJECT")
        self.assertIn("progressionA", gen["responseSchema"]["properties"])
        self.assertEqual(body["contents"][0]["role"], "user")

    def test_conversation_roles_and_state_block(self):
        msgs = [{"role": "user", "text": "привет"},
                {"role": "model", "text": "привет! что сделаем?"},
                {"role": "user", "text": "сделай темнее"}]
        ai.chat(msgs, {"recipe": {"style": "lofi", "mood": "dreamy", "seed": "s1", "key": 2}},
                self.config())
        body = self.gemini.calls[0][2]
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model", "user"])
        self.assertIn("Сейчас в генераторе", body["contents"][-1]["parts"][0]["text"])
        self.assertTrue(body["contents"][-1]["parts"][0]["text"].startswith("сделай темнее"))

    def test_history_is_capped(self):
        msgs = [{"role": "user", "text": f"сообщение {i}"} for i in range(30)]
        ai.chat(msgs, None, self.config())
        self.assertLessEqual(len(self.gemini.calls[0][2]["contents"]), ai.MAX_HISTORY)

    def test_model_discovery_after_404(self):
        self.gemini.handler = lambda path, body, n: (
            (404, {"error": {"message": "models/gemini-test is not found"}}) if n == 1
            else (200, gemini_body()))
        res = self.ask()
        self.assertEqual(res["model"], "gemini-test-flash")
        self.assertEqual(len(self.gemini.calls), 3)  # 404, list models, retry

    def test_retries_without_schema_when_config_rejected(self):
        self.gemini.handler = lambda path, body, n: (
            (400, {"error": {"message": "Invalid value at 'generation_config.response_schema'"}})
            if n == 1 else (200, gemini_body()))

        res = self.ask()
        self.assertEqual(res["recipe"]["style"], "synthwave")
        retry = self.gemini.calls[1][2]
        self.assertNotIn("responseSchema", retry["generationConfig"])
        self.assertNotIn("safetySettings", retry)
        self.assertIn("systemInstruction", retry)  # contract is kept

    def test_api_key_in_url_only(self):
        self.ask()
        self.assertNotIn("test-key", json.dumps(self.gemini.calls[0][2]))


class TestErrorMapping(GeminiTestBase):
    def _expect(self, status, payload, code, http_status=None):
        self.gemini.handler = lambda p, b, n: (status, payload)
        with self.assertRaises(ai.DirectorError) as ctx:
            self.ask()
        self.assertEqual(ctx.exception.code, code)
        if http_status:
            self.assertEqual(ctx.exception.status, http_status)

    def test_bad_key(self):
        self._expect(400, {"error": {"message": "API key not valid. Please pass a valid API key."}},
                     "bad_key", 401)

    def test_forbidden(self):
        self._expect(403, {"error": {"message": "Permission denied"}}, "bad_key", 401)

    def test_quota(self):
        self._expect(429, {"error": {"message": "Resource exhausted"}}, "quota", 429)

    def test_upstream(self):
        self._expect(503, {"error": {"message": "backend overloaded"}}, "upstream")

    def test_blocked(self):
        self.gemini.handler = lambda p, b, n: (200, {"promptFeedback": {"blockReason": "SAFETY"}})
        with self.assertRaises(ai.DirectorError) as ctx:
            self.ask()
        self.assertEqual(ctx.exception.code, "blocked")

    def test_empty_response(self):
        self.gemini.handler = lambda p, b, n: (200, {"candidates": []})
        with self.assertRaises(ai.DirectorError) as ctx:
            self.ask()
        self.assertEqual(ctx.exception.code, "empty")

    def test_non_json_answer(self):
        self.gemini.handler = lambda p, b, n: (
            200, {"candidates": [{"content": {"parts": [{"text": "извини, я не знаю"}]}}]})
        with self.assertRaises(ai.DirectorError) as ctx:
            self.ask()
        self.assertEqual(ctx.exception.code, "bad_json")

    def test_unreachable_host(self):
        dead = self.config(GEMINI_BASE_URL="http://127.0.0.1:1/v1beta")
        with self.assertRaises(ai.DirectorError) as ctx:
            self.ask(config=dead)
        self.assertEqual(ctx.exception.code, "network")

    def test_missing_key(self):
        with self.assertRaises(ai.DirectorError) as ctx:
            ai.chat([{"role": "user", "text": "hi"}], None, ai.Config(env={}))
        self.assertEqual(ctx.exception.code, "no_key")
        self.assertEqual(ctx.exception.status, 503)


class TestHealthAndFake(unittest.TestCase):
    def test_health_without_key(self):
        info = ai.health(ai.Config(env={}))
        self.assertFalse(info["ready"])
        self.assertEqual(info["reason"], "no_key")
        self.assertIn("GEMINI_API_KEY", info["message"])

    def test_health_with_key(self):
        info = ai.health(ai.Config(env={"GEMINI_API_KEY": "k"}))
        self.assertTrue(info["ready"])
        self.assertEqual(info["provider"], "gemini")

    def test_fake_mode_needs_no_network(self):
        cfg = ai.Config(env={"MYBOT_AI_FAKE": "1"})
        res = ai.chat([{"role": "user", "text": "хочу грустный лоуфай под дождь на 140 bpm"}], None, cfg)
        self.assertEqual(res["recipe"]["style"], "lofi")
        self.assertEqual(res["recipe"]["mood"], "sad")
        self.assertEqual(res["recipe"]["bpm"], 140)
        self.assertIn("заглушка", res["reply"])


class TestHttpEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def post(self, path, payload):
        req = urllib.request.Request(
            self.url(path), data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_health_endpoint(self):
        with urllib.request.urlopen(self.url("/api/health"), timeout=20) as resp:
            self.assertEqual(resp.status, 200)
            self.assertTrue(resp.headers.get("Content-Type").startswith("application/json"))
            data = json.loads(resp.read())
        self.assertIn("ai", data)
        self.assertIn("ready", data["ai"])

    def test_static_index_is_served(self):
        with urllib.request.urlopen(self.url("/"), timeout=20) as resp:
            body = resp.read().decode()
        self.assertEqual(resp.status, 200)
        self.assertIn("AI-дирижёр", body)

    def test_unknown_api_route(self):
        status, data = self.post("/api/nope", {})
        self.assertEqual(status, 404)
        self.assertFalse(data["ok"])

    def test_bad_body(self):
        req = urllib.request.Request(self.url("/api/chat"), data=b"not json", method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=20)
            self.fail("expected 400")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            self.assertEqual(json.loads(exc.read())["error"]["code"], "bad_json")

    def test_no_message(self):
        status, data = self.post("/api/chat", {"messages": []})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"]["code"], "no_message")

    def test_chat_end_to_end_in_fake_mode(self):
        os.environ["MYBOT_AI_FAKE"] = "1"
        self.addCleanup(os.environ.pop, "MYBOT_AI_FAKE", None)
        status, data = self.post("/api/chat", {
            "messages": [{"role": "user", "text": "эпичное техно для забега 145 bpm"}],
            "current": {"recipe": {"style": "lofi", "mood": "dreamy", "seed": "x"}},
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["recipe"]["style"], "techno")
        self.assertEqual(data["recipe"]["bpm"], 145)
        self.assertIn("reply", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
