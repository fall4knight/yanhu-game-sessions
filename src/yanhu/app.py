"""Yanhu web app for viewing sessions and triggering pipeline runs.

A local web UI to browse session outputs and submit new jobs.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request

# HTML templates (keeping existing templates, adding job form)
BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }} - Yanhu Sessions</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        header {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        h2 { color: #34495e; margin: 20px 0 10px; }
        h3 { color: #555; margin: 15px 0 8px; }
        .nav { margin-bottom: 20px; }
        .nav a { color: #3498db; text-decoration: none; }
        .nav a:hover { text-decoration: underline; }
        .content {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .session-list { list-style: none; }
        .session-item {
            padding: 15px;
            margin: 10px 0;
            background: #f8f9fa;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }
        .session-item a {
            color: #2c3e50;
            text-decoration: none;
            font-weight: 500;
        }
        .session-item a:hover { color: #3498db; }
        .session-meta {
            font-size: 0.9em;
            color: #7f8c8d;
            margin-top: 5px;
        }
        .status-pending { color: #f39c12; }
        .status-processing { color: #3498db; }
        .status-done { color: #27ae60; }
        .status-failed { color: #e74c3c; }
        .status-cancelled { color: #95a5a6; }
        .status-cancel_requested { color: #e67e22; }
        .job-form {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
        }
        .form-group input {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .form-group small {
            color: #7f8c8d;
            font-size: 12px;
        }
        .form-group select {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            background: white;
        }
        .whisper-options {
            margin-left: 20px;
            padding-left: 15px;
            border-left: 3px solid #3498db;
        }
        .btn {
            background: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .btn:hover { background: #2980b9; }
        .upload-area {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 20px;
            border: 2px dashed #ddd;
        }
        .upload-area.dragover {
            border-color: #3498db;
            background: #e8f4f8;
        }
        .file-input-wrapper {
            margin-bottom: 15px;
        }
        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        .tab {
            padding: 10px 20px;
            background: #f0f0f0;
            border: none;
            cursor: pointer;
            border-radius: 6px 6px 0 0;
            font-size: 14px;
        }
        .tab.active {
            background: white;
            border-bottom: 2px solid #3498db;
            margin-bottom: -2px;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .analysis-part {
            background: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .analysis-part h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .analysis-summary p {
            margin: 8px 0;
        }
        .raw-json {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 12px;
        }
        .progress-bar {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .progress-bar.done {
            background: #d4edda;
            border-color: #28a745;
        }
        .progress-info { font-size: 14px; }
        .progress-info strong { color: #333; }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
        }
        pre {
            background: #f4f4f4;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
        }
        blockquote {
            border-left: 4px solid #ddd;
            padding-left: 15px;
            color: #666;
            margin: 10px 0;
        }
        /* Command blocks for error banners */
        .cmd-block {
            background: #1a1a1a;
            border-radius: 4px;
            padding: 8px 12px;
            margin: 8px 0;
            display: flex;
            align-items: center;
            gap: 10px;
            font-family: 'Monaco', 'Courier New', monospace;
        }
        .cmd-label {
            color: #aaa;
            font-size: 13px;
            min-width: 60px;
        }
        .cmd-text {
            color: #f0f0f0;
            font-size: 13px;
            flex: 1;
            user-select: all;
        }
        .cmd-copy-btn {
            background: #444;
            color: #fff;
            border: none;
            padding: 4px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 11px;
            transition: background 0.2s;
        }
        .cmd-copy-btn:hover {
            background: #555;
        }
        .cmd-copy-btn.copied {
            background: #27ae60;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            padding: 10px;
            border: 1px solid #ddd;
            text-align: left;
        }
        th { background: #f8f9fa; font-weight: 600; }
        .error { color: #e74c3c; padding: 20px; }
        .success { color: #27ae60; padding: 10px; margin-bottom: 20px; }
        .ffmpeg-warning {
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 6px;
            padding: 15px;
            margin: 20px;
            color: #856404;
        }
        .ffmpeg-warning a { color: #856404; text-decoration: underline; }
        .ffmpeg-warning code {
            background: #ffeaa7;
            color: #2d3436;
        }
        .transcript-segments { margin-top: 20px; }
        .transcript-segment {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }
        .transcript-segment h4 {
            margin-bottom: 10px;
            color: #2c3e50;
        }
        .transcript-segment ul {
            list-style: none;
            padding-left: 0;
        }
        .transcript-segment li {
            padding: 5px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        .transcript-segment li:last-child { border-bottom: none; }
        #model-selector button {
            margin-right: 10px;
            margin-bottom: 10px;
        }
        #model-selector button.active {
            background: #2980b9;
        }
    </style>
</head>
<body>
    <header>
        <h1>Yanhu Sessions</h1>
        <div class="nav">
            <a href="/">← All Sessions</a>
            <span style="margin-left: 15px;">
                <a href="/settings">⚙️ Settings</a>
            </span>
            <span style="float: right;">
                <span style="color: #7f8c8d; font-size: 0.9em; margin-right: 15px;">
                    🔒 Local processing only
                </span>
                <button id="quitButton" onclick="quitServer()"
                        style="background: #e74c3c; color: white; border: none; padding: 5px 15px; border-radius: 4px; cursor: pointer; font-size: 0.9em;">
                    Quit Server
                </button>
            </span>
        </div>
    </header>
    {% if ffmpeg_warning %}
    <div class="ffmpeg-warning">
        <strong>⚠️ ffmpeg not available:</strong> {{ ffmpeg_warning }}
        <br>
        <small>
            Install ffmpeg to process videos:
            <strong>macOS:</strong> <code>brew install ffmpeg</code> |
            <strong>Windows:</strong> Download from
            <a href="https://ffmpeg.org/download.html" target="_blank">ffmpeg.org</a> |
            <strong>Linux:</strong> <code>sudo apt-get install ffmpeg</code>
        </small>
    </div>
    {% endif %}
    <div class="content">
        {% block content %}{% endblock %}
    </div>
    <script>
        const SHUTDOWN_TOKEN = "{{ shutdown_token }}";

        function quitServer() {
            if (!confirm("Quit the Yanhu server? The web page will become inaccessible.")) {
                return;
            }

            const formData = new FormData();
            formData.append("token", SHUTDOWN_TOKEN);

            fetch("/api/shutdown", {
                method: "POST",
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.ok) {
                    alert("Server stopped. You can close this tab.");
                    // Disable the button
                    document.getElementById("quitButton").disabled = true;
                    document.getElementById("quitButton").textContent = "Server Stopped";
                }
            })
            .catch(error => {
                // Expected: connection error after shutdown
                alert("Server stopped. You can close this tab.");
            });
        }

        // Copy command to clipboard
        function copyCommand(button, text) {
            navigator.clipboard.writeText(text).then(function() {
                const originalText = button.textContent;
                button.textContent = "Copied!";
                button.classList.add("copied");
                setTimeout(function() {
                    button.textContent = originalText;
                    button.classList.remove("copied");
                }, 2000);
            }).catch(function(err) {
                console.error("Failed to copy: ", err);
                button.textContent = "Failed";
                setTimeout(function() {
                    button.textContent = "Copy";
                }, 2000);
            });
        }
    </script>
    {% block scripts %}{% endblock %}
</body>
</html>
"""

SESSION_LIST_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """
    {% if worker_enabled %}
    <div class="upload-area" id="upload-area">
        <h3>Upload Video</h3>
        {% if not ffprobe_available %}
        <div style="background: #fff3cd; border: 1px solid #ffc107; padding: 10px; margin-bottom: 15px; border-radius: 4px; color: #856404;">
            <strong>⚠️ Upload disabled:</strong> ffprobe not found. Please install ffmpeg to enable video processing.
        </div>
        {% endif %}
        <form method="POST" action="/api/uploads" enctype="multipart/form-data" id="upload-form">
            <div class="file-input-wrapper">
                <input type="file" id="file" name="file" accept=".mp4,.mov,.mkv,.webm" required {{ "disabled" if not ffprobe_available else "" }}>
                <small>Drag & drop or click to select (.mp4, .mov, .mkv, .webm, max 5GB)</small>
            </div>
            <div class="form-group">
                <label for="upload_game">Game (optional)</label>
                <input type="text" id="upload_game" name="game" placeholder="genshin">
            </div>
            <div class="form-group">
                <label for="upload_preset">Preset</label>
                <select id="upload_preset" name="preset">
                    <option value="fast" selected>Fast (base model, int8)</option>
                    <option value="quality">Quality (small model, float32)</option>
                </select>
            </div>
            <div class="form-group">
                <label for="upload_transcribe_limit">Transcribe Limit (optional)</label>
                <input type="number" id="upload_transcribe_limit" name="transcribe_limit"
                       placeholder="0 = no limit">
                <small>Max segments to transcribe (0 or empty = no limit)</small>
            </div>
            <div class="form-group">
                <label for="upload_transcribe_max_seconds">Transcribe Max Seconds (optional)</label>
                <input type="number" step="0.1" id="upload_transcribe_max_seconds"
                       name="transcribe_max_seconds" placeholder="0 = no limit">
                <small>Max total duration to transcribe (0 or empty = no limit)</small>
            </div>
            <div class="form-group">
                <label for="asr_model">ASR Model</label>
                <select id="asr_model" name="asr_model" onchange="toggleWhisperOptions()">
                    {% for model in available_asr_models %}
                    <option value="{{ model.key }}"
                            {% if model.key == 'whisper_local' %}selected{% endif %}>
                        {{ model.display_name }}
                    </option>
                    {% endfor %}
                </select>
                <small>Select transcription model</small>
            </div>
            <div class="form-group whisper-options" id="whisper_options" style="display: block;">
                <label for="whisper_device">Whisper Device</label>
                <select id="whisper_device" name="whisper_device">
                    <option value="cpu" selected>CPU (int8)</option>
                    <option value="cuda">GPU/CUDA (float16)</option>
                </select>
                <small>CPU mode uses int8 quantization, GPU uses float16</small>
            </div>
            <button type="submit" class="btn" {{ "disabled" if not ffprobe_available else "" }}>Upload & Start Job</button>
        </form>
    </div>

    <div class="job-form">
        <h3>New Job (Existing File)</h3>
        {% if not ffprobe_available %}
        <div style="background: #fff3cd; border: 1px solid #ffc107; padding: 10px; margin-bottom: 15px; border-radius: 4px; color: #856404;">
            <strong>⚠️ Job submission disabled:</strong> ffprobe not found. Please install ffmpeg to enable video processing.
        </div>
        {% endif %}
        <form method="POST" action="/api/jobs">
            <div class="form-group">
                <label for="raw_path">Video Path</label>
                <input type="text" id="raw_path" name="raw_path"
                       placeholder="/path/to/video.mp4" required>
                <small>Absolute path to video file
                    {% if raw_dir %}(must be under {{ raw_dir }}){% endif %}
                </small>
            </div>
            <div class="form-group">
                <label for="game">Game (optional)</label>
                <input type="text" id="game" name="game"
                       placeholder="genshin">
                <small>Game name for session ID</small>
            </div>
            <div class="form-group">
                <label for="transcribe_limit">Transcribe Limit (optional)</label>
                <input type="number" id="transcribe_limit" name="transcribe_limit"
                       placeholder="0 = no limit">
                <small>Max segments to transcribe (0 or empty = no limit)</small>
            </div>
            <div class="form-group">
                <label for="transcribe_max_seconds">Transcribe Max Seconds (optional)</label>
                <input type="number" step="0.1" id="transcribe_max_seconds"
                       name="transcribe_max_seconds" placeholder="0 = no limit">
                <small>Max total duration to transcribe (0 or empty = no limit)</small>
            </div>
            <div class="form-group">
                <label for="asr_model">ASR Model</label>
                <select id="asr_model" name="asr_model" onchange="toggleWhisperOptions()">
                    {% for model in available_asr_models %}
                    <option value="{{ model.key }}"
                            {% if model.key == 'whisper_local' %}selected{% endif %}>
                        {{ model.display_name }}
                    </option>
                    {% endfor %}
                </select>
                <small>Select transcription model</small>
            </div>
            <div class="form-group whisper-options" id="whisper_options" style="display: block;">
                <label for="whisper_device">Whisper Device</label>
                <select id="whisper_device" name="whisper_device">
                    <option value="cpu" selected>CPU (int8)</option>
                    <option value="cuda">GPU/CUDA (float16)</option>
                </select>
                <small>CPU mode uses int8 quantization, GPU uses float16</small>
            </div>
            <button type="submit" class="btn" {{ "disabled" if not ffprobe_available else "" }}>Submit Job</button>
        </form>
    </div>
    {% endif %}

    <h2>Sessions & Jobs</h2>
    {% if jobs %}
        <ul class="session-list">
        {% for job in jobs %}
            <li class="session-item">
                {% if job.session_id %}
                    <a href="/s/{{ job.session_id }}">{{ job.session_id }}</a>
                {% elif job.job_id %}
                    <a href="/jobs/{{ job.job_id }}">{{ job.raw_filename or job.raw_path }}</a>
                {% else %}
                    <span>{{ job.raw_filename or job.raw_path }}</span>
                {% endif %}
                <div class="session-meta">
                    Status: <span class="status-{{ job.status }}">{{ job.status }}</span>
                    {% if job.created_at %}
                    | Created: {{ job.created_at }}
                    {% endif %}
                    {% if job.error %}
                    | Error: {{ job.error }}
                    {% endif %}
                    {% if job.job_id %}
                    | <a href="/jobs/{{ job.job_id }}">Details</a>
                    {% endif %}
                </div>
            </li>
        {% endfor %}
        </ul>
    {% else %}
        <p>No sessions or jobs found</p>
    {% endif %}
    """,
).replace(
    "{% block scripts %}{% endblock %}",
    """
    {% if worker_enabled %}
    <script>
    // Toggle Whisper options based on ASR model selection
    function toggleWhisperOptions() {
        const asrModel = document.getElementById('asr_model').value;
        const whisperOptions = document.getElementById('whisper_options');
        if (asrModel === 'whisper_local') {
            whisperOptions.style.display = 'block';
        } else {
            whisperOptions.style.display = 'none';
        }
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        toggleWhisperOptions();
    });

    // Drag & drop functionality
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file');

    if (uploadArea && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('dragover');
            }, false);
        });

        uploadArea.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                fileInput.files = files;
            }
        }, false);
    }
    </script>
    {% endif %}
    """,
)

