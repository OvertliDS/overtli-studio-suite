import pathlib


def _root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def _input_types_block(text: str) -> str:
    start = text.index("def INPUT_TYPES(cls)")
    end = text.index("\n    def execute(", start)
    return text[start:end]


def test_lm_studio_schema_is_network_free():
    text = (_root() / "engine" / "llm_text_enhancer.py").read_text(encoding="utf-8")
    block = _input_types_block(text)
    assert "get_schema_models()" in block
    assert "refresh_models()" not in block
    assert "requests.get" not in block


def test_pollinations_schema_is_network_free():
    text = (_root() / "engine" / "pollinations" / "text_enhancer.py").read_text(encoding="utf-8")
    block = _input_types_block(text)
    assert "get_schema_models()" in block
    assert "refresh_models()" not in block
    assert "requests." not in block


def test_lm_studio_offline_discovery_is_silent_and_fast_pathed():
    text = (_root() / "engine" / "llm_text_enhancer.py").read_text(encoding="utf-8")
    assert "_loopback_service_available(cfg.base_url)" in text
    assert 'logger.warning("Failed to fetch local models' not in text
    assert 'logger.debug("Local model discovery unavailable:' in text


def test_schema_refresh_workers_are_daemons():
    lm = (_root() / "engine" / "llm_text_enhancer.py").read_text(encoding="utf-8")
    poll = (_root() / "engine" / "pollinations" / "text_enhancer.py").read_text(encoding="utf-8")
    assert 'name="overtli-lmstudio-model-refresh"' in lm
    assert 'name="overtli-pollinations-model-refresh"' in poll
    assert "daemon=True" in lm
    assert "daemon=True" in poll
