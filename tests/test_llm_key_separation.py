"""
Tests verifying that Fulfillment and Coordinator use separate Gemini API keys/clients.
All tests are purely unit tests — no real Gemini API calls are made.
"""
import pytest
from unittest.mock import MagicMock, patch


# ============================================================================
# 1. LLMConfig API isolation tests
# ============================================================================

def test_get_client_uses_gemini_api_key():
    """Coordinator get_client() uses GEMINI_API_KEY, not FULFILLMENT_GEMINI_API_KEY."""
    with patch('config.llm_config.genai') as mock_genai, \
         patch('config.llm_config.settings') as mock_settings:
        mock_settings.GEMINI_API_KEY = "coord-key-abc"
        mock_settings.FULFILLMENT_GEMINI_API_KEY = "fulfillment-key-xyz"
        mock_settings.LLM_PRIMARY = "gemini"

        from config.llm_config import LLMConfig
        cfg = LLMConfig()
        cfg.get_client()

        mock_genai.Client.assert_called_once_with(api_key="coord-key-abc")


def test_get_fulfillment_client_uses_fulfillment_gemini_api_key():
    """Fulfillment get_fulfillment_client() uses FULFILLMENT_GEMINI_API_KEY."""
    with patch('config.llm_config.genai') as mock_genai, \
         patch('config.llm_config.settings') as mock_settings:
        mock_settings.GEMINI_API_KEY = "coord-key-abc"
        mock_settings.FULFILLMENT_GEMINI_API_KEY = "fulfillment-key-xyz"
        mock_settings.LLM_PRIMARY = "gemini"

        from config.llm_config import LLMConfig
        cfg = LLMConfig()
        cfg.get_fulfillment_client()

        mock_genai.Client.assert_called_once_with(api_key="fulfillment-key-xyz")


def test_get_client_raises_if_coordinator_key_missing():
    """get_client() raises ValueError if GEMINI_API_KEY is not set."""
    with patch('config.llm_config.settings') as mock_settings:
        mock_settings.GEMINI_API_KEY = ""
        mock_settings.FULFILLMENT_GEMINI_API_KEY = "fulfillment-key-xyz"
        mock_settings.LLM_PRIMARY = "gemini"

        from config.llm_config import LLMConfig
        cfg = LLMConfig()
        with pytest.raises(ValueError, match="GEMINI_API_KEY not found"):
            cfg.get_client()


def test_get_fulfillment_client_raises_if_fulfillment_key_missing():
    """get_fulfillment_client() raises ValueError if FULFILLMENT_GEMINI_API_KEY is not set."""
    with patch('config.llm_config.settings') as mock_settings:
        mock_settings.GEMINI_API_KEY = "coord-key-abc"
        mock_settings.FULFILLMENT_GEMINI_API_KEY = ""
        mock_settings.LLM_PRIMARY = "gemini"

        from config.llm_config import LLMConfig
        cfg = LLMConfig()
        with pytest.raises(ValueError, match="FULFILLMENT_GEMINI_API_KEY not found"):
            cfg.get_fulfillment_client()


def test_coordinator_key_missing_does_not_affect_fulfillment():
    """FULFILLMENT_GEMINI_API_KEY is independent — missing GEMINI_API_KEY doesn't block it."""
    with patch('config.llm_config.genai') as mock_genai, \
         patch('config.llm_config.settings') as mock_settings:
        mock_settings.GEMINI_API_KEY = ""  # Coordinator key is absent
        mock_settings.FULFILLMENT_GEMINI_API_KEY = "fulfillment-key-xyz"
        mock_settings.LLM_PRIMARY = "gemini"

        from config.llm_config import LLMConfig
        cfg = LLMConfig()
        cfg.get_fulfillment_client()  # Must succeed

        mock_genai.Client.assert_called_once_with(api_key="fulfillment-key-xyz")


# ============================================================================
# 2. FulfillmentIntentClassifier uses get_fulfillment_client()
# ============================================================================

def test_fulfillment_classifier_calls_get_fulfillment_client():
    """FulfillmentIntentClassifier.client property invokes get_fulfillment_client()."""
    from agents.fulfillment.intent_classifier import FulfillmentIntentClassifier

    mock_client = MagicMock()
    with patch('agents.fulfillment.intent_classifier.llm_config') as mock_cfg:
        mock_cfg.get_fulfillment_client.return_value = mock_client

        classifier = FulfillmentIntentClassifier()  # No injected llm
        returned = classifier.client

        mock_cfg.get_fulfillment_client.assert_called_once()
        mock_cfg.get_client.assert_not_called()
        assert returned is mock_client


def test_fulfillment_classifier_injected_llm_skips_get_fulfillment_client():
    """If an LLM is injected directly, get_fulfillment_client() is never called."""
    from agents.fulfillment.intent_classifier import FulfillmentIntentClassifier

    injected = MagicMock()
    with patch('agents.fulfillment.intent_classifier.llm_config') as mock_cfg:
        classifier = FulfillmentIntentClassifier(llm=injected)
        returned = classifier.client

        mock_cfg.get_fulfillment_client.assert_not_called()
        mock_cfg.get_client.assert_not_called()
        assert returned is injected


# ============================================================================
# 3. Coordinator intent classifier still uses get_client()
# ============================================================================

def test_coordinator_classifier_calls_get_client_not_fulfillment():
    """CoordinatorIntentClassifier still calls get_client(), not get_fulfillment_client()."""
    from agents.coordinator.intent_classifier import IntentClassifier

    mock_client = MagicMock()
    with patch('agents.coordinator.intent_classifier.llm_config') as mock_cfg:
        mock_cfg.get_client.return_value = mock_client

        classifier = IntentClassifier()  # No injected llm
        returned = classifier.client  # Triggers the property

        mock_cfg.get_client.assert_called_once()
        mock_cfg.get_fulfillment_client.assert_not_called()
        assert returned is mock_client
