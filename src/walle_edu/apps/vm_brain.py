import logging
import os
import re
import time
from dotenv import load_dotenv

from walle_edu.config import Config
from walle_edu.logging_setup import setup_logging

from walle_edu.audio.recorder import Recorder
from walle_edu.audio.stt_whisper import WhisperSTT

from walle_edu.nlu.router import NLURouter
from walle_edu.net.udp_sender import UDPSender

from walle_edu.tts.tts_espeak import EspeakTTS
from walle_edu.edu.guard import decide, redirect_message
from walle_edu.edu.qa_chatgpt import answer_educational


log = logging.getLogger("walle.vm_brain")


# ===== Voice phrases (you can change these anytime) =====
WAKE_WORDS = (
    "wake up",
    "wakeup",
    "wall e wake up",
    "walle wake up",
    "wall-e wake up",
)

SLEEP_WORDS = (
    "go to sleep",
    "sleep now",
    "wall e sleep",
    "walle sleep",
    "wall-e sleep",
)

# Whisper catches these better than only "stop speaking"
STOP_WORDS = (
    "abort",
    "cancel",
    "stop now",
    "wall e stop",
    "walle stop",
    "wall-e stop",
    "stop speaking",
    "stop talking",
    "be quiet",
    "quiet",
    "mute",
)

INTRO_WORDS = (
    "introduce yourself",
    "who are you",
    "what are you",
)

# ===== Small behaviour tuning =====
MAX_FAILS_BEFORE_HELP = 2
MIN_TEXT_LEN = 3
MIN_ALPHA_RATIO = 0.60

# Long answer chunking (for clearer TTS)
MAX_CHARS_PER_CHUNK = 240
MAX_SENTENCES_PER_CHUNK = 3

# While WALL-E is speaking, we record small clips just to listen for stop words.
# Keep it an integer because arecord -d often doesn't support decimals.
INTERRUPT_SECONDS = 1
INTERRUPT_WAV = "/tmp/walle_interrupt.wav"


# ----------------- Text cleaning / helpers -----------------

def _has_any(text_lower: str, phrases) -> bool:
    return any(p in text_lower for p in phrases)


def _alpha_ratio(s: str) -> float:
    if not s:
        return 0.0
    letters = sum(ch.isalpha() for ch in s)
    return letters / max(len(s), 1)


def _looks_uncertain(stt_text: str) -> bool:
    """
    Quick heuristics for low-quality transcripts (noise / mumbling):
    - too short
    - too many non-letters
    """
    s = (stt_text or "").strip()
    if len(s) < MIN_TEXT_LEN:
        return True
    if _alpha_ratio(s) < MIN_ALPHA_RATIO:
        return True
    return False


def _clean_for_tts(text: str) -> str:
    """Remove markdown/code stuff so speech sounds normal."""
    if not text:
        return ""

    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)      # code blocks
    text = re.sub(r"`([^`]+)`", r"\1", text)                    # inline code
    text = re.sub(r"^\s*[-*•]+\s*", "", text, flags=re.M)       # bullets
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.M)           # headings

    text = text.replace("|", " ")
    for ch in ("*", "_", "~", "^"):
        text = text.replace(ch, "")

    text = re.sub(r"([!?.,:;])\1+", r"\1", text)                # !!! -> !
    text = re.sub(r"\s+", " ", text).strip()                    # whitespace
    return text


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


# ----------------- Speech + interrupt logic -----------------

def _listen_for_stop(interrupt_recorder: Recorder, stt: WhisperSTT) -> bool:
    """
    Records a short snippet and checks for stop words.
    This is only used while WALL-E is speaking.
    """
    try:
        if os.path.exists(INTERRUPT_WAV):
            os.remove(INTERRUPT_WAV)

        interrupt_recorder.record()

        if not os.path.exists(INTERRUPT_WAV):
            return False

        heard = stt.transcribe(INTERRUPT_WAV) or ""
        h = heard.lower().strip()

        if not h:
            return False

        return _has_any(h, STOP_WORDS)

    except Exception:
        # keep it quiet in the terminal
        log.debug("interrupt listening failed", exc_info=True)
        return False


def _wait_until_done_or_stopped(tts: EspeakTTS, interrupt_recorder: Recorder, stt: WhisperSTT) -> bool:
    """
    Waits for speech to finish.
    While waiting, allow user to stop speech.
    Returns True if speech was interrupted.
    """
    while tts.is_playing():
        if _listen_for_stop(interrupt_recorder, stt):
            tts.stop()
            return True
        time.sleep(0.05)
    return False


def _say_long(tts: EspeakTTS, interrupt_recorder: Recorder, stt: WhisperSTT, text: str) -> None:
    """
    Speak a long answer in chunks so it doesn't get cut off.
    Each chunk can be interrupted by stop words.
    """
    cleaned = _clean_for_tts(text)
    if not cleaned:
        tts.speak("I don’t have an answer right now.")
        _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
        return

    sentences = _split_sentences(cleaned)
    if not sentences:
        tts.speak(cleaned)
        _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
        return

    chunk = ""
    count = 0

    for s in sentences:
        candidate = (chunk + " " + s).strip() if chunk else s

        if chunk and (len(candidate) > MAX_CHARS_PER_CHUNK or count >= MAX_SENTENCES_PER_CHUNK):
            tts.speak(chunk)
            if _wait_until_done_or_stopped(tts, interrupt_recorder, stt):
                return
            chunk = s
            count = 1
        else:
            chunk = candidate
            count += 1

    if chunk:
        tts.speak(chunk)
        _wait_until_done_or_stopped(tts, interrupt_recorder, stt)


