import json
import re


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

TYPE_PRIORITY = ["K", "A", "P", "B", "C", "S", "O", "D"]


def derive_test_type(keys: list[str]) -> str:
    if not keys:
        return "K"
    derived = [KEYS_TO_TYPE.get(k, "K") for k in keys]
    for preferred in TYPE_PRIORITY:
        if preferred in derived:
            return preferred
    return derived[0]


def extract_json(raw: str) -> dict:
    raw = raw.strip()
  
    
    # Fix double curly braces from f-string escaping leak
    raw = raw.replace("{{", "{").replace("}}", "}")
    
    # Step 1: Strip markdown fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Step 2: Direct parse
    try:
        parsed = json.loads(raw)
        # Check if reply field itself contains JSON string (nested JSON)
        if isinstance(parsed, dict) and "reply" in parsed:
            reply_val = parsed.get("reply", "")
            if isinstance(reply_val, str) and reply_val.strip().startswith("{"):
                try:
                    inner = json.loads(reply_val)
                    if "recommendations" in inner:
                        return inner
                except json.JSONDecodeError:
                    pass
        return parsed
    except json.JSONDecodeError:
        pass

    # Step 3: Find ALL { } blocks, pick best one with recommendations
    candidates = []
    depth = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append(raw[start:i+1])

    best = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                if "recommendations" in parsed and "reply" in parsed:
                    # Check if this one's reply also contains nested JSON
                    reply_val = parsed.get("reply", "")
                    if isinstance(reply_val, str) and reply_val.strip().startswith("{"):
                        try:
                            inner = json.loads(reply_val)
                            if "recommendations" in inner:
                                return inner
                        except json.JSONDecodeError:
                            pass
                    best = parsed
                    break
                elif best is None:
                    best = parsed
        except json.JSONDecodeError:
            continue

    if best:
        return best

    # Step 4: Fallback
    first_brace = raw.find('{')
    reply_text = raw[:first_brace].strip() if first_brace > 0 else raw
    return {
        "reply": reply_text if reply_text else "I encountered an error. Please try again.",
        "recommendations": [],
        "end_of_conversation": False,
    }
def enforce_schema(data: dict, valid_links: set[str]) -> dict:
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
        if url in valid_links and name:
            clean_recs.append({
                "name": name,
                "url": url,
                "test_type": test_type if test_type else "K",
            })

    return {
        "reply": str(reply).strip() if reply else "",
        "recommendations": clean_recs[:10],
        "end_of_conversation": bool(eoc),
    }


def get_last_user_message(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"]
    return ""


def get_all_user_content(messages: list[dict]) -> str:
    return " ".join(m["content"] for m in messages if m["role"] == "user")