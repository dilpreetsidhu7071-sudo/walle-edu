import logging
import subprocess
import tempfile
import os

log = logging.getLogger("walle.tts")


class EspeakTTS:
    def __init__(self, enabled: bool, speed: int, amplitude: int):
        self.enabled = enabled
        self.speed = speed
        self.amplitude = amplitude

        self._play_proc: subprocess.Popen | None = None
        self._wav_path: str | None = None

    def is_playing(self) -> bool:
        return self._play_proc is not None and self._play_proc.poll() is None

    def stop(self) -> None:
        try:
            if self._play_proc and self._play_proc.poll() is None:
                self._play_proc.terminate()
                try:
                    self._play_proc.wait(timeout=0.2)
                except Exception:
                    self._play_proc.kill()
        except Exception:
            log.exception("Failed to stop TTS playback")
        finally:
            self._play_proc = None

            if self._wav_path and os.path.exists(self._wav_path):
                try:
                    os.remove(self._wav_path)
                except Exception:
                    pass
            self._wav_path = None

    def speak(self, text: str) -> None:
        if not self.enabled:
            return

        text = (text or "").strip()
        if not text:
            return

        self.stop()

        try:
            fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            self._wav_path = wav_path

            gen_cmd = [
                "espeak",
                f"-s{self.speed}",
                f"-a{self.amplitude}",
                "-w", wav_path,
                text,
            ]
            subprocess.run(gen_cmd, check=True)

            self._play_proc = subprocess.Popen(["aplay", "-q", wav_path])

        except Exception:
            log.exception("TTS speak failed")
            self.stop()
