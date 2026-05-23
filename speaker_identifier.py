import numpy as np
import logging
from typing import List, Dict, Any, Optional
from sklearn.cluster import AgglomerativeClustering
from sklearn.mixture import GaussianMixture
import librosa
from collections import defaultdict

logger = logging.getLogger(__name__)

class SpeakerIdentifier:
    """Advanced speaker diarization and identification"""

    def __init__(self):
        logger.info("🔊 Initializing Speaker Identifier...")

        # Speaker profiles database (in production, this would be persistent)
        self.speaker_profiles = {}
        self.next_speaker_id = 0

        logger.info("✅ Speaker Identifier initialized")

    def extract_speaker_embeddings(self, audio_segments: List[np.ndarray],
                                   sr: int) -> List[np.ndarray]:
        """
        Extract speaker embeddings from audio segments

        Args:
            audio_segments: List of audio segments
            sr: Sample rate

        Returns:
            List of speaker embeddings
        """
        embeddings = []

        for segment in audio_segments:
            try:
                # Extract MFCC features
                mfccs = librosa.feature.mfcc(y=segment, sr=sr, n_mfcc=20)

                # Statistical features
                mfccs_mean = np.mean(mfccs, axis=1)
                mfccs_std = np.std(mfccs, axis=1)

                # Pitch features
                pitches, magnitudes = librosa.piptrack(y=segment, sr=sr)
                pitches_mean = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0

                # Energy features
                rms = librosa.feature.rms(y=segment)[0]
                rms_mean = np.mean(rms)

                # Combine features into embedding
                embedding = np.concatenate([
                    mfccs_mean,
                    mfccs_std,
                    [pitches_mean, rms_mean]
                ])

                embeddings.append(embedding)

            except Exception as e:
                logger.warning(f"Embedding extraction error: {e}")
                embeddings.append(np.zeros(42))  # 20+20+2

        return embeddings

    def cluster_speakers(self, embeddings: List[np.ndarray],
                         min_speakers: int = 1,
                         max_speakers: int = 10) -> List[int]:
        """
        Cluster audio segments by speaker

        Args:
            embeddings: List of speaker embeddings
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers

        Returns:
            List of speaker labels for each segment
        """
        if len(embeddings) < 2:
            return [0] * len(embeddings)

        try:
            # Try different numbers of clusters and pick best
            best_labels = None
            best_score = -np.inf

            for n_clusters in range(min_speakers, min(max_speakers, len(embeddings)) + 1):
                # Use agglomerative clustering
                clustering = AgglomerativeClustering(
                    n_clusters=n_clusters,
                    metric='euclidean',
                    linkage='ward'
                )

                labels = clustering.fit_predict(embeddings)

                # Calculate silhouette score if we have enough samples
                if len(embeddings) > n_clusters and n_clusters > 1:
                    from sklearn.metrics import silhouette_score
                    try:
                        score = silhouette_score(embeddings, labels)
                        if score > best_score:
                            best_score = score
                            best_labels = labels
                    except:
                        pass

            if best_labels is None:
                # Default to single speaker
                best_labels = [0] * len(embeddings)

            return best_labels.tolist()

        except Exception as e:
            logger.error(f"Speaker clustering error: {e}")
            return [0] * len(embeddings)

    def identify_speakers(self, audio_segments: List[np.ndarray],
                          sr: int,
                          known_speakers: Optional[Dict] = None) -> List[Dict]:
        """
        Identify speakers (cluster unknown speakers or match known profiles)

        Args:
            audio_segments: List of audio segments
            sr: Sample rate
            known_speakers: Known speaker profiles (optional)

        Returns:
            List of speaker identifications for each segment
        """
        if not audio_segments:
            return []

        # Extract embeddings
        embeddings = self.extract_speaker_embeddings(audio_segments, sr)

        # Cluster speakers
        cluster_labels = self.cluster_speakers(embeddings)

        # Create speaker IDs
        unique_clusters = set(cluster_labels)
        cluster_to_speaker = {}

        for cluster in unique_clusters:
            if cluster not in cluster_to_speaker:
                cluster_to_speaker[cluster] = self.next_speaker_id
                self.next_speaker_id += 1

        # Map clusters to speaker IDs
        speaker_ids = [cluster_to_speaker[c] for c in cluster_labels]

        # Create results
        results = []
        for i, (speaker_id, embedding) in enumerate(zip(speaker_ids, embeddings)):
            results.append({
                'speaker_id': speaker_id,
                'confidence': 0.8,  # Could be calculated from cluster quality
                'embedding': embedding.tolist()
            })

        return results

    def create_speaker_profile(self, speaker_id: int,
                               audio_segments: List[np.ndarray],
                               sr: int,
                               name: str = None) -> Dict:
        """
        Create a speaker profile for future identification

        Args:
            speaker_id: Speaker ID
            audio_segments: Audio segments for this speaker
            sr: Sample rate
            name: Speaker name (optional)

        Returns:
            Speaker profile
        """
        # Extract embeddings for all segments
        embeddings = self.extract_speaker_embeddings(audio_segments, sr)

        # Average embeddings to create profile
        profile_embedding = np.mean(embeddings, axis=0)

        profile = {
            'speaker_id': speaker_id,
            'name': name or f"Speaker {speaker_id}",
            'embedding': profile_embedding.tolist(),
            'num_segments': len(audio_segments),
            'created_at': np.datetime64('now').astype(str)
        }

        # Store profile
        self.speaker_profiles[speaker_id] = profile

        return profile

    def match_to_known_speaker(self, embedding: np.ndarray,
                               threshold: float = 0.7) -> Optional[Dict]:
        """
        Match embedding to known speaker profiles

        Args:
            embedding: Speaker embedding
            threshold: Similarity threshold

        Returns:
            Matched speaker profile or None
        """
        if not self.speaker_profiles:
            return None

        best_match = None
        best_similarity = -1

        for speaker_id, profile in self.speaker_profiles.items():
            profile_embedding = np.array(profile['embedding'])

            # Cosine similarity
            similarity = np.dot(embedding, profile_embedding) / (
                np.linalg.norm(embedding) * np.linalg.norm(profile_embedding) + 1e-10
            )

            if similarity > best_similarity and similarity > threshold:
                best_similarity = similarity
                best_match = profile

        return best_match

    def analyze_speaker_characteristics(self, audio_segments: List[np.ndarray],
                                        sr: int) -> Dict:
        """
        Analyze speaker characteristics from audio

        Args:
            audio_segments: Audio segments for a speaker
            sr: Sample rate

        Returns:
            Speaker characteristics
        """
        if not audio_segments:
            return {}

        # Concatenate all segments
        audio = np.concatenate(audio_segments)

        # Extract features
        try:
            # Pitch
            pitches, magnitudes = librosa.piptrack(y=audio, sr=sr)
            pitches_clean = pitches[pitches > 0]
            avg_pitch = np.mean(pitches_clean) if len(pitches_clean) > 0 else 0
            pitch_range = np.ptp(pitches_clean) if len(pitches_clean) > 0 else 0

            # Energy
            rms = librosa.feature.rms(y=audio)[0]
            avg_energy = np.mean(rms)
            energy_variation = np.std(rms)

            # Speech rate (approximate)
            # Count syllables (simplified: peaks in amplitude envelope)
            envelope = np.abs(librosa.stft(audio))
            envelope_mean = np.mean(envelope, axis=0)
            peaks = len(librosa.util.peak_pick(envelope_mean, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10))
            duration = len(audio) / sr
            speech_rate = peaks / duration if duration > 0 else 0

            # Voice quality (using harmonics-to-noise ratio)
            hnr = librosa.effects.harmonic(audio)

            characteristics = {
                'pitch': {
                    'average': float(avg_pitch),
                    'range': float(pitch_range),
                    'stability': float(np.std(pitches_clean)) if len(pitches_clean) > 0 else 0
                },
                'energy': {
                    'average': float(avg_energy),
                    'variation': float(energy_variation)
                },
                'speech_rate': float(speech_rate),  # syllables per second
                'voice_quality': {
                    'hnr': float(np.mean(hnr))
                },
                'duration': float(duration)
            }

            return characteristics

        except Exception as e:
            logger.error(f"Speaker characteristics analysis error: {e}")
            return {}