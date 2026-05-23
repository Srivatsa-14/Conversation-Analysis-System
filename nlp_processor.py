import os
import logging
import json
import re
from typing import Dict, List, Any, Tuple
from collections import Counter
from datetime import datetime
import numpy as np
import sys

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# NLP Libraries
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer
from nltk.chunk import ne_chunk
from nltk.tree import Tree

# Download NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('averaged_perceptron_tagger')
    nltk.data.find('vader_lexicon')
    nltk.data.find('stopwords')
    nltk.data.find('wordnet')
    nltk.data.find('maxent_ne_chunker')
    nltk.data.find('words')
except:
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('vader_lexicon', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
    nltk.download('maxent_ne_chunker', quiet=True)
    nltk.download('words', quiet=True)

logger = logging.getLogger(__name__)

class NLPProcessor:
    """Complete NLP processing pipeline for conversation analysis"""

    def __init__(self):
        """Initialize all NLP models and components"""
        logger.info(" Initializing Advanced NLP Processor...")

        try:
            # Sentiment Analysis
            self.sia = SentimentIntensityAnalyzer()
            logger.info(" VADER sentiment analyzer loaded")

            # Text processing utilities
            self.stop_words = set(stopwords.words('english'))
            self.lemmatizer = WordNetLemmatizer()

            # Intent patterns
            self.intent_patterns = {
                'question': [r'\?', r'what is', r'how to', r'can you', r'could you', r'why', r'when', r'where', r'who', r'which'],
                'request': [r'please', r'could you', r'would you', r'I need', r'I want', r'help me', r'can we', r'can you'],
                'complaint': [r'problem', r'issue', r'not working', r'broken', r'bad', r'terrible', r'frustrated', r'annoying'],
                'compliment': [r'thank', r'great', r'excellent', r'good job', r'awesome', r'amazing', r'perfect', r'love'],
                'greeting': [r'hello', r'hi there', r'good morning', r'hey', r'greetings', r'hi', r'welcome', r'good afternoon'],
                'farewell': [r'goodbye', r'bye', r'see you', r'take care', r'later', r'thanks', r'thank you', r'have a good'],
                'agreement': [r'agree', r'yes', r'correct', r'exactly', r'right', r'absolutely', r'sure', r'okay', r'fine'],
                'disagreement': [r'disagree', r'no', r'wrong', r'incorrect', r'not true', r'false', r'dispute', r'not right'],
                'confusion': [r'confused', r'not sure', r'dont know', r"don't understand", r'clarify', r'explain', r'what do you mean'],
                'urgency': [r'urgent', r'asap', r'immediately', r'now', r'quick', r'emergency', r'critical', r'important'],
                'decision': [r'decide', r'decision', r'let\'s', r'we will', r'we should', r'we need to', r'going to'],
                'suggestion': [r'suggest', r'recommend', r'how about', r'what about', r'maybe we', r'perhaps', r'consider'],
                'information': [r'info', r'information', r'let me know', r'tell me', r'update', r'status', r'progress']
            }

            logger.info(" Advanced NLP Processor initialized successfully")

        except Exception as e:
            logger.error(f" Failed to initialize NLP Processor: {e}")
            raise

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Comprehensive sentiment analysis with detailed scores"""
        try:
            if not text or len(text.strip()) < 5:
                return self._default_sentiment()

            # VADER sentiment
            vader_scores = self.sia.polarity_scores(text)

            # Combined sentiment score
            compound = vader_scores['compound']

            # Enhanced sentiment detection
            words = text.lower().split()
            positive_words = ['good', 'great', 'excellent', 'happy', 'love', 'best', 'awesome', 'wonderful', 'fantastic', 'amazing', 'perfect', 'brilliant', 'nice', 'glad', 'pleased']
            negative_words = ['bad', 'terrible', 'worst', 'hate', 'angry', 'sad', 'poor', 'awful', 'horrible', 'disappointing', 'frustrating', 'annoying', 'wrong', 'issue', 'problem']

            positive_count = sum(1 for word in words if word in positive_words)
            negative_count = sum(1 for word in words if word in negative_words)

            # Adjust score based on word presence
            if positive_count > negative_count * 1.5:
                compound = max(compound, 0.2)
            elif negative_count > positive_count * 1.5:
                compound = min(compound, -0.2)

            # Determine sentiment label with thresholds
            if compound >= 0.3:
                label = "Very Positive"
                emoji = "😄"
                color = "#10B981"
            elif compound >= 0.1:
                label = "Positive"
                emoji = "🙂"
                color = "#34D399"
            elif compound <= -0.3:
                label = "Very Negative"
                emoji = "😡"
                color = "#DC2626"
            elif compound <= -0.1:
                label = "Negative"
                emoji = "🙁"
                color = "#F87171"
            else:
                label = "Neutral"
                emoji = "😐"
                color = "#6B7280"

            # Calculate confidence
            confidence = min(abs(compound) * 1.5, 1.0)

            result = {
                'label': label,
                'score': round(compound, 3),
                'emoji': emoji,
                'color': color,
                'confidence': round(confidence, 2),
                'detailed': {
                    'positive': round(vader_scores['pos'], 3),
                    'neutral': round(vader_scores['neu'], 3),
                    'negative': round(vader_scores['neg'], 3),
                    'compound': round(vader_scores['compound'], 3)
                },
                'word_counts': {
                    'positive_words': positive_count,
                    'negative_words': negative_count
                }
            }

            return result

        except Exception as e:
            logger.error(f" Sentiment analysis error: {e}")
            return self._default_sentiment()

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities with detailed classification"""
        try:
            if not text or len(text.strip()) < 20:
                return []

            entities = []

            # Use NLTK for named entity recognition
            sentences = sent_tokenize(text)

            for sentence in sentences:
                words = word_tokenize(sentence)
                tagged = pos_tag(words)

                # Extract named entities using NLTK's ne_chunk
                try:
                    chunked = ne_chunk(tagged)

                    for chunk in chunked:
                        if isinstance(chunk, Tree):
                            entity_text = ' '.join([word for word, pos in chunk.leaves()])
                            entity_type = chunk.label()

                            # Map NLTK entity types to standard categories
                            category, icon = self._map_entity_type_nltk(entity_type)

                            entities.append({
                                'text': entity_text,
                                'type': entity_type,
                                'category': category,
                                'icon': icon,
                                'confidence': 0.8,
                                'occurrences': 1
                            })
                except:
                    # Fallback: extract proper nouns
                    for i, (word, tag) in enumerate(tagged):
                        if tag == 'NNP' and len(word) > 2 and i < len(tagged) - 1:
                            # Check if it's part of a multi-word entity
                            if i + 1 < len(tagged) and tagged[i + 1][1] == 'NNP':
                                entity_text = f"{word} {tagged[i + 1][0]}"
                                entities.append({
                                    'text': entity_text,
                                    'type': 'PERSON',
                                    'category': 'People',
                                    'icon': '👤',
                                    'confidence': 0.6,
                                    'occurrences': 1
                                })
                            else:
                                entities.append({
                                    'text': word,
                                    'type': 'PERSON',
                                    'category': 'People',
                                    'icon': '👤',
                                    'confidence': 0.5,
                                    'occurrences': 1
                                })

            # Merge duplicate entities
            merged_entities = {}
            for entity in entities:
                key = f"{entity['text'].lower()}_{entity['type']}"
                if key in merged_entities:
                    merged_entities[key]['occurrences'] += 1
                else:
                    merged_entities[key] = entity

            # Sort by occurrences and return
            result = list(merged_entities.values())
            result.sort(key=lambda x: x['occurrences'], reverse=True)

            return result[:25]

        except Exception as e:
            logger.error(f" Entity extraction error: {e}")
            return []

    def extract_topics(self, text: str, num_topics: int = 8) -> List[Dict[str, Any]]:
        """Extract key topics with confidence scores"""
        try:
            if not text or len(text.strip()) < 50:
                return [{'topic': 'General Discussion', 'confidence': 1.0}]

            # Tokenize and clean
            words = word_tokenize(text.lower())
            words = [word for word in words if word.isalnum() and word not in self.stop_words and len(word) > 2]

            # Get word frequencies
            word_freq = Counter(words)

            # Extract noun phrases as topics
            sentences = sent_tokenize(text)
            topics = []

            for sentence in sentences[:10]:  # Limit to first 10 sentences
                words_sent = word_tokenize(sentence)
                tagged = pos_tag(words_sent)

                # Extract noun phrases (NN.*)
                noun_phrases = []
                current_phrase = []

                for word, tag in tagged:
                    if tag.startswith('NN'):
                        current_phrase.append(word)
                    else:
                        if current_phrase:
                            phrase = ' '.join(current_phrase).lower()
                            if len(phrase) > 2 and phrase not in self.stop_words:
                                noun_phrases.append(phrase)
                            current_phrase = []

                if current_phrase:
                    phrase = ' '.join(current_phrase).lower()
                    if len(phrase) > 2 and phrase not in self.stop_words:
                        noun_phrases.append(phrase)

                for phrase in noun_phrases:
                    freq = word_freq.get(phrase.split()[0] if ' ' in phrase else phrase, 0)
                    if freq > 0:
                        topics.append({
                            'topic': phrase.title(),
                            'confidence': min(freq / 10, 1.0),
                            'frequency': freq,
                            'category': self._categorize_topic(phrase)
                        })

            # Add individual words as topics
            for word, freq in word_freq.most_common(20):
                if freq > 1 and len(word) > 2:
                    topics.append({
                        'topic': word.title(),
                        'confidence': min(freq / 10, 0.9),
                        'frequency': freq,
                        'category': self._categorize_topic(word)
                    })

            # Remove duplicates and sort
            unique_topics = {}
            for topic in topics:
                key = topic['topic'].lower()
                if key not in unique_topics or topic['confidence'] > unique_topics[key]['confidence']:
                    unique_topics[key] = topic

            sorted_topics = sorted(unique_topics.values(),
                                  key=lambda x: (x['frequency'], x['confidence']),
                                  reverse=True)

            if not sorted_topics:
                sorted_topics.append({
                    'topic': 'General Conversation',
                    'confidence': 1.0,
                    'frequency': 1,
                    'category': 'General'
                })

            return sorted_topics[:num_topics]

        except Exception as e:
            logger.error(f" Topic extraction error: {e}")
            return [{'topic': 'General Discussion', 'confidence': 1.0}]

    def detect_intents(self, text: str) -> List[Dict[str, Any]]:
        """Detect conversational intents with confidence scoring"""
        try:
            if not text or len(text.strip()) < 10:
                return [{
                    'intent': 'Information',
                    'confidence': 0.5,
                    'description': 'General information sharing',
                    'icon': '💬'
                }]

            text_lower = text.lower()
            intents = []

            # Check each intent pattern
            for intent_name, patterns in self.intent_patterns.items():
                max_confidence = 0
                matched_pattern = None

                for pattern in patterns:
                    matches = re.findall(pattern, text_lower, re.IGNORECASE)
                    if matches:
                        confidence = min(0.3 + (len(matches) * 0.15), 0.9)
                        if confidence > max_confidence:
                            max_confidence = confidence
                            matched_pattern = pattern

                if max_confidence > 0.3:
                    intents.append({
                        'intent': intent_name.title(),
                        'confidence': round(max_confidence, 2),
                        'pattern': matched_pattern,
                        'description': self._get_intent_description(intent_name),
                        'icon': self._get_intent_icon(intent_name)
                    })

            # Sort by confidence
            intents.sort(key=lambda x: x['confidence'], reverse=True)

            # Add fallback intent if none detected
            if not intents:
                intents.append({
                    'intent': 'Information',
                    'confidence': 0.5,
                    'description': 'Providing or seeking information',
                    'icon': '💬'
                })

            return intents[:6]

        except Exception as e:
            logger.error(f" Intent detection error: {e}")
            return []

    def extract_key_phrases(self, text: str, num_phrases: int = 15) -> List[Dict[str, Any]]:
        """Extract key phrases with importance scoring"""
        try:
            if not text or len(text.strip()) < 30:
                return []

            phrases = []

            # Basic phrase extraction using NLTK
            sentences = sent_tokenize(text)
            for sentence in sentences[:10]:  # Limit to first 10 sentences
                words = word_tokenize(sentence)
                if len(words) >= 3 and len(words) <= 8:
                    phrases.append({
                        'phrase': sentence[:100],
                        'score': 0.5,
                        'length': len(words),
                        'word_count': len(words)
                    })

            # Sort by score
            phrases.sort(key=lambda x: x.get('score', 0), reverse=True)

            return phrases[:num_phrases]

        except Exception as e:
            logger.error(f" Key phrase extraction error: {e}")
            return []

    def extract_pos_tags(self, text: str) -> Dict[str, Any]:
        """Extract detailed Part-of-Speech tags"""
        try:
            if not text:
                return {}

            words = word_tokenize(text)
            tagged = pos_tag(words)

            # Count POS tags
            pos_counts = Counter([tag for word, tag in tagged])

            # Group by broad categories
            categories = {
                'Nouns': ['NN', 'NNS', 'NNP', 'NNPS'],
                'Verbs': ['VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ'],
                'Adjectives': ['JJ', 'JJR', 'JJS'],
                'Adverbs': ['RB', 'RBR', 'RBS'],
                'Pronouns': ['PRP', 'PRP$', 'WP', 'WP$'],
                'Determiners': ['DT', 'PDT', 'WDT'],
                'Prepositions': ['IN'],
                'Conjunctions': ['CC'],
                'Interjections': ['UH']
            }

            category_counts = {}
            for category, tags in categories.items():
                category_counts[category] = sum(pos_counts.get(tag, 0) for tag in tags)

            return {
                'detailed_counts': dict(pos_counts.most_common()),
                'category_counts': category_counts,
                'total_words': len(words),
                'tagged_words': [(word, tag) for word, tag in tagged[:50]]  # Preview
            }

        except Exception as e:
            logger.error(f" POS tag extraction error: {e}")
            return {}

    def analyze_conversation_timing(self, paragraphs: List[Dict]) -> Dict[str, Any]:
        """Analyze timing and exchanges between speakers"""
        if not paragraphs or len(paragraphs) < 2:
            return self._default_timing_analysis(paragraphs)

        try:
            exchanges = []
            speaker_times = {}
            last_speaker = None
            last_end = 0

            for i, para in enumerate(paragraphs):
                speaker = para.get('speaker', 0)
                start = para.get('start', 0)
                end = para.get('end', 0)
                duration = end - start
                text = para.get('text', '')

                # Track speaker timing
                if speaker not in speaker_times:
                    speaker_times[speaker] = {
                        'total_time': 0,
                        'segments': 0,
                        'start_times': [],
                        'end_times': []
                    }

                speaker_times[speaker]['total_time'] += duration
                speaker_times[speaker]['segments'] += 1
                speaker_times[speaker]['start_times'].append(start)
                speaker_times[speaker]['end_times'].append(end)

                # Track exchanges
                if last_speaker is not None and speaker != last_speaker:
                    gap = start - last_end
                    exchanges.append({
                        'from_speaker': last_speaker,
                        'to_speaker': speaker,
                        'gap': gap,
                        'time': start,
                        'is_interruption': gap < 0.5
                    })

                last_speaker = speaker
                last_end = end

            # Calculate statistics
            total_duration = max(p.get('end', 0) for p in paragraphs)
            avg_segment_duration = np.mean([p.get('end', 0) - p.get('start', 0) for p in paragraphs])

            # Speaker overlap detection
            overlaps = []
            for i in range(len(paragraphs) - 1):
                p1 = paragraphs[i]
                p2 = paragraphs[i + 1]
                if p1.get('speaker') != p2.get('speaker'):
                    overlap_start = max(p1.get('start', 0), p2.get('start', 0))
                    overlap_end = min(p1.get('end', 0), p2.get('end', 0))
                    if overlap_end > overlap_start:
                        overlaps.append({
                            'speaker1': p1.get('speaker'),
                            'speaker2': p2.get('speaker'),
                            'start': overlap_start,
                            'end': overlap_end,
                            'duration': overlap_end - overlap_start
                        })

            return {
                'total_duration': total_duration,
                'num_exchanges': len(exchanges),
                'interruptions': sum(1 for e in exchanges if e['is_interruption']),
                'avg_gap': np.mean([e['gap'] for e in exchanges]) if exchanges else 0,
                'avg_segment_duration': avg_segment_duration,
                'exchanges': exchanges[:20],  # Limit for display
                'overlaps': overlaps[:10],
                'speaker_timing': speaker_times,
                'conversation_pace': len(paragraphs) / total_duration if total_duration > 0 else 0
            }

        except Exception as e:
            logger.error(f" Timing analysis error: {e}")
            return self._default_timing_analysis(paragraphs)

    def analyze_conversation_flow(self, paragraphs: List[Dict]) -> Dict[str, Any]:
        """Analyze conversation dynamics"""
        if not paragraphs or len(paragraphs) < 2:
            return {}

        try:
            speaker_stats = {}
            turn_transitions = []
            last_speaker = None
            last_end = 0

            for i, para in enumerate(paragraphs):
                speaker = para.get('speaker', 0)
                start = para.get('start', 0)
                end = para.get('end', 0)
                duration = end - start
                text = para.get('text', '')

                # Initialize speaker stats
                if speaker not in speaker_stats:
                    speaker_stats[speaker] = {
                        'speech_count': 0,
                        'total_duration': 0,
                        'total_words': len(text.split()),
                        'total_turns': 0,
                        'avg_duration': 0
                    }

                # Update speaker stats
                stats = speaker_stats[speaker]
                stats['speech_count'] += 1
                stats['total_duration'] += duration
                stats['total_words'] += len(text.split())

                # Track turn transitions
                if last_speaker is not None and speaker != last_speaker:
                    gap = start - last_end
                    turn_transitions.append({
                        'from': last_speaker,
                        'to': speaker,
                        'gap': gap,
                        'time': start,
                        'is_interruption': gap < 0.5
                    })

                last_speaker = speaker
                last_end = end

            # Calculate averages
            for speaker, stats in speaker_stats.items():
                if stats['speech_count'] > 0:
                    stats['avg_duration'] = stats['total_duration'] / stats['speech_count']
                    stats['avg_words'] = stats['total_words'] / stats['speech_count']
                    stats['speaking_rate'] = (stats['total_words'] / stats['total_duration'] * 60) \
                                           if stats['total_duration'] > 0 else 0

            # Find dominant speaker
            dominant_speaker = max(speaker_stats.items(),
                                  key=lambda x: x[1]['total_words'])[0] if speaker_stats else None

            return {
                'speaker_stats': speaker_stats,
                'total_transitions': len(turn_transitions),
                'interruptions': sum(1 for t in turn_transitions if t.get('is_interruption', False)),
                'dominant_speaker': dominant_speaker,
                'turn_transitions': turn_transitions[:20]
            }

        except Exception as e:
            logger.error(f" Conversation flow error: {e}")
            return {}

    def process_conversation(self, transcript: str, paragraphs: List[Dict] = None) -> Dict[str, Any]:
        """Complete NLP processing pipeline"""
        logger.info(" Starting comprehensive NLP processing...")

        start_time = datetime.now()

        try:
            # Perform all analyses
            sentiment = self.analyze_sentiment(transcript)
            entities = self.extract_entities(transcript)
            topics = self.extract_topics(transcript, 12)
            intents = self.detect_intents(transcript)
            key_phrases = self.extract_key_phrases(transcript, 20)
            pos_tags = self.extract_pos_tags(transcript)
            timing = self.analyze_conversation_timing(paragraphs) if paragraphs else {}

            # Conversation flow
            flow = {}
            if paragraphs:
                flow = self.analyze_conversation_flow(paragraphs)

            results = {
                'sentiment': sentiment,
                'entities': entities,
                'topics': topics,
                'intents': intents,
                'key_phrases': key_phrases,
                'pos_tags': pos_tags,
                'timing_analysis': timing,
                'conversation_flow': flow,
                'text_statistics': self._calculate_text_stats(transcript),
                'processing_time': None
            }

            # Generate summary insights
            results['summary_insights'] = self._generate_summary_insights(results)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            results['processing_time'] = round(processing_time, 2)

            logger.info(f" NLP processing complete in {processing_time:.2f}s")

            return results

        except Exception as e:
            logger.error(f" NLP processing failed: {e}")
            return self._default_nlp_results()

    def _calculate_text_stats(self, text: str) -> Dict[str, Any]:
        """Calculate comprehensive text statistics"""
        try:
            words = word_tokenize(text)
            sentences = sent_tokenize(text)

            # Remove punctuation for word analysis
            words_clean = [word.lower() for word in words if word.isalnum()]

            # Calculate various metrics
            word_count = len(words_clean)
            sentence_count = len(sentences)
            unique_words = len(set(words_clean))

            # Readability metrics
            avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
            avg_word_length = sum(len(word) for word in words_clean) / word_count if word_count > 0 else 0

            # Vocabulary richness
            lexical_diversity = unique_words / word_count if word_count > 0 else 0

            # Common word analysis
            word_freq = Counter(words_clean)
            common_words = dict(word_freq.most_common(10))

            return {
                'word_count': word_count,
                'sentence_count': sentence_count,
                'unique_words': unique_words,
                'avg_sentence_length': round(avg_sentence_length, 1),
                'avg_word_length': round(avg_word_length, 1),
                'lexical_diversity': round(lexical_diversity, 3),
                'char_count': len(text),
                'char_count_no_spaces': len(text.replace(' ', '')),
                'most_common_words': common_words,
                'readability_level': self._assess_readability(avg_sentence_length, lexical_diversity)
            }
        except:
            return self._default_text_stats()

    def _generate_summary_insights(self, nlp_results: Dict) -> Dict[str, Any]:
        """Generate key insights from NLP results"""
        try:
            insights = {}

            # Sentiment insights
            sentiment = nlp_results.get('sentiment', {})
            insights['overall_sentiment'] = {
                'label': sentiment.get('label', 'Neutral'),
                'score': sentiment.get('score', 0),
                'confidence': sentiment.get('confidence', 0)
            }

            # Entity insights
            entities = nlp_results.get('entities', [])
            entity_summary = {}
            for entity in entities[:10]:
                etype = entity.get('category', 'Other')
                if etype not in entity_summary:
                    entity_summary[etype] = []
                entity_summary[etype].append(entity['text'])

            insights['entity_summary'] = entity_summary

            # Topic insights
            topics = nlp_results.get('topics', [])
            insights['main_topics'] = [
                {'topic': t['topic'], 'confidence': t.get('confidence', 0)}
                for t in topics[:5]
            ]

            # Intent insights
            intents = nlp_results.get('intents', [])
            insights['primary_intents'] = [
                {'intent': i['intent'], 'confidence': i.get('confidence', 0)}
                for i in intents[:3]
            ]

            # POS insights
            pos_tags = nlp_results.get('pos_tags', {})
            insights['language_style'] = {
                'noun_density': pos_tags.get('category_counts', {}).get('Nouns', 0) / pos_tags.get('total_words', 1) if pos_tags.get('total_words') else 0,
                'verb_density': pos_tags.get('category_counts', {}).get('Verbs', 0) / pos_tags.get('total_words', 1) if pos_tags.get('total_words') else 0,
                'adjective_density': pos_tags.get('category_counts', {}).get('Adjectives', 0) / pos_tags.get('total_words', 1) if pos_tags.get('total_words') else 0
            }

            return insights

        except Exception as e:
            logger.error(f" Insight generation error: {e}")
            return {}

    def _map_entity_type_nltk(self, nltk_type: str) -> Tuple[str, str]:
        """Map NLTK entity types to categories and icons"""
        mapping = {
            'PERSON': ('People', '👤'),
            'ORGANIZATION': ('Organizations', '🏢'),
            'GPE': ('Locations', '📍'),
            'LOCATION': ('Locations', '📍'),
            'FACILITY': ('Facilities', '🏭'),
            'GSP': ('Locations', '📍'),
            'DATE': ('Dates', '📅'),
            'TIME': ('Times', '⏰'),
            'MONEY': ('Financial', '💰'),
            'PERCENT': ('Numbers', '📊'),
            'PRODUCT': ('Products', '📦'),
            'EVENT': ('Events', '🎉'),
            'LAW': ('Legal', '⚖️'),
            'LANGUAGE': ('Languages', '🔤')
        }
        return mapping.get(nltk_type, ('Other', '🏷️'))

    def _categorize_topic(self, topic: str) -> str:
        """Categorize topics into predefined categories"""
        topic_lower = topic.lower()

        categories = {
            'Business': ['business', 'company', 'corporate', 'enterprise', 'market', 'industry', 'sales', 'revenue', 'profit'],
            'Technology': ['tech', 'software', 'hardware', 'digital', 'ai', 'machine', 'computer', 'system', 'data', 'cloud'],
            'Finance': ['finance', 'money', 'investment', 'bank', 'stock', 'price', 'cost', 'budget', 'payment'],
            'Health': ['health', 'medical', 'doctor', 'hospital', 'patient', 'medicine', 'care', 'wellness'],
            'Education': ['education', 'school', 'university', 'learning', 'student', 'study', 'course', 'training'],
            'Entertainment': ['entertainment', 'movie', 'music', 'game', 'sport', 'fun', 'show', 'film'],
            'Travel': ['travel', 'trip', 'hotel', 'flight', 'destination', 'vacation', 'tour'],
            'Food': ['food', 'restaurant', 'meal', 'drink', 'coffee', 'lunch', 'dinner', 'cuisine'],
            'Personal': ['family', 'friend', 'home', 'life', 'personal', 'relationship', 'feeling'],
            'Professional': ['work', 'job', 'career', 'project', 'meeting', 'team', 'office', 'deadline']
        }

        for category, keywords in categories.items():
            if any(keyword in topic_lower for keyword in keywords):
                return category

        return 'General'

    def _get_intent_description(self, intent_name: str) -> str:
        """Get description for intent types"""
        descriptions = {
            'question': 'Asking a question or seeking information',
            'request': 'Making a request or asking for something',
            'complaint': 'Expressing dissatisfaction or reporting an issue',
            'compliment': 'Giving praise or positive feedback',
            'greeting': 'Greeting or starting a conversation',
            'farewell': 'Ending a conversation or saying goodbye',
            'agreement': 'Expressing agreement or confirmation',
            'disagreement': 'Expressing disagreement or denial',
            'confusion': 'Expressing confusion or seeking clarification',
            'urgency': 'Expressing urgency or time sensitivity',
            'decision': 'Making a decision or commitment',
            'suggestion': 'Offering a suggestion or recommendation',
            'information': 'Providing or sharing information'
        }
        return descriptions.get(intent_name, 'General conversation')

    def _get_intent_icon(self, intent_name: str) -> str:
        """Get icon for intent types"""
        icons = {
            'question': '❓',
            'request': '🙏',
            'complaint': '⚠️',
            'compliment': '⭐',
            'greeting': '👋',
            'farewell': '👋',
            'agreement': '✅',
            'disagreement': '❌',
            'confusion': '🤔',
            'urgency': '⏰',
            'decision': '🎯',
            'suggestion': '💡',
            'information': '💬'
        }
        return icons.get(intent_name, '💬')

    def _assess_readability(self, avg_sentence_length: float, lexical_diversity: float) -> str:
        """Assess text readability level"""
        if avg_sentence_length < 10 and lexical_diversity < 0.4:
            return 'Easy'
        elif avg_sentence_length < 20 and lexical_diversity < 0.6:
            return 'Medium'
        elif avg_sentence_length < 30:
            return 'Advanced'
        else:
            return 'Complex'

    def _default_sentiment(self) -> Dict[str, Any]:
        return {
            'label': 'Neutral',
            'score': 0,
            'emoji': '😐',
            'color': '#6B7280',
            'confidence': 0,
            'detailed': {'positive': 0, 'neutral': 1, 'negative': 0, 'compound': 0},
            'word_counts': {'positive_words': 0, 'negative_words': 0}
        }

    def _default_timing_analysis(self, paragraphs: List[Dict]) -> Dict[str, Any]:
        if paragraphs:
            return {
                'total_duration': max(p.get('end', 0) for p in paragraphs),
                'num_exchanges': 0,
                'interruptions': 0,
                'avg_gap': 0,
                'avg_segment_duration': np.mean([p.get('end', 0) - p.get('start', 0) for p in paragraphs]),
                'exchanges': [],
                'overlaps': [],
                'speaker_timing': {},
                'conversation_pace': 0
            }
        return {}

    def _default_nlp_results(self) -> Dict[str, Any]:
        return {
            'sentiment': self._default_sentiment(),
            'entities': [],
            'topics': [{'topic': 'General Discussion', 'confidence': 1.0}],
            'intents': [{'intent': 'Information', 'confidence': 0.5}],
            'key_phrases': [],
            'pos_tags': {},
            'timing_analysis': {},
            'conversation_flow': {},
            'text_statistics': self._default_text_stats(),
            'summary_insights': {},
            'processing_time': 0
        }

    def _default_text_stats(self) -> Dict[str, Any]:
        return {
            'word_count': 0,
            'sentence_count': 0,
            'unique_words': 0,
            'avg_sentence_length': 0,
            'avg_word_length': 0,
            'lexical_diversity': 0,
            'char_count': 0,
            'char_count_no_spaces': 0,
            'most_common_words': {},
            'readability_level': 'Unknown'
        }

# Global instance
_nlp_processor = None

def get_nlp_processor():
    """Get or create singleton NLP processor instance"""
    global _nlp_processor
    if _nlp_processor is None:
        _nlp_processor = NLPProcessor()
    return _nlp_processor