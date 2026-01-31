from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any

MoveAction = Literal["forward", "backward", "left", "right", "stop"]
GripAction = Literal["open", "close", "stop"]

@dataclass
class MoveCommand:
    type: Literal["MOVE"] = "MOVE"
    action: MoveAction = "stop"
    speed: Literal["slow", "normal", "fast"] = "normal"

@dataclass
class GripperCommand:
    type: Literal["GRIPPER"] = "GRIPPER"
    action: GripAction = "stop"
    strength: Literal["gentle", "normal", "firm"] = "normal"

@dataclass
class ChatCommand:
    type: Literal["CHAT"] = "CHAT"
    query: str = ""
    # optional fields
    topic: Optional[str] = None

def to_dict(obj) -> Dict[str, Any]:
    return obj.__dict__