SESSION_VIEW_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """
    <div id="progress-container"></div>
    <h2>{{ session_id }}</h2>

    {% if not has_api_key %}
    <div class="info-banner" style="background: #d4edda; color: #155724; padding: 15px; margin: 15px 0; border-radius: 4px; border: 1px solid #c3e6cb;">
        <strong>ℹ️ ASR-Only Mode:</strong> Vision/OCR analysis disabled (no ANTHROPIC_API_KEY). Timeline and highlights generated from audio transcription only.
    </div>
    {% endif %}

    {% if asr_error_summary %}
    {% if asr_error_summary.dependency_error %}
    <div class="error-banner" style="background: #e74c3c; color: white; padding: 15px; margin: 15px 0; border-radius: 4px;">
        <strong>⚠️ ASR Processing Failed:</strong> {{ asr_error_summary.dependency_error }}<br>
        <div style="margin-top: 10px;">
            <strong>How to fix:</strong>
            <div class="cmd-block">
                <span class="cmd-label">macOS:</span>
                <span class="cmd-text">brew install ffmpeg</span>
                <button class="cmd-copy-btn" onclick="copyCommand(this, 'brew install ffmpeg')">Copy</button>
            </div>
            <div class="cmd-block">
                <span class="cmd-label">Ubuntu:</span>
                <span class="cmd-text">sudo apt install ffmpeg</span>
                <button class="cmd-copy-btn" onclick="copyCommand(this, 'sudo apt install ffmpeg')">Copy</button>
            </div>
            <div class="cmd-block">
                <span class="cmd-label">Windows:</span>
                <span class="cmd-text">Download from <a href="https://ffmpeg.org/download.html" style="color: #3498db; text-decoration: underline;" target="_blank">ffmpeg.org</a></span>
            </div>
            <div style="margin-top: 10px; font-size: 0.9em;">
                After installing, re-run the pipeline for this session.
            </div>
        </div>
    </div>
    {% elif asr_error_summary.failed_segments > 0 %}
    <div class="warning-banner" style="background: #f39c12; color: white; padding: 15px; margin: 15px 0; border-radius: 4px;">
        <strong>⚠️ Partial ASR Failures:</strong> {{ asr_error_summary.failed_segments }}/{{ asr_error_summary.total_segments }} segments failed transcription.<br>
        <div style="margin-top: 5px; font-size: 0.9em;">
            Check the Transcripts tab for details. Timeline and highlights may be incomplete.
        </div>
    </div>
    {% endif %}
    {% endif %}

    <div class="tabs">
        <button class="tab active" onclick="showTab('overview')">Overview</button>
        <button class="tab" onclick="showTab('highlights')">Highlights</button>
        <button class="tab" onclick="showTab('timeline')">Timeline</button>
        <button class="tab" onclick="showTab('transcripts')">Transcripts</button>
        <button class="tab" onclick="showTab('analysis')">Analysis</button>
        <button class="tab" onclick="showTab('manifest')">Manifest</button>
    </div>
    <div id="overview" class="tab-content active">{{ overview_html|safe }}</div>
    <div id="highlights" class="tab-content">{{ highlights_html|safe }}</div>
    <div id="timeline" class="tab-content">{{ timeline_html|safe }}</div>
    <div id="transcripts" class="tab-content">
        <div id="transcripts-loading">Loading transcripts...</div>
        <div id="transcripts-content" style="display:none;">
            <div id="model-selector" style="margin-bottom: 1em;"></div>
            <div id="transcript-display"></div>
        </div>
    </div>
    <div id="analysis" class="tab-content">
        <div id="analysis-loading">Loading analysis...</div>
        <div id="analysis-content" style="display:none;"></div>
    </div>
    <div id="manifest" class="tab-content"><pre>{{ manifest_json }}</pre></div>
    """,
).replace(
    "{% block scripts %}{% endblock %}",
    """
    <script>
    let transcriptsData = null;
    let currentModel = null;

    function showTab(tabName, skipHashUpdate) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

        // Find and activate the tab button
        document.querySelectorAll('.tab').forEach(btn => {
            if (btn.textContent.trim().toLowerCase() === tabName.toLowerCase()) {
                btn.classList.add('active');
            }
        });

        document.getElementById(tabName).classList.add('active');

        // Update URL hash (unless called from hashchange to avoid loop)
        if (!skipHashUpdate) {
            window.location.hash = 'tab=' + tabName;
        }

        // Load transcripts when tab is clicked
        if (tabName === 'transcripts' && !transcriptsData) {
            loadTranscripts();
        }

        // Load analysis when tab is clicked
        if (tabName === 'analysis' && !analysisData) {
            loadAnalysis();
        }

        // Patch frame links to open in new tab
        patchFrameLinks();
    }

    function getActiveTabFromHash() {
        const hash = window.location.hash;
        const match = hash.match(/tab=(\\w+)/);
        return match ? match[1] : 'overview';
    }

    function activateTabFromHash() {
        const tabName = getActiveTabFromHash();
        showTab(tabName, true);  // skipHashUpdate=true to avoid loop
    }

    function patchFrameLinks() {
        // Find all links that point to frames and make them open in new tab
        document.querySelectorAll('a[href*="/frames/"]').forEach(link => {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');
        });
    }

    let analysisData = null;

    // Listen for hash changes (browser back/forward)
    window.addEventListener('hashchange', activateTabFromHash);

    // Activate tab from hash on page load
    document.addEventListener('DOMContentLoaded', () => {
        activateTabFromHash();
    });

    function loadTranscripts() {
        fetch('/s/{{ session_id }}/transcripts')
            .then(response => response.json())
            .then(data => {
                transcriptsData = data.models;
                const models = Object.keys(transcriptsData);

                if (models.length === 0) {
                    document.getElementById('transcripts-loading').innerHTML =
                        'No multi-model transcripts found.';
                    return;
                }

                // Hide loading, show content
                document.getElementById('transcripts-loading').style.display = 'none';
                document.getElementById('transcripts-content').style.display = 'block';

                // Create model selector
                const selector = document.getElementById('model-selector');
                selector.innerHTML = '<label>Select model: </label>';
                models.forEach((model, idx) => {
                    const btn = document.createElement('button');
                    btn.textContent = model;
                    btn.className = idx === 0 ? 'btn active' : 'btn';
                    btn.onclick = () => displayTranscript(model);
                    selector.appendChild(btn);
                });

                // Display first model by default
                if (models.length > 0) {
                    currentModel = models[0];
                    displayTranscript(currentModel);
                }
            })
            .catch(err => {
                console.error('Failed to load transcripts:', err);
                document.getElementById('transcripts-loading').innerHTML =
                    'Failed to load transcripts.';
            });
    }

    function displayTranscript(modelKey) {
        currentModel = modelKey;

        // Update button states
        document.querySelectorAll('#model-selector button').forEach(btn => {
            btn.classList.toggle('active', btn.textContent === modelKey);
        });

        const transcript = transcriptsData[modelKey];
        const display = document.getElementById('transcript-display');

        if (transcript.error) {
            display.innerHTML = `<p class="error">${transcript.error}</p>`;
            return;
        }

        // Group segments by segment_id
        let html = '<div class="transcript-segments">';
        transcript.forEach(seg => {
            const segId = seg.segment_id || 'unknown';
            const backend = seg.asr_backend || 'unknown';
            const error = seg.asr_error;
            const items = seg.asr_items || [];

            html += `<div class="transcript-segment">`;
            html += `<h4>${segId} <small>(${backend})</small></h4>`;

            if (error) {
                html += `<p class="error">Error: ${error}</p>`;
            } else if (items.length === 0) {
                html += `<p><em>No transcription items</em></p>`;
            } else {
                html += '<ul>';
                items.forEach(item => {
                    const text = item.text || '';
                    const tStart = item.t_start != null ? item.t_start.toFixed(2) : '?';
                    const tEnd = item.t_end != null ? item.t_end.toFixed(2) : '?';
                    html += `<li>[${tStart}s - ${tEnd}s]: ${escapeHtml(text)}</li>`;
                });
                html += '</ul>';
            }

            html += '</div>';
        });
        html += '</div>';

        display.innerHTML = html;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function loadAnalysis() {
        fetch('/s/{{ session_id }}/analysis')
            .then(response => response.json())
            .then(data => {
                analysisData = data;
                const parts = data.parts || [];

                if (parts.length === 0) {
                    document.getElementById('analysis-loading').innerHTML =
                        data.message || 'No analysis files found.';
                    return;
                }

                // Hide loading, show content
                document.getElementById('analysis-loading').style.display = 'none';
                document.getElementById('analysis-content').style.display = 'block';

                // Display parts
                displayAnalysisParts(parts);
            })
            .catch(err => {
                console.error('Failed to load analysis:', err);
                document.getElementById('analysis-loading').innerHTML =
                    'Failed to load analysis.';
            });
    }

    function displayAnalysisParts(parts) {
        const content = document.getElementById('analysis-content');
        let html = '<div class="analysis-parts">';

        parts.forEach(part => {
            html += `<div class="analysis-part">`;
            html += `<h3>${part.part_id}</h3>`;
            html += `<div class="analysis-summary">`;
            html += `<p><strong>Scene:</strong> ${escapeHtml(part.scene_label || 'N/A')}</p>`;
            if (part.what_changed) {
                const truncated = part.what_changed.length > 100
                    ? part.what_changed.substring(0, 100) + '...'
                    : part.what_changed;
                html += `<p><strong>Change:</strong> ${escapeHtml(truncated)}</p>`;
            }
            if (part.ui_key_text && part.ui_key_text.length > 0) {
                const uiText = part.ui_key_text.join(', ');
                const truncated = uiText.length > 80
                    ? uiText.substring(0, 80) + '...'
                    : uiText;
                html += `<p><strong>UI Text:</strong> ${escapeHtml(truncated)}</p>`;
            }
            html += `<p><strong>Counts:</strong> `;
            html += `OCR: ${part.ocr_count || 0}, `;
            html += `ASR: ${part.asr_count || 0}, `;
            html += `Quotes: ${part.quotes_count || 0}, `;
            html += `Symbols: ${part.symbols_count || 0}`;
            html += `</p>`;
            html += `</div>`;
            html += `<button class="btn" onclick="toggleRawJson('${part.part_id}')">
                     Toggle Raw JSON</button>`;
            html += `<pre id="raw-${part.part_id}" class="raw-json"
                     style="display:none; margin-top: 1em;"></pre>`;
            html += `</div>`;
        });

        html += '</div>';
        content.innerHTML = html;
    }

    function toggleRawJson(partId) {
        const pre = document.getElementById(`raw-${partId}`);
        if (pre.style.display === 'none') {
            // Load raw JSON if not loaded
            if (!pre.textContent) {
                fetch(`/s/{{ session_id }}/analysis/${partId}`)
                    .then(response => response.json())
                    .then(data => {
                        pre.textContent = JSON.stringify(data, null, 2);
                        pre.style.display = 'block';
                    })
                    .catch(err => {
                        pre.textContent = 'Error loading raw JSON: ' + err;
                        pre.style.display = 'block';
                    });
            } else {
                pre.style.display = 'block';
            }
        } else {
            pre.style.display = 'none';
        }
    }

    let pollInterval = null;

    function updateProgress() {
        fetch('/s/{{ session_id }}/progress')
            .then(response => response.ok ? response.json() : null)
            .then(data => {
                if (!data) {
                    document.getElementById('progress-container').innerHTML = '';
                    if (pollInterval) {
                        clearInterval(pollInterval);
                        pollInterval = null;
                    }
                    return;
                }

                const isDone = data.stage === 'done';
                const isDownloading = data.stage === 'download_model';
                const barClass = isDone ? 'progress-bar done' : 'progress-bar';
                const eta = data.eta_sec ? `, ETA ${formatDuration(data.eta_sec)}` : '';
                const coverage = data.coverage
                    ? `<br><strong>Partial:</strong> ` +
                      `${data.coverage.processed}/${data.coverage.total} segments transcribed`
                    : '';

                // Display message prominently if present (especially for download_model)
                const messageHtml = data.message
                    ? `<div style="margin-top: 8px; font-size: 14px; color: #555;">${data.message}</div>`
                    : '';

                // For download_model, don't show segment progress (not applicable)
                const progressDetails = isDownloading
                    ? `<strong>Elapsed:</strong> ${formatDuration(data.elapsed_sec)}`
                    : `<strong>Progress:</strong> ${data.done}/${data.total} segments
                       &nbsp;|&nbsp;
                       <strong>Elapsed:</strong> ${formatDuration(data.elapsed_sec)}${eta}`;

                document.getElementById('progress-container').innerHTML = `
                    <div class="${barClass}">
                        <div class="progress-info">
                            <strong>Stage:</strong> ${data.stage}
                            &nbsp;|&nbsp;
                            ${progressDetails}
                            ${coverage}
                            ${messageHtml}
                        </div>
                    </div>
                `;

                if (isDone && pollInterval) {
                    clearInterval(pollInterval);
                    pollInterval = null;
                }
            })
            .catch(err => console.error('Progress fetch error:', err));
    }

    function formatDuration(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.round(seconds % 60);
            return `${mins}m ${secs}s`;
        }
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }

    // Initial fetch
    updateProgress();

    // Poll every second if not done
    pollInterval = setInterval(updateProgress, 1000);
    </script>
    """,
)

