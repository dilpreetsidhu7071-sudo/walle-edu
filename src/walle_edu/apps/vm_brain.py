# test github sync
import logging
import time
import re
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

def clean_for_tts(text: str) -> str:
    if not text:
        return ""

    # Remove code blocks ```...```
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Remove inline code `like this`
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove markdown bullets and headings
    text = re.sub(r"^\s*[-*•]+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)

    # Remove unwanted symbols
    text = text.replace("*", "")
    text = text.replace("_", "")
    text = text.replace("|", " ")
    text = text.replace("~", "")
    text = text.replace("^", "")

    # Remove repeated punctuation
    text = re.sub(r"([!?.,:;])\1+", r"\1", text)

    # Limit to first 3 sentences (professional for TTS)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    text = " ".join(sentences[:3])

    # Clean extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text



def _handle_robot_command(intent: dict, sender: UDPSender, tts: EspeakTTS) -> None:
    sender.send(intent)

    intent_type = intent.get("type")
    action = intent.get("action", "").strip()

    if not action:
        action = "done"

    if intent_type == "MOVE":
        tts.speak(f"Okay, {action}.")
    else:
        tts.speak(f"Gripper {action}.")


def _handle_educational_chat(query: str, cfg: Config, tts: EspeakTTS) -> None:
    gate = decide(query, cfg.edu_mode)

    if gate == "ALLOW":
        if cfg.use_chatgpt_edu:
            answer = answer_educational(query, cfg.edu_model, cfg.edu_temperature)
            tts.speak(answer or "I can answer educational questions, but I’m offline right now.")
        else:
            tts.speak("Ask me an educational question like maths, chemistry, science, or physics .")
        return

    if gate == "REFUSE":
        tts.speak("Sorry, I can answer only educational questions.")
        return

    # redirecting
    tts.speak(redirect_message(query))


def main() -> None:
    load_dotenv()
    setup_logging()

    cfg = Config()

    recorder = Recorder(cfg.record_seconds, cfg.wav_path)
    stt = WhisperSTT(cfg.whisper_model)

    nlu = NLURouter(cfg.use_chatgpt_nlu, cfg.nlu_model, cfg.nlu_temperature)
    sender = UDPSender(cfg.pi_ip, cfg.pi_port)

    tts = EspeakTTS(cfg.tts_enabled, cfg.tts_speed, cfg.tts_amplitude)

    log.info("VM Brain started (%s).", cfg.robot_name)
    log.info("UDP target: %s:%s", cfg.pi_ip, cfg.pi_port)

    while True:
        try:
            recorder.record()

            text = stt.transcribe(cfg.wav_path)
            if not text:
                log.info("No clear command detected.")
                continue

            log.info("Transcribed: %s", text)
       # already built-in introduction.
            t = text.lower().strip()

            if "introduce yourself" in t or "who are you" in t:
                tts.speak(
                    "Hi, I’m WALL-E. I’m a educational robot. "
                    "I can follow voice commands like forward, left, right and stop, "
                    "and I can also answer educational questions."
                )
                continue


            intent = nlu.parse(text) or {}
            log.info("Intent: %s", intent)

            intent_type = intent.get("type")

            if intent_type in ("MOVE", "GRIPPER"):
                _handle_robot_command(intent, sender, tts)
                continue

            query = intent.get("query") or text
            _handle_educational_chat(query, cfg, tts)

            time.sleep(0.2)

        except KeyboardInterrupt:
            log.info("Exiting.")
            break
        except Exception:
            log.exception("Error in VM Brain loop")
            time.sleep(0.5)


if __name__ == "__main__":
    main()

