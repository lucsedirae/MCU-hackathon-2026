import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app import llm
from app.main import app
from app.auth import administrator


class LLMTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[administrator] = lambda: None
        self.directory = tempfile.TemporaryDirectory()
        self.directory_patch = patch.object(
            llm, "settings_dir", Path(self.directory.name)
        )
        self.directory_patch.start()
        self.client = TestClient(app)
        self.payload = {
            "base_url": "https://api.openai.com/v1",
            "model": "test-model",
            "api_key": "test-secret-only",
        }

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.directory_patch.stop()
        self.directory.cleanup()

    def save(self):
        response = self.client.put("/api/settings/llm", json=self.payload)
        self.assertEqual(response.status_code, 200)
        return response

    def test_secret_storage_retention_and_disconnect(self):
        self.assertNotIn(self.payload["api_key"], self.save().text)
        self.assertNotIn(
            self.payload["api_key"], (llm.settings_dir / "connection.json").read_text()
        )
        response = self.client.get("/api/settings/llm")
        self.assertTrue(response.json()["has_api_key"])
        self.assertNotIn("encrypted_key", response.json())
        update = {**self.payload, "model": "another-model", "api_key": None}
        self.assertEqual(
            self.client.put("/api/settings/llm", json=update).status_code, 200
        )
        update["base_url"] = "https://different.example/v1"
        changed = self.client.put("/api/settings/llm", json=update)
        self.assertEqual(changed.status_code, 422)
        self.assertTrue(self.client.get("/api/settings/llm").json()["has_api_key"])
        self.assertEqual(self.client.delete("/api/settings/llm").status_code, 200)
        self.assertFalse(self.client.get("/api/settings/llm").json()["has_api_key"])

    def test_optional_connection_fields(self):
        response = self.client.put(
            "/api/settings/llm",
            json={"model": "", "system_prompt": "Review carefully."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get("/api/settings/llm").json()["system_prompt"],
            "Review carefully.",
        )
        self.assertEqual(self.client.post("/api/settings/llm/test").status_code, 409)
        self.assertEqual(self.client.put("/api/settings/llm", json={}).status_code, 200)
        self.save()
        response = self.client.put(
            "/api/settings/llm", json={"review_rubric": "Check alignment."}
        )
        self.assertTrue(response.json()["has_api_key"])
        self.assertEqual(response.json()["model"], self.payload["model"])

    def test_validation_and_cross_site_requests(self):
        self.assertEqual(
            self.client.put(
                "/api/settings/llm",
                json={**self.payload, "base_url": "http://provider.example"},
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.put(
                "/api/settings/llm",
                json=self.payload,
                headers={"sec-fetch-site": "cross-site"},
            ).status_code,
            403,
        )
        self.assertEqual(self.client.post("/api/settings/llm/test").status_code, 409)

    def test_legacy_provider_requires_new_credentials(self):
        self.save()
        path = llm.settings_dir / "connection.json"
        settings = json.loads(path.read_text())
        settings.update(base_url="https://openrouter.ai/api/v1", system_prompt="Keep instructions")
        path.write_text(json.dumps(settings))
        result = self.client.get("/api/settings/llm").json()
        self.assertFalse(result["has_api_key"])
        self.assertEqual(result["model"], "")
        self.assertEqual(result["system_prompt"], "Keep instructions")
        self.assertEqual(self.client.post("/api/settings/llm/test").status_code, 409)
        self.client.put("/api/settings/llm", json={"model": "test-model", "api_key": "new-openai-key"})
        self.assertTrue(self.client.get("/api/settings/llm").json()["has_api_key"])

    def test_model_dropdown_list_and_failures(self):
        self.assertEqual(self.client.get("/api/settings/llm/models").status_code, 409)
        self.save()
        real_client = httpx.AsyncClient
        def models(request):
            self.assertEqual(str(request.url), "https://api.openai.com/v1/models")
            self.assertEqual(request.headers["authorization"], "Bearer test-secret-only")
            return httpx.Response(200, json={"data": [{"id": value} for value in
                ["gpt-4o", "gpt-4o", "gpt-4o-audio-preview", "text-embedding-3-small", "gpt-4-preview", "o3", "o3-pro"]]})
        with patch.object(llm.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(models), **kwargs)):
            response = self.client.get("/api/settings/llm/models")
            self.assertEqual(response.json()["models"], ["gpt-4-preview", "gpt-4o", "o3"])
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn("test-secret-only", response.text)
        for status, body in [(401, {}), (429, {}), (500, {}), (200, {"data": None})]:
            with self.subTest(status=status), patch.object(llm.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)), **kwargs)):
                self.assertEqual(self.client.get("/api/settings/llm/models").status_code, 502)

    def test_routing_and_provider_errors(self):
        self.payload.update(
            system_prompt="Review the curriculum.",
            guardrails_prompt="Ask when information is missing.",
            review_rubric="Check alignment.",
            evidence_rules="Cite the source.",
            examples="Finding: objectives align.",
        )
        self.save()
        saved = self.client.get("/api/settings/llm").json()
        self.assertEqual(saved["system_prompt"], self.payload["system_prompt"])
        self.assertEqual(saved["guardrails_prompt"], self.payload["guardrails_prompt"])
        for field in ("review_rubric", "evidence_rules", "examples"):
            self.assertEqual(saved[field], self.payload[field])
        real_client = httpx.AsyncClient

        def provider(request):
            self.assertEqual(
                str(request.url), "https://api.openai.com/v1/chat/completions"
            )
            self.assertEqual(
                request.headers["authorization"], "Bearer test-secret-only"
            )
            messages = json.loads(request.content)["messages"]
            self.assertEqual(
                messages[0],
                {
                    "role": "system",
                    "content": "Review the curriculum.\n\nGuardrails:\nAsk when information is missing.\n\nReview rubric:\nCheck alignment.\n\nEvidence rules:\nCite the source.\n\nExamples:\nFinding: objectives align.",
                },
            )
            self.assertEqual(messages[1]["role"], "user")
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "Hello from the model"}}]},
            )

        with patch.object(
            llm.httpx,
            "AsyncClient",
            side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(provider), **kwargs
            ),
        ):
            response = self.client.post("/api/llm/prompt", json={"prompt": "Hello"})
            self.assertEqual(response.json()["text"], "Hello from the model")
            self.assertEqual(
                self.client.post("/api/settings/llm/test").status_code, 200
            )

        for status in [401, 429, 500]:
            with self.subTest(status=status):
                transport = httpx.MockTransport(
                    lambda request: httpx.Response(status, text="test-secret-only")
                )
                with patch.object(
                    llm.httpx,
                    "AsyncClient",
                    side_effect=lambda **kwargs: real_client(
                        transport=transport, **kwargs
                    ),
                ):
                    response = self.client.post(
                        "/api/llm/prompt", json={"prompt": "Hello"}
                    )
                    self.assertEqual(response.status_code, 502)
                    self.assertNotIn("test-secret-only", response.text)


if __name__ == "__main__":
    unittest.main()
