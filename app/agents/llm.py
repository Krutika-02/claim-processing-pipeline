"""LLM initialization helper with smart rate-limit retry and instant daily quota fallback."""

import logging
import time
from typing import Any, List
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings

logger = logging.getLogger(__name__)


def get_llm(model: str = None, temperature: float = None) -> ChatGoogleGenerativeAI:
    """Instantiates the ChatGoogleGenerativeAI LLM instance."""
    return ChatGoogleGenerativeAI(
        model=model or settings.DEFAULT_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        max_retries=1,
    )


def extract_content_text(content: Any) -> str:
    """Extracts raw string text from LLM response content (handles string, list of dicts, etc)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(getattr(item, "text"))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def invoke_llm_with_retry(llm: ChatGoogleGenerativeAI, messages: List[BaseMessage], max_attempts: int = 2) -> str:
    """Invokes LLM with retry for temporary RPM rate limits, or immediately raises for daily quota exhaustion."""
    for attempt in range(max_attempts):
        try:
            response = llm.invoke(messages)
            return extract_content_text(response.content)
        except Exception as e:
            err_msg = str(e)
            # If daily quota is exceeded, retrying is futile - raise immediately
            if "per day limit exceeded" in err_msg or "retryDelay': '4" in err_msg:
                logger.warning("Daily free tier quota exhausted for this model. Immediately engaging fallback.")
                raise e

            # Temporary per-minute burst rate limit
            if ("429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg) and attempt < max_attempts - 1:
                logger.info(f"Temporary rate limit (attempt {attempt+1}/{max_attempts}). Backing off for 6s...")
                time.sleep(6)
                continue

            raise e
