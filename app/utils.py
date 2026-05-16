import json
import re

# Map keys[] values to single-letter test_type codes
KEYS_TO_TYPE = {
    "Ability & Aptitude": "A",
    "Personality & Behavior": "P",
    "Knowledge & Skills": "K",
    "Biodata & Situational Judgment": "B",
    "Competencies": "C",
    "Simulations": "S",
    "Assessment Exercises": "O",
    "Development & 360": "D",
}

# Priority order when multiple keys are present
TYPE_PRIORITY = ["K", "A", "P", "B", "C", "S", "O", "D"]


def derive_test_type(keys: list[str]) -> str:
    """Derive a single test_type letter from the keys array."""
    if not keys:
        return "K"
    derived = [KEYS_TO_TYPE.get(k, "K") for k in keys]
    for preferred in TYPE_PRIORITY:
        if preferred in derived:
            return preferred
    return derived[0]


def extract_json(raw: str) -> dict:
    """
    Robustly extract JSON from LLM output.
    Handles: raw JSON, ```json fences, leading/trailing text.
    """
    raw = raw.strip()

    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence_match:
        raw = fence_match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Find first { ... } block
    brace_match = re.search(r"\{[\s\S]*\}", raw)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback
    return {
        "reply": raw if raw else "I encountered an error. Please try again.",
        "recommendations": [],
        "end_of_conversation": False,
    }


def enforce_schema(data: dict, valid_links: set[str]) -> dict:
    """
    Ensure the response dict is schema-compliant.
    - Validates URLs against catalog links
    - Caps recommendations at 10
    - Ensures correct field types
    """
    reply = data.get("reply", "")
    recs = data.get("recommendations", [])
    eoc = data.get("end_of_conversation", False)

    clean_recs = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        url = r.get("url", "").strip()
        name = r.get("name", "").strip()
        test_type = r.get("test_type", "K").strip()

        # Accept if URL is in valid catalog links
        if url in valid_links and name:
            clean_recs.append({
                "name": name,
                "url": url,
                "test_type": test_type if test_type else "K",
            })

    return {
        "reply": str(reply) if reply else "",
        "recommendations": clean_recs[:10],
        "end_of_conversation": bool(eoc),
    }


def get_last_user_message(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"]
    return ""


def get_all_user_content(messages: list[dict]) -> str:
    """Concatenate all user messages for richer retrieval on multi-turn conversations."""
    return " ".join(m["content"] for m in messages if m["role"] == "user")