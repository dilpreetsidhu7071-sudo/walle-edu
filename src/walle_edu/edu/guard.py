from typing import Literal

EduDecision = Literal["ALLOW", "REFUSE", "REDIRECT"]

# the basic keywords of the educational questions.
EDU_KEYWORDS = [
    "math", "physics", "chemistry", "biology",
    "history", "geography", "science",
    "english", "grammer", "algebra", "calculus","geometry",
    "homework","how is that", "explain", "define", "example", "solve",
    "what is", "why", "how","explain me","what does it mean","why is that",
]

#  the below keywords suggests that the questions are non-educational.
NON_EDU_HINTS = [
    "insult", "hate", "porn", "sex", "dating", "gambling", "drugs","football  game score","daily news",
]


def is_educational(text: str) -> bool:
    # convert everthing into lower-case to make it easier to check.
    text = text.lower()

    # if bad words appear in the commands , then treat it as a non-educational questions.
    for word in NON_EDU_HINTS:
        if word in text:
            return False

    # If there are educational questions , then it will pass the command.
    for word in EDU_KEYWORDS:
        if word in text:
            return True

    return False


def decide(text: str, mode: str = "redirect") -> EduDecision:
    # this is the main deciding function.
    if is_educational(text):
        return "ALLOW"

    if mode == "strict":
        return "REFUSE"

    return "REDIRECT"


def redirect_message(_: str) -> str:
    # the voice response of WALL-E if only non-educational questions were asked.
    return (
        "I can help with learning questions only. "
        "Please try asking it in an educational way."
    )

