import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

from app.prompts import build_system_prompt
from app.retriever import retrieve, get_all_catalog_links
from app.utils import extract_json, enforce_schema, get_last_user_message, get_all_user_content
from app.guards import is_off_topic, is_vague, count_user_turns

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )
    return _client


def _refusal_response() -> dict:
    return {
        "reply": "I can only help with SHL assessment selection.",
        "recommendations": [],
        "end_of_conversation": False,
    }


def _call_llm(system: str, messages: list[dict], retries: int = 2) -> str:
    """Call LLM with retry on timeout."""
    for attempt in range(retries + 1):
        try:
            response = _get_client().chat.completions.create(
                model=os.getenv("MODEL_NAME", "poolside/laguna-m.1:free"),
                messages=[{"role": "system", "content": system}] + messages,
                temperature=0.1,
                max_tokens=800,   # reduced — faster response
                timeout=90,       # increased from 25s
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            if attempt < retries:
                wait = 3 * (attempt + 1)
                print(f"LLM call failed (attempt {attempt+1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e


def chat(messages: list[dict]) -> dict:
    last_user = get_last_user_message(messages)
    all_user_text = get_all_user_content(messages)
    turn_count = count_user_turns(messages)

    # Guard: off-topic
    if is_off_topic(last_user):
        return _refusal_response()

    # Guard: vague turn 1
    force_clarify = is_vague(last_user) and turn_count == 1

    # Retrieval
    query = all_user_text if len(all_user_text.strip()) > len(last_user.strip()) else last_user
    catalog_hits = retrieve(query, k=10)  # reduced from 12 → shorter prompt → faster

    # Build prompt
    system = build_system_prompt(catalog_hits)

    if force_clarify:
        system += (
            "\n\n## OVERRIDE: The user's request is too vague. "
            "Ask exactly ONE clarifying question. Return recommendations: []."
        )

    if turn_count >= 6:
        system += (
            "\n\n## OVERRIDE: Conversation is near the 8-turn limit. "
            "You MUST provide your best recommendations now."
        )

    # LLM call with retry
    try:
        raw = _call_llm(system, messages)
    except Exception as e:
        return {
            "reply": f"I'm having trouble connecting. Please try again. ({type(e).__name__})",
            "recommendations": [],
            "end_of_conversation": False,
        }

    # Parse and validate
    parsed = extract_json(raw)
    valid_links = get_all_catalog_links()
    clean = enforce_schema(parsed, valid_links)

    if force_clarify:
        clean["recommendations"] = []

    return clean