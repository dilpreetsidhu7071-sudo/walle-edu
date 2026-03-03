"""
WALL-E VM Brain - Continuous Listening (Option B, faster STOP)

Fixes added:
- Stays silent on noise / Whisper hallucinations
- Ignores short/noisy “utterances” at mic level (better VAD gating)
- Still supports single-word movement commands + wake/sleep/help/stop
"""

import logging
import os
import random
import re
import time
import math
import wave
import subprocess
import threading
from collections import deque
from dotenv import load_dotenv

from walle_edu.config import Config
from walle_edu.logging_setup import setup_logging
from walle_edu.audio.stt_whisper import WhisperSTT
from walle_edu.nlu.router import NLURouter
from walle_edu.net.udp_sender import UDPSender
from walle_edu.tts.tts_espeak import EspeakTTS
from walle_edu.edu.guard import decide, redirect_message
from walle_edu.edu.qa_chatgpt import answer_educational

log = logging.getLogger("walle.vm_brain")


# ---------------- Phrases ----------------

WAKE_WORDS = ("wake up", "walle wake up", "wall e wake up")
SLEEP_WORDS = ("go to sleep", "sleep now", "walle sleep")

# stop TALKING (interrupt speech)
SPEECH_STOP_WORDS = (
    "stop", "stop talking", "stop speaking",
    "be quiet", "quiet", "mute", "shut up",
    "cancel", "abort", "enough"
)

# stop robot movement (explicit)
ROBOT_STOP_WORDS = ("stop robot", "stop moving", "halt", "freeze", "emergency stop")

INTRO_WORDS = ("introduce yourself", "who are you")
HELP_WORDS = ("help", "what can you do", "commands")

MOVE_WORDS = {
    "forward": ("forward", "go forward", "move forward"),
    "back": ("back", "go back", "move back", "backward"),
    "left": ("left", "turn left", "go left"),
    "right": ("right", "turn right", "go right"),
}

ACKS = ["Okay.", "Alright.", "Got it."]
WAKE_ACKS = ["I'm awake.", "Yep — I'm here."]
SLEEP_ACKS = ["Going to sleep. Say wake up if you need me."]
STOP_TALKING_ACK = ["Okay, I’ll stop."]
TEACH_START = ["Alright, here’s the idea.", "Good question."]

MAX_CHUNK_CHARS = 120  # smaller chunks = more stop chances


# ---------------- Noise / hallucination filters ----------------

# If Whisper outputs these from noise, ignore them
NOISE_TEXTS = {
    "you", "thank you", "thanks", "okay", "ok", "hello", "hi",
    "bye", "yes", "no", "hmm", "mm", "uh", "um"
}
MIN_TEXT_CHARS = 4      # ignore tiny transcriptions
MIN_TEXT_WORDS = 2      # require >= 2 words for chat (movement/wake/sleep are exceptions)


# ---------------- Helpers ----------------

def pick(xs):
    return random.choice(xs)

def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def contains(text: str, phrases) -> bool:
    t = norm(text)
    return any(p in t for p in phrases)

