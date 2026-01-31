import re
from typing import Literal

EduDecision = Literal["ALLOW", "REFUSE", "REDIRECT"]

EDU_KEYWORDS = [
    "math", "physics", "chemistry", "biology", "history", "geography",
    "grammar", "english", "science", "algebra", "calculus", "homework",
    "explain", "define", "what is", "why", "how does", "example", "solve",
]

NON_EDU_HINTS = [
    "insult", "hate", "porn", "sex", "dating", "gambling", "drugs",
]

def is_educational_simple(text: str) -> bool:
    t = text.lower()
    if any(bad in t for bad in NON_EDU_HINTS):
        return False
    return any(k in t for k in EDU_KEYWORDS)

def decide(text: str, mode: str = "redirect") -> EduDecision:
    ok = is_educational_simple(text)
    if ok:
        return "ALLOW"
    return "REFUSE" if mode == "strict" else "REDIRECT"

def redirect_message(text: str) -> str:
    # Turn non-edu into a “learning” alternative
    return (
        "I’m an education WALL-E. I can help with learning questions. "
        "Try asking it like: 'Explain the topic behind that' or 'Teach me the basics of it.'"
    )
