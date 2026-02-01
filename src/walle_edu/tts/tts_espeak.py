import subprocess

class EspeakTTS:
    def __init__(self, enabled: bool, speed: str, amplitude: str):
        self.enabled = enabled
        self.speed = speed
        self.amplitude = amplitude

    def speak(self, text: str) -> None:
        if not self.enabled:
            return
        subprocess.run(["espeak", "-s", self.speed, "-a", self.amplitude, text], check=False)
