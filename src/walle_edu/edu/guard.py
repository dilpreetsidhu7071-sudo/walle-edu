from typing import Literal

EduDecision = Literal["ALLOW", "REFUSE", "REDIRECT"]

# basic keywords of the questions
EDU_KEYWORDS = [
    "math", "physics", "chemistry", "biology",
    "history", "geography", "science",
    "english", "grammer", "algebra", "calculus","geometry",
    "homework","how is that", "explain", "define", "example", "solve",
    "what is", "why", "how","explain me","what does it mean","why is that",
]

# below keywords are for the non-educational questions.
NON_EDU_HINTS = [
    "insult", "hate", "porn", "sex", "dating", "gambling", "drugs","football  game score","daily news",
]


def is_educational(text: str) -> bool:
    # convert everthing into the lowercase
    text = text.lower()

    # if bad words appear , then treat it as non eduaction question.
    for word in NON_EDU_HINTS:
        if word in text:
            return False

    # only educational questions will pass through
    for word in EDU_KEYWORDS:
        if word in text:
            return True

    return False


def decide(text: str, mode: str = "redirect") -> EduDecision:
    # deciding  function
    if is_educational(text):
        return "ALLOW"

    if mode == "strict":
        return "REFUSE"

    return "REDIRECT"


def redirect_message(_: str) -> str:
    # the answer, when non educational questions were asked
    return (
        "I can help with learning questions only. "
        "Please try asking it in an educational way."
    )

