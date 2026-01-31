import subprocess
import logging
from dataclasses import dataclass

log = logging.getLogger("walle.audio.recorder")

@dataclass
class Recorder:
    record_seconds: int
    wav_path: str

    def record(self) -> None:
        """
        Records audio using arecord. In VirtualBox if mic sleeps, keep pavucontrol open.
        """
        cmd = ["arecord", "-f", "cd", "-d", str(self.record_seconds), self.wav_path]
        log.info("Recording %ss to %s", self.record_seconds, self.wav_path)
        subprocess.run(cmd, check=False)
