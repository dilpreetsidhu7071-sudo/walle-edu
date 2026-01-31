import logging
from walle_edu.logging_setup import setup_logging
from walle_edu.config import Config
from walle_edu.net.udp_receiver import UDPReceiver
from walle_edu.robot.command_dispatch import dispatch
from walle_edu.robot.pi_robot_stub import PiRobotStub
from walle_edu.robot.dummy_robot import DummyRobot

log = logging.getLogger("walle.pi_body")

def main(use_dummy: bool = False):
    setup_logging()
    cfg = Config()

    robot = DummyRobot() if use_dummy else PiRobotStub()

    recv = UDPReceiver(
        host="0.0.0.0",
        port=cfg.pi_port,
        safety_timeout_s=cfg.pi_safety_timeout_s
    )

    def on_command(payload):
        dispatch(robot, payload)

    def on_timeout():
        robot.stop_all()

    log.info("Pi Body started on UDP port %s (dummy=%s)", cfg.pi_port, use_dummy)
    recv.serve_forever(on_command=on_command, on_timeout=on_timeout)

if __name__ == "__main__":
    main(use_dummy=False)
