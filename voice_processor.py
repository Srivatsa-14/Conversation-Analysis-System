import numpy as np
import logging
import webrtcvad
import librosa
import soundfile as sf
from pydub import AudioSegment
from typing import List, Dict, Tuple, Optional
import os
from datetime import datetime
import sys

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """Handles voice activity detection and audio preprocessing"""

    def __init__(self, aggressiveness=3):
        """
        Initialize Voice Activity Detector

        Args:
            aggressiveness: VAD aggressiveness (0-3, where 3 is most aggressive)
        """
        logger.info(" Initializing Voice Processor...")
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = 16000  # WebRTC VAD requires 16kHz
        self.frame_duration = 30  # ms (10, 20, or 30)
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)

        logger.info(" Voice Processor initialized")

    def preprocess_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """
        Preprocess audio file for analysis

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (audio_array, sample_rate)
        """
        try:
            logger.info(f"Preprocessing audio: {audio_path}")

            # Try multiple methods to load audio
            audio = None
            sr = None

            # Method 1: Try soundfile directly
            try:
                audio, sr = sf.read(audio_path)
                if sr != self.sample_rate:
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
                    sr = self.sample_rate
                logger.info("Loaded audio with soundfile")
            except:
                # Method 2: Try librosa
                try:
                    audio, sr = librosa.load(audio_path, sr=self.sample_rate, res_type='kaiser_fast')
                    logger.info("Loaded audio with librosa")
                except:
                    # Method 3: Try pydub
                    try:
                        sound = AudioSegment.from_file(audio_path)
                        sound = sound.set_frame_rate(self.sample_rate).set_channels(1)
                        audio = np.array(sound.get_array_of_samples()).astype(np.float32) / 32768.0
                        sr = self.sample_rate
                        logger.info("Loaded audio with pydub")
                    except Exception as e:
                        logger.error(f"All audio loading methods failed: {e}")
                        raise

            if audio is None:
                raise Exception("Could not load audio file")

            # Convert to mono if stereo
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)

            # Apply preprocessing
            audio = self._remove_noise(audio, sr)
            audio = self._normalize_audio(audio)

            return audio, sr

        except Exception as e:
            logger.error(f"Audio preprocessing error: {e}")
            raise

    def _remove_noise(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Apply simple noise reduction"""
        try:
            # Simple high-pass filter to remove low-frequency noise
            from scipy import signal
            sos = signal.butter(10, 80, 'hp', fs=sr, output='sos')
            audio_clean = signal.sosfilt(sos, audio)
            return audio_clean
        except:
            return audio

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val
        return audio

    def detect_voice_activity(self, audio: np.ndarray, sr: int) -> List[Dict]:
        """
        Detect voice activity segments

        Args:
            audio: Audio array
            sr: Sample rate

        Returns:
            List of voice activity segments with start/end times
        """
        try:
            # Convert to 16-bit PCM for WebRTC VAD
            audio_int16 = (audio * 32767).astype(np.int16)

            # Split into frames
            frames = []
            for i in range(0, len(audio_int16), self.frame_size):
                frame = audio_int16[i:i + self.frame_size]
                if len(frame) == self.frame_size:
                    frames.append(frame.tobytes())

            # Detect voice activity per frame
            is_speech = []
            for frame in frames:
                try:
                    is_speech.append(self.vad.is_speech(frame, self.sample_rate))
                except:
                    is_speech.append(False)

            # Merge consecutive frames into segments
            segments = []
            in_speech = False
            start_time = 0

            for i, speech in enumerate(is_speech):
                time = i * self.frame_duration / 1000

                if speech and not in_speech:
                    # Start of speech
                    in_speech = True
                    start_time = time
                elif not speech and in_speech:
                    # End of speech
                    in_speech = False
                    segments.append({
                        'start': start_time,
                        'end': time,
                        'duration': time - start_time
                    })

            # Handle case where speech continues to end
            if in_speech:
                segments.append({
                    'start': start_time,
                    'end': len(is_speech) * self.frame_duration / 1000,
                    'duration': len(is_speech) * self.frame_duration / 1000 - start_time
                })

            # Filter very short segments (likely noise)
            segments = [s for s in segments if s['duration'] > 0.3]

            logger.info(f"Detected {len(segments)} voice segments")
            return segments

        except Exception as e:
            logger.error(f"Voice activity detection error: {e}")
            return []

    def segment_audio_by_speaker(self, audio: np.ndarray, sr: int,
                                  speaker_timeline: List[Dict]) -> Dict[int, List[np.ndarray]]:
        """
        Segment audio by speaker based on diarization timeline

        Args:
            audio: Audio array
            sr: Sample rate
            speaker_timeline: Speaker diarization timeline

        Returns:
            Dictionary mapping speaker IDs to list of audio segments
        """
        try:
            speaker_segments = {}

            for segment in speaker_timeline:
                speaker = segment.get('speaker')
                start = int(segment.get('start', 0) * sr)
                end = int(segment.get('end', 0) * sr)

                if start < len(audio) and end <= len(audio):
                    audio_segment = audio[start:end]

                    if speaker not in speaker_segments:
                        speaker_segments[speaker] = []

                    speaker_segments[speaker].append(audio_segment)

            logger.info(f"Segmented audio for {len(speaker_segments)} speakers")
            return speaker_segments

        except Exception as e:
            logger.error(f"Audio segmentation error: {e}")
            return {}

    def extract_audio_features(self, audio: np.ndarray, sr: int) -> Dict:
        """
        Extract acoustic features from audio

        Args:
            audio: Audio array
            sr: Sample rate

        Returns:
            Dictionary of acoustic features
        """
        try:
            features = {}

            # Energy/RMS
            rms = librosa.feature.rms(y=audio)[0]

            # Zero crossing rate (voice quality)
            zcr = librosa.feature.zero_crossing_rate(audio)[0]

            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)[0]

            # MFCCs (voice characteristics)
            mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
            mfccs_mean = np.mean(mfccs, axis=1)

            features = {
                'energy_mean': float(np.mean(rms)),
                'energy_std': float(np.std(rms)),
                'zcr_mean': float(np.mean(zcr)),
                'spectral_centroid_mean': float(np.mean(spectral_centroids)),
                'spectral_rolloff_mean': float(np.mean(spectral_rolloff)),
                'mfccs': mfccs_mean.tolist()
            }

            return features

        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return {}