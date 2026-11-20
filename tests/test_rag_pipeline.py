import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from agents import pipeline
from retrieval import build_index


class _MemoryCollection:
    def __init__(self, metadata):
        self.metadata = metadata
        self.add_calls = 0
        self.record_count = 0

    def add(self, ids, **_kwargs):
        self.add_calls += 1
        self.record_count += len(ids)

    def count(self):
        return self.record_count


class _MemoryChromaClient:
    def __init__(self):
        self.collections = {}
        self.deleted = []
        self.created = []

    def list_collections(self):
        return [SimpleNamespace(name=name) for name in self.collections]

    def get_collection(self, name):
        return self.collections[name]

    def delete_collection(self, name):
        self.deleted.append(name)
        del self.collections[name]

    def create_collection(self, name, embedding_function, metadata):
        self.created.append(name)
        collection = _MemoryCollection(metadata)
        self.collections[name] = collection
        return collection


class RoutingTests(unittest.TestCase):
    def test_project_env_overrides_inherited_environment(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "ANTHROPIC_API_KEY=file-key\n"
                "MINDBRIDGE_PRELOAD_EMBEDDINGS=false\n",
                encoding="utf-8",
            )
            with (
                patch.object(pipeline, "ROOT", root),
                patch.dict(os.environ, {
                    "ANTHROPIC_API_KEY": "inherited-key",
                    "MINDBRIDGE_PRELOAD_EMBEDDINGS": "true",
                }),
            ):
                pipeline._load_project_env()

                self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "file-key")
                self.assertEqual(os.environ["MINDBRIDGE_PRELOAD_EMBEDDINGS"], "false")

    def test_routes_to_all_five_catalogs(self):
        examples = {
            "Where can I talk to someone on campus?": "resources",
            "Can you share an uplifting quote?": "quotes",
            "What are some mindfulness tips?": "wellness",
            "What are common signs of ADHD?": "conditions_and_signs",
            "What number can I call in a crisis?": "resources",
            "What is mental health?": "generalinfo",
        }
        for question, expected in examples.items():
            with self.subTest(question=question):
                self.assertEqual(pipeline.route(question), expected)

    def test_crisis_message_returns_before_retrieval(self):
        with (
            patch("agents.pipeline.is_crisis", return_value=True),
            patch("agents.pipeline.load_crisis_message", return_value="Fixed crisis text"),
            patch("agents.pipeline.route") as route,
            patch("agents.pipeline.search") as search,
        ):
            result = pipeline.respond("I want to die")

        self.assertEqual(result, {
            "route": "crisis",
            "answer": "Fixed crisis text",
            "sources": [],
        })
        route.assert_not_called()
        search.assert_not_called()

    def test_missing_index_is_reported(self):
        with patch(
            "agents.pipeline.search",
            side_effect=build_index.IndexNotBuiltError("Build the index first."),
        ):
            with self.assertRaisesRegex(
                pipeline.RetrievalIndexError, "Build the index first"
            ):
                pipeline.respond("What is mental health?")

    def test_answer_uses_route_results_without_api_key(self):
        sources = [{
            "id": "node-1",
            "text": "A grounded passage from the source library.",
            "title": "Example source",
            "url": "https://example.org",
            "organization": "Example organization",
        }]
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}),
            patch("agents.pipeline.search", return_value=sources) as search,
        ):
            result = pipeline.respond("What are common signs of ADHD?")

        self.assertEqual(search.call_args_list, [
            unittest.mock.call(
                "What are common signs of ADHD?", route="conditions_and_signs"
            ),
            unittest.mock.call(
                "What are common signs of ADHD? practical coping action",
                k=6,
                route="wellness",
            ),
            unittest.mock.call(
                "encouragement for What are common signs of ADHD?",
                k=6,
                route="quotes",
            ),
            unittest.mock.call(
                "support resources for What are common signs of ADHD?",
                k=6,
                route="resources",
            ),
        ])
        self.assertEqual(result["route"], "conditions_and_signs")
        self.assertIn("[1] A grounded passage", result["answer"])
        self.assertEqual(result["sources"], sources)

    def test_empty_llm_answer_falls_back_to_source_passages(self):
        sources = [{
            "text": "A grounded fallback passage.",
            "title": "Example source",
            "organization": "Example organization",
        }]
        response = SimpleNamespace(content=[
            SimpleNamespace(type="text", text="")
        ])
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.Anthropic") as anthropic_client,
        ):
            anthropic_client.return_value.messages.create.return_value = response
            answer = pipeline._generate_answer("A question", sources)

        self.assertIn("[1] A grounded fallback passage", answer)

    def test_configured_llm_receives_grounded_prompt(self):
        source = {
            "text": "Retrieved evidence",
            "title": "Example source",
            "organization": "Example organization",
        }
        response = SimpleNamespace(content=[
            SimpleNamespace(type="text", text="Grounded answer [1]")
        ])
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.Anthropic") as anthropic_client,
        ):
            anthropic_client.return_value.messages.create.return_value = response
            answer = pipeline._generate_answer("A question", [source])

        self.assertEqual(answer, "Grounded answer [1]")
        request = anthropic_client.return_value.messages.create.call_args.kwargs
        self.assertIn("Do not diagnose", request["system"])
        self.assertIn("Retrieved evidence", request["messages"][0]["content"])

    def test_answer_and_dashboard_are_generated_in_one_grounded_request(self):
        response = SimpleNamespace(content=[
            SimpleNamespace(type="text", text='{"answer":"A grounded reply [1]",'
                                                '"tips":[{"title":"Pause","description":"Relax",'
                                                '"actionable_tip":"Breathe slowly"}],'
                                                '"breathing":"Take a slow breath.",'
                                                '"quote":{"text":"A quote","author":"Source"},'
                                                '"resource_summaries":[{"title":"Campus Support",'
                                                '"summary":"Talk to someone"}]}')
        ])
        candidates = {
            "tips": [{"title": "Breathing", "text": "Breathe slowly"}],
            "quotes": [{"title": "Quote", "text": "A quote"}],
            "resources": [{"title": "Campus Support", "text": "Counseling details"}],
        }
        sources = [{
            "title": "Grounding skills",
            "text": "Slow breathing can help someone feel calmer.",
            "organization": "Example",
        }]
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.Anthropic") as anthropic_client,
        ):
            anthropic_client.return_value.messages.create.return_value = response
            answer, sections = pipeline._generate_dashboard_response(
                "I am stressed", sources, candidates
            )

        self.assertEqual(answer, "A grounded reply [1]")
        self.assertEqual(sections["generated_tips"][0]["title"], "Pause")
        self.assertEqual(sections["quote_copy"]["author"], "Source")
        self.assertEqual(sections["breathing"], "Take a slow breath.")
        self.assertEqual(sections["resource_summaries"][0]["title"], "Campus Support")
        self.assertEqual(anthropic_client.return_value.messages.create.call_count, 1)
        prompt = anthropic_client.return_value.messages.create.call_args.kwargs[
            "messages"
        ][0]["content"]
        self.assertIn("natural-language response", prompt)
        self.assertIn("Cite every factual claim from Answer sources", prompt)

    def test_plain_natural_language_model_response_is_not_replaced_by_passages(self):
        response = SimpleNamespace(content=[
            SimpleNamespace(
                type="text",
                text="Midterms can feel overwhelming. Try breaking your study plan "
                     "into smaller steps and reach out to someone you trust [1].",
            )
        ])
        candidates = {"tips": [], "quotes": [], "resources": []}
        sources = [{
            "title": "Coping with stress",
            "text": "Break tasks into smaller steps and talk to someone you trust.",
        }]
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.Anthropic") as anthropic_client,
        ):
            anthropic_client.return_value.messages.create.return_value = response
            answer, dashboard = pipeline._generate_dashboard_response(
                "I feel overwhelmed about midterms", sources, candidates
            )

        self.assertIn("Midterms can feel overwhelming.", answer)
        self.assertNotIn("Here are the most relevant passages", answer)
        self.assertEqual(dashboard, {})

    def test_complete_answer_is_recovered_from_truncated_json(self):
        response = SimpleNamespace(content=[
            SimpleNamespace(
                type="text",
                text='{"answer":"You can make this feel more manageable by choosing '
                     'one small study task and taking a short break afterward [1]",'
                     '"tips":[{"title":"Plan",',
            )
        ])
        candidates = {"tips": [], "quotes": [], "resources": []}
        sources = [{
            "title": "Coping with stress",
            "text": "Break tasks into smaller steps.",
        }]
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.Anthropic") as anthropic_client,
        ):
            anthropic_client.return_value.messages.create.return_value = response
            answer, dashboard = pipeline._generate_dashboard_response(
                "I feel overwhelmed about midterms", sources, candidates
            )

        self.assertIn("one small study task", answer)
        self.assertNotIn("Here are the most relevant passages", answer)
        self.assertEqual(dashboard, {})

    def test_raw_model_response_logging_is_opt_in_and_preserves_api_payload(self):
        response = SimpleNamespace(
            model_dump=lambda mode: {
                "id": "msg_test",
                "content": [{"type": "text", "text": "Generated response"}],
            }
        )
        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "logs" / "model_responses.jsonl"
            with (
                patch.object(pipeline, "_MODEL_RESPONSE_LOG", log_path),
                patch.dict(os.environ, {"MINDBRIDGE_LOG_MODEL_RESPONSES": "false"}),
            ):
                pipeline._log_model_response(response, "test-model")
                self.assertFalse(log_path.exists())

                with patch.dict(
                    os.environ, {"MINDBRIDGE_LOG_MODEL_RESPONSES": "true"}
                ):
                    pipeline._log_model_response(response, "test-model")

            entry = json.loads(log_path.read_text(encoding="utf-8"))

        self.assertEqual(entry["model"], "test-model")
        self.assertEqual(entry["response"]["id"], "msg_test")
        self.assertEqual(
            entry["response"]["content"][0]["text"], "Generated response"
        )
        self.assertTrue(entry["timestamp_utc"])


