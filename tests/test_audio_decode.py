import math
import tempfile
import unittest
import wave
from pathlib import Path

from faster_whisper.audio import decode_audio


class AudioDecodeTests(unittest.TestCase):
    def test_decodes_wav_with_installed_pyav(self):
        sample_rate = 16000
        samples = bytes().join(
            int(8000 * math.sin(2 * math.pi * 440 * i / sample_rate)).to_bytes(
                2, "little", signed=True
            )
            for i in range(sample_rate // 10)
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(sample_rate)
                audio.writeframes(samples)

            decoded = decode_audio(str(path), sampling_rate=sample_rate)

        self.assertEqual(decoded.shape, (sample_rate // 10,))
        self.assertGreater(float(abs(decoded).max()), 0.1)
