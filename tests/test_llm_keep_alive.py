"""Tests for configurable Ollama idle unloading."""

from unittest.mock import patch

from core import llm_client


def test_default_keep_alive_unloads_after_five_minutes():
    with patch.object(llm_client, "_load_config", return_value={}):
        assert llm_client.get_llm_keep_alive() == "5m"


def test_custom_keep_alive_is_respected():
    with patch.object(
        llm_client, "_load_config", return_value={"llm_keep_alive": "2m"}
    ):
        assert llm_client.get_llm_keep_alive() == "2m"


def test_invalid_keep_alive_falls_back_to_safe_default():
    for value in (None, 5, "", "x" * 33):
        with patch.object(
            llm_client, "_load_config", return_value={"llm_keep_alive": value}
        ):
            assert llm_client.get_llm_keep_alive() == "5m"
