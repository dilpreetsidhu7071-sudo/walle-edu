import re
from typing import Dict, Any

def _norm(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t

def parse_rules(text: str) -> Dict[str, Any]:
    t = _norm(text)
    # Common speech-to-text mis-hear fixes (Whisper + accents + noise)
    COMMON_FIXES = {
        "for word": "forward",
        "for ward": "forward",
        "go foreword": "forward",
        "lift": "left",
        "write": "right",
        "grip her": "gripper",
        "open grip her": "open gripper",
        "close grip her": "close gripper",
    }
    for wrong, right in COMMON_FIXES.items():
        t = t.replace(wrong, right)

    speed = "normal"
    if "slow" in t or "slowly" in t:
        speed = "slow"
    elif "fast" in t or "quick" in t:
        speed = "fast"

    # Movement
    if "stop" in t or "halt" in t:
        return {"type": "MOVE", "action": "stop", "speed": "normal"}

    if "forward" in t or "ahead" in t:
        return {"type": "MOVE", "action": "forward", "speed": speed}

    if "backward" in t or "reverse" in t or "go back" in t:
        return {"type": "MOVE", "action": "backward", "speed": speed}

    if "left" in t:
        return {"type": "MOVE", "action": "left", "speed": speed}

    if "right" in t:
        return {"type": "MOVE", "action": "right", "speed": speed}

    # Gripper
    if "open gripper" in t or "open the gripper" in t or "open hand" in t:
        return {"type": "GRIPPER", "action": "open", "strength": "normal"}

    if "close gripper" in t or "close the gripper" in t or "grab" in t:
        strength = "firm" if "firm" in t or "tight" in t else "normal"
        return {"type": "GRIPPER", "action": "close", "strength": strength}

    # Otherwise treat as educational chat query
    return {"type": "CHAT", "query": text}
