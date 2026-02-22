
import logging
import os
import random
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

# ---------------- Voice phrases ----------------

WAKE_WORDS = ("wake up", "walle wake up", "wall e wake up")
SLEEP_WORDS = ("go to sleep", "sleep now", "walle sleep")

STOP_WORDS = (
    "stop", "stop now", "stop it", "stopped",
    "cancel", "abort",
    "stop talking", "be quiet", "mute",
    "shut up"
)

INTRO_WORDS = ("introduce yourself", "who are you")
HELP_WORDS = ("help", "what can you do", "commands")

# Simple movement phrases (fast detection)
MOVE_WORDS = {
    "forward": ("forward", "go forward", "move forward"),
    "back": ("back", "go back", "move back"),
    "left": ("left", "turn left"),
    "right": ("right", "turn right"),
}

# ---------------- Human responses ----------------

ACKS = ["Okay.", "Alright.", "Got it."]
WAKE_ACKS = ["I'm awake."]
SLEEP_ACKS = ["Going to sleep. Say wake up to wake me."]
CONFUSED = ["Sorry, can you repeat that?", "I didn’t catch that clearly."]
TEACH_START = ["Alright, here’s the idea.", "Good question."]

# ---------------- Settings ----------------

MIN_TEXT_LEN = 3

# IMPORTANT: This file is used ONLY for quick interrupt listening (STOP detection)
INTERRUPT_WAV = "/tmp/walle_interrupt.wav"

# Keep short so STOP feels instant
INTERRUPT_SECONDS = 1

# ---------------- Helpers ----------------

def pick(options):
    return random.choice(options)

def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def contains(text: str, phrases) -> bool:
    t = norm(text)
    return any(p in t for p in phrases)

def looks_bad(text: str) -> bool:
    return not text or len(text.strip()) < MIN_TEXT_LEN