# ----------------- Main handlers -----------------

def _intro(tts: EspeakTTS, interrupt_recorder: Recorder, stt: WhisperSTT) -> None:
    _say_long(
        tts,
        interrupt_recorder,
        stt,
        "Hi, I’m WALL-E. I’m an educational robot. "
        "I can follow voice commands like forward, left, right and stop, "
        "and I can also answer educational questions."
    )


def _handle_robot(intent: dict, sender: UDPSender, tts: EspeakTTS,
                  interrupt_recorder: Recorder, stt: WhisperSTT) -> None:
    sender.send(intent)

    intent_type = intent.get("type")
    action = (intent.get("action") or "").strip() or "done"

    if intent_type == "MOVE":
        tts.speak(f"Okay, {action}.")
    else:
        tts.speak(f"Gripper {action}.")

    _wait_until_done_or_stopped(tts, interrupt_recorder, stt)


def _handle_edu(query: str, cfg: Config, tts: EspeakTTS,
                interrupt_recorder: Recorder, stt: WhisperSTT) -> None:
    gate = decide(query, cfg.edu_mode)

    if gate == "ALLOW":
        if cfg.use_chatgpt_edu:
            answer = answer_educational(query, cfg.edu_model, cfg.edu_temperature)
            _say_long(tts, interrupt_recorder, stt, answer)
        else:
            tts.speak("Ask me an educational question like maths, chemistry, science, or physics.")
            _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
        return

    if gate == "REFUSE":
        tts.speak("Sorry, I can answer only educational questions.")
        _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
        return

    # redirect response (still spoken as chunks)
    _say_long(tts, interrupt_recorder, stt, redirect_message(query))


def main() -> None:
    load_dotenv()
    setup_logging()

    cfg = Config()

    recorder = Recorder(cfg.record_seconds, cfg.wav_path)
    stt = WhisperSTT(cfg.whisper_model)

    # only used while speaking
    interrupt_recorder = Recorder(INTERRUPT_SECONDS, INTERRUPT_WAV)

    nlu = NLURouter(cfg.use_chatgpt_nlu, cfg.nlu_model, cfg.nlu_temperature)
    sender = UDPSender(cfg.pi_ip, cfg.pi_port)
    tts = EspeakTTS(cfg.tts_enabled, cfg.tts_speed, cfg.tts_amplitude)

    log.info("VM Brain started (%s).", cfg.robot_name)
    log.info("UDP target: %s:%s", cfg.pi_ip, cfg.pi_port)

    awake = False
    no_hear = 0
    unsure = 0

    while True:
        try:
            # If something is still speaking, wait (and allow stop)
            _wait_until_done_or_stopped(tts, interrupt_recorder, stt)

            recorder.record()
            text = stt.transcribe(cfg.wav_path)

            if not text:
                no_hear += 1
                log.info("No speech detected.")
                if awake:
                    if no_hear <= MAX_FAILS_BEFORE_HELP:
                        tts.speak("I didn’t catch that. Please try again.")
                    else:
                        tts.speak("Sorry, I still can’t hear clearly. Try speaking closer and slower.")
                        no_hear = 0
                    _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
                continue

            no_hear = 0

            t = text.lower().strip()
            log.info("Heard: %s", text)

            # stop words always allowed
            if _has_any(t, STOP_WORDS):
                tts.stop()
                tts.speak("Okay.")
                _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
                continue

            # sleep command
            if _has_any(t, SLEEP_WORDS):
                awake = False
                tts.stop()
                tts.speak("Going to sleep. Say wake up to wake me.")
                _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
                continue

            # waking up
            if not awake:
                if _has_any(t, WAKE_WORDS):
                    awake = True
                    tts.speak("I'm awake.")
                    _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
                else:
                    log.info("Asleep: ignoring until wake word.")
                continue

            # awake mode from here
            if _looks_uncertain(text):
                unsure += 1
                if unsure <= MAX_FAILS_BEFORE_HELP:
                    tts.speak("I might be wrong — can you repeat that?")
                else:
                    tts.speak("I’m not sure I understood. Please say it again slowly.")
                    unsure = 0
                _wait_until_done_or_stopped(tts, interrupt_recorder, stt)
                continue

            unsure = 0

            if _has_any(t, INTRO_WORDS):
                _intro(tts, interrupt_recorder, stt)
                continue

            intent = nlu.parse(text) or {}
            log.info("Intent: %s", intent)

            intent_type = intent.get("type")
            if intent_type in ("MOVE", "GRIPPER"):
                _handle_robot(intent, sender, tts, interrupt_recorder, stt)
                continue

            query = intent.get("query") or text
            _handle_edu(query, cfg, tts, interrupt_recorder, stt)

            time.sleep(0.2)

        except KeyboardInterrupt:
            log.info("Exiting.")
            break
        except Exception:
            log.exception("Error in VM Brain loop")
            time.sleep(0.5)


if __name__ == "__main__":
    main()
