class PiRobotStub:
    """
    Raspberry Pi side (placeholder). Replace prints with GPIO / motor driver code.
    """

    def move(self, action: str, speed: str) -> None:
        print(f"🧯 PI MOVE -> action={action} speed={speed}")

    def gripper(self, action: str, strength: str) -> None:
        print(f"🧯 PI GRIPPER -> action={action} strength={strength}")

    def stop_all(self) -> None:
        print("🛑 PI STOP ALL (timeout safety)")
