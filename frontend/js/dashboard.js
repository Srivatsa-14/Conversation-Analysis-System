// Dashboard functionality

class DashboardManager {
    constructor() {
        this.api = new APIClient();
        this.currentMode = 'upload';
        this.selectedFile = null;
        this.analysisResult = null;
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.recordingStream = null;
        this.charts = {};

        this.init();
    }

    init() {
        this.loadUserData();
        this.loadConversationHistory();
        this.setupEventListeners();
        this.checkAPIHealth();
    }

    setupEventListeners() {
        // Mode selection
        document.querySelectorAll('.mode-card').forEach(card => {
            card.addEventListener('click', () => this.selectMode(card.dataset.mode));
        });

        // File input
        const fileInput = document.getElementById('audioFile');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }

        // Recording button
        const recordBtn = document.getElementById('recordBtn');
        if (recordBtn) {
            recordBtn.addEventListener('click', () => this.toggleRecording());
        }

        // Analyze button
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.analyzeConversation());
        }

        // Reset button
        const resetBtn = document.getElementById('resetBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetAnalysis());
        }

        // Download button
        const downloadBtn = document.getElementById('downloadBtn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadReport());
        }
    }

    async loadUserData() {
        try {
            const conversations = await this.api.getConversations();
            document.getElementById('totalConversations').textContent = conversations.length;
        } catch (error) {
            console.error('Error loading user data:', error);
        }
    }

    async loadConversationHistory() {
        try {
            const conversations = await this.api.getConversations();
            this.renderConversationHistory(conversations);
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }

    renderConversationHistory(conversations) {
        const historyGrid = document.getElementById('historyGrid');

        if (!conversations || conversations.length === 0) {
            historyGrid.innerHTML = '<p style="color: var(--gray); text-align: center; grid-column: 1/-1;">No conversations yet. Start by uploading or recording one!</p>';
            return;
        }

        historyGrid.innerHTML = conversations.slice(0, 6).map(conv => `
            <div class="history-item" onclick="dashboard.loadConversation('${conv.conversation_id}')">
                <h4>${conv.filename || 'Recording'}</h4>
                <p>${conv.conversation_type || 'General'} conversation</p>
                <div class="history-meta">
                    <span><i class="fas fa-users"></i> ${conv.speaker_count} speakers</span>
                    <span><i class="fas fa-clock"></i> ${Math.round(conv.duration/60)} min</span>
                    <span><i class="far fa-calendar"></i> ${new Date(conv.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');
    }

    async loadConversation(conversationId) {
        try {
            this.showLoader(true);
            const conversation = await this.api.getConversation(conversationId);
            this.analysisResult = conversation;
            this.displayResults();
            this.showSuccess('Conversation loaded successfully');
        } catch (error) {
            console.error('Error loading conversation:', error);
            this.showError('Failed to load conversation');
        } finally {
            this.showLoader(false);
        }
    }

    selectMode(mode) {
        this.currentMode = mode;

        // Update UI
        document.querySelectorAll('.mode-card').forEach(card => {
            card.classList.toggle('active', card.dataset.mode === mode);
        });

        const titles = {
            'upload': 'Upload Audio File',
            'live': 'Live Recording',
            'url': 'Audio URL'
        };
        document.getElementById('modeTitle').textContent = titles[mode];

        // Show/hide sections
        document.getElementById('uploadSection').style.display = mode === 'upload' ? 'block' : 'none';
        document.getElementById('liveSection').style.display = mode === 'live' ? 'block' : 'none';
        document.getElementById('urlSection').style.display = mode === 'url' ? 'block' : 'none';

        this.resetAnalysis();
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        this.selectedFile = file;

        // Update file info
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = this.formatFileSize(file.size);

        // Calculate audio duration
        if (file.type.startsWith('audio/')) {
            const audio = new Audio(URL.createObjectURL(file));
            audio.onloadedmetadata = () => {
                const duration = Math.round(audio.duration);
                const minutes = Math.floor(duration / 60);
                const seconds = duration % 60;
                document.getElementById('fileDuration').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            };
        }

        document.getElementById('fileInfo').classList.add('active');
        document.getElementById('analyzeBtn').disabled = false;
    }

    async toggleRecording() {
        const recordBtn = document.getElementById('recordBtn');
        const btnIcon = recordBtn.querySelector('i');
        const btnText = recordBtn.querySelector('span');

        if (!this.isRecording) {
            try {
                // Request microphone access
                this.recordingStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });

                // Create media recorder
                const options = { mimeType: 'audio/webm' };
                this.mediaRecorder = new MediaRecorder(
                    this.recordingStream,
                    MediaRecorder.isTypeSupported('audio/webm') ? options : undefined
                );

                this.audioChunks = [];

                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        this.audioChunks.push(event.data);
                    }
                };

                this.mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                    const fileName = `recording_${new Date().getTime()}.wav`;

                    this.selectedFile = new File([audioBlob], fileName, {
                        type: 'audio/wav',
                        lastModified: new Date().getTime()
                    });

                    // Update file info
                    document.getElementById('fileName').textContent = fileName;
                    document.getElementById('fileSize').textContent = this.formatFileSize(audioBlob.size);

                    // Approximate duration
                    const duration = audioBlob.size / 16000 / 2;
                    const minutes = Math.floor(duration / 60);
                    const seconds = Math.floor(duration % 60);
                    document.getElementById('fileDuration').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;

                    document.getElementById('fileInfo').classList.add('active');
                    document.getElementById('analyzeBtn').disabled = false;

                    // Stop all tracks
                    if (this.recordingStream) {
                        this.recordingStream.getTracks().forEach(track => track.stop());
                        this.recordingStream = null;
                    }

                    this.showSuccess('Recording completed! Click "Start Analysis" to process.');
                };

                this.mediaRecorder.start(1000);
                this.isRecording = true;

                // Update UI
                recordBtn.classList.add('recording');
                btnIcon.className = 'fas fa-stop';
                btnText.textContent = 'Stop Recording';
                document.getElementById('recordingStatus').style.display = 'block';

                this.showSuccess('Recording started... Click stop when done.');

            } catch (error) {
                console.error('Recording error:', error);
                this.handleRecordingError(error);
            }
        } else {
            // Stop recording
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                this.mediaRecorder.stop();
            }

            this.isRecording = false;
            recordBtn.classList.remove('recording');
            btnIcon.className = 'fas fa-microphone';
            btnText.textContent = 'Start Recording';
            document.getElementById('recordingStatus').style.display = 'none';
        }
    }

    handleRecordingError(error) {
        let errorMessage = 'Microphone access denied or not available.';

        if (error.name === 'NotAllowedError') {
            errorMessage = 'Microphone access denied. Please allow microphone access and try again.';
        } else if (error.name === 'NotFoundError') {
            errorMessage = 'No microphone found. Please connect a microphone and try again.';
        } else if (error.name === 'NotReadableError') {
            errorMessage = 'Microphone is busy or not available. Please check your audio settings.';
        }

        this.showError(errorMessage);

        // Reset UI
        const recordBtn = document.getElementById('recordBtn');
        recordBtn.classList.remove('recording');
        recordBtn.querySelector('i').className = 'fas fa-microphone';
        recordBtn.querySelector('span').textContent = 'Start Recording';
        this.isRecording = false;
    }

    async analyzeConversation() {
        // Validate input
        if (this.currentMode === 'upload' && !this.selectedFile) {
            this.showError('Please select a file to upload');
            return;
        }

        if (this.currentMode === 'live' && !this.selectedFile) {
            this.showError('Please record audio first');
            return;
        }

        if (this.currentMode === 'url') {
            const url = document.getElementById('audioUrl').value.trim();
            if (!url) {
                this.showError('Please enter an audio URL');
                return;
            }
            if (!this.isValidUrl(url)) {
                this.showError('Please enter a valid URL');
                return;
            }
        }

        this.showLoader(true);
        document.getElementById('analyzeBtn').disabled = true;
        this.updateProgress(10);

        try {
            let uploadResponse;

            if (this.currentMode === 'upload' || this.currentMode === 'live') {
                if (!this.selectedFile) {
                    throw new Error('No audio file available');
                }

                uploadResponse = await this.api.uploadFile(this.selectedFile);
                this.updateProgress(40);
            } else if (this.currentMode === 'url') {
                const url = document.getElementById('audioUrl').value.trim();
                uploadResponse = {
                    data: {
                        url: url,
                        conversation_id: `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
                    }
                };
                this.updateProgress(20);
            }

            const transcribeRequest = {
                url: uploadResponse.data.url,
                conversation_id: uploadResponse.data.conversation_id,
                filename: this.selectedFile ? this.selectedFile.name : 'url_recording'
            };

            this.updateProgress(60);

            const analysisResult = await this.api.transcribe(transcribeRequest);
            this.updateProgress(100);

            this.analysisResult = analysisResult;

            this.displayResults();
            document.getElementById('downloadBtn').disabled = false;
            await this.loadConversationHistory();

            this.showSuccess('Analysis completed successfully!');

        } catch (error) {
            console.error('Analysis error:', error);
            this.showError(error.message || 'Analysis failed');
            this.updateProgress(0);
        } finally {
            this.showLoader(false);
            document.getElementById('analyzeBtn').disabled = false;
        }
    }

    displayResults() {
        if (!this.analysisResult) return;

        document.getElementById('resultsSection').style.display = 'block';
        document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });

        this.updateStats();
        this.updateSummary();
        this.updateSpeakerNamingUI();
        this.updateSpeakerSummaries();
        this.updateCharts();
        this.updateNLPInsights();
        this.updateKeyPoints();
        this.updateActionItems();
        this.updateEmotionalAnalysis();
        this.updateConclusions();
        this.updateTimingAnalysis();
        this.updatePOSTags();
        this.updateTranscript();
        this.updateSpeakerAnalysis();
    }

    updateSpeakerNamingUI() {
        const container = document.getElementById('speakerNamingContainer');
        if (!container) return;
        
        const speakers = this.analysisResult.speaker_analysis || {};
        const speakerNames = this.analysisResult.speaker_names || {};
        
        if (Object.keys(speakers).length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <div style="margin-bottom: 20px;">
                <h3><i class="fas fa-user-edit"></i> Name Speakers</h3>
                <p style="color: var(--gray); margin-bottom: 15px;">Assign names to speakers for personalized transcripts and summaries.</p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    ${Object.keys(speakers).map(speakerId => `
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <label style="font-weight: bold; min-width: 80px;">Speaker ${speakerId}:</label>
                            <input type="text" 
                                   class="speaker-name-input" 
                                   data-speaker-id="${speakerId}"
                                   value="${speakerNames[speakerId] || ''}"
                                   placeholder="Enter name..."
                                   style="flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 5px;">
                        </div>
                    `).join('')}
                </div>
                <button onclick="dashboard.saveSpeakerNames()" 
                        style="margin-top: 15px; padding: 10px 20px; background: var(--primary); color: white; border: none; border-radius: 5px; cursor: pointer;">
                    <i class="fas fa-save"></i> Save Names
                </button>
            </div>
        `;
    }

    async saveSpeakerNames() {
        if (!this.analysisResult || !this.analysisResult.conversation_id) {
            this.showError('No conversation loaded');
            return;
        }

        const inputs = document.querySelectorAll('.speaker-name-input');
        const speakerNames = {};
        
        inputs.forEach(input => {
            const speakerId = input.dataset.speakerId;
            const name = input.value.trim();
            if (name) {
                speakerNames[speakerId] = name;
            }
        });

        try {
            await this.api.updateSpeakerNames(this.analysisResult.conversation_id, speakerNames);
            this.analysisResult.speaker_names = speakerNames;
            this.showSuccess('Speaker names saved successfully!');
            
            // Update transcript and speaker analysis with new names
            this.updateTranscript();
            this.updateSpeakerAnalysis();
            this.updateSpeakerSummaries();
        } catch (error) {
            console.error('Error saving speaker names:', error);
            this.showError('Failed to save speaker names');
        }
    }

    getSpeakerName(speakerId) {
        const speakerNames = this.analysisResult?.speaker_names || {};
        return speakerNames[speakerId] || `Speaker ${speakerId}`;
    }

    updateStats() {
        const statsGrid = document.getElementById('statsGrid');
        const meta = this.analysisResult.metadata || {};
        const nlp = this.analysisResult.nlp_analysis || {};

        const durationMinutes = meta.duration_minutes || (meta.total_duration ? (meta.total_duration / 60).toFixed(1) : '0');
        const sentimentLabel = nlp.sentiment?.label || 'Neutral';

        const stats = [
            { value: meta.speaker_count || 1, label: 'Speakers', icon: 'fa-users', color: '#4361ee' },
            { value: meta.word_count || 0, label: 'Words', icon: 'fa-font', color: '#7209b7' },
            { value: durationMinutes, label: 'Minutes', icon: 'fa-clock', color: '#06d6a0' },
            { value: sentimentLabel, label: 'Sentiment', icon: 'fa-smile', color: this.getSentimentColor(sentimentLabel) }
        ];

        statsGrid.innerHTML = stats.map(stat => `
            <div class="stat-card">
                <div class="stat-value" style="color: ${stat.color}">${stat.value}</div>
                <div class="stat-label">${stat.label}</div>
            </div>
        `).join('');
    }

    updateSummary() {
        const summaryBox = document.getElementById('executiveSummary');
        const summary = this.analysisResult.ai_summary || {};
        summaryBox.textContent = summary.executive_summary || summary.summary || 'No executive summary available.';
    }

    updateSpeakerSummaries() {
        const speakerSummaries = document.getElementById('speakerSummaries');
        const summary = this.analysisResult.ai_summary || {};
        const speakerAnalysis = summary.speaker_analysis || {};

        if (Object.keys(speakerAnalysis).length === 0) {
            speakerSummaries.style.display = 'none';
            return;
        }

        speakerSummaries.style.display = 'grid';
        speakerSummaries.innerHTML = Object.entries(speakerAnalysis).map(([speaker, text]) => {
            // Extract speaker ID from the key (e.g., "Speaker 0" -> "0")
            const speakerId = speaker.replace('Speaker ', '');
            const displayName = this.getSpeakerName(speakerId);
            return `
                <div class="speaker-summary-card">
                    <h4><i class="fas fa-user-circle"></i> ${displayName}</h4>
                    <p>${text}</p>
                </div>
            `;
        }).join('');
    }

    updateCharts() {
        // Destroy existing charts
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};

        // Speaker distribution chart
        const speakerCtx = document.getElementById('speakerChart').getContext('2d');
        const speakerData = this.analysisResult.visualization_data?.speaker_distribution || [];

        if (speakerData.length > 0) {
            const colors = ['#4361ee', '#7209b7', '#06d6a0', '#ffd166', '#ef476f', '#f95738', '#3d5a80'];

            this.charts.speaker = new Chart(speakerCtx, {
                type: 'doughnut',
                data: {
                    labels: speakerData.map(s => `Speaker ${s.speaker}`),
                    datasets: [{
                        data: speakerData.map(s => s.percentage),
                        backgroundColor: colors.slice(0, speakerData.length),
                        borderWidth: 2,
                        borderColor: 'white'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right' },
                        tooltip: {
                            callbacks: {
                                label: (context) => `${context.label}: ${context.raw.toFixed(1)}%`
                            }
                        }
                    }
                }
            });
        }

        // Sentiment timeline chart
        const sentimentCtx = document.getElementById('sentimentChart').getContext('2d');
        const sentimentData = this.analysisResult.visualization_data?.sentiment_over_time || [];

        if (sentimentData.length > 0) {
            this.charts.sentiment = new Chart(sentimentCtx, {
                type: 'line',
                data: {
                    labels: sentimentData.map((s, i) => this.formatTime(s.time)),
                    datasets: [{
                        label: 'Sentiment Score',
                        data: sentimentData.map(s => s.sentiment),
                        borderColor: '#4361ee',
                        backgroundColor: 'rgba(67, 97, 238, 0.1)',
                        borderWidth: 3,
                        pointBackgroundColor: sentimentData.map(s =>
                            s.sentiment > 0.1 ? '#06d6a0' : s.sentiment < -0.1 ? '#ef476f' : '#ffd166'
                        ),
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            min: -1,
                            max: 1,
                            grid: { color: 'rgba(0,0,0,0.05)' },
                            title: { display: true, text: 'Sentiment' }
                        }
                    }
                }
            });
        }
    }

    updateNLPInsights() {
        const nlpInsights = document.getElementById('nlpInsights');
        const nlp = this.analysisResult.nlp_analysis || {};

        const insights = [
            {
                title: 'Sentiment Analysis',
                icon: 'fa-smile',
                content: nlp.sentiment ? `
                    <div style="text-align: center; margin-bottom: 10px;">
                        <span style="font-size: 2rem;">${nlp.sentiment.emoji || '😐'}</span>
                    </div>
                    <span class="sentiment-badge sentiment-${this.getSentimentClass(nlp.sentiment.label)}"
                          style="background-color: ${nlp.sentiment.color}20; color: ${nlp.sentiment.color};">
                        ${nlp.sentiment.label} (${(nlp.sentiment.score * 100).toFixed(0)}%)
                    </span>
                    <p style="margin-top: 10px;">Confidence: ${(nlp.sentiment.confidence * 100).toFixed(0)}%</p>
                ` : 'No sentiment data'
            },
            {
                title: 'Key Topics',
                icon: 'fa-tags',
                content: nlp.topics && nlp.topics.length > 0 ? `
                    <div class="tag-cloud">
                        ${nlp.topics.slice(0, 8).map(topic => `
                            <span class="tag primary">
                                ${topic.topic} (${(topic.confidence * 100).toFixed(0)}%)
                            </span>
                        `).join('')}
                    </div>
                ` : 'No topics detected'
            },
            {
                title: 'Named Entities',
                icon: 'fa-building',
                content: nlp.entities && nlp.entities.length > 0 ? `
                    <div class="tag-cloud">
                        ${nlp.entities.slice(0, 10).map(entity => `
                            <span class="tag">
                                ${entity.icon || '🏷️'} ${entity.text} (${entity.type})
                            </span>
                        `).join('')}
                    </div>
                ` : 'No entities detected'
            }
        ];

        nlpInsights.innerHTML = insights.map(insight => `
            <div class="analysis-card">
                <h3><i class="fas ${insight.icon}"></i> ${insight.title}</h3>
                ${insight.content}
            </div>
        `).join('');
    }

    updateKeyPoints() {
        const keyPoints = document.getElementById('keyPoints');
        const summary = this.analysisResult.ai_summary || {};
        const points = summary.key_points || [];

        if (points.length === 0) {
            keyPoints.innerHTML = '<li style="color: var(--gray);">No key points extracted</li>';
            return;
        }

        keyPoints.innerHTML = points.map(point => `
            <li style="margin-bottom: 10px; padding-left: 20px; position: relative;">
                <i class="fas fa-circle" style="color: var(--primary); font-size: 0.5rem; position: absolute; left: 0; top: 8px;"></i>
                ${point}
            </li>
        `).join('');
    }

    updateActionItems() {
        const actionItems = document.getElementById('actionItems');
        const summary = this.analysisResult.ai_summary || {};
        const items = summary.action_items || [];

        if (items.length === 0) {
            actionItems.innerHTML = '<li style="color: var(--gray);">No action items detected</li>';
            return;
        }

        actionItems.innerHTML = items.map(item => `
            <li style="margin-bottom: 10px; padding-left: 20px; position: relative;">
                <i class="fas fa-check-circle" style="color: var(--success); position: absolute; left: 0; top: 3px;"></i>
                ${item}
            </li>
        `).join('');
    }

    updateEmotionalAnalysis() {
        const emotionalAnalysis = document.getElementById('emotionalAnalysis');
        const summary = this.analysisResult.ai_summary || {};
        emotionalAnalysis.textContent = summary.emotional_analysis || 'No emotional analysis available.';
    }

    updateConclusions() {
        const conclusions = document.getElementById('conclusions');
        const summary = this.analysisResult.ai_summary || {};
        conclusions.textContent = summary.conclusions || 'No conclusions available.';
    }

    updateTimingAnalysis() {
        const timing = this.analysisResult.nlp_analysis?.timing_analysis || {};

        document.getElementById('totalExchanges').textContent = timing.num_exchanges || 0;
        document.getElementById('interruptions').textContent = timing.interruptions || 0;
        document.getElementById('avgGap').textContent = timing.avg_gap ? timing.avg_gap.toFixed(2) + 's' : '0s';
        document.getElementById('convPace').textContent = timing.conversation_pace ?
            timing.conversation_pace.toFixed(2) + ' turns/sec' : '0 turns/sec';
    }

    updatePOSTags() {
        const posTags = document.getElementById('posTags');
        const pos = this.analysisResult.nlp_analysis?.pos_tags?.category_counts || {};

        if (Object.keys(pos).length === 0) {
            posTags.innerHTML = '<p style="color: var(--gray);">No POS data available</p>';
            return;
        }

        const total = Object.values(pos).reduce((a, b) => a + b, 0);
        posTags.innerHTML = Object.entries(pos).map(([category, count]) => `
            <div style="flex: 1; min-width: 120px;">
                <strong>${category}:</strong> ${count} (${((count/total)*100).toFixed(1)}%)
            </div>
        `).join('');
    }

    updateTranscript() {
        const transcriptContainer = document.getElementById('transcriptContainer');
        const transcript = this.analysisResult.transcript || {};

        if (transcript.paragraphs && transcript.paragraphs.length > 0) {
            transcriptContainer.innerHTML = transcript.paragraphs.map(para => `
                <div class="transcript-line">
                    <div class="transcript-speaker">
                        <span class="speaker-tag speaker-${para.speaker}">${this.getSpeakerName(para.speaker)}</span>
                        <span class="transcript-time">
                            <i class="fas fa-clock"></i> ${this.formatTime(para.start)} - ${this.formatTime(para.end)}
                        </span>
                    </div>
                    <div class="transcript-text">${para.text}</div>
                    <div class="transcript-meta">
                        <span class="sentiment-badge sentiment-${this.getSentimentClass(para.sentiment?.label)}">
                            ${para.sentiment?.emoji || ''} ${para.sentiment?.label || 'Neutral'}
                        </span>
                        ${para.intents ? para.intents.map(i => `
                            <span class="sentiment-badge sentiment-neutral">
                                ${i.icon || '💬'} ${i.intent}
                            </span>
                        `).join('') : ''}
                    </div>
                </div>
            `).join('');
        } else if (transcript.full_text) {
            transcriptContainer.innerHTML = `
                <div class="transcript-line">
                    <div class="transcript-text">${transcript.full_text}</div>
                </div>
            `;
        } else {
            transcriptContainer.innerHTML = '<p style="text-align: center; color: var(--gray);">No transcript available.</p>';
        }
    }

    updateSpeakerAnalysis() {
        const speakerAnalysis = document.getElementById('speakerAnalysis');
        const speakers = this.analysisResult.speaker_analysis || {};

        if (Object.keys(speakers).length === 0) {
            speakerAnalysis.innerHTML = '<p style="color: var(--gray);">No speaker analysis available.</p>';
            return;
        }

        speakerAnalysis.innerHTML = Object.values(speakers).map(speaker => `
            <div class="analysis-card">
                <h4>
                    <span class="speaker-tag speaker-${speaker.id}">${this.getSpeakerName(speaker.id)}</span>
                </h4>
                <div style="margin-top: 15px;">
                    <div style="margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span>Contribution</span>
                            <span><strong>${speaker.contribution_percentage}%</strong> (${speaker.word_count} words)</span>
                        </div>
                        <div style="height: 8px; background: var(--light-gray); border-radius: 4px;">
                            <div style="width: ${speaker.contribution_percentage}%; height: 100%; background: var(--primary); border-radius: 4px;"></div>
                        </div>
                    </div>

                    <p><i class="fas fa-chart-line"></i> Speaking Rate: ${speaker.speaking_rate} words/min</p>
                    <p><i class="fas fa-clock"></i> Duration: ${speaker.duration}s</p>

                    ${speaker.sentiment ? `
                        <p><i class="fas fa-smile"></i> Sentiment:
                            <span class="sentiment-badge sentiment-${this.getSentimentClass(speaker.sentiment.label)}">
                                ${speaker.sentiment.label}
                            </span>
                        </p>
                    ` : ''}

                    ${speaker.key_phrases && speaker.key_phrases.length > 0 ? `
                        <p><i class="fas fa-key"></i> Key Phrases: ${speaker.key_phrases.join(' • ')}</p>
                    ` : ''}

                    <p><i class="fas fa-check-circle"></i> Confidence: ${(speaker.avg_word_confidence * 100).toFixed(0)}%</p>
                </div>
            </div>
        `).join('');
    }

    async downloadReport() {
        const response = await fetch(`/api/export/${this.analysisResult.conversation_id}/pdf`, {
            headers: this.getHeaders()
        });

        if (!response.ok) {
            throw new Error('Download failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `conversation_report_${this.analysisResult.conversation_id}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    async updateSpeakerNames(conversationId, speakerNames) {
        const response = await fetch(`/api/conversations/${conversationId}/speakers`, {
            method: 'PUT',
            headers: this.getHeaders(),
            body: JSON.stringify({ speaker_names: speakerNames })
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to update speaker names');
        }
        return data;
    }

    async downloadReportFull(conversationId, format = 'pdf') {
        const endpoint = format === 'pdf' ? `/api/export/${conversationId}/pdf` : `/api/export/${conversationId}`;
        const filename = format === 'pdf' 
            ? `conversation_report_${conversationId}.pdf` 
            : `conversation_report_${conversationId}.html`;
        
        const response = await fetch(endpoint, {
            headers: this.getHeaders()
        });

        if (!response.ok) {
            throw new Error('Download failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    resetAnalysis() {
        this.selectedFile = null;
        document.getElementById('audioFile').value = '';
        document.getElementById('fileInfo').classList.remove('active');
        document.getElementById('audioUrl').value = '';

        if (this.isRecording) {
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                this.mediaRecorder.stop();
            }
            if (this.recordingStream) {
                this.recordingStream.getTracks().forEach(track => track.stop());
                this.recordingStream = null;
            }
            this.isRecording = false;

            const recordBtn = document.getElementById('recordBtn');
            recordBtn.classList.remove('recording');
            recordBtn.querySelector('i').className = 'fas fa-microphone';
            recordBtn.querySelector('span').textContent = 'Start Recording';
            document.getElementById('recordingStatus').style.display = 'none';
        }

        this.resetResults();

        document.getElementById('analyzeBtn').disabled = false;
        document.getElementById('downloadBtn').disabled = true;
        this.updateProgress(0);
        document.getElementById('errorMessage').style.display = 'none';
        document.getElementById('successMessage').style.display = 'none';
    }

    resetResults() {
        this.analysisResult = null;
        document.getElementById('resultsSection').style.display = 'none';

        // Clear all result containers
        document.getElementById('statsGrid').innerHTML = '';
        document.getElementById('executiveSummary').textContent = 'Loading...';
        document.getElementById('speakerSummaries').innerHTML = '';
        document.getElementById('nlpInsights').innerHTML = '';
        document.getElementById('keyPoints').innerHTML = '';
        document.getElementById('actionItems').innerHTML = '';
        document.getElementById('emotionalAnalysis').textContent = '';
        document.getElementById('conclusions').textContent = '';
        document.getElementById('posTags').innerHTML = '';
        document.getElementById('transcriptContainer').innerHTML = '';
        document.getElementById('speakerAnalysis').innerHTML = '';

        // Reset charts
        const speakerCanvas = document.getElementById('speakerChart');
        const sentimentCanvas = document.getElementById('sentimentChart');

        if (speakerCanvas) {
            speakerCanvas.parentNode.innerHTML = '<canvas id="speakerChart"></canvas>';
        }
        if (sentimentCanvas) {
            sentimentCanvas.parentNode.innerHTML = '<canvas id="sentimentChart"></canvas>';
        }

        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
    }

    async checkAPIHealth() {
        try {
            const response = await fetch('/api/health');
            const data = await response.json();
            if (!data.success) {
                this.showError('API connection issue. Some features may not work.');
            }
        } catch (error) {
            this.showError('Cannot connect to server. Make sure the backend is running.');
        }
    }

    // Utility functions
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatTime(seconds) {
        if (!seconds && seconds !== 0) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch {
            return false;
        }
    }

    getSentimentClass(label) {
        if (!label) return 'neutral';
        const lower = label.toLowerCase();
        if (lower.includes('positive')) return 'positive';
        if (lower.includes('negative')) return 'negative';
        return 'neutral';
    }

    getSentimentColor(label) {
        const cls = this.getSentimentClass(label);
        return cls === 'positive' ? '#06d6a0' : cls === 'negative' ? '#ef476f' : '#6c757d';
    }

    // UI helpers
    updateProgress(percent) {
        document.getElementById('progressFill').style.width = percent + '%';
    }

    showLoader(show) {
        const loader = document.getElementById('loader');
        loader.classList.toggle('active', show);

        if (show) {
            const texts = [
                'Processing audio...',
                'Detecting speakers...',
                'Transcribing speech...',
                'Analyzing sentiment...',
                'Extracting topics...',
                'Identifying entities...',
                'Generating speaker summaries...',
                'Creating visualizations...'
            ];
            let index = 0;

            const interval = setInterval(() => {
                if (!show) {
                    clearInterval(interval);
                    return;
                }
                document.getElementById('loaderText').textContent = texts[index % texts.length];
                index++;
            }, 2500);
        }
    }

    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }

    showSuccess(message) {
        const successDiv = document.getElementById('successMessage');
        successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
        successDiv.style.display = 'block';
        setTimeout(() => {
            successDiv.style.display = 'none';
        }, 3000);
    }
}

// API Client
class APIClient {
    constructor() {
        this.baseURL = '';
    }

    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };

        const token = localStorage.getItem('token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        return headers;
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('audio', file);

        const response = await fetch('/api/upload', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Upload failed');
        }
        return data;
    }

    async transcribe(request) {
        const response = await fetch('/api/transcribe', {
            method: 'POST',
            headers: this.getHeaders(),
            body: JSON.stringify(request)
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Transcription failed');
        }
        return data.data;
    }

    async getConversations() {
        const response = await fetch('/api/conversations', {
            headers: this.getHeaders()
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to fetch conversations');
        }
        return data.data;
    }

    async getConversation(conversationId) {
        const response = await fetch(`/api/conversations/${conversationId}`, {
            headers: this.getHeaders()
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to fetch conversation');
        }
        return data.data;
    }

    async updateSpeakerNames(conversationId, speakerNames) {
        const response = await fetch(`/api/conversations/${conversationId}/speakers`, {
            method: 'PUT',
            headers: this.getHeaders(),
            body: JSON.stringify({ speaker_names: speakerNames })
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to update speaker names');
        }
        return data;
    }
}

// Initialize dashboard
const dashboard = new DashboardManager();
window.dashboard = dashboard;