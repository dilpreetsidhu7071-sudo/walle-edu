import logging
import re
from dataclasses import dataclass
from faster_whisper import WhisperModel

log = logging.getLogger("walle.audio.stt")


@dataclass
class WhisperSTT:
    whisper_model: str

    def __post_init__(self) -> None:
        # In starting , loading of whisper model is initiated
        log.info("Loading Faster-Whisper model: %s", self.whisper_model)
        self.model = WhisperModel(self.whisper_model, compute_type="int8")

        # some unneccesary short words that will be ignored.
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
            #  If there is failure in the system because of bad recording , system will remain working.
            log.exception(" Failure in speech transcription")
            return ""

        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.debug("Whisper raw output: %r", text)

        if not text:
            return ""

        # removal of symbols,commas and question marks to make filtertaion simple.
        cleaned = re.sub(r"[^a-zA-Z]+", "", text).lower()

        # Ignore unneccesary short response.
        if cleaned in self._ignored_words:
            return ""

        return text

