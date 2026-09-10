"""
Voice Activity Detection using WebRTC VAD.
Twilio media streams send 8kHz mu-law audio in 20ms frames; we decode to
PCM16 before feeding into webrtcvad.
"""
import audioop
import webrtcvad


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2, sample_rate: int = 8000):
        """
        aggressiveness: 0 (least aggressive filtering) - 3 (most aggressive)
        """
        self._vad = webrtcvad.Vad(aggressiveness)
        self._sample_rate = sample_rate

    def is_speech(self, mulaw_frame: bytes) -> bool:
        """
        mulaw_frame must correspond to a 10/20/30ms chunk at 8kHz.
        Twilio sends 20ms mu-law frames (160 bytes) by default.
        """
        pcm16 = audioop.ulaw2lin(mulaw_frame, 2)
        return self._vad.is_speech(pcm16, self._sample_rate)


class SilenceTracker:
    """
    Tracks consecutive non-speech frames to decide when the caller has
    finished a turn (end-of-utterance) or gone silent long enough to prompt.
    """

    def __init__(self, frame_ms: int = 20, end_of_turn_ms: int = 700, timeout_ms: int = 8000):
        self.frame_ms = frame_ms
        self.end_of_turn_frames = end_of_turn_ms // frame_ms
        self.timeout_frames = timeout_ms // frame_ms
        self._silence_frames = 0
        self._had_speech = False

    def update(self, is_speech: bool) -> None:
        if is_speech:
            self._had_speech = True
            self._silence_frames = 0
        else:
            self._silence_frames += 1

    @property
    def end_of_turn(self) -> bool:
        return self._had_speech and self._silence_frames >= self.end_of_turn_frames

    @property
    def timed_out(self) -> bool:
        return not self._had_speech and self._silence_frames >= self.timeout_frames

    def reset(self) -> None:
        self._silence_frames = 0
        self._had_speech = False