JOB_DETAIL_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """
    <div id="progress-container"></div>
    <h2>Job: {{ job.job_id }}</h2>

    <div class="session-meta">
        <strong>Status:</strong> <span class="status-{{ job.status }}">{{ job.status }}</span>
    </div>

    {% if job.status == 'failed' and job.error %}
    <div class="error-banner" style="background: #e74c3c; color: white; padding: 15px; margin: 15px 0; border-radius: 4px;">
        <strong>⚠️ Job Failed:</strong> {{ job.error }}<br>
        {% if 'ffmpeg' in job.error %}
        <div style="margin-top: 10px;">
            <strong>How to fix:</strong>
            <div class="cmd-block">
                <span class="cmd-label">macOS:</span>
                <span class="cmd-text">brew install ffmpeg</span>
                <button class="cmd-copy-btn" onclick="copyCommand(this, 'brew install ffmpeg')">Copy</button>
            </div>
            <div class="cmd-block">
                <span class="cmd-label">Ubuntu:</span>
                <span class="cmd-text">sudo apt install ffmpeg</span>
                <button class="cmd-copy-btn" onclick="copyCommand(this, 'sudo apt install ffmpeg')">Copy</button>
            </div>
            <div class="cmd-block">
                <span class="cmd-label">Windows:</span>
                <span class="cmd-text">Download from <a href="https://ffmpeg.org/download.html" style="color: #3498db; text-decoration: underline;" target="_blank">ffmpeg.org</a></span>
            </div>
            <div style="margin-top: 10px; font-size: 0.9em;">
                After installing, retry this job or create a new one.
            </div>
        </div>
        {% endif %}
    </div>
    {% endif %}

    {% if job.outputs and job.outputs.get('asr_error_summary') %}
    {% set asr_errors = job.outputs.asr_error_summary %}
    {% if asr_errors.failed_segments > 0 and not asr_errors.dependency_error %}
    <div class="warning-banner" style="background: #f39c12; color: white; padding: 15px; margin: 15px 0; border-radius: 4px;">
        <strong>⚠️ Partial ASR Failures:</strong> {{ asr_errors.failed_segments }}/{{ asr_errors.total_segments }} segments failed transcription.<br>
        <div style="margin-top: 5px; font-size: 0.9em;">
            Check the Transcripts tab for details. The session was still created successfully.
        </div>
    </div>
    {% endif %}
    {% endif %}

    {% if job.media %}
    <h3>Media Info</h3>
    <table>
        <tr>
            <th>Property</th>
            <th>Value</th>
        </tr>
        {% if job.media.duration_sec %}
        <tr>
            <td>Duration</td>
            <td>{{ format_duration(job.media.duration_sec) }}</td>
        </tr>
        {% endif %}
        {% if job.media.file_size_bytes %}
        <tr>
            <td>File Size</td>
            <td>{{ format_size(job.media.file_size_bytes) }}</td>
        </tr>
        {% endif %}
        {% if job.media.width and job.media.height %}
        <tr>
            <td>Resolution</td>
            <td>{{ job.media.width }}×{{ job.media.height }}</td>
        </tr>
        {% endif %}
        {% if job.media.fps %}
        <tr>
            <td>FPS</td>
            <td>{{ "%.1f"|format(job.media.fps) }}</td>
        </tr>
        {% endif %}
        {% if job.media.video_codec %}
        <tr>
            <td>Video Codec</td>
            <td>{{ job.media.video_codec }}</td>
        </tr>
        {% endif %}
        {% if job.media.audio_codec %}
        <tr>
            <td>Audio Codec</td>
            <td>{{ job.media.audio_codec }}</td>
        </tr>
        {% endif %}
        {% if job.media.container %}
        <tr>
            <td>Container</td>
            <td>{{ job.media.container }}</td>
        </tr>
        {% endif %}
        {% if job.media.bitrate_kbps %}
        <tr>
            <td>Bitrate</td>
            <td>{{ job.media.bitrate_kbps }} kbps</td>
        </tr>
        {% endif %}
    </table>
    {% endif %}

    {% if job.estimated_segments %}
    <h3>Estimates</h3>
    <table>
        <tr>
            <th>Property</th>
            <th>Value</th>
        </tr>
        <tr>
            <td>Estimated Segments</td>
            <td>{{ job.estimated_segments }}</td>
        </tr>
        {% if job.estimated_runtime_sec %}
        <tr>
            <td>Estimated Runtime</td>
            <td>~{{ format_duration(job.estimated_runtime_sec) }}</td>
        </tr>
        {% endif %}
    </table>
    {% endif %}

    <h3>Job Details</h3>
    <table>
        <tr>
            <th>Field</th>
            <th>Value</th>
        </tr>
        <tr>
            <td>Job ID</td>
            <td><code>{{ job.job_id }}</code></td>
        </tr>
        <tr>
            <td>Created At</td>
            <td>{{ job.created_at }}</td>
        </tr>
        <tr>
            <td>Raw Path</td>
            <td><code>{{ job.raw_path }}</code></td>
        </tr>
        {% if job.suggested_game %}
        <tr>
            <td>Game</td>
            <td>{{ job.suggested_game }}</td>
        </tr>
        {% endif %}
        {% if job.preset %}
        <tr>
            <td>Preset</td>
            <td>{{ job.preset }}</td>
        </tr>
        {% endif %}
        {% if job.session_id %}
        <tr>
            <td>Session ID</td>
            <td><a href="/s/{{ job.session_id }}">{{ job.session_id }}</a></td>
        </tr>
        {% endif %}
        {% if job.error %}
        <tr>
            <td>Error</td>
            <td class="status-failed">{{ job.error }}</td>
        </tr>
        {% endif %}
    </table>

    {% if job.status in ['pending', 'processing', 'cancel_requested'] %}
    <div style="margin-top: 20px;">
        <form method="POST" action="/api/jobs/{{ job.job_id }}/cancel" style="display: inline;">
            <button type="submit" class="btn" style="background: #e74c3c;">Cancel Job</button>
        </form>
    </div>
    {% endif %}
    """,
).replace(
    "{% block scripts %}{% endblock %}",
    """
    <script>
    let pollInterval = null;
    let rateEma = null;  // For EMA smoothing

    function updateJobStatus() {
        fetch('/api/jobs/{{ job.job_id }}')
            .then(response => response.ok ? response.json() : null)
            .then(data => {
                if (!data) {
                    return;
                }

                // Update status display
                const statusElem = document.querySelector('.status-{{ job.status }}');
                if (statusElem && data.status !== '{{ job.status }}') {
                    // Reload page if status changed
                    window.location.reload();
                }

                // If processing and has session_id, try to fetch progress
                if (data.status === 'processing' && data.session_id) {
                    updateProgress(data.session_id);
                }

                // Stop polling if job is done
                if (data.status in ['done', 'failed', 'cancelled']) {
                    if (pollInterval) {
                        clearInterval(pollInterval);
                        pollInterval = null;
                    }
                }
            })
            .catch(err => console.error('Job status fetch error:', err));
    }

    function updateProgress(sessionId) {
        fetch('/s/' + sessionId + '/progress')
            .then(response => response.ok ? response.json() : null)
            .then(data => {
                if (!data) {
                    document.getElementById('progress-container').innerHTML = '';
                    return;
                }

                const isDone = data.stage === 'done';
                const isDownloading = data.stage === 'download_model';
                const barClass = isDone ? 'progress-bar done' : 'progress-bar';

                // Compute calibrated ETA if we have progress (not for download_model)
                let calibratedInfo = '';
                if (!isDownloading && data.done >= 1 && data.elapsed_sec > 0 && !isDone) {
                    const currentRate = data.done / data.elapsed_sec;

                    // Apply EMA smoothing (alpha = 0.2)
                    if (rateEma === null) {
                        rateEma = currentRate;
                    } else {
                        rateEma = 0.2 * currentRate + 0.8 * rateEma;
                    }

                    // Compute calibrated ETA
                    const remaining = data.total - data.done;
                    const etaCalibrated = remaining / rateEma;

                    // Estimate finish time
                    const finishTime = new Date(Date.now() + etaCalibrated * 1000);
                    const finishTimeStr = finishTime.toLocaleTimeString(
                        [], {hour: '2-digit', minute: '2-digit'}
                    );

                    calibratedInfo = `
                        <br><strong>Observed rate:</strong> ${rateEma.toFixed(3)} seg/s
                        &nbsp;|&nbsp;
                        <strong>Calibrated ETA:</strong> ~${formatDuration(etaCalibrated)}
                        &nbsp;|&nbsp;
                        <strong>Est. finish:</strong> ${finishTimeStr}
                    `;
                }

                const eta = data.eta_sec ? `, ETA ${formatDuration(data.eta_sec)}` : '';
                const coverage = data.coverage
                    ? `<br><strong>Partial:</strong> ` +
                      `${data.coverage.processed}/${data.coverage.total} segments transcribed`
                    : '';

                // Display message prominently if present (especially for download_model)
                const messageHtml = data.message
                    ? `<div style="margin-top: 8px; font-size: 14px; color: #555;">${data.message}</div>`
                    : '';

                // For download_model, don't show segment progress (not applicable)
                const progressDetails = isDownloading
                    ? `<strong>Elapsed:</strong> ${formatDuration(data.elapsed_sec)}`
                    : `<strong>Progress:</strong> ${data.done}/${data.total} segments
                       &nbsp;|&nbsp;
                       <strong>Elapsed:</strong> ${formatDuration(data.elapsed_sec)}${eta}`;

                document.getElementById('progress-container').innerHTML = `
                    <div class="${barClass}">
                        <div class="progress-info">
                            <strong>Stage:</strong> ${data.stage}
                            &nbsp;|&nbsp;
                            ${progressDetails}
                            ${coverage}
                            ${calibratedInfo}
                            ${messageHtml}
                        </div>
                    </div>
                `;
            })
            .catch(err => console.error('Progress fetch error:', err));
    }

    function formatDuration(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.round(seconds % 60);
            return `${mins}m ${secs}s`;
        }
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }

    // Initial status check
    updateJobStatus();

    // Poll every 2 seconds if not done
    {% if job.status in ['pending', 'processing', 'cancel_requested'] %}
    pollInterval = setInterval(updateJobStatus, 2000);
    {% endif %}
    </script>
    """,
)

