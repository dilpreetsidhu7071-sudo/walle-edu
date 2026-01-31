class DummyRobot:
    """
    Used for VM-only testing. Prints what the physical robot would do.
    """

    def move(self, action: str, speed: str) -> None:
        print(f"🤖 DUMMY MOVE -> action={action} speed={speed}")

    def gripper(self, action: str, strength: str) -> None:
        print(f"🦾 DUMMY GRIPPER -> action={action} strength={strength}")

    def stop_all(self) -> None:
        print("🧯 DUMMY STOP ALL (safety)")