class RetrievalCatalogTests(unittest.TestCase):
    @staticmethod
    def _sample_records():
        return {
            route: [{
                "id": f"{route}-1",
                "text": f"Text for {route}",
                "title": f"Title for {route}",
                "url": "",
                "organization": "Test",
                "category": route,
            }]
            for route in build_index.ROUTES
        }

    def test_build_skips_unchanged_collections_without_loading_model(self):
        records = self._sample_records()
        client = _MemoryChromaClient()
        with (
            patch.object(build_index, "load_records", return_value=records),
            patch.object(build_index, "_client", return_value=client),
            patch.object(build_index, "_embedding_function", return_value=object()) as model,
        ):
            expected_count = sum(map(len, records.values()))
            self.assertEqual(build_index.build(), expected_count)
            self.assertEqual(model.call_count, 1)
            add_calls = {
                name: collection.add_calls
                for name, collection in client.collections.items()
            }

            with patch.object(
                build_index,
                "_embedding_function",
                side_effect=AssertionError("unchanged build loaded the model"),
            ):
                self.assertEqual(build_index.build(), 0)

        self.assertEqual(add_calls, {
            name: 1 for name in client.collections
        })
        self.assertEqual(
            {name: collection.add_calls for name, collection in client.collections.items()},
            add_calls,
        )
        self.assertEqual(client.deleted, [])

    def test_build_rebuilds_changed_catalog_only_and_force_rebuilds_all(self):
        records = self._sample_records()
        client = _MemoryChromaClient()
        with (
            patch.object(build_index, "load_records", return_value=records),
            patch.object(build_index, "_client", return_value=client),
            patch.object(build_index, "_embedding_function", return_value=object()),
        ):
            build_index.build()

            client.deleted.clear()
            changed = self._sample_records()
            changed["quotes"][0]["text"] = "Updated quote"
            with patch.object(build_index, "load_records", return_value=changed):
                self.assertEqual(build_index.build(), 1)
            self.assertEqual(client.deleted, ["mindbridge_quotes"])
            self.assertEqual(client.created[-1], "mindbridge_quotes")

            client.deleted.clear()
            with patch.object(build_index, "load_records", return_value=changed):
                self.assertEqual(
                    build_index.build(force=True),
                    sum(map(len, changed.values())),
                )
        self.assertCountEqual(
            client.deleted,
            [build_index.collection_name(route) for route in build_index.ROUTES],
        )

    def test_chunk_text_bounds_long_paragraphs_and_rejects_bad_sizes(self):
        text = "word " * 120
        chunks = build_index.chunk_text(text, chunk_size=40, overlap=8)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 40 for chunk in chunks))
        with self.assertRaises(ValueError):
            build_index.chunk_text(text, chunk_size=10, overlap=10)

    def test_all_catalogs_produce_index_records_without_placeholders(self):
        records = build_index.load_records()

        self.assertEqual(set(records), set(build_index.ROUTES))
        for route, route_records in records.items():
            with self.subTest(route=route):
                self.assertTrue(route_records)
                self.assertTrue(all(record["text"] for record in route_records))
                if route == "resources":
                    names = [record["title"] for record in route_records]
                    self.assertEqual(len(names), len(set(names)))
                    self.assertFalse(any(
                        "TODO" in record["text"] for record in route_records
                    ))


if __name__ == "__main__":
    unittest.main()