SETTINGS_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """
    <h2>Settings</h2>

    <div class="settings-section">
        <h3>API Keys</h3>
        <p style="color: #666; margin-bottom: 20px;">
            Manage API keys for vision and analysis backends. Keys are stored securely
            <span id="storage-backend">(loading...)</span>.
        </p>

        <div id="keys-container">
            <p>Loading...</p>
        </div>
    </div>

    <script>
    const shutdownToken = '{{ shutdown_token }}';
    let keysData = {};

    async function loadKeys() {
        try {
            const response = await fetch('/api/settings/keys');
            const data = await response.json();
            keysData = data.keys;

            // Update storage backend display
            const backendName = data.backend === 'keychain' ? 'in OS keychain' : 'in ~/.yanhu-sessions/.env';
            document.getElementById('storage-backend').textContent = backendName;

            // Render keys
            renderKeys();
        } catch (err) {
            console.error('Failed to load keys:', err);
            document.getElementById('keys-container').innerHTML =
                '<p class="error">Failed to load API keys</p>';
        }
    }

    function renderKeys() {
        const container = document.getElementById('keys-container');
        container.innerHTML = '';

        const keyNames = ['ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'OPENAI_API_KEY'];
        const keyLabels = {
            'ANTHROPIC_API_KEY': 'Anthropic API Key',
            'GEMINI_API_KEY': 'Gemini API Key',
            'OPENAI_API_KEY': 'OpenAI API Key',
        };

        keyNames.forEach(keyName => {
            const keyStatus = keysData[keyName] || { set: false, masked: '' };
            const keyDiv = document.createElement('div');
            keyDiv.className = 'key-item';
            keyDiv.style.cssText = 'margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 6px;';

            const statusText = keyStatus.set
                ? `<strong>Status:</strong> Set (${keyStatus.masked})`
                : '<strong>Status:</strong> Not set';

            keyDiv.innerHTML = `
                <div style="margin-bottom: 10px;">
                    <strong>${keyLabels[keyName]}</strong><br>
                    <span style="color: #666; font-size: 14px;">${statusText}</span>
                </div>
                <div>
                    <input type="text" id="${keyName}-input" placeholder="Paste new key here"
                           style="width: 60%; padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                    <button class="btn" onclick="saveKey('${keyName}')">Save</button>
                    ${keyStatus.set ? `<button class="btn" style="background: #e74c3c; margin-left: 5px;" onclick="clearKey('${keyName}')">Clear</button>` : ''}
                </div>
                <div id="${keyName}-status" style="margin-top: 8px; font-size: 14px;"></div>
            `;

            container.appendChild(keyDiv);
        });
    }

    async function saveKey(keyName) {
        const input = document.getElementById(`${keyName}-input`);
        const statusDiv = document.getElementById(`${keyName}-status`);
        const keyValue = input.value.trim();

        if (!keyValue) {
            statusDiv.innerHTML = '<span style="color: #e74c3c;">Please enter a key value</span>';
            return;
        }

        statusDiv.innerHTML = '<span style="color: #666;">Saving...</span>';

        try {
            const response = await fetch('/api/settings/keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    token: shutdownToken,
                    key_name: keyName,
                    key_value: keyValue,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                statusDiv.innerHTML = '<span style="color: #27ae60;">✓ Key saved successfully</span>';
                input.value = '';
                // Reload keys to show updated masked value
                setTimeout(loadKeys, 500);
            } else {
                statusDiv.innerHTML = `<span style="color: #e74c3c;">Error: ${data.error}</span>`;
            }
        } catch (err) {
            console.error('Failed to save key:', err);
            statusDiv.innerHTML = '<span style="color: #e74c3c;">Failed to save key</span>';
        }
    }

    async function clearKey(keyName) {
        if (!confirm(`Clear ${keyName}?`)) {
            return;
        }

        const statusDiv = document.getElementById(`${keyName}-status`);
        statusDiv.innerHTML = '<span style="color: #666;">Clearing...</span>';

        try {
            const response = await fetch('/api/settings/keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    token: shutdownToken,
                    key_name: keyName,
                    key_value: null,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                statusDiv.innerHTML = '<span style="color: #27ae60;">✓ Key cleared</span>';
                setTimeout(loadKeys, 500);
            } else {
                statusDiv.innerHTML = `<span style="color: #e74c3c;">Error: ${data.error}</span>`;
            }
        } catch (err) {
            console.error('Failed to clear key:', err);
            statusDiv.innerHTML = '<span style="color: #e74c3c;">Failed to clear key</span>';
        }
    }

    // Load keys on page load
    loadKeys();
    </script>
    """,
)


