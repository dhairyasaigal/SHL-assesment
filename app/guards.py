import re

OFF_TOPIC_PATTERNS = [
    r"\b(salary|compensation|pay scale|offer letter|legal advice|lawsuit|discriminat|gdpr|privacy law)\b",
    r"\b(write me|draft|compose).{0,20}(email|letter|contract|agreement)\b",
    r"\bfire\b|\bterminate\b|\blayoff\b",
    r"ignore (previous|all|your) instructions",
    r"forget (everything|all|your) (instructions|rules|system)",
    r"act as (a |an )(?!shl|assessment advisor)",
    r"jailbreak|dan mode|developer mode|ignore all previous",
    r"pretend you (are|were|have no)",
    r"you are now|from now on you",
]

# Patterns that indicate a too-vague first message
VAGUE_PATTERNS = [
    r"^(i need|give me|show me|find me|get me)?\s*(an?\s*)?assessment\.?\s*$",
    r"^help\.?\s*$",
    r"^(what|which)\s+(assessments?|tests?)\s+(do you have|are available|exist)\??\s*$",
    r"^(something|anything)\s+(for|about)\s+hiring\.?\s*$",
    r"^hello\.?\s*$",
    r"^hi\.?\s*$",
]


def is_off_topic(text: str) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t) for p in OFF_TOPIC_PATTERNS)


def is_vague(text: str) -> bool:
    t = text.lower().strip()
    return any(re.fullmatch(p, t) for p in VAGUE_PATTERNS)


def count_user_turns(messages: list[dict]) -> int:
    return sum(1 for m in messages if m["role"] == "user")


def has_prior_recommendations(messages: list[dict]) -> bool:
    """Check if assistant has already given recommendations in this conversation."""
    for m in messages:
        if m["role"] == "assistant":
            try:
                import json
                data = json.loads(m["content"])
                if data.get("recommendations"):
                    return True
            except Exception:
                pass
    return False