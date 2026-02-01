from typing import Dict, Any
from walle_edu.nlu.intent_rules import parse_rules
from walle_edu.nlu.intent_chatgpt import parse_with_chatgpt

class NLURouter:
    def __init__(self, use_chatgpt: bool, model: str, temperature: float):
        self.use_chatgpt = use_chatgpt
        self.model = model
        self.temperature = temperature

    def parse(self, text: str) -> Dict[str, Any]:
        if self.use_chatgpt:
            intent = parse_with_chatgpt(text, self.model, self.temperature)
            if intent:
                return intent
        return parse_rules(text)
