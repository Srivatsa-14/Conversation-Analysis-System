import os
import logging
import json
import re
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class AISummarizer:
    """AI-powered summary generation using NLP Cloud API (free tier)"""

    # NLP Cloud API endpoints
    NLP_CLOUD_URL = "https://api.nlpcloud.io/v1/"

    # Available free models for summarization
    SUMMARIZATION_MODELS = {
        'bart-large-cnn': 'facebook/bart-large-cnn',  # Best for general summarization
        'pegasus-xsum': 'google/pegasus-xsum',        # Good for news/article style
        't5-base': 't5-base',                          # Versatile model
    }

    # Default model (best free option)
    DEFAULT_MODEL = 'bart-large-cnn'

    def __init__(self, model: str = DEFAULT_MODEL):
        logger.info(f" Initializing AI Summarizer with NLP Cloud ({model})...")

        # Try to set up NLP Cloud API key
        self.nlpcloud_api_key = os.getenv('NLPCLOUD_API_KEY')
        if not self.nlpcloud_api_key:
            logger.warning(" NLPCLOUD_API_KEY not found in environment - checking alternative names...")
            # Try alternative environment variable names
            self.nlpcloud_api_key = os.getenv('NLP_CLOUD_API_KEY') or os.getenv('NLPCLOUD_KEY')

        if self.nlpcloud_api_key:
            logger.info("✅ NLP Cloud API key found")
            # Mask the key for logging
            masked_key = self.nlpcloud_api_key[:4] + "..." + self.nlpcloud_api_key[-4:] if len(self.nlpcloud_api_key) > 8 else "***"
            logger.info(f"API Key: {masked_key}")
        else:
            logger.error("❌ No NLP Cloud API key found in environment variables")
            logger.info("Please set NLPCLOUD_API_KEY in your .env file")
            logger.info("Get a free key from: https://nlpcloud.com/")

        self.model = model
        logger.info(f" Using model: {self.model}")
        logger.info(" AI Summarizer ready")

    def generate_summary(self, transcript: str, nlp_results: Dict,
                        speaker_analysis: Dict, metadata: Dict) -> Dict[str, Any]:
        """Generate comprehensive AI summary using NLP Cloud"""
        logger.info(" Generating comprehensive AI summary with NLP Cloud...")

        # Validate inputs
        if not transcript or len(transcript.strip()) < 10:
            logger.warning(" Transcript too short for meaningful summary")
            return self._generate_minimal_summary("Transcript too short", metadata)

        if not self.nlpcloud_api_key:
            logger.error(" Cannot generate summary: No NLP Cloud API key")
            return self._generate_error_summary("API key not configured. Please add NLPCLOUD_API_KEY to your .env file")

        try:
            # Step 1: Generate main summary using NLP Cloud
            logger.info(" Step 1: Generating main summary...")
            main_summary = self._generate_nlpcloud_summary(transcript)

            if not main_summary:
                logger.error(" Failed to generate main summary with NLP Cloud")
                return self._generate_error_summary("Summary generation failed - API returned empty response")

            logger.info(f" Main summary generated ({len(main_summary)} chars)")

            # Step 2: Generate bullet points (key moments)
            logger.info(" Step 2: Generating key moments...")
            key_moments = self._generate_key_moments(transcript, nlp_results)

            # Step 3: Generate speaker insights
            logger.info(" Step 3: Generating speaker insights...")
            speaker_insights = self._generate_speaker_insights(speaker_analysis, transcript)

            # Step 4: Extract action items
            logger.info(" Step 4: Extracting action items...")
            action_items = self._extract_action_items(transcript, nlp_results)

            # Step 5: Determine conversation type and generate emotional analysis
            logger.info(" Step 5: Analyzing conversation characteristics...")
            conv_type = self._determine_conversation_type(nlp_results, transcript)
            emotional_analysis = self._generate_emotional_analysis(nlp_results, speaker_analysis)

            # Step 6: Generate executive summary (shorter version)
            logger.info(" Step 6: Creating executive summary...")
            executive_summary = self._create_executive_summary(main_summary, metadata)

            # Step 7: Extract conclusions/core theme
            logger.info(" Step 7: Extracting conclusions...")
            conclusions = self._extract_conclusions(main_summary, nlp_results)

            # Build the complete response
            result = {
                'summary': main_summary,
                'executive_summary': executive_summary,
                'speaker_analysis': speaker_insights,
                'key_points': key_moments[:10],  # Limit to top 10
                'action_items': action_items[:8],  # Limit to top 8
                'emotional_analysis': emotional_analysis,
                'conclusions': conclusions,
                'method': f'nlpcloud_{self.model}',
                'confidence': 0.92,  # High confidence for AI-generated content
                'conversation_type': conv_type,
                'metadata': {
                    'model': self.model,
                    'generated_at': datetime.now().isoformat(),
                    'transcript_length': len(transcript),
                    'speaker_count': metadata.get('speaker_count', 1)
                }
            }

            logger.info("✅ AI summary generated successfully with NLP Cloud")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f" Network error calling NLP Cloud API: {e}")
            return self._generate_error_summary(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f" Invalid JSON response from NLP Cloud: {e}")
            return self._generate_error_summary("Invalid API response format")
        except Exception as e:
            logger.error(f" Unexpected error in summary generation: {e}", exc_info=True)
            return self._generate_error_summary(f"Unexpected error: {str(e)}")

    def _generate_nlpcloud_summary(self, text: str, max_length: int = 250, min_length: int = 80) -> Optional[str]:
        """Generate summary using NLP Cloud API"""

        # Clean and prepare text
        text = self._prepare_text_for_summary(text)

        # For very long texts, we need to truncate (NLP Cloud has token limits)
        if len(text) > 5000:
            logger.warning(f" Text too long ({len(text)} chars), truncating to 5000 chars")
            text = text[:5000] + "..."

        headers = {
            'Authorization': f'Token {self.nlpcloud_api_key}',
            'Content-Type': 'application/json'
        }

        # Prepare the request payload
        payload = {
            'text': text,
            'max_length': max_length,
            'min_length': min_length,
            'do_sample': False  # Deterministic output
        }

        try:
            logger.info(f" Calling NLP Cloud API with model: {self.model}")

            # Make the API request
            response = requests.post(
                f'{self.NLP_CLOUD_URL}{self.model}/summarization',
                headers=headers,
                json=payload,
                timeout=30  # 30 second timeout
            )

            # Log response status
            logger.info(f" API Response Status: {response.status_code}")

            # Check for errors
            if response.status_code == 200:
                result = response.json()
                summary = result.get('summary_text', '')

                if summary:
                    logger.info(f" Summary generated successfully ({len(summary)} chars)")
                    return summary
                else:
                    logger.error(" API returned empty summary")
                    return None

            elif response.status_code == 401:
                logger.error(" Authentication failed - invalid API key")
                return None
            elif response.status_code == 402:
                logger.error(" Payment required - free tier limits exceeded")
                return None
            elif response.status_code == 429:
                logger.error(" Rate limit exceeded - too many requests")
                return None
            else:
                logger.error(f" API error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error(" NLP Cloud API request timed out")
            return None
        except Exception as e:
            logger.error(f" Error calling NLP Cloud API: {e}")
            return None

    def _prepare_text_for_summary(self, text: str) -> str:
        """Clean and prepare text for summarization"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove very short sentences (likely noise)
        sentences = text.split('. ')
        filtered_sentences = []
        for sent in sentences:
            if len(sent.split()) > 3:  # Keep sentences with at least 4 words
                filtered_sentences.append(sent)

        return '. '.join(filtered_sentences)

    def _generate_key_moments(self, transcript: str, nlp_results: Dict) -> List[str]:
        """Extract key moments from the conversation"""
        key_moments = []

        # Use intent analysis for key moments
        intents = nlp_results.get('intents', [])
        for intent in intents[:5]:
            if intent.get('confidence', 0) > 0.6:
                key_moments.append(f"Important: {intent.get('intent', '')}")

        # Use topics for key moments
        topics = nlp_results.get('topics', [])
        for topic in topics[:5]:
            if topic.get('confidence', 0) > 0.5:
                key_moments.append(f"Key topic: {topic.get('topic', '')}")

        # Extract from transcript if we don't have enough
        if len(key_moments) < 3:
            # Get the longest sentences as potential key moments
            sentences = transcript.split('. ')
            sentences.sort(key=len, reverse=True)
            for sent in sentences[:3]:
                if len(sent.split()) > 5:
                    key_moments.append(sent[:100] + "..." if len(sent) > 100 else sent)

        return key_moments

    def _generate_speaker_insights(self, speaker_analysis: Dict, transcript: str) -> Dict:
        """Generate insights for each speaker"""
        insights = {}

        for speaker_id, speaker in speaker_analysis.items():
            contribution = speaker.get('contribution_percentage', 0)
            sentiment = speaker.get('sentiment', {}).get('label', 'Neutral')
            word_count = speaker.get('word_count', 0)

            insight = f"Speaker {speaker_id} contributed {contribution:.1f}% of the conversation "
            insight += f"with {word_count} words. Overall tone: {sentiment.lower()}. "

            # Add key phrases if available
            key_phrases = speaker.get('key_phrases', [])[:3]
            if key_phrases:
                insight += f"Key phrases: {', '.join(key_phrases)}."

            insights[f"Speaker {speaker_id}"] = insight

        return insights

    def _extract_action_items(self, transcript: str, nlp_results: Dict) -> List[str]:
        """Extract action items from the conversation"""
        action_items = []

        # Look for action-oriented intents
        intents = nlp_results.get('intents', [])
        action_keywords = ['action', 'todo', 'need to', 'must', 'should', 'will', 'going to']

        for intent in intents:
            intent_text = intent.get('intent', '').lower()
            if any(keyword in intent_text for keyword in action_keywords):
                action_items.append(f"Action: {intent.get('intent', '')}")

        # If no action items found, add a default
        if not action_items:
            action_items.append("Review conversation for follow-up items")
            action_items.append("Consider key discussion points")

        return action_items

    def _generate_emotional_analysis(self, nlp_results: Dict, speaker_analysis: Dict) -> str:
        """Generate emotional analysis of the conversation"""
        # Get overall sentiment
        sentiment = nlp_results.get('sentiment', {})
        sentiment_label = sentiment.get('label', 'neutral')
        sentiment_score = sentiment.get('score', 0)

        # Determine intensity
        if abs(sentiment_score) > 0.5:
            intensity = "strongly"
        elif abs(sentiment_score) > 0.2:
            intensity = "moderately"
        else:
            intensity = "mildly"

        # Build analysis
        analysis = f"The conversation maintains a {intensity} {sentiment_label.lower()} tone"

        # Add speaker dynamics
        if len(speaker_analysis) > 1:
            sentiments = []
            for speaker in speaker_analysis.values():
                sent = speaker.get('sentiment', {}).get('label', 'neutral')
                sentiments.append(sent)

            if len(set(sentiments)) > 1:
                analysis += f" with varying emotions across speakers ({', '.join(set(sentiments))})"
            else:
                analysis += " with consistent emotion across all speakers"

        return analysis + "."

    def _create_executive_summary(self, main_summary: str, metadata: Dict) -> str:
        """Create a shorter executive summary"""
        if len(main_summary) <= 200:
            return main_summary

        # Take first 2-3 sentences for executive summary
        sentences = main_summary.split('. ')
        exec_sentences = sentences[:min(3, len(sentences))]
        executive = '. '.join(exec_sentences)

        # Add metadata context
        speaker_count = metadata.get('speaker_count', 1)
        duration = metadata.get('duration', 0)
        duration_min = round(duration / 60, 1)

        return f"{executive}. This conversation involved {speaker_count} speaker(s) over {duration_min} minutes."

    def _extract_conclusions(self, summary: str, nlp_results: Dict) -> str:
        """Extract main conclusions from the summary"""
        # Use the last part of the summary as conclusions
        sentences = summary.split('. ')

        if len(sentences) > 3:
            # Take last 2 sentences as conclusions
            conclusions = '. '.join(sentences[-2:])
        else:
            conclusions = summary

        # Add topic context
        topics = nlp_results.get('topics', [])
        if topics:
            main_topics = [t['topic'] for t in topics[:3]]
            if main_topics:
                conclusions += f" The main topics discussed were {', '.join(main_topics)}."

        return conclusions

    def _determine_conversation_type(self, nlp_results: Dict, transcript: str) -> str:
        """Determine the type of conversation"""
        topics = nlp_results.get('topics', [])
        intents = nlp_results.get('intents', [])

        topic_text = ' '.join([t.get('topic', '').lower() for t in topics])
        transcript_lower = transcript.lower()

        # Check for specific conversation types
        if any(word in transcript_lower for word in ['meeting', 'agenda', 'project', 'deadline', 'team']):
            return 'business_meeting'
        elif any(word in transcript_lower for word in ['interview', 'candidate', 'position', 'job', 'hiring']):
            return 'interview'
        elif any(word in transcript_lower for word in ['customer', 'support', 'help', 'issue', 'problem']):
            return 'customer_service'
        elif any(word in transcript_lower for word in ['friend', 'family', 'home', 'weekend', 'vacation']):
            return 'casual'
        elif any(word in transcript_lower for word in ['lecture', 'class', 'student', 'teacher', 'course']):
            return 'educational'
        else:
            return 'general_conversation'

    def _generate_minimal_summary(self, reason: str, metadata: Dict) -> Dict[str, Any]:
        """Generate a minimal summary when transcript is too short"""
        return {
            'summary': f"Unable to generate detailed summary: {reason}",
            'executive_summary': f"Conversation too brief for analysis",
            'speaker_analysis': {},
            'key_points': ["Conversation was too short for detailed analysis"],
            'action_items': ["N/A"],
            'emotional_analysis': "Unable to analyze",
            'conclusions': "Conversation was too brief for meaningful conclusions",
            'method': 'minimal',
            'confidence': 0.1,
            'conversation_type': 'unknown',
            'metadata': metadata
        }

    def _generate_error_summary(self, error_message: str) -> Dict[str, Any]:
        """Generate an error summary when API fails"""
        logger.error(f" Returning error summary: {error_message}")

        return {
            'summary': f"⚠️ Summary generation failed: {error_message}",
            'executive_summary': "Summary could not be generated due to an error",
            'speaker_analysis': {},
            'key_points': ["Error in summary generation"],
            'action_items': ["Check API configuration", "Verify API key is valid", "Check network connection"],
            'emotional_analysis': "Unable to analyze due to error",
            'conclusions': "Summary generation failed",
            'method': 'error',
            'confidence': 0.0,
            'conversation_type': 'error',
            'error_details': error_message
        }

# Global instance
_ai_summarizer = None

def get_ai_summarizer(model: str = AISummarizer.DEFAULT_MODEL):
    """Get or create singleton AI summarizer instance"""
    global _ai_summarizer
    if _ai_summarizer is None:
        _ai_summarizer = AISummarizer(model=model)
    return _ai_summarizer