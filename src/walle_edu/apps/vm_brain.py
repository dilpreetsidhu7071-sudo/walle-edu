import time
import logging
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

def main():
    load_dotenv()
    setup_logging()

    cfg = Config()

    recorder = Recorder(cfg.record_seconds, cfg.wav_path)
    stt = WhisperSTT(cfg.whisper_model)
    nlu = NLURouter(cfg.use_chatgpt_nlu, cfg.nlu_model, cfg.nlu_temperature)
    sender = UDPSender(cfg.pi_ip, cfg.pi_port)
    tts = EspeakTTS(cfg.tts_enabled, cfg.tts_speed, cfg.tts_amplitude)

    log.info("VM Brain started. UDP target=%s:%s", cfg.pi_ip, cfg.pi_port)
    log.info("Tip: If mic sleeps in VirtualBox, keep pavucontrol open while running.")

    while True:
        try:
            recorder.record()
            text = stt.transcribe(cfg.wav_path)

            if not text:
                log.info("Heard nothing.")
                continue

            log.info("Transcribed: %s", text)

            intent = nlu.parse(text)
            log.info("Intent: %s", intent)

            t = intent.get("type")

            if t in ("MOVE", "GRIPPER"):
                # Send to Pi
                sender.send(intent)
                # Speak confirmation
                if t == "MOVE":
                    tts.speak(f"Okay. {intent.get('action', 'move')}.")
                else:
                    tts.speak(f"Gripper {intent.get('action', '')}.")
                continue

            # CHAT: educational-only
            query = intent.get("query", text)
            decision = decide(query, cfg.edu_mode)

            if decision == "ALLOW":
                if cfg.use_chatgpt_edu:
                    ans = answer_educational(query, cfg.edu_model, cfg.edu_temperature)
                    if ans:
                        tts.speak(ans)
                    else:
                        tts.speak("I can answer educational questions, but I am offline right now.")
                else:
                    tts.speak("Ask me an educational question like math, science, or history.")
            elif decision == "REFUSE":
                tts.speak("Sorry, I can only answer educational questions.")
            else:
                tts.speak(redirect_message(query))

            time.sleep(0.2)

        except KeyboardInterrupt:
            log.info("Exiting.")
            break

if __name__ == "__main__":
    main()
