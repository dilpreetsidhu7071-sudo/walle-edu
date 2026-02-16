import socket
import json
import logging

log = logging.getLogger("walle.udp")


class UDPSender:
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, payload):
        try:
            data = json.dumps(payload).encode("utf-8")
            self.socket.sendto(data, (self.ip, self.port))
        except Exception as e:
            log.error("UDP send failed: %s", e)

