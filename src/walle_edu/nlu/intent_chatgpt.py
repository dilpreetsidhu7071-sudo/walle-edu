import json
import os
from typing import Dict, Any, Optional

def parse_with_chatgpt(text: str, model: str, temperature: float) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system = (
            "You are an intent parser for a WALL-E robot. Return ONLY JSON.\n"
            "Supported intents:\n"
            "MOVE: {type:'MOVE', action:'forward|backward|left|right|stop', speed:'slow|normal|fast'}\n"
            "GRIPPER: {type:'GRIPPER', action:'open|close|stop', strength:'gentle|normal|firm'}\n"
            "CHAT: {type:'CHAT', query:'...'}\n"
            "If the user is asking a question, use CHAT.\n"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            temperature=temperature
        )

        content = resp.choices[0].message.content.strip()
        data = json.loads(content)
        if isinstance(data, dict) and "type" in data:
            return data
        return None

    except Exception:
        return None