def clean_for_tts(text: str) -> str:
    """
    Remove markdown, code blocks, weird symbols, and links so espeak
    doesn't read them as "symbols".
    """
    if not text:
        return ""

    # Remove code blocks ```...```
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Remove inline code `like this`
    text = re.sub(r"`[^`]+`", "", text)

    # Remove markdown headings/bullets
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*•]+\s*", "", text, flags=re.MULTILINE)

    # Remove links
    text = re.sub(r"https?://\S+", "", text)

    # Keep letters/numbers/basic punctuation only
    text = re.sub(r"[^a-zA-Z0-9\s\.\,\?\!\:\;\'\"\-\(\)]", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text

# ---------------- Audio helpers ----------------

def listen_for_stop(rec: Recorder, stt: WhisperSTT) -> bool:
    """
    Record a very short clip and check if it contains STOP words.
    Used for quick interrupt while speaking AND as a fast check when idle.
    """
    if os.path.exists(INTERRUPT_WAV):
        os.remove(INTERRUPT_WAV)

    rec.record()
    if not os.path.exists(INTERRUPT_WAV):
        return False

    heard = stt.transcribe(INTERRUPT_WAV) or ""
    return contains(heard, STOP_WORDS)

def wait_or_interrupt(tts: EspeakTTS, rec: Recorder, stt: WhisperSTT) -> bool:
    """
    While TTS is playing, keep checking for STOP.
    If STOP is heard, stop TTS and return True.
    """
    while tts.is_playing():
        if listen_for_stop(rec, stt):
            tts.stop()
            return True
        time.sleep(0.1)
    return False

# ---------------- Robot helpers ----------------

def stop_robot(sender: UDPSender):
    sender.send({"type": "MOVE", "action": "stop"})

def emergency_stop(sender: UDPSender, tts: EspeakTTS):
    stop_robot(sender)
    tts.stop()

def quick_move(text: str):
    t = norm(text)
    for action, phrases in MOVE_WORDS.items():
        for p in phrases:
            if p in t:
                return {"type": "MOVE", "action": action}
    return None

def safe_speak(tts: EspeakTTS, text: str):
    """
    Always clean before speaking.
    """
    tts.speak(clean_for_tts(text))

# ---------------- Main ----------------

def main():
    load_dotenv()
    setup_logging()

    cfg = Config()

    # Main recording (normal listening)
    recorder = Recorder(cfg.record_seconds, cfg.wav_path)

    # Interrupt recording (very short, for STOP detection)
    interrupt_rec = Recorder(INTERRUPT_SECONDS, INTERRUPT_WAV)

    stt = WhisperSTT(cfg.whisper_model)

    nlu = NLURouter(cfg.use_chatgpt_nlu, cfg.nlu_model, cfg.nlu_temperature)
    sender = UDPSender(cfg.pi_ip, cfg.pi_port)
    tts = EspeakTTS(cfg.tts_enabled, cfg.tts_speed, cfg.tts_amplitude)

    awake = False
    last_spoken = ""

    log.info("WALL-E VM Brain started")

    while True:
        try:
            # If we are speaking, allow STOP to interrupt speech
            wait_or_interrupt(tts, interrupt_rec, stt)

            # NEW: Even if we are NOT speaking, do a quick STOP check
            # This makes STOP feel instant (doesn't wait for long record_seconds)
            if listen_for_stop(interrupt_rec, stt):
                emergency_stop(sender, tts)
                msg = pick(ACKS)
                safe_speak(tts, msg)
                last_spoken = msg
                wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            # Normal listening (longer clip)
            recorder.record()
            text = stt.transcribe(cfg.wav_path)
            log.info("Heard: %s", text)

            if looks_bad(text):
                if awake:
                    msg = pick(CONFUSED)
                    safe_speak(tts, msg)
                    last_spoken = msg
                    wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            t = norm(text)

            # -------- PRIORITY 1: STOP --------
            if contains(t, STOP_WORDS):
                emergency_stop(sender, tts)
                msg = pick(ACKS)
                safe_speak(tts, msg)
                last_spoken = msg
                wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            # -------- SLEEP / WAKE --------
            if contains(t, SLEEP_WORDS):
                awake = False
                stop_robot(sender)
                msg = pick(SLEEP_ACKS)
                safe_speak(tts, msg)
                last_spoken = msg
                wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            if not awake:
                if contains(t, WAKE_WORDS):
                    awake = True
                    msg = pick(WAKE_ACKS)
                    safe_speak(tts, msg)
                    last_spoken = msg
                    wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            # -------- PRIORITY 2: MOVE --------
            move = quick_move(text)
            if move:
                sender.send(move)
                msg = f"{pick(ACKS)} Moving {move['action']}."
                safe_speak(tts, msg)
                last_spoken = msg
                wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            # -------- PRIORITY 3: CHAT --------
            # Always stop robot before chatting
            stop_robot(sender)

            if contains(t, HELP_WORDS):
                msg = (
                    "You can move me with forward, back, left, right, or stop. "
                    "You can also ask me educational questions."
                )
                safe_speak(tts, msg)
                last_spoken = msg
                wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            if contains(t, INTRO_WORDS):
                msg = (
                    "Hi, I’m WALL-E. I’m an educational robot. "
                    "I can move using voice commands and answer questions."
                )
                safe_speak(tts, msg)
                last_spoken = msg
                wait_or_interrupt(tts, interrupt_rec, stt)
                continue

            # Educational chat
            gate = decide(text, cfg.edu_mode)
            if gate == "ALLOW":
                safe_speak(tts, pick(TEACH_START))
                wait_or_interrupt(tts, interrupt_rec, stt)

                answer = answer_educational(text, cfg.edu_model, cfg.edu_temperature)
                answer = clean_for_tts(answer)
                safe_speak(tts, answer)
                last_spoken = answer
                wait_or_interrupt(tts, interrupt_rec, stt)
            else:
                msg = redirect_message(text)
                safe_speak(tts, msg)
                last_spoken = msg
                wait_or_interrupt(tts, interrupt_rec, stt)

        except KeyboardInterrupt:
            log.info("Shutting down")
            break
        except Exception:
            log.exception("Error in main loop")
            time.sleep(0.5)


if __name__ == "__main__":
    main()
