import subprocess
import logging

log = logging.getLogger("recorder")


class Recorder:
    def __init__(self, seconds, wav_path):
        self.seconds = seconds
        self.wav_path = wav_path

    def record(self):
        # Recording  audio using arecord (Linux)
        command = [
            "arecord",
            "-f", "S16_LE",
            "-r", "16000",
            "-c", "1",
            "-d", str(self.seconds),
            self.wav_path,
        ]

        try:
            subprocess.run(command)
        except Exception as e:
            log.error("Audio recording failed: %s", e)

