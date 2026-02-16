import os
import json
import re
import logging
from dataclasses import dataclass

from openai import OpenAI

log = logging.getLogger("walle.router")


@dataclass
class NLURouter:
    use_chatgpt_nlu: bool
    model: str
    temperature: float = 0.1

    def parse(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return {"type": "CHAT", "query": ""}

        # Basic commands
        intent = self._simple_rules(text)
        if intent:
            return intent

        # Treat everything as chat if NLU model is disabled or not working.
        if not self.use_chatgpt_nlu:
            return {"type": "CHAT", "query": text}

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"type": "CHAT", "query": text}

        return self._chatgpt_parse(text, api_key)

    def _simple_rules(self, text: str):
        t = text.lower()

        if t in ("forward", "go forward"):
            return {"type": "MOVE", "action": "forward"}
        if t in ("back", "backward"):
            return {"type": "MOVE", "action": "backward"}
        if t in ("left", "turn left"):
            return {"type": "MOVE", "action": "left"}
        if t in ("right", "turn right"):
            return {"type": "MOVE", "action": "right"}
        if t in ("stop",):
            return {"type": "MOVE", "action": "stop"}

        if re.search(r"open.*gripper|gripper.*open", t):
            return {"type": "GRIPPER", "action": "open"}
        if re.search(r"close.*gripper|gripper.*close", t):
            return {"type": "GRIPPER", "action": "close"}

        return None

    def _chatgpt_parse(self, text: str, api_key: str) -> dict:
        client = OpenAI(api_key=api_key)

        prompt = (
            "Convert this  message into a JSON command.\n"
            "Only reply with JSON (no extra text).\n"
            "Use one of these:\n"
            "- MOVE: {\"type\":\"MOVE\",\"action\":\"forward|backward|left|right|stop\"}\n"
            "- GRIPPER: {\"type\":\"GRIPPER\",\"action\":\"open|close\"}\n"
            "- CHAT: {\"type\":\"CHAT\",\"query\":\"...\"}\n"
)


        try:
            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
            )
            raw = response.choices[0].message.content.strip()
        except Exception:
            log.error("ChatGPT NLU failed")
            return {"type": "CHAT", "query": text}

        try:
            data = json.loads(raw)
            return data if "type" in data else {"type": "CHAT", "query": text}
        except Exception:
            return {"type": "CHAT", "query": text}

