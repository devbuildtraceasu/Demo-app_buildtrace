"""Gemini/Vertex AI client for vision processing."""

import logging
import os
from enum import StrEnum

from google import genai

from config import config


class GeminiModel(StrEnum):
    """Available Gemini models."""

    GEMINI_3_PRO = "gemini-3-pro-preview"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_3_FLASH = "gemini-3-flash-preview"


# Module-level singleton instance
_gemini_client: genai.Client | None = None
logger = logging.getLogger(__name__)


def _is_local_dev() -> bool:
    """Check if running in local development environment."""
    return os.environ.get("PUBSUB_EMULATOR_HOST") is not None


def get_gemini_client() -> genai.Client:
    """
    Get or create the singleton Gemini client instance.

    - Local dev (PUBSUB_EMULATOR_HOST set): Uses GEMINI_API_KEY
    - Production: Uses Vertex AI with workload identity

    Returns:
        genai.Client: Configured Gemini client (singleton)

    Raises:
        ValueError: If required config is missing for the environment
    """
    global _gemini_client

    if _gemini_client is None:
        if _is_local_dev():
            if not config.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required for local development")
            _gemini_client = genai.Client(api_key=config.gemini_api_key)
            logger.info("[gemini.client] using api key auth")
        else:
            if not config.vertex_ai_project:
                raise ValueError("VERTEX_AI_PROJECT is required for Gemini client in production")
            _gemini_client = genai.Client(
                vertexai=True,
                project=config.vertex_ai_project,
                location="global",
            )
            logger.info(f"[gemini.client] using vertex_ai_project={config.vertex_ai_project}")

    return _gemini_client


def close_gemini_client():
    """Close and reset the Gemini client singleton."""
    global _gemini_client
    _gemini_client = None
