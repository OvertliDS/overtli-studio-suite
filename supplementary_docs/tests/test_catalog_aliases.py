import importlib
import pathlib
import sys
import time
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
# Load the real catalog without importing GPU/node integrations from __init__.
for name, path in (
    ("catalog_alias_test", ROOT),
    ("catalog_alias_test.engine", ROOT / "engine"),
    ("catalog_alias_test.engine.pollinations", ROOT / "engine" / "pollinations"),
):
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules[name] = package
catalog = importlib.import_module("catalog_alias_test.engine.pollinations.model_catalog")


class CatalogAliasTests(unittest.TestCase):
    def test_saved_options_survive_renaming_in_each_modality(self):
        cases = [
            ("openai", "openai/gpt-5-mini", ["text", "image"], ["text"],
             "/v1/chat/completions", lambda: catalog.fetch_pollinations_text_models(True, [])),
            ("flux", "black-forest-labs/flux-schnell", ["text"], ["image"],
             "/v1/images/generations", lambda: catalog.fetch_pollinations_modality_models("image", [])),
            ("wan", "alibaba/wan-2.6", ["text"], ["video"],
             "/video", lambda: catalog.fetch_pollinations_modality_models("video", [])),
            ("elevenlabs", "elevenlabs/eleven-v3", ["text"], ["audio"],
             "/v1/audio/speech", lambda: catalog.fetch_pollinations_audio_models_for_task("generation_speech", [])),
        ]
        for legacy, canonical, inputs, outputs, endpoint, options in cases:
            with self.subTest(model=legacy):
                entry = {"name": legacy, "input_modalities": inputs,
                         "output_modalities": outputs, "supported_endpoints": [endpoint]}
                catalog._CACHE_MODELS = [entry]
                catalog._CACHE_TS = time.time()
                saved = options()[0]
                catalog._CACHE_MODELS = [{**entry, "name": canonical, "aliases": [legacy]}]
                self.assertIn(saved, options())
                self.assertTrue(any(option.startswith(canonical + " ") for option in options()))
                self.assertEqual(catalog.get_pollinations_model_entry(legacy)["input_modalities"], inputs)

    def test_duplicate_catalog_sources_preserve_aliases(self):
        merged = catalog._merge_catalog_entries({"name": "openai/gpt-5-mini"}, {"aliases": ["openai"]})
        self.assertEqual(merged["aliases"], ["openai"])


if __name__ == "__main__":
    unittest.main()
