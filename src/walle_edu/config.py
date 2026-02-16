import os
from dataclasses import dataclass


def get_bool(env_name: str, default: bool) -> bool:
    value = os.environ.get(env_name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def get_int(env_name: str, default: int) -> int:
    value = os.environ.get(env_name)
    return default if value is None else int(value)


def get_float(env_name: str, default: float) -> float:
    value = os.environ.get(env_name)
    return default if value is None else float(value)


def get_str(env_name: str, default: str) -> str:
    value = os.environ.get(env_name)
    return default if value is None else value


@dataclass(frozen=True)
class Config:
    # generalized settings
    robot_name: str = get_str("ROBOT_NAME", "walle")

    # Speech-to-text (Whisper model)
    whisper_model: str = get_str("WHISPER_MODEL", "small")
    record_seconds: int = get_int("RECORD_SECONDS", 6)
    wav_path: str = get_str("WAV_PATH", "/tmp/walle_cmd.wav")

    # LLM model ( language understanding)
    use_chatgpt_nlu: bool = get_bool("USE_CHATGPT_NLU", True)
    nlu_model: str = get_str("NLU_MODEL", "gpt-4o-mini")
    nlu_temperature: float = get_float("NLU_TEMPERATURE", 0.1)

    # Educational chat bot mode.
    use_chatgpt_edu: bool = get_bool("USE_CHATGPT_EDU", True)
    edu_model: str = get_str("EDU_MODEL", "gpt-4o-mini")
    edu_temperature: float = get_float("EDU_TEMPERATURE", 0.4)
    edu_mode: str = get_str("EDU_MODE", "redirect")

    # Raspberry Pi / UDP communication
    pi_ip: str = get_str("PI_IP", "127.0.0.1")
    pi_port: int = get_int("PI_PORT", 5005)
    pi_safety_timeout_s: float = get_float("PI_SAFETY_TIMEOUT_S", 1.5)

    # Text-to-speech
    tts_enabled: bool = get_bool("TTS_ENABLED", True)
    tts_speed: str = get_str("TTS_SPEED", "160")
    tts_amplitude: str = get_str("TTS_AMPLITUDE", "180")