def clean_for_tts(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^a-zA-Z0-9\s\.\,\?\!\:\;\'\"\-\(\)]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS):
    cleaned = clean_for_tts(text)
    if not cleaned:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    out, chunk = [], ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if chunk and len(chunk) + 1 + len(s) > max_chars:
            out.append(chunk)
            chunk = s
        else:
            chunk = (chunk + " " + s).strip() if chunk else s
    if chunk:
        out.append(chunk)
    return out

def is_movement_single_word(t: str) -> bool:
    # t should already be norm()'d
    for _action, phrases in MOVE_WORDS.items():
        for p in phrases:
            if t == norm(p):
                return True
    return False

def looks_like_noise(text: str) -> bool:
    t = norm(text)
    if not t:
        return True

    # allow core single-word intents even if short
    if is_movement_single_word(t):
        return False
    if t in ("stop", "help"):
        return False
    if contains(t, WAKE_WORDS) or contains(t, SLEEP_WORDS):
        return False

    # tiny / filler-like outputs
    if len(t) < MIN_TEXT_CHARS:
        return True

    words = t.split()
    if len(words) < MIN_TEXT_WORDS:
        if t in NOISE_TEXTS:
            return True
        return True

    # common noise hallucinations
    if t in NOISE_TEXTS:
        return True

    return False


# ---------------- Continuous Mic ----------------

class ContinuousMic:
    """
    Continuous mic capture + simple VAD (RMS threshold).

    Extra noise protection:
    - Require minimum "speech frames" (min_speech_ms)
    - Require minimum average loudness (min_avg_rms)
    """

    def __init__(
        self,
        device: str = "pulse",
        rate: int = 16000,
        channels: int = 1,

        frame_ms: int = 10,           # more responsive
        rms_threshold: int = 450,     # raise to reduce noise triggers (try 420-600)
        silence_ms_to_end: int = 220, # shorter utterances

        min_speech_ms: int = 220,     # must have at least this much "loud" audio
        min_avg_rms: int = 480,       # utterance average loudness must exceed this

        max_utterance_s: int = 5,
    ):
        self.device = device
        self.rate = rate
        self.channels = channels

        self.frame_ms = frame_ms
        self.bytes_per_sample = 2  # S16_LE
        self.frame_bytes = int(rate * (frame_ms / 1000.0) * self.bytes_per_sample * channels)

        self.rms_threshold = rms_threshold
        self.silence_frames_to_end = max(1, silence_ms_to_end // frame_ms)
        self.max_frames = int((max_utterance_s * 1000) / frame_ms)

        self.min_speech_frames = max(1, min_speech_ms // frame_ms)
        self.min_avg_rms = min_avg_rms

        self._proc = None
        self._thread = None
        self._stop = threading.Event()

        self._lock = threading.Lock()
        self._queue = deque(maxlen=20)

    def start(self):
        cmd = [
            "arecord",
            "-D", self.device,
            "-f", "S16_LE",
            "-r", str(self.rate),
            "-c", str(self.channels),
            "-t", "raw",
        ]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def pop_wav(self):
        with self._lock:
            if self._queue:
                return self._queue.popleft()
        return None

    def _rms(self, pcm_bytes: bytes) -> float:
        if not pcm_bytes:
            return 0.0
        count = len(pcm_bytes) // 2
        if count <= 0:
            return 0.0
        total = 0
        for i in range(0, len(pcm_bytes), 2):
            s = int.from_bytes(pcm_bytes[i:i+2], "little", signed=True)
            total += s * s
        return math.sqrt(total / count)

    def _write_wav(self, path: str, raw_pcm: bytes):
        with wave.open(path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.rate)
            wf.writeframes(raw_pcm)

    def _run(self):
        speaking = False
        silence_count = 0
        frames = []

        speech_frames = 0
        rms_sum = 0.0
        rms_count = 0

        while not self._stop.is_set():
            if not self._proc or not self._proc.stdout:
                break

            data = self._proc.stdout.read(self.frame_bytes)
            if not data:
                continue

            level = self._rms(data)

            if level >= self.rms_threshold:
                if not speaking:
                    speaking = True
                    frames = []
                    silence_count = 0
                    speech_frames = 0
                    rms_sum = 0.0
                    rms_count = 0

                frames.append(data)
                speech_frames += 1

                rms_sum += level
                rms_count += 1
            else:
                if speaking:
                    frames.append(data)
                    silence_count += 1

                    rms_sum += level
                    rms_count += 1

                    if silence_count >= self.silence_frames_to_end or len(frames) >= self.max_frames:
                        avg_rms = (rms_sum / rms_count) if rms_count else 0.0

                        # HARD FILTERS: ignore short/noisy "utterances"
                        if speech_frames >= self.min_speech_frames and avg_rms >= self.min_avg_rms:
                            raw = b"".join(frames)
                            out = f"/tmp/walle_utt_{int(time.time()*1000)}.wav"
                            self._write_wav(out, raw)

                            with self._lock:
                                self._queue.append(out)

                        speaking = False
                        frames = []
                        silence_count = 0
                        speech_frames = 0
                        rms_sum = 0.0
                        rms_count = 0


# ---------------- Robot helpers ----------------

def stop_robot(sender: UDPSender):
    sender.send({"type": "MOVE", "action": "stop"})

def quick_move(text: str):
    t = norm(text)
    for action, phrases in MOVE_WORDS.items():
        for p in phrases:
            if norm(p) in t:
                return {"type": "MOVE", "action": action}
    return None


# ---------------- Main ----------------

def main():
    load_dotenv()
    setup_logging()

    cfg = Config()
    stt = WhisperSTT(cfg.whisper_model)
    nlu = NLURouter(cfg.use_chatgpt_nlu, cfg.nlu_model, cfg.nlu_temperature)
    sender = UDPSender(cfg.pi_ip, cfg.pi_port)
    tts = EspeakTTS(cfg.tts_enabled, cfg.tts_speed, cfg.tts_amplitude)

    # Continuous mic
    mic_device = os.getenv("WALLE_MIC_DEVICE", "pulse")

    # Tuned defaults for noisy VirtualBox
    mic = ContinuousMic(
        device=mic_device,
        frame_ms=10,
        rms_threshold=int(os.getenv("WALLE_RMS_THRESHOLD", "450")),
        silence_ms_to_end=int(os.getenv("WALLE_SILENCE_MS", "220")),
        min_speech_ms=int(os.getenv("WALLE_MIN_SPEECH_MS", "220")),
        min_avg_rms=int(os.getenv("WALLE_MIN_AVG_RMS", "480")),
    )
    mic.start()

    awake = False
    speaking_mode = False

    log.info("WALL-E started (continuous mic: %s)", mic_device)

    try:
        while True:
            wav_path = mic.pop_wav()
            if not wav_path:
                time.sleep(0.01)
                continue

            text = (stt.transcribe(wav_path) or "").strip()
            try:
                os.remove(wav_path)
            except Exception:
                pass

            # ✅ SILENT ON NOISE / HALLUCINATIONS
            if looks_like_noise(text):
                continue

            log.info("Heard: %s", text)
            t = norm(text)

            # FAST STOP: if bot is talking and user says stop -> stop immediately
            if speaking_mode and contains(t, SPEECH_STOP_WORDS):
                try:
                    tts.stop()
                except Exception:
                    pass
                tts.speak(pick(STOP_TALKING_ACK))
                speaking_mode = False
                continue

            # Sleep / Wake
            if contains(t, SLEEP_WORDS):
                awake = False
                stop_robot(sender)
                tts.speak(pick(SLEEP_ACKS))
                continue

            if not awake:
                if contains(t, WAKE_WORDS):
                    awake = True
                    tts.speak(pick(WAKE_ACKS))
                continue

            # Robot stop
            if contains(t, ROBOT_STOP_WORDS):
                stop_robot(sender)
                tts.speak(pick(ACKS))
                continue

            # Movement local
            move = quick_move(text)
            if move:
                sender.send(move)
                speaking_mode = True
                tts.speak(f"{pick(ACKS)} Moving {move['action']}.")
                while tts.is_playing():
                    time.sleep(0.02)
                speaking_mode = False
                continue

            # Chat: always stop robot first
            stop_robot(sender)

            if contains(t, HELP_WORDS):
                speaking_mode = True
                tts.speak(
                    "You can move me with forward, back, left, right. "
                    "Say stop robot to stop movement. "
                    "Ask me educational questions too."
                )
                while tts.is_playing():
                    time.sleep(0.02)
                speaking_mode = False
                continue

            if contains(t, INTRO_WORDS):
                speaking_mode = True
                tts.speak("Hi, I’m WALL-E. I’m an educational robot.")
                while tts.is_playing():
                    time.sleep(0.02)
                speaking_mode = False
                continue

            intent = nlu.parse(text) or {}
            if intent.get("type") in ("MOVE", "GRIPPER"):
                sender.send(intent)
                tts.speak(pick(ACKS))
                continue

            query = intent.get("query") or text
            gate = decide(query, cfg.edu_mode)

            if gate == "ALLOW":
                speaking_mode = True
                tts.speak(pick(TEACH_START))
                while tts.is_playing():
                    time.sleep(0.02)

                answer = answer_educational(query, cfg.edu_model, cfg.edu_temperature)

                for chunk in split_into_chunks(answer):
                    tts.speak(chunk)
                    while tts.is_playing():
                        time.sleep(0.02)
                    # continuous mic keeps listening; if user says "stop",
                    # next utterance triggers the fast-stop block above.

                speaking_mode = False
            else:
                speaking_mode = True
                msg = redirect_message(query) or "Sorry, I can only answer educational questions."
                tts.speak(msg)
                while tts.is_playing():
                    time.sleep(0.02)
                speaking_mode = False

    except KeyboardInterrupt:
        log.info("Shutting down")
    finally:
        mic.stop()


if __name__ == "__main__":
    main()
