import json
import socket
import logging
from dataclasses import dataclass
from typing import Dict, Any

log = logging.getLogger("walle.net.sender")

@dataclass
class UDPSender:
    ip: str
    port: int

    def send(self, payload: Dict[str, Any]) -> None:
        msg = json.dumps(payload).encode("utf-8")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(msg, (self.ip, self.port))
            log.info("Sent UDP to %s:%s -> %s", self.ip, self.port, payload)
        finally:
            sock.close()

