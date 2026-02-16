import os
import logging
from typing import Optional

from openai import OpenAI

log = logging.getLogger("walle.edu.qa")


def answer_educational(question: str, model: str, temperature: float = 0.4) -> Optional[str]:
    # clear all input first
    question = (question or "").strip()
    if not question:
        return None

    # use environment to extract the API keys.
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.warning("OPENAI_API_KEY did not found")
        return None

    client = OpenAI(api_key=api_key)

    # the below given code keeps the prompt simple and clear to understand.
    system_prompt = (
        "You are helping with educational questions for a student project. "
        "Keep answers clear, short, and easy to understand.and if student wants bried explanation then explain it in brief with the relevant examples"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )
    except Exception:
        log.exception("ChatGPT request failed")
        return None

    # safe extraction of the answer.
    try:
        answer = response.choices[0].message.content
        if not answer:
            return None
        return answer.strip()
    except Exception:
        log.exception("Failure in reading ChatGPT response")
        return None

