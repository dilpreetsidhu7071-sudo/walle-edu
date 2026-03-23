import logging
import re
from dataclasses import dataclass
from faster_whisper import WhisperModel

log = logging.getLogger("walle.audio.stt")


@dataclass
class WhisperSTT:
    whisper_model: str

    def __post_init__(self) -> None:
        # In  begining the whisper model start loading
        log.info("Loading Faster-Whisper model: %s", self.whisper_model)
        self.model = WhisperModel(self.whisper_model, compute_type="int8")

        # some useless words that can be ignored.
        self._ignored_words = {
            "you", "yeah", "yah", "um", "uh", "okay", "ok"
        }

    def transcribe(self, wav_path: str) -> str:
        try:
            segments, _ = self.model.transcribe(
                wav_path,
                language="en",
                beam_size=2,
                vad_filter=True,
                condition_on_previous_text=False,
            )
        except Exception:
            # the system will keep working if is there issue with bad recording.
            log.exception(" Failure in speech transcription")
            return ""

        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.debug("Whisper raw output: %r", text)

        if not text:
            return ""

        # Remove symbols,commas and signs during voice generation.
        cleaned = re.sub(r"[^a-zA-Z]+", "", text).lower()

        # Ignore short reponse
        if cleaned in self._ignored_words:
            return ""

        return text

