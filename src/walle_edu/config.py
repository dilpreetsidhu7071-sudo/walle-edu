from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    # ===== General =====
    robot_name: str = "walle"

    # ===== Audio / STT =====
    whisper_model: str = "base"     # tiny/base/small
    record_seconds: int = 3
    wav_path: str = "/tmp/walle_cmd.wav"

    # ===== NLU =====
    use_chatgpt_nlu: bool = True
    nlu_model: str = "gpt-4o-mini"
    nlu_temperature: float = 0.1

    # ===== Educational Q&A =====
    use_chatgpt_edu: bool = True
    edu_model: str = "gpt-4o-mini"
    edu_temperature: float = 0.4
    edu_mode: str = "redirect"   # strict | redirect

    # ===== Networking =====
    pi_ip: str = "127.0.0.1"
    pi_port: int = 5005

    # ===== Safety timeout on Pi =====
    pi_safety_timeout_s: float = 1.5

    # ===== TTS =====
    tts_enabled: bool = True
    tts_speed: str = "160"
    tts_amplitude: str = "140"
