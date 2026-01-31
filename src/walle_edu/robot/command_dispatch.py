from typing import Dict, Any

def dispatch(robot, payload: Dict[str, Any]) -> None:
    t = payload.get("type")

    if t == "MOVE":
        robot.move(payload.get("action", "stop"), payload.get("speed", "normal"))
        return

    if t == "GRIPPER":
        robot.gripper(payload.get("action", "stop"), payload.get("strength", "normal"))
        return

    # Unknown payload types should always result in safety stop
    robot.stop_all()

