import logging
from dataclasses import dataclass
import whisper

log = logging.getLogger("walle.audio.stt")

@dataclass
class WhisperSTT:
    model_name: str

    def __post_init__(self):
        log.info("Loading Whisper model: %s", self.model_name)
        self.model = whisper.load_model(self.model_name)

    def transcribe(self, wav_path: str) -> str:
        result = self.model.transcribe(wav_path, fp16=False)
        text = (result.get("text") or "").strip()
        return text
