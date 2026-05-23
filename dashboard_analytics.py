import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import base64
from io import BytesIO
import logging
import os

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available - PDF export disabled")

logger = logging.getLogger(__name__)

class DashboardAnalytics:
    """Generates visualizations and analytics for dashboard"""

    def __init__(self, output_dir='static/charts'):
        self.output_dir = output_dir
        self.reports_dir = 'static/reports'
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        logger.info("Dashboard Analytics initialized")

    def generate_sentiment_timeline(self, sentiment_data: list,
                                    conversation_id: str) -> str:
        """
        Generate interactive sentiment timeline chart

        Args:
            sentiment_data: List of sentiment points with time, value, speaker
            conversation_id: Conversation ID for filename

        Returns:
            Path to generated chart
        """
        try:
            if not sentiment_data:
                return None

            df = pd.DataFrame(sentiment_data)

            # Create interactive plot
            fig = make_subplots(specs=[[{"secondary_y": False}]])

            # Add traces for each speaker
            speakers = df['speaker'].unique()
            colors = px.colors.qualitative.Set1

            for i, speaker in enumerate(speakers):
                speaker_data = df[df['speaker'] == speaker]

                fig.add_trace(
                    go.Scatter(
                        x=speaker_data['time'],
                        y=speaker_data['sentiment'],
                        mode='lines+markers',
                        name=f'Speaker {speaker}',
                        line=dict(color=colors[i % len(colors)], width=2),
                        marker=dict(size=6)
                    )
                )

            # Add zero line
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

            # Update layout
            fig.update_layout(
                title='Sentiment Timeline',
                xaxis_title='Time (seconds)',
                yaxis_title='Sentiment Score',
                hovermode='x unified',
                template='plotly_white',
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01
                )
            )

            # Add sentiment regions
            fig.add_hrect(y0=0.1, y1=1.0, line_width=0, fillcolor="green", opacity=0.1)
            fig.add_hrect(y0=-0.1, y1=0.1, line_width=0, fillcolor="yellow", opacity=0.1)
            fig.add_hrect(y0=-1.0, y1=-0.1, line_width=0, fillcolor="red", opacity=0.1)

            # Save
            output_path = f"{self.output_dir}/sentiment_{conversation_id}.html"
            fig.write_html(output_path)

            return output_path

        except Exception as e:
            logger.error(f"Sentiment timeline generation error: {e}")
            return None

    def generate_speaker_distribution(self, speaker_data: dict,
                                      conversation_id: str) -> str:
        """
        Generate speaker distribution pie chart

        Args:
            speaker_data: Speaker statistics
            conversation_id: Conversation ID for filename

        Returns:
            Path to generated chart
        """
        try:
            if not speaker_data:
                return None

            speakers = list(speaker_data.keys())
            word_counts = [speaker_data[s]['word_count'] for s in speakers]
            percentages = [speaker_data[s]['contribution_percentage'] for s in speakers]

            # Create pie chart
            fig = go.Figure(data=[go.Pie(
                labels=[f"Speaker {s}" for s in speakers],
                values=percentages,
                hole=.3,
                marker=dict(colors=px.colors.qualitative.Set2),
                textinfo='label+percent',
                textposition='auto',
                hoverinfo='label+percent+value',
                hovertemplate='<b>%{label}</b><br>Contribution: %{percent}<br>Words: %{value}<extra></extra>'
            )])

            fig.update_layout(
                title='Speaker Distribution',
                template='plotly_white',
                annotations=[dict(
                    text=f'Total Words: {sum(word_counts)}',
                    x=0.5, y=0.5, font_size=14, showarrow=False
                )]
            )

            # Save
            output_path = f"{self.output_dir}/speaker_dist_{conversation_id}.html"
            fig.write_html(output_path)

            return output_path

        except Exception as e:
            logger.error(f"Speaker distribution generation error: {e}")
            return None

    def generate_topic_cloud(self, topics: list, conversation_id: str) -> str:
        """
        Generate topic importance bar chart

        Args:
            topics: List of topics with confidence scores
            conversation_id: Conversation ID for filename

        Returns:
            Path to generated chart
        """
        try:
            if not topics:
                return None

            # Prepare data
            topic_names = [t['topic'] for t in topics[:10]]
            confidences = [t['confidence'] * 100 for t in topics[:10]]
            colors = px.colors.sequential.Viridis

            # Create horizontal bar chart
            fig = go.Figure(data=[
                go.Bar(
                    x=confidences,
                    y=topic_names,
                    orientation='h',
                    marker=dict(
                        color=confidences,
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title="Confidence %")
                    ),
                    text=[f"{c:.1f}%" for c in confidences],
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>Confidence: %{x:.1f}%<extra></extra>'
                )
            ])

            fig.update_layout(
                title='Top Topics',
                xaxis_title='Confidence (%)',
                yaxis_title='',
                template='plotly_white',
                height=400,
                margin=dict(l=10, r=10, t=40, b=20)
            )

            # Save
            output_path = f"{self.output_dir}/topics_{conversation_id}.html"
            fig.write_html(output_path)

            return output_path

        except Exception as e:
            logger.error(f"Topic cloud generation error: {e}")
            return None

    def generate_conversation_flow(self, flow_data: dict,
                                   conversation_id: str) -> str:
        """
        Generate conversation flow visualization

        Args:
            flow_data: Conversation flow data
            conversation_id: Conversation ID for filename

        Returns:
            Path to generated chart
        """
        try:
            if not flow_data or 'turn_transitions' not in flow_data:
                return None

            transitions = flow_data.get('turn_transitions', [])

            if not transitions:
                return None

            # Create flow diagram
            fig = go.Figure()

            # Track speaker turns
            speakers = set()
            for t in transitions:
                speakers.add(t['from'])
                speakers.add(t['to'])

            speakers = sorted(list(speakers))
            speaker_map = {s: i for i, s in enumerate(speakers)}

            # Create Sankey diagram
            source = []
            target = []
            value = []
            labels = [f"Speaker {s}" for s in speakers]

            # Count transitions
            transition_counts = {}
            for t in transitions:
                key = (t['from'], t['to'])
                transition_counts[key] = transition_counts.get(key, 0) + 1

            for (from_speaker, to_speaker), count in transition_counts.items():
                source.append(speaker_map[from_speaker])
                target.append(speaker_map[to_speaker])
                value.append(count)

            fig = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=labels,
                    color=px.colors.qualitative.Set1[:len(labels)]
                ),
                link=dict(
                    source=source,
                    target=target,
                    value=value
                )
            )])

            fig.update_layout(
                title='Conversation Flow (Speaker Transitions)',
                template='plotly_white',
                height=400
            )

            # Save
            output_path = f"{self.output_dir}/flow_{conversation_id}.html"
            fig.write_html(output_path)

            return output_path

        except Exception as e:
            logger.error(f"Conversation flow generation error: {e}")
            return None

    def generate_interaction_matrix(self, speaker_analysis: dict,
                                   conversation_id: str) -> str:
        """
        Generate speaker interaction heatmap

        Args:
            speaker_analysis: Speaker analysis data
            conversation_id: Conversation ID for filename

        Returns:
            Path to generated chart
        """
        try:
            if not speaker_analysis:
                return None

            speakers = list(speaker_analysis.keys())
            n_speakers = len(speakers)

            if n_speakers < 2:
                return None

            # Create interaction matrix (simplified - based on turn patterns)
            matrix = np.zeros((n_speakers, n_speakers))

            # Fill diagonal with speaking time
            for i, s in enumerate(speakers):
                matrix[i][i] = speaker_analysis[s]['duration']

            # Create heatmap
            fig = go.Figure(data=go.Heatmap(
                z=matrix,
                x=[f"Speaker {s}" for s in speakers],
                y=[f"Speaker {s}" for s in speakers],
                colorscale='Blues',
                hoverongaps=False,
                hovertemplate='<b>From: %{y}</b><br>To: %{x}<br>Duration: %{z:.1f}s<extra></extra>'
            ))

            fig.update_layout(
                title='Speaker Interaction Heatmap',
                template='plotly_white',
                height=400
            )

            # Save
            output_path = f"{self.output_dir}/interaction_{conversation_id}.html"
            fig.write_html(output_path)

            return output_path

        except Exception as e:
            logger.error(f"Interaction matrix generation error: {e}")
            return None

    def generate_comprehensive_report(self, analysis_result: dict,
                                      conversation_id: str) -> dict:
        """
        Generate all visualizations for a conversation

        Args:
            analysis_result: Complete analysis result
            conversation_id: Conversation ID

        Returns:
            Dictionary with paths to all generated charts
        """
        charts = {}

        try:
            # Extract data
            viz_data = analysis_result.get('visualization_data', {})
            speaker_analysis = analysis_result.get('speaker_analysis', {})
            nlp_analysis = analysis_result.get('nlp_analysis', {})

            # Generate charts
            if viz_data.get('sentiment_over_time'):
                charts['sentiment'] = self.generate_sentiment_timeline(
                    viz_data['sentiment_over_time'], conversation_id
                )

            if viz_data.get('speaker_distribution'):
                charts['speaker_dist'] = self.generate_speaker_distribution(
                    {str(s['speaker']): {'word_count': s['word_count'],
                                         'contribution_percentage': s['percentage']}
                     for s in viz_data['speaker_distribution']},
                    conversation_id
                )

            if nlp_analysis.get('topics'):
                charts['topics'] = self.generate_topic_cloud(
                    nlp_analysis['topics'], conversation_id
                )

            if nlp_analysis.get('conversation_flow'):
                charts['flow'] = self.generate_conversation_flow(
                    nlp_analysis['conversation_flow'], conversation_id
                )

            if speaker_analysis:
                charts['interaction'] = self.generate_interaction_matrix(
                    speaker_analysis, conversation_id
                )

            logger.info(f"Generated {len(charts)} charts for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Comprehensive report generation error: {e}")

        return charts

    def export_to_html(self, analysis_result: dict, charts: dict,
                      conversation_id: str) -> str:
        """
        Export complete analysis to HTML dashboard

        Args:
            analysis_result: Complete analysis result
            charts: Dictionary of chart paths
            conversation_id: Conversation ID

        Returns:
            Path to HTML dashboard
        """
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Conversation Analysis Report - {conversation_id}</title>
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                              color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
                    .section {{ background: white; padding: 20px; border-radius: 10px;
                               margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    .chart-container {{ height: 400px; margin-bottom: 20px; }}
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                                   gap: 20px; margin-bottom: 20px; }}
                    .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                  color: white; padding: 20px; border-radius: 10px;
                                  text-align: center; }}
                    .stat-value {{ font-size: 2.5rem; font-weight: bold; }}
                    .stat-label {{ font-size: 0.9rem; opacity: 0.9; }}
                    .speaker-analysis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                                         gap: 20px; }}
                    .speaker-card {{ background: #f8f9fa; padding: 15px; border-radius: 10px;
                                     border-left: 5px solid #667eea; }}
                    h2 {{ color: #333; }}
                    h3 {{ color: #667eea; margin-top: 0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Conversation Analysis Report</h1>
                    <p>Conversation ID: {conversation_id}</p>
                    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>

                <div class="section">
                    <h2>Executive Summary</h2>
                    <div class="summary-box" style="background: #e8f4fd; padding: 15px; border-radius: 10px;">
                        <p>{analysis_result.get('ai_summary', {}).get('summary', 'No summary available')}</p>
                        <p><strong>Conversation Type:</strong> {analysis_result.get('ai_summary', {}).get('conversation_type', 'General')}</p>
                    </div>
                </div>

                <div class="stats-grid">
            """

            # Add statistics
            metadata = analysis_result.get('metadata', {})
            stats = [
                ('Speakers', metadata.get('speaker_count', 1)),
                ('Words', metadata.get('word_count', 0)),
                ('Duration', f"{metadata.get('total_duration', 0)/60:.1f} min"),
                ('Sentiment', analysis_result.get('nlp_analysis', {}).get('sentiment', {}).get('label', 'Neutral'))
            ]

            for label, value in stats:
                html_content += f"""
                    <div class="stat-card">
                        <div class="stat-value">{value}</div>
                        <div class="stat-label">{label}</div>
                    </div>
                """

            html_content += """
                </div>

                <div class="section">
                    <h2>Speaker Analysis</h2>
                    <div class="speaker-analysis">
            """

            # Add speaker analysis
            speaker_analysis = analysis_result.get('speaker_analysis', {})
            speaker_names = analysis_result.get('speaker_names', {})
            for speaker_id, speaker in speaker_analysis.items():
                # Get custom name or use default
                display_name = speaker_names.get(str(speaker_id), speaker_names.get(speaker_id, f"Speaker {speaker_id}"))
                if not display_name or display_name == f"Speaker {speaker_id}":
                    display_name = speaker_names.get(str(speaker_id), f"Speaker {speaker_id}")
                
                html_content += f"""
                        <div class="speaker-card">
                            <h3>{display_name}</h3>
                            <p><strong>Words:</strong> {speaker.get('word_count', 0)}</p>
                            <p><strong>Speaking Time:</strong> {speaker.get('duration', 0):.1f}s</p>
                            <p><strong>Speaking Rate:</strong> {speaker.get('speaking_rate', 0):.1f} words/min</p>
                            <p><strong>Contribution:</strong> {speaker.get('contribution_percentage', 0)}%</p>
                            <p><strong>Sentiment:</strong> {speaker.get('sentiment', {}).get('label', 'Neutral')}</p>
                            <p><strong>Key Phrases:</strong> {', '.join(speaker.get('key_phrases', [])[:3])}</p>
                        </div>
                """

            html_content += """
                    </div>
                </div>

                <div class="section">
                    <h2>Visualizations</h2>
            """

            # Embed charts
            for chart_type, chart_path in charts.items():
                if chart_path and os.path.exists(chart_path):
                    try:
                        with open(chart_path, 'r', encoding='utf-8') as f:
                            chart_html = f.read()
                            html_content += f'<div class="chart-container">{chart_html}</div>'
                    except Exception as e:
                        logger.warning(f"Could not embed chart {chart_type}: {e}")

            html_content += """
                </div>

                <div class="section">
                    <h2>NLP Insights</h2>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
            """

            # Add NLP insights
            nlp = analysis_result.get('nlp_analysis', {})

            # Topics
            topics = nlp.get('topics', [])
            if topics:
                html_content += """
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px;">
                            <h3>Key Topics</h3>
                            <ul>
                """
                for topic in topics[:5]:
                    html_content += f"<li><strong>{topic.get('topic')}</strong> (confidence: {topic.get('confidence', 0)*100:.0f}%)</li>"
                html_content += """
                            </ul>
                        </div>
                """

            # Entities
            entities = nlp.get('entities', [])
            if entities:
                html_content += """
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px;">
                            <h3>Named Entities</h3>
                            <ul>
                """
                for entity in entities[:8]:
                    html_content += f"<li><strong>{entity.get('text')}</strong> ({entity.get('type')})</li>"
                html_content += """
                            </ul>
                        </div>
                """

            # Intents
            intents = nlp.get('intents', [])
            if intents:
                html_content += """
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px;">
                            <h3>Primary Intents</h3>
                            <ul>
                """
                for intent in intents[:5]:
                    html_content += f"<li><strong>{intent.get('intent')}</strong> (confidence: {intent.get('confidence', 0)*100:.0f}%)</li>"
                html_content += """
                            </ul>
                        </div>
                """

            html_content += """
                    </div>
                </div>

                <div class="section">
                    <h2>Full Transcript</h2>
                    <div style="max-height: 400px; overflow-y: auto; background: #f8f9fa; padding: 15px; border-radius: 10px;">
            """

            # Add transcript
            transcript_data = analysis_result.get('transcript', {})
            speaker_names = analysis_result.get('speaker_names', {})
            if transcript_data.get('paragraphs'):
                for para in transcript_data['paragraphs']:
                    speaker_id = str(para.get('speaker', 0))
                    display_name = speaker_names.get(speaker_id, f"Speaker {para.get('speaker', 0)}")
                    html_content += f"""
                        <div style="margin-bottom: 15px; padding: 10px; background: white; border-left: 5px solid #667eea;">
                            <strong>{display_name}</strong> <small>({para.get('start', 0):.1f}s - {para.get('end', 0):.1f}s)</small>
                            <p>{para.get('text', '')}</p>
                            <small>Sentiment: {para.get('sentiment', {}).get('label', 'Neutral')}</small>
                        </div>
                    """
            else:
                html_content += f"<p>{transcript_data.get('full_text', 'No transcript available')}</p>"

            html_content += """
                    </div>
                </div>
            </body>
            </html>
            """

            # Save HTML report
            output_path = f"{self.reports_dir}/report_{conversation_id}.html"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            return output_path

        except Exception as e:
            logger.error(f"HTML export error: {e}")
            return None

    def export_to_pdf(self, analysis_result: dict, conversation_id: str) -> str:
        """
        Export complete analysis to PDF document

        Args:
            analysis_result: Complete analysis result
            conversation_id: Conversation ID

        Returns:
            Path to PDF file
        """
        if not REPORTLAB_AVAILABLE:
            logger.error("ReportLab not available for PDF export")
            return None

        try:
            output_path = f"{self.reports_dir}/report_{conversation_id}.pdf"
            
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#333333'),
                spaceAfter=12,
                spaceBefore=20
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=10,
                alignment=TA_JUSTIFY
            )
            
            # Title
            story.append(Paragraph("Conversation Analysis Report", title_style))
            story.append(Spacer(1, 10))
            
            # Metadata
            metadata = analysis_result.get('metadata', {})
            speaker_names = analysis_result.get('speaker_names', {})
            
            story.append(Paragraph(f"Conversation ID: {conversation_id}", normal_style))
            story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
            story.append(Paragraph(f"Duration: {((metadata.get('total_duration', 0) or 0) / 60):.1f} minutes", normal_style))
            story.append(Paragraph(f"Speakers: {metadata.get('speaker_count', 1)}", normal_style))
            story.append(Paragraph(f"Words: {metadata.get('word_count', 0)}", normal_style))
            story.append(Spacer(1, 20))
            
            # Executive Summary
            summary = analysis_result.get('ai_summary', {})
            story.append(Paragraph("Executive Summary", heading_style))
            
            exec_summary = summary.get('executive_summary', summary.get('summary', 'No summary available'))
            story.append(Paragraph(exec_summary, normal_style))
            story.append(Spacer(1, 20))
            
            # Speaker Analysis
            story.append(Paragraph("Speaker Analysis", heading_style))
            
            speaker_analysis = analysis_result.get('speaker_analysis', {})
            for speaker_id, speaker in speaker_analysis.items():
                display_name = speaker_names.get(str(speaker_id), f"Speaker {speaker_id}")
                story.append(Paragraph(f"<b>{display_name}</b>", normal_style))
                story.append(Paragraph(
                    f"Words: {speaker.get('word_count', 0)} | "
                    f"Duration: {speaker.get('duration', 0):.1f}s | "
                    f"Speaking Rate: {speaker.get('speaking_rate', 0):.1f} words/min | "
                    f"Contribution: {speaker.get('contribution_percentage', 0)}%",
                    normal_style
                ))
                sentiment = speaker.get('sentiment', {})
                if sentiment:
                    story.append(Paragraph(f"Sentiment: {sentiment.get('label', 'Neutral')}", normal_style))
                story.append(Spacer(1, 10))
            
            # NLP Insights
            story.append(Paragraph("NLP Insights", heading_style))
            
            nlp = analysis_result.get('nlp_analysis', {})
            
            # Sentiment
            sentiment = nlp.get('sentiment', {})
            if sentiment:
                story.append(Paragraph(f"<b>Overall Sentiment:</b> {sentiment.get('label', 'Neutral')} "
                                     f"(Score: {sentiment.get('score', 0):.2f})", normal_style))
                story.append(Spacer(1, 10))
            
            # Topics
            topics = nlp.get('topics', [])
            if topics:
                story.append(Paragraph("<b>Key Topics:</b>", normal_style))
                for topic in topics[:5]:
                    story.append(Paragraph(
                        f"• {topic.get('topic', '')} ({topic.get('confidence', 0)*100:.0f}%)",
                        normal_style
                    ))
                story.append(Spacer(1, 10))
            
            # Entities
            entities = nlp.get('entities', [])
            if entities:
                story.append(Paragraph("<b>Named Entities:</b>", normal_style))
                entity_text = ", ".join([e.get('text', '') for e in entities[:8]])
                story.append(Paragraph(entity_text, normal_style))
                story.append(Spacer(1, 10))
            
            # Intents
            intents = nlp.get('intents', [])
            if intents:
                story.append(Paragraph("<b>Primary Intents:</b>", normal_style))
                for intent in intents[:3]:
                    story.append(Paragraph(
                        f"• {intent.get('intent', '')} ({intent.get('confidence', 0)*100:.0f}%)",
                        normal_style
                    ))
                story.append(Spacer(1, 10))
            
            # Key Points
            key_points = summary.get('key_points', [])
            if key_points:
                story.append(Paragraph("Key Discussion Points", heading_style))
                for point in key_points[:5]:
                    story.append(Paragraph(f"• {point}", normal_style))
                story.append(Spacer(1, 10))
            
            # Action Items
            action_items = summary.get('action_items', [])
            if action_items and action_items[0] != "N/A":
                story.append(Paragraph("Action Items", heading_style))
                for item in action_items[:5]:
                    story.append(Paragraph(f"• {item}", normal_style))
                story.append(Spacer(1, 10))
            
            # Transcript (abbreviated)
            story.append(Paragraph("Transcript Summary", heading_style))
            transcript_data = analysis_result.get('transcript', {})
            if transcript_data.get('paragraphs'):
                for para in transcript_data['paragraphs'][:10]:  # Limit to first 10 paragraphs
                    speaker_id = str(para.get('speaker', 0))
                    display_name = speaker_names.get(speaker_id, f"Speaker {para.get('speaker', 0)}")
                    text = para.get('text', '')[:200] + ('...' if len(para.get('text', '')) > 200 else '')
                    story.append(Paragraph(f"<b>{display_name}:</b> {text}", normal_style))
                    story.append(Spacer(1, 5))
            else:
                full_text = transcript_data.get('full_text', 'No transcript available')
                story.append(Paragraph(full_text[:1000] + ('...' if len(full_text) > 1000 else ''), normal_style))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF report generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDF export error: {e}")
            return None