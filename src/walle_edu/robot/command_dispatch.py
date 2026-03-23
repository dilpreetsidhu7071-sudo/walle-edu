from typing import Dict, Any

def dispatch(robot, payload: Dict[str, Any]) -> None:
    t = payload.get("type")

    if t == "MOVE":
        robot.move(payload.get("action", "stop"), payload.get("speed", "normal"))
        return

    if t == "GRIPPER":
        robot.gripper(payload.get("action", "stop"), payload.get("strength", "normal"))
        return

    # always stop if payload is unknown.
    robot.stop_all()

