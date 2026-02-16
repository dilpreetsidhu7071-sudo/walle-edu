import json
import socket
import time
import logging
from dataclasses import dataclass
from typing import Callable, Dict, Any

log = logging.getLogger("walle.net.receiver")

@dataclass
class UDPReceiver:
    host: str
    port: int
    safety_timeout_s: float

    def serve_forever(
        self,
        on_command: Callable[[Dict[str, Any]], None],
        on_timeout: Callable[[], None],
    ) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(0.5)

        last_cmd = time.time()
        timed_out = False

        log.info("Listening on UDP %s:%s", self.host, self.port)

        while True:
            try:
                data, addr = sock.recvfrom(4096)
                payload = json.loads(data.decode("utf-8"))
                log.info("Received from %s: %s", addr, payload)
                on_command(payload)
                last_cmd = time.time()
                timed_out = False
            except socket.timeout:
                if (time.time() - last_cmd) > self.safety_timeout_s and not timed_out:
                    on_timeout()
                    timed_out = True