def create_app(
    sessions_dir: str | Path,
    raw_dir: str | Path | None = None,
    worker_enabled: bool = False,
    allow_any_path: bool = False,
    preset: str = "fast",
    max_upload_size: int = 5 * 1024 * 1024 * 1024,  # 5GB default
    jobs_dir: str | Path | None = None,
) -> Flask:
    """Create and configure the Flask app.

    Args:
        sessions_dir: Path to directory containing session folders
        raw_dir: Path to raw video directory (for job submission validation)
        worker_enabled: Enable background worker for job processing
        allow_any_path: Allow any raw_path (skip validation that path is under raw_dir)
        preset: Processing preset for jobs (fast or quality)
        max_upload_size: Maximum upload file size in bytes (default: 5GB)
        jobs_dir: Path to jobs directory (if None, derived from sessions_dir)

    Returns:
        Configured Flask application
    """
    # Convert string paths to Path objects for internal use
    sessions_path = Path(sessions_dir) if isinstance(sessions_dir, str) else sessions_dir
    raw_path = Path(raw_dir) if isinstance(raw_dir, str) else raw_dir

    app = Flask(__name__)
    app.config["sessions_dir"] = sessions_path
    app.config["raw_dir"] = raw_path
    app.config["worker_enabled"] = worker_enabled
    app.config["allow_any_path"] = allow_any_path
    app.config["preset"] = preset
    app.config["queue_dir"] = sessions_path.parent / "_queue" if sessions_path else None
    # Use provided jobs_dir or derive from sessions_path
    if jobs_dir is not None:
        app.config["jobs_dir"] = Path(jobs_dir) if isinstance(jobs_dir, str) else jobs_dir
    else:
        app.config["jobs_dir"] = (
            sessions_path.parent / "_queue" / "jobs" if sessions_path else Path("_queue/jobs")
        )
    app.config["MAX_CONTENT_LENGTH"] = max_upload_size

    # Discover ffprobe path (with fallback for packaged apps)
    from yanhu.ffmpeg_utils import find_ffprobe

    ffprobe_path = find_ffprobe()
    app.config["ffprobe_path"] = ffprobe_path
    if not ffprobe_path:
        app.config["ffprobe_error"] = (
            "ffprobe not found. Please install ffmpeg to enable video processing."
        )

    # Generate per-launch shutdown token for security
    import secrets

    app.config["shutdown_token"] = secrets.token_urlsafe(32)

    # Check if ANTHROPIC_API_KEY is available
    import os
    app.config["has_api_key"] = bool(os.environ.get("ANTHROPIC_API_KEY"))

    @app.route("/")
    def index():
        """List all sessions and jobs, newest first."""
        from yanhu.asr_registry import list_asr_models

        sessions_path = Path(app.config["sessions_dir"])

        # Load jobs from jobs directory
        jobs_list = []
        if app.config["jobs_dir"]:
            from yanhu.watcher import list_all_jobs

            jobs = list_all_jobs(Path(app.config["jobs_dir"]))
            # Convert to dicts for template
            for job in jobs:
                job_dict = {
                    "job_id": job.job_id,
                    "raw_path": job.raw_path,
                    "raw_filename": Path(job.raw_path).name,
                    "status": job.status,
                    "created_at": job.created_at,
                    "session_id": job.session_id,
                    "error": job.error,
                }
                jobs_list.append(job_dict)

        # Load sessions from sessions dir (only those not already in jobs)
        # This is for backward compatibility with existing sessions
        if sessions_path.exists():
            session_ids_in_jobs = {j["session_id"] for j in jobs_list if j.get("session_id")}
            session_dirs = [d for d in sessions_path.iterdir() if d.is_dir()]
            for session_dir in session_dirs:
                # Skip if already tracked in jobs
                if session_dir.name in session_ids_in_jobs:
                    continue

                manifest_file = session_dir / "manifest.json"
                if not manifest_file.exists():
                    continue

                try:
                    with open(manifest_file, encoding="utf-8") as f:
                        manifest = json.load(f)

                    # Add as completed session (no job_id)
                    jobs_list.append(
                        {
                            "job_id": None,
                            "session_id": session_dir.name,
                            "created_at": manifest.get("created_at", "Unknown"),
                            "status": "done",
                            "raw_path": manifest.get("source_video", ""),
                            "raw_filename": Path(manifest.get("source_video", "")).name,
                            "error": None,
                        }
                    )
                except (json.JSONDecodeError, OSError):
                    continue

        # Sort by created_at descending (newest first)
        jobs_list.sort(key=lambda j: j.get("created_at", ""), reverse=True)

        return render_template_string(
            SESSION_LIST_TEMPLATE,
            jobs=jobs_list,
            worker_enabled=app.config["worker_enabled"],
            raw_dir=str(app.config["raw_dir"]) if app.config["raw_dir"] else None,
            title="Sessions",
            ffmpeg_warning=app.config.get("ffmpeg_error"),
            ffprobe_available=app.config.get("ffprobe_path") is not None,
            shutdown_token=app.config.get("shutdown_token", ""),
            available_asr_models=list_asr_models(),
        )

    @app.route("/s/<session_id>")
    def session_view(session_id: str):
        """View a specific session."""
        session_dir = Path(app.config["sessions_dir"]) / session_id

        if not session_dir.exists():
            return f"<div class='error'>Session not found: {session_id}</div>", 404

        # Load markdown files
        overview_md = session_dir / "overview.md"
        highlights_md = session_dir / "highlights.md"
        timeline_md = session_dir / "timeline.md"
        manifest_file = session_dir / "manifest.json"

        if not all(f.exists() for f in [overview_md, highlights_md, timeline_md]):
            return (
                "<div class='error'>Session incomplete: missing required output files</div>",
                404,
            )

        # Render markdown to HTML
        import markdown

        overview_html = markdown.markdown(
            overview_md.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"]
        )
        highlights_html = markdown.markdown(
            highlights_md.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"]
        )
        timeline_html = markdown.markdown(
            timeline_md.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"]
        )

        # Load manifest
        manifest_json = ""
        asr_models = None
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                manifest_json = json.dumps(manifest_data, indent=2, ensure_ascii=False)
                asr_models = manifest_data.get("asr_models")
            except (json.JSONDecodeError, OSError):
                manifest_json = "Error loading manifest"

        # Aggregate ASR errors
        from yanhu.watcher import aggregate_asr_errors
        asr_error_summary = aggregate_asr_errors(session_dir, asr_models)

        return render_template_string(
            SESSION_VIEW_TEMPLATE,
            session_id=session_id,
            overview_html=overview_html,
            highlights_html=highlights_html,
            timeline_html=timeline_html,
            manifest_json=manifest_json,
            title=session_id,
            ffmpeg_warning=app.config.get("ffmpeg_error"),
            asr_error_summary=asr_error_summary,
            shutdown_token=app.config.get("shutdown_token", ""),
            has_api_key=app.config.get("has_api_key", False),
        )

    @app.route("/s/<session_id>/progress")
    def session_progress(session_id: str):
        """Get progress.json for a session."""
        progress_file = Path(app.config["sessions_dir"]) / session_id / "outputs" / "progress.json"

        if not progress_file.exists():
            return jsonify({"error": "Progress not found"}), 404

        try:
            with open(progress_file, encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data)
        except (json.JSONDecodeError, OSError) as e:
            return jsonify({"error": f"Failed to load progress: {e}"}), 500

    @app.route("/s/<session_id>/manifest")
    def session_manifest(session_id: str):
        """Get manifest.json for a session."""
        manifest_file = Path(app.config["sessions_dir"]) / session_id / "manifest.json"

        if not manifest_file.exists():
            return jsonify({"error": "Manifest not found"}), 404

        try:
            with open(manifest_file, encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data)
        except (json.JSONDecodeError, OSError) as e:
            return jsonify({"error": f"Failed to load manifest: {e}"}), 500

    @app.route("/s/<session_id>/transcripts")
    def session_transcripts(session_id: str):
        """Get all per-model transcripts for a session."""
        session_dir = Path(app.config["sessions_dir"]) / session_id
        asr_dir = session_dir / "outputs" / "asr"

        if not asr_dir.exists():
            return jsonify({"models": {}})

        transcripts = {}
        for model_dir in asr_dir.iterdir():
            if model_dir.is_dir():
                transcript_file = model_dir / "transcript.json"
                if transcript_file.exists():
                    try:
                        with open(transcript_file, encoding="utf-8") as f:
                            transcripts[model_dir.name] = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        transcripts[model_dir.name] = {"error": "Failed to load"}

        return jsonify({"models": transcripts})

    @app.route("/s/<session_id>/analysis")
    def session_analysis_list(session_id: str):
        """Get list of available analysis files for a session.

        Returns JSON with parts list and summary info.
        """
        sessions_dir = Path(app.config["sessions_dir"])
        session_dir = sessions_dir / session_id
        analysis_dir = session_dir / "analysis"

        # Validate session exists
        if not session_dir.exists() or not session_dir.is_dir():
            return jsonify({"error": "Session not found", "parts": []}), 404

        # Check if analysis directory exists
        if not analysis_dir.exists() or not analysis_dir.is_dir():
            return jsonify({"message": "No analysis available yet", "parts": []})

        # Find all part_XXXX.json files
        import re

        parts_data = []
        for json_file in sorted(analysis_dir.glob("part_*.json")):
            # Validate filename pattern
            if not re.match(r"^part_\d{4}\.json$", json_file.name):
                continue

            part_id = json_file.stem  # e.g., "part_0001"

            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Extract summary fields
                parts_data.append(
                    {
                        "part_id": part_id,
                        "scene_label": data.get("scene_label", ""),
                        "what_changed": data.get("what_changed", ""),
                        "ui_key_text": data.get("ui_key_text", []),
                        "ocr_count": len(data.get("ocr_items", [])),
                        "asr_count": len(data.get("asr_items", [])),
                        "quotes_count": len(data.get("aligned_quotes", [])),
                        "symbols_count": len(data.get("ui_symbol_items", [])),
                    }
                )
            except (json.JSONDecodeError, OSError):
                # Skip invalid files
                continue

        return jsonify({"parts": parts_data})

    @app.route("/s/<session_id>/analysis/<part_id>")
    def session_analysis_part(session_id: str, part_id: str):
        """Get raw analysis JSON for a specific part.

        Args:
            session_id: Session identifier
            part_id: Part identifier (e.g., "part_0001")

        Returns:
            JSON content of analysis file or 404 if not found
        """
        import re

        # Validate session exists
        sessions_dir = Path(app.config["sessions_dir"])
        session_dir = sessions_dir / session_id

        if not session_dir.exists() or not session_dir.is_dir():
            return jsonify({"error": "Session not found"}), 404

        # Validate part_id pattern (security)
        if not re.match(r"^part_\d{4}$", part_id):
            return jsonify({"error": "Invalid part_id format"}), 400

        # Construct safe path
        analysis_dir = session_dir / "analysis"
        analysis_file = analysis_dir / f"{part_id}.json"

        # Verify file exists and is within expected directory (path traversal protection)
        try:
            analysis_file = analysis_file.resolve()
            analysis_dir = analysis_dir.resolve()
            if not str(analysis_file).startswith(str(analysis_dir)):
                return jsonify({"error": "Invalid path"}), 400
        except (OSError, ValueError):
            return jsonify({"error": "Invalid path"}), 400

        if not analysis_file.exists() or not analysis_file.is_file():
            return jsonify({"error": "Analysis file not found"}), 404

        # Load and return JSON
        try:
            with open(analysis_file, encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data)
        except (json.JSONDecodeError, OSError) as e:
            return jsonify({"error": f"Failed to load analysis: {e}"}), 500

    @app.route("/s/<session_id>/frames/<part_id>/<filename>")
    def session_frame(session_id: str, part_id: str, filename: str):
        """Serve a frame image file from a session.

        Args:
            session_id: Session identifier
            part_id: Segment/part identifier (e.g., "part_0001")
            filename: Frame filename (e.g., "frame_0001.jpg")

        Returns:
            Image file or 404 if not found
        """
        from flask import send_from_directory

        # Validate session exists
        sessions_dir = Path(app.config["sessions_dir"])
        session_dir = sessions_dir / session_id

        if not session_dir.exists() or not session_dir.is_dir():
            return jsonify({"error": "Session not found"}), 404

        # Validate part_id and filename for safety (prevent path traversal)
        # Only allow alphanumeric, underscore, hyphen, and dot
        import re

        if not re.match(r"^[\w\-]+$", part_id):
            return jsonify({"error": "Invalid part_id"}), 400
        if not re.match(r"^[\w\-\.]+$", filename):
            return jsonify({"error": "Invalid filename"}), 400

        # Check for path traversal attempts
        if ".." in part_id or ".." in filename:
            return jsonify({"error": "Invalid path"}), 400

        # Construct safe path
        frames_dir = session_dir / "frames" / part_id

        if not frames_dir.exists() or not frames_dir.is_dir():
            return jsonify({"error": "Frame directory not found"}), 404

        frame_path = frames_dir / filename

        # Verify file exists and is within expected directory (additional safety)
        try:
            frame_path = frame_path.resolve()
            frames_dir = frames_dir.resolve()
            if not str(frame_path).startswith(str(frames_dir)):
                return jsonify({"error": "Invalid path"}), 400
        except (OSError, ValueError):
            return jsonify({"error": "Invalid path"}), 400

        if not frame_path.exists() or not frame_path.is_file():
            return jsonify({"error": "Frame not found"}), 404

        # Serve the file
        return send_from_directory(frames_dir, filename)

    @app.route("/api/jobs", methods=["POST"])
    def submit_job():
        """Submit a new job to the queue."""
        if not app.config["worker_enabled"]:
            return jsonify({"error": "Worker not enabled"}), 400

        # Check ffprobe availability
        if not app.config.get("ffprobe_path"):
            return jsonify(
                {
                    "error": "ffprobe not found. Please install ffmpeg to enable video processing."
                }
            ), 400

        # Get form data
        raw_path_str = request.form.get("raw_path", "").strip()
        game = request.form.get("game", "").strip() or None
        transcribe_limit_str = request.form.get("transcribe_limit", "").strip()
        transcribe_max_seconds_str = request.form.get("transcribe_max_seconds", "").strip()

        # Validate raw_path
        if not raw_path_str:
            return jsonify({"error": "raw_path is required"}), 400

        raw_path = Path(raw_path_str)
        if not raw_path.exists():
            return jsonify({"error": f"File not found: {raw_path_str}"}), 400

        if not raw_path.is_file():
            return jsonify({"error": f"Path is not a file: {raw_path_str}"}), 400

        # Validate path is under raw_dir (unless allow_any_path)
        if not app.config["allow_any_path"] and app.config["raw_dir"]:
            try:
                raw_path.resolve().relative_to(Path(app.config["raw_dir"]).resolve())
            except ValueError:
                return jsonify(
                    {"error": f"Path must be under raw_dir: {app.config['raw_dir']}"}
                ), 400

        # Parse optional fields
        transcribe_limit = None
        if transcribe_limit_str:
            try:
                limit = int(transcribe_limit_str)
                transcribe_limit = limit if limit > 0 else None
            except ValueError:
                return jsonify({"error": "transcribe_limit must be an integer"}), 400

        transcribe_max_seconds = None
        if transcribe_max_seconds_str:
            try:
                max_sec = float(transcribe_max_seconds_str)
                transcribe_max_seconds = max_sec if max_sec > 0 else None
            except ValueError:
                return jsonify({"error": "transcribe_max_seconds must be a number"}), 400

        # Parse ASR model (single selection from dropdown)
        asr_model = request.form.get("asr_model", "whisper_local").strip()
        whisper_device = request.form.get("whisper_device", "cpu").strip()

        if asr_model:
            from yanhu.asr_registry import validate_asr_models

            # Validate single model
            is_valid, error_msg = validate_asr_models([asr_model])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            asr_models = [asr_model]
        else:
            # Fallback to whisper_local
            asr_models = ["whisper_local"]
            whisper_device = "cpu"

        # Probe media metadata
        from yanhu.watcher import (
            QueueJob,
            calculate_job_estimates,
            generate_job_id,
            probe_media,
            save_job_to_file,
        )

        media_info = probe_media(raw_path)

        # Create job with generated job_id
        job_preset = app.config["preset"]
        job = QueueJob(
            job_id=generate_job_id(),
            created_at=datetime.now().isoformat(),
            raw_path=str(raw_path.resolve()),
            status="pending",
            suggested_game=game,
            preset=job_preset,
        )

        # Store media info
        job.media = media_info.to_dict()

        # Calculate estimates (with metrics if available)
        metrics_file = Path(app.config["sessions_dir"]).parent / "_metrics.json"
        estimated_segments, estimated_runtime_sec = calculate_job_estimates(
            media_info, segment_strategy="auto", preset=job_preset, metrics_file=metrics_file
        )
        job.estimated_segments = estimated_segments
        job.estimated_runtime_sec = estimated_runtime_sec

        # Store transcribe options in job metadata (custom fields)
        # We'll pass these to process_job via run_config
        if transcribe_limit is not None or transcribe_max_seconds is not None:
            # Store in outputs field temporarily (will be used by worker)
            job.outputs = {
                "transcribe_limit": transcribe_limit,
                "transcribe_max_seconds": transcribe_max_seconds,
            }

        # Store ASR models and Whisper device
        if asr_models is not None:
            job.asr_models = asr_models
        if whisper_device:
            job.whisper_device = whisper_device

        # Save to per-job file
        jobs_dir = Path(app.config["jobs_dir"])
        save_job_to_file(job, jobs_dir)

        # Redirect to home page
        return redirect("/")

    @app.route("/api/jobs", methods=["GET"])
    def list_jobs():
        """List all jobs from jobs directory."""
        if not app.config["jobs_dir"]:
            return jsonify({"jobs": []})

        from yanhu.watcher import list_all_jobs

        jobs = list_all_jobs(Path(app.config["jobs_dir"]))
        return jsonify({"jobs": [job.to_dict() for job in jobs]})

    @app.route("/jobs/<job_id>")
    def job_detail(job_id: str):
        """View job details."""
        if not app.config["jobs_dir"]:
            return "<div class='error'>Jobs not configured</div>", 404

        from yanhu.watcher import get_job_by_id

        job = get_job_by_id(job_id, Path(app.config["jobs_dir"]))
        if not job:
            return f"<div class='error'>Job not found: {job_id}</div>", 404

        # Helper functions for template
        def format_duration(seconds):
            """Format duration in seconds to human-readable string."""
            if seconds < 60:
                return f"{int(seconds)}s"
            elif seconds < 3600:
                mins = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{mins}m {secs}s"
            else:
                hours = int(seconds // 3600)
                mins = int((seconds % 3600) // 60)
                return f"{hours}h {mins}m"

        def format_size(bytes_val):
            """Format file size in bytes to human-readable string."""
            if bytes_val < 1024:
                return f"{bytes_val} B"
            elif bytes_val < 1024 * 1024:
                return f"{bytes_val / 1024:.1f} KB"
            elif bytes_val < 1024 * 1024 * 1024:
                return f"{bytes_val / (1024 * 1024):.1f} MB"
            else:
                return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"

        return render_template_string(
            JOB_DETAIL_TEMPLATE,
            job=job,
            title=f"Job {job_id}",
            format_duration=format_duration,
            format_size=format_size,
            ffmpeg_warning=app.config.get("ffmpeg_error"),
            shutdown_token=app.config.get("shutdown_token", ""),
        )

    @app.route("/api/jobs/<job_id>", methods=["GET"])
    def get_job_json(job_id: str):
        """Get job details as JSON."""
        if not app.config["jobs_dir"]:
            return jsonify({"error": "Jobs not configured"}), 404

        from yanhu.watcher import get_job_by_id

        job = get_job_by_id(job_id, Path(app.config["jobs_dir"]))
        if not job:
            return jsonify({"error": f"Job not found: {job_id}"}), 404

        return jsonify(job.to_dict())

    @app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
    def cancel_job_route(job_id: str):
        """Cancel a job."""
        if not app.config["jobs_dir"]:
            return jsonify({"error": "Jobs not configured"}), 404

        from yanhu.watcher import cancel_job

        job = cancel_job(job_id, Path(app.config["jobs_dir"]))
        if not job:
            return jsonify({"error": f"Job not found: {job_id}"}), 404

        # Redirect to job detail page
        return redirect(f"/jobs/{job_id}")

    @app.route("/api/uploads", methods=["POST"])
    def upload_video():
        """Upload a video file and enqueue a job."""
        if not app.config["worker_enabled"]:
            return jsonify({"error": "Worker not enabled"}), 400

        if not app.config["raw_dir"]:
            return jsonify({"error": "Raw directory not configured"}), 400

        # Check ffprobe availability
        if not app.config.get("ffprobe_path"):
            return jsonify(
                {
                    "error": "ffprobe not found. Please install ffmpeg to enable video processing."
                }
            ), 400

        # Check if file was uploaded
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Sanitize and validate filename
        import os
        import re

        original_filename = os.path.basename(file.filename)  # Remove path components

        # Validate extension
        allowed_extensions = {".mp4", ".mov", ".mkv", ".webm"}
        file_ext = Path(original_filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return jsonify(
                {"error": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"}
            ), 400

        # Sanitize filename (remove unsafe characters)
        safe_filename = re.sub(r"[^\w\-_\.]", "_", original_filename)

        # Generate unique filename with timestamp + hash
        from yanhu.watcher import generate_job_id

        job_id_prefix = generate_job_id().replace("job_", "")  # Reuse same format
        unique_filename = f"{job_id_prefix}_{safe_filename}"

        # Save file to raw_dir
        raw_dir = Path(app.config["raw_dir"])
        raw_dir.mkdir(parents=True, exist_ok=True)
        file_path = raw_dir / unique_filename

        # Atomic write: save to temp file first
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            file.save(str(temp_path))
            # Atomic rename
            temp_path.rename(file_path)
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            return jsonify({"error": f"Failed to save file: {e}"}), 500

        # Parse optional fields
        game = request.form.get("game", "").strip() or None
        preset_override = request.form.get("preset", "").strip() or None
        transcribe_limit_str = request.form.get("transcribe_limit", "").strip()
        transcribe_max_seconds_str = request.form.get("transcribe_max_seconds", "").strip()

        # Parse transcribe options
        transcribe_limit = None
        if transcribe_limit_str:
            try:
                limit = int(transcribe_limit_str)
                transcribe_limit = limit if limit > 0 else None
            except ValueError:
                # Clean up uploaded file on error
                file_path.unlink()
                return jsonify({"error": "transcribe_limit must be an integer"}), 400

        transcribe_max_seconds = None
        if transcribe_max_seconds_str:
            try:
                max_sec = float(transcribe_max_seconds_str)
                transcribe_max_seconds = max_sec if max_sec > 0 else None
            except ValueError:
                # Clean up uploaded file on error
                file_path.unlink()
                return jsonify({"error": "transcribe_max_seconds must be a number"}), 400

        # Parse ASR model (single selection from dropdown)
        asr_model = request.form.get("asr_model", "whisper_local").strip()
        whisper_device = request.form.get("whisper_device", "cpu").strip()

        if asr_model:
            from yanhu.asr_registry import validate_asr_models

            # Validate single model
            is_valid, error_msg = validate_asr_models([asr_model])
            if not is_valid:
                # Clean up uploaded file on error
                file_path.unlink()
                return jsonify({"error": error_msg}), 400
            asr_models = [asr_model]
        else:
            # Fallback to whisper_local
            asr_models = ["whisper_local"]
            whisper_device = "cpu"

        # Probe media metadata
        from yanhu.watcher import (
            QueueJob,
            calculate_job_estimates,
            generate_job_id,
            probe_media,
            save_job_to_file,
        )

        media_info = probe_media(file_path)

        # Create job
        job_preset = preset_override or app.config["preset"]
        job = QueueJob(
            job_id=generate_job_id(),
            created_at=datetime.now().isoformat(),
            raw_path=str(file_path.resolve()),
            status="pending",
            suggested_game=game,
            preset=job_preset,
        )

        # Store media info
        job.media = media_info.to_dict()

        # Calculate estimates (with metrics if available)
        metrics_file = Path(app.config["sessions_dir"]).parent / "_metrics.json"
        estimated_segments, estimated_runtime_sec = calculate_job_estimates(
            media_info, segment_strategy="auto", preset=job_preset, metrics_file=metrics_file
        )
        job.estimated_segments = estimated_segments
        job.estimated_runtime_sec = estimated_runtime_sec

        # Store transcribe options
        if transcribe_limit is not None or transcribe_max_seconds is not None:
            job.outputs = {
                "transcribe_limit": transcribe_limit,
                "transcribe_max_seconds": transcribe_max_seconds,
            }

        # Store ASR models and Whisper device
        if asr_models is not None:
            job.asr_models = asr_models
        if whisper_device:
            job.whisper_device = whisper_device

        # Save job
        jobs_dir = Path(app.config["jobs_dir"])
        save_job_to_file(job, jobs_dir)

        # Redirect to job detail page
        return redirect(f"/jobs/{job.job_id}")

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown_server():
        """Shutdown the server (local requests only, requires token).

        Reliably terminates the process and releases the port by:
        1. Returning 200 OK immediately
        2. Attempting werkzeug shutdown if available
        3. Using os._exit(0) as final fallback after 300ms delay

        This works in both dev server and packaged PyInstaller environments.
        """
        # Check if request is from localhost (best-effort)
        remote_addr = request.remote_addr
        if remote_addr not in ("127.0.0.1", "localhost", "::1"):
            return jsonify({"error": "Shutdown only allowed from localhost"}), 403

        # Verify shutdown token
        provided_token = request.form.get("token", "")
        expected_token = app.config.get("shutdown_token", "")

        if not expected_token or provided_token != expected_token:
            return jsonify({"error": "Invalid shutdown token"}), 403

        # Schedule robust shutdown
        import os
        from threading import Timer

        # Capture werkzeug shutdown function from request context
        # (must be done here, inside the request context)
        werkzeug_shutdown = request.environ.get("werkzeug.server.shutdown")

        def terminate():
            """Terminate the process reliably."""
            # Try werkzeug shutdown first (dev server)
            if werkzeug_shutdown is not None:
                try:
                    werkzeug_shutdown()
                except Exception:
                    pass

            # Final fallback: force exit
            # os._exit(0) bypasses cleanup and threads, terminates immediately
            os._exit(0)

        # Schedule termination after 300ms to allow response to be sent
        Timer(0.3, terminate).start()

        return jsonify({"ok": True}), 200

    @app.route("/settings")
    def settings_page():
        """Settings page for API key management."""
        return render_template_string(
            SETTINGS_TEMPLATE,
            title="Settings",
            shutdown_token=app.config.get("shutdown_token", ""),
        )

    @app.route("/api/settings/keys", methods=["GET"])
    def get_api_keys():
        """Get API key status (masked values only).

        Returns JSON with masked key status for supported API keys.
        Never returns full key values.
        """
        from yanhu.keystore import SUPPORTED_KEYS, get_default_keystore, get_key_status

        keystore = get_default_keystore()
        backend = keystore.get_backend_name()

        keys_status = {}
        for key_name in SUPPORTED_KEYS:
            key_value = keystore.get_key(key_name)
            keys_status[key_name] = get_key_status(key_value)
            keys_status[key_name]["source"] = backend

        return jsonify(
            {
                "keys": keys_status,
                "backend": backend,
            }
        )

    @app.route("/api/settings/keys", methods=["POST"])
    def update_api_keys():
        """Update or clear API keys (local requests only, requires token).

        Accepts JSON:
        {
            "key_name": "ANTHROPIC_API_KEY",
            "key_value": "sk-ant-..." or null to clear
        }

        Returns masked status after save.
        """
        # Check if request is from localhost
        remote_addr = request.remote_addr
        if remote_addr not in ("127.0.0.1", "localhost", "::1"):
            return jsonify({"error": "Settings only allowed from localhost"}), 403

        # Verify token (use shutdown token for now)
        provided_token = request.json.get("token", "") if request.json else ""
        expected_token = app.config.get("shutdown_token", "")

        if not expected_token or provided_token != expected_token:
            return jsonify({"error": "Invalid token"}), 403

        # Get key name and value
        if not request.json:
            return jsonify({"error": "JSON body required"}), 400

        key_name = request.json.get("key_name")
        key_value = request.json.get("key_value")

        from yanhu.keystore import SUPPORTED_KEYS, get_default_keystore, get_key_status

        if key_name not in SUPPORTED_KEYS:
            return jsonify({"error": f"Unsupported key: {key_name}"}), 400

        keystore = get_default_keystore()

        try:
            if key_value is None or key_value == "":
                # Clear key
                keystore.delete_key(key_name)
            else:
                # Set key
                keystore.set_key(key_name, key_value)

            # Return masked status (never full key)
            updated_value = keystore.get_key(key_name)
            status = get_key_status(updated_value)
            status["source"] = keystore.get_backend_name()

            return jsonify(
                {
                    "ok": True,
                    "key_name": key_name,
                    "status": status,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle file too large error."""
        max_size_mb = app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
        return jsonify({"error": f"File too large. Maximum size: {max_size_mb:.0f}MB"}), 413

    return app


class BackgroundWorker:
    """Background worker for processing jobs."""

    def __init__(
        self,
        jobs_dir: Path,
        output_dir: Path,
        preset: str = "fast",
        poll_interval: float = 2.0,
    ):
        """Initialize worker.

        Args:
            jobs_dir: Path to jobs directory
            output_dir: Path to output directory for sessions
            preset: Processing preset (fast or quality)
            poll_interval: Seconds between queue polls
        """
        self.jobs_dir = jobs_dir
        self.output_dir = output_dir
        self.preset = preset
        self.poll_interval = poll_interval
        self.running = False
        self.thread = None
        self.current_job_id = None  # Track current job for cancellation

    def start(self):
        """Start the background worker thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the background worker thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _update_metrics(self, job, result):
        """Update throughput metrics after successful job completion.

        Args:
            job: Completed QueueJob
            result: JobResult with transcribe stats
        """
        try:
            # Get transcribe stats from result
            transcribe_processed = result.outputs.get("transcribe_processed", 0)

            if transcribe_processed < 1:
                return  # No valid data to update metrics

            # Get segment duration from manifest or run_config
            # We need to check the actual session for this
            session_dir = self.output_dir / result.session_id
            manifest_file = session_dir / "manifest.json"

            if not manifest_file.exists():
                return

            import json

            with open(manifest_file, encoding="utf-8") as f:
                manifest = json.load(f)

            segment_duration = manifest.get("segment_duration_seconds", 15)

            # Load progress.json to get elapsed time
            progress_file = session_dir / "outputs" / "progress.json"
            if not progress_file.exists():
                return

            with open(progress_file, encoding="utf-8") as f:
                progress = json.load(f)

            if progress.get("stage") != "done":
                return

            elapsed_sec = progress.get("elapsed_sec", 0)
            if elapsed_sec <= 0:
                return

            # Compute observed rate
            observed_rate = transcribe_processed / elapsed_sec

            # Update metrics
            from yanhu.metrics import MetricsStore

            metrics_file = self.output_dir.parent / "_metrics.json"
            store = MetricsStore(metrics_file)
            store.update_metrics(
                preset=job.preset or self.preset,
                segment_duration=segment_duration,
                observed_rate=observed_rate,
            )

        except Exception:
            # Don't fail the job if metrics update fails
            pass

    def _worker_loop(self):
        """Main worker loop."""
        from yanhu.watcher import get_job_by_id, get_pending_jobs_v2, process_job, update_job_by_id

        while self.running:
            # Get pending jobs
            pending = get_pending_jobs_v2(self.jobs_dir)
            if pending:
                # Process one job at a time
                job = pending[0]

                # Skip if job was cancelled while pending
                if job.status == "cancelled":
                    continue

                # Update status to processing
                self.current_job_id = job.job_id
                update_job_by_id(job.job_id, self.jobs_dir, status="processing")

                # Extract transcribe options from job if present
                transcribe_limit = None
                transcribe_max_seconds = None
                if job.outputs:
                    transcribe_limit = job.outputs.get("transcribe_limit")
                    transcribe_max_seconds = job.outputs.get("transcribe_max_seconds")

                # Build run config
                from yanhu.watcher import get_preset_config

                # Use job's preset if specified, otherwise use worker default
                job_preset = job.preset or self.preset
                run_config = get_preset_config(job_preset)
                run_config["preset"] = job_preset
                run_config["source_mode"] = "link"
                if transcribe_limit is not None:
                    run_config["transcribe_limit"] = transcribe_limit
                if transcribe_max_seconds is not None:
                    run_config["transcribe_max_seconds"] = transcribe_max_seconds

                # Apply whisper device settings from job
                if job.whisper_device:
                    run_config["whisper_device"] = job.whisper_device
                    # Set compute_type based on device
                    if job.whisper_device == "cuda":
                        run_config["transcribe_compute"] = "float16"
                    else:  # cpu
                        run_config["transcribe_compute"] = "int8"

                # Check for cancellation before starting
                current_job = get_job_by_id(job.job_id, self.jobs_dir)
                if current_job and current_job.status == "cancel_requested":
                    # Cancel immediately
                    update_job_by_id(job.job_id, self.jobs_dir, status="cancelled")
                    self.current_job_id = None
                    continue

                # Process job
                result = process_job(
                    job,
                    self.output_dir,
                    force=False,
                    source_mode="link",
                    run_config=run_config,
                )

                # Check for cancellation after processing
                current_job = get_job_by_id(job.job_id, self.jobs_dir)
                if current_job and current_job.status == "cancel_requested":
                    # Mark as cancelled (best-effort, job completed but user cancelled)
                    update_job_by_id(job.job_id, self.jobs_dir, status="cancelled")
                    self.current_job_id = None
                    continue

                # Update status based on result
                if result.success:
                    update_job_by_id(
                        job.job_id,
                        self.jobs_dir,
                        status="done",
                        session_id=result.session_id,
                        outputs=result.outputs,
                    )

                    # Update metrics if we have transcribe stats
                    if result.outputs and "transcribe_processed" in result.outputs:
                        self._update_metrics(job, result)
                else:
                    update_job_by_id(
                        job.job_id,
                        self.jobs_dir,
                        status="failed",
                        error=result.error,
                    )

                self.current_job_id = None

            # Sleep before next poll
            time.sleep(self.poll_interval)


def run_app(
    sessions_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8787,
    raw_dir: Path | None = None,
    worker_enabled: bool = False,
    allow_any_path: bool = False,
    preset: str = "fast",
    max_upload_size: int = 5 * 1024 * 1024 * 1024,  # 5GB default
    debug: bool | None = None,
):
    """Run the Flask development server with optional background worker.

    Args:
        sessions_dir: Path to directory containing session folders
        host: Host to bind to (default: 127.0.0.1)
        port: Port to bind to (default: 8787)
        raw_dir: Path to raw video directory (for job submission and uploads)
        worker_enabled: Enable background worker for job processing
        allow_any_path: Allow any raw_path (skip raw_dir validation)
        preset: Processing preset for worker (fast or quality)
        max_upload_size: Maximum upload file size in bytes (default: 5GB)
        debug: Enable Flask debug mode (default: False)
    """
    app = create_app(
        sessions_dir,
        raw_dir=raw_dir,
        worker_enabled=worker_enabled,
        allow_any_path=allow_any_path,
        preset=preset,
        max_upload_size=max_upload_size,
    )

    # Start background worker if enabled
    worker = None
    if worker_enabled:
        queue_dir = sessions_dir.parent / "_queue" if sessions_dir else Path("_queue")
        jobs_dir = queue_dir / "jobs"
        worker = BackgroundWorker(
            jobs_dir=jobs_dir,
            output_dir=sessions_dir,
            preset=preset,
        )
        worker.start()
        print(f"Background worker started (preset: {preset})")

    print(f"Starting Yanhu web app at http://{host}:{port}")
    print(f"Sessions directory: {sessions_dir.resolve()}")
    if raw_dir:
        print(f"Raw directory: {raw_dir.resolve()}")
    if worker_enabled:
        print("Job submission: enabled")
    print("Press Ctrl+C to stop")

    try:
        debug_mode = debug if debug is not None else False
        app.run(host=host, port=port, debug=debug_mode, use_reloader=False)
    finally:
        if worker:
            print("\nStopping background worker...")
            worker.stop()
