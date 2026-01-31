import os
from typing import Optional

def answer_educational(query: str, model: str, temperature: float) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system = (
            "You are WALL-E in 'education mode'. "
            "You must only answer educational questions. "
            "If the user asks a non-educational question, politely refuse and suggest an educational reframe.\n"
            "When answering educational questions:\n"
            "- Be clear and beginner-friendly\n"
            "- Use examples\n"
            "- Keep it concise\n"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": query},
            ],
            temperature=temperature
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None
