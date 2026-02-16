import subprocess
import logging
import tempfile
import os

log = logging.getLogger("walle.tts")


class EspeakTTS:
    def __init__(self, enabled: bool, speed: str, amplitude: str):
        self.enabled = enabled

    def speak(self, text: str):
        if not self.enabled:
            return

        text = (text or "").strip()
        if not text:
            return

        wav_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                wav_path = f.name

            subprocess.run(["pico2wave", "-w", wav_path, text], check=True)

            # Play sound (no unsupported --volume flag)
            subprocess.run(["aplay", "-q", wav_path], check=False)

        except Exception as e:
            log.error("TTS failed: %s", e)

        finally:
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)

