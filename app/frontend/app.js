/* ═══════════════════════════════════════════════════════════════
   CLOUD GOD PLATFORM — Frontend Application Logic
   ═══════════════════════════════════════════════════════════════ */

const API = '';
let accessToken = localStorage.getItem('cg_access') || '';
let refreshToken = localStorage.getItem('cg_refresh') || '';
let currentUser = null;
let searchCount = 0;
let chatCount = 0;

/* ── API Helper ───────────────────────────────────────────── */
async function api(path, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

    const resp = await fetch(`${API}${path}`, { ...opts, headers });

    if (resp.status === 401 && refreshToken) {
        const refreshed = await tryRefresh();
        if (refreshed) {
            headers['Authorization'] = `Bearer ${accessToken}`;
            return fetch(`${API}${path}`, { ...opts, headers });
        } else {
            handleLogout();
            throw new Error('Session expired');
        }
    }
    return resp;
}

async function tryRefresh() {
    try {
        const resp = await fetch(`${API}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (resp.ok) {
            const data = await resp.json();
            accessToken = data.access_token;
            refreshToken = data.refresh_token;
            localStorage.setItem('cg_access', accessToken);
            localStorage.setItem('cg_refresh', refreshToken);
            return true;
        }
    } catch (e) { /* ignore */ }
    return false;
}

/* ── Toast Notifications ──────────────────────────────────── */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/* ═══════════════════════════════════════════════════════════════
   AUTH
   ═══════════════════════════════════════════════════════════════ */

function switchAuthTab(tab) {
    document.getElementById('tab-login').classList.toggle('active', tab === 'login');
    document.getElementById('tab-register').classList.toggle('active', tab === 'register');
    document.getElementById('login-form').style.display = tab === 'login' ? 'block' : 'none';
    document.getElementById('register-form').style.display = tab === 'register' ? 'block' : 'none';
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    btn.innerHTML = '<span class="spinner"></span> Signing in...';
    btn.disabled = true;
    try {
        const resp = await fetch(`${API}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: document.getElementById('login-email').value,
                password: document.getElementById('login-password').value,
            })
        });
        if (resp.ok) {
            const data = await resp.json();
            setTokens(data);
            showToast('Welcome back!', 'success');
            await enterApp();
        } else {
            const err = await resp.json();
            showToast(err.detail || 'Login failed', 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }
    btn.innerHTML = '<span>Sign In</span>';
    btn.disabled = false;
}

async function handleRegister(e) {
    e.preventDefault();
    const btn = document.getElementById('register-btn');
    btn.innerHTML = '<span class="spinner"></span> Creating account...';
    btn.disabled = true;
    try {
        const resp = await fetch(`${API}/api/v1/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: document.getElementById('reg-email').value,
                password: document.getElementById('reg-password').value,
                full_name: document.getElementById('reg-name').value,
            })
        });
        if (resp.ok) {
            const data = await resp.json();
            setTokens(data);
            showToast('Account created! Welcome to Cloud God.', 'success');
            await enterApp();
        } else {
            const err = await resp.json();
            showToast(err.detail || err.errors?.join(', ') || 'Registration failed', 'error');
        }
    } catch (e) {
        showToast('Network error', 'error');
    }
    btn.innerHTML = '<span>Create Account</span>';
    btn.disabled = false;
}

function setTokens(data) {
    accessToken = data.access_token;
    refreshToken = data.refresh_token;
    localStorage.setItem('cg_access', accessToken);
    localStorage.setItem('cg_refresh', refreshToken);
}

function handleLogout() {
    accessToken = '';
    refreshToken = '';
    currentUser = null;
    localStorage.removeItem('cg_access');
    localStorage.removeItem('cg_refresh');
    document.getElementById('auth-screen').style.display = 'flex';
    document.getElementById('app-layout').classList.remove('active');
    showToast('Signed out', 'info');
}

async function enterApp() {
    try {
        const resp = await api('/api/v1/auth/me');
        if (resp.ok) {
            currentUser = await resp.json();
            document.getElementById('user-display-name').textContent = currentUser.full_name || currentUser.email;
            document.getElementById('user-avatar').textContent = (currentUser.full_name || currentUser.email).charAt(0).toUpperCase();
        }
    } catch (e) { /* continue without user details */ }
    document.getElementById('auth-screen').style.display = 'none';
    document.getElementById('app-layout').classList.add('active');
    loadDocuments();
    checkHealth();
    startTelemetryPolling();
}

/* ═══════════════════════════════════════════════════════════════
   NAVIGATION
   ═══════════════════════════════════════════════════════════════ */

function switchView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(`view-${viewId}`).classList.add('active');
    document.querySelector(`.nav-item[data-view="${viewId}"]`).classList.add('active');
    if (viewId === 'monitor') {
        fetchLiveMonitorMetrics();
    }
}

/* ═══════════════════════════════════════════════════════════════
   DASHBOARD
   ═══════════════════════════════════════════════════════════════ */

async function checkHealth() {
    try {
        const resp = await fetch(`${API}/ready`);
        const data = await resp.json();
        document.getElementById('stat-status').textContent = data.status === 'ok' ? 'Live' : 'Degraded';
    } catch (e) {
        document.getElementById('stat-status').textContent = 'Offline';
    }
}

/* ═══════════════════════════════════════════════════════════════
   DOCUMENTS
   ═══════════════════════════════════════════════════════════════ */

async function loadDocuments() {
    try {
        const resp = await api('/api/v1/documents?limit=100');
        if (!resp.ok) return;
        const data = await resp.json();
        const docs = data.items || [];
        const total = data.pagination?.total || 0;

        document.getElementById('stat-docs').textContent = total;
        document.getElementById('doc-count-badge').textContent = total;
        document.getElementById('doc-total-label').textContent = `${total} document${total !== 1 ? 's' : ''}`;

        const renderDocs = (containerId, items) => {
            const el = document.getElementById(containerId);
            if (items.length === 0) {
                el.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><h3>No documents yet</h3><p>Upload or seed your first document.</p></div>`;
                return;
            }
            el.innerHTML = items.map(d => `
                <div class="doc-item" style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:1rem; min-width:0; flex:1;">
                        <div class="doc-icon">📄</div>
                        <div class="doc-info" style="min-width:0; flex:1;">
                            <div class="doc-name" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escHtml(d.filename)}</div>
                            <div class="doc-meta">ID: ${d.id} · Tenant: ${d.tenant_id}</div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:0.5rem; flex-shrink:0;">
                        <button class="btn btn-ghost btn-sm" onclick="openPreviewModal(${d.id}, '${escHtml(d.filename)}', '${d.status}')" style="padding: 4px 10px; font-size: 0.75rem; display:inline-flex; align-items:center; gap:3px;">👁️ Preview</button>
                        <button class="btn btn-ghost btn-sm" onclick="deleteDocument(${d.id}, '${escHtml(d.filename)}')" style="padding: 4px 8px; font-size: 0.75rem; display:inline-flex; align-items:center; color:var(--accent-danger); border-color:transparent;" title="Delete Document">🗑️</button>
                        <span class="doc-status ${d.status}">${d.status}</span>
                    </div>
                </div>
            `).join('');
        };
        renderDocs('doc-list', docs);
        renderDocs('recent-docs', docs.slice(0, 5));
    } catch (e) { /* ignore */ }
}

async function deleteDocument(docId, filename) {
    if (!confirm(`Are you sure you want to permanently delete "${filename}"? This will delete all associated chunks and vectors.`)) {
        return;
    }
    showToast(`Deleting ${filename}...`, 'info');
    try {
        const resp = await api(`/api/v1/documents/${docId}`, {
            method: 'DELETE'
        });
        if (resp.status === 204 || resp.ok) {
            showToast(`Document "${filename}" deleted successfully.`, 'success');
            loadDocuments();
        } else {
            const err = await resp.json();
            showToast(err.detail || 'Delete failed', 'error');
        }
    } catch (e) {
        showToast('Delete request failed.', 'error');
    }
}

async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    form.append('tenant_id', 'default');

    showToast(`Uploading ${file.name}...`, 'info');
    try {
        const resp = await fetch(`${API}/api/v1/documents/upload`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${accessToken}` },
            body: form
        });
        if (resp.ok) {
            showToast(`${file.name} uploaded successfully!`, 'success');
            loadDocuments();
        } else {
            const err = await resp.json();
            showToast(err.detail || 'Upload failed', 'error');
        }
    } catch (e) {
        showToast('Upload failed — is LocalStack running?', 'error');
    }
    e.target.value = '';
}

// Drag & drop
const uploadZone = document.getElementById('upload-zone');
if (uploadZone) {
    ['dragenter', 'dragover'].forEach(evt =>
        uploadZone.addEventListener(evt, e => { e.preventDefault(); uploadZone.classList.add('dragover'); }));
    ['dragleave', 'drop'].forEach(evt =>
        uploadZone.addEventListener(evt, e => { e.preventDefault(); uploadZone.classList.remove('dragover'); }));
    uploadZone.addEventListener('drop', e => {
        const file = e.dataTransfer?.files[0];
        if (file) {
            const dt = new DataTransfer();
            dt.items.add(file);
            document.getElementById('file-input').files = dt.files;
            handleFileUpload({ target: { files: [file], value: '' } });
        }
    });
}

/* ═══════════════════════════════════════════════════════════════
   SEED MODAL
   ═══════════════════════════════════════════════════════════════ */

function openSeedModal() { document.getElementById('seed-modal').classList.add('active'); }
function closeSeedModal() { document.getElementById('seed-modal').classList.remove('active'); }

async function handleSeedDocument() {
    const text = document.getElementById('seed-text').value.trim();
    if (!text) { showToast('Please enter some text', 'error'); return; }

    let docId = parseInt(document.getElementById('seed-doc-id').value) || 0;

    // Auto-create a document if docId is 0
    if (docId === 0) {
        try {
            const blob = new Blob([text], { type: 'text/plain' });
            const form = new FormData();
            form.append('file', blob, `seeded_${Date.now()}.txt`);
            form.append('tenant_id', 'default');
            const upResp = await fetch(`${API}/api/v1/documents/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${accessToken}` },
                body: form
            });
            if (upResp.ok) {
                const upData = await upResp.json();
                docId = upData.id;
            } else {
                showToast('Failed to create document record', 'error');
                return;
            }
        } catch (e) {
            showToast('Failed to create document — is the server running?', 'error');
            return;
        }
    }

    try {
        const resp = await api('/api/v1/documents/seed', {
            method: 'POST',
            body: JSON.stringify({ document_id: docId, tenant_id: 'default', text })
        });
        if (resp.ok) {
            const data = await resp.json();
            showToast(`Indexed ${data.chunks_created} chunk(s) for document #${docId}!`, 'success');
            closeSeedModal();
            document.getElementById('seed-text').value = '';
            loadDocuments();
        } else {
            const err = await resp.json();
            showToast(err.detail || 'Seed failed', 'error');
        }
    } catch (e) {
        showToast('Seed failed', 'error');
    }
}

/* ═══════════════════════════════════════════════════════════════
   SEARCH
   ═══════════════════════════════════════════════════════════════ */

async function handleSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;

    const container = document.getElementById('search-results');
    container.innerHTML = '<div style="text-align:center;padding:2rem"><div class="spinner" style="color:var(--accent-primary);width:28px;height:28px;border-width:3px"></div><p style="color:var(--text-muted);margin-top:1rem">Searching...</p></div>';

    try {
        const resp = await api('/api/v1/documents/search', {
            method: 'POST',
            body: JSON.stringify({ query, tenant_id: 'default', top_k: 10 })
        });
        if (resp.ok) {
            const data = await resp.json();
            searchCount++;
            document.getElementById('stat-searches').textContent = searchCount;

            if (data.results.length === 0) {
                container.innerHTML = `<div class="empty-state"><div class="empty-icon">🔍</div><h3>No results found</h3><p>Try a different query or seed more documents.</p></div>`;
                return;
            }
            container.innerHTML = data.results.map(r => `
                <div class="search-result">
                    <div class="search-result-header">
                        <span class="search-result-source">📄 ${escHtml(r.source)}</span>
                        <span class="search-result-score">Score: ${r.score.toFixed(4)}</span>
                    </div>
                    <div class="search-result-text">${escHtml(r.text)}</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Search failed</h3></div>';
        }
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Network error</h3></div>';
    }
}

/* ═══════════════════════════════════════════════════════════════
   RAG CHAT
   ═══════════════════════════════════════════════════════════════ */

let chatHistory = [];

function askSuggestion(text) {
    document.getElementById('chat-input').value = text;
    handleChat();
}

function handleChatKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChat(); }
}

function autoResizeTextarea(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

async function handleChat() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question) return;

    input.value = '';
    input.style.height = 'auto';

    const messagesEl = document.getElementById('chat-messages');

    // Remove welcome screen
    const welcome = messagesEl.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // Add user message
    appendMessage('user', question);

    // Add typing indicator
    const typingId = 'typing-' + Date.now();
    messagesEl.innerHTML += `
        <div class="chat-message assistant" id="${typingId}">
            <div class="msg-avatar">☁️</div>
            <div class="msg-content">
                <div class="typing-dots"><span></span><span></span><span></span></div>
            </div>
        </div>
    `;
    messagesEl.scrollTop = messagesEl.scrollHeight;

    const sendBtn = document.getElementById('chat-send-btn');
    sendBtn.disabled = true;

    try {
        const resp = await fetch(`${API}/api/v1/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({ question, tenant_id: 'default', top_k: 5 })
        });

        // Remove typing indicator immediately
        document.getElementById(typingId)?.remove();

        if (!resp.ok) {
            appendMessage('assistant', 'Sorry, something went wrong. Please try again.');
            sendBtn.disabled = false;
            return;
        }

        chatCount++;
        document.getElementById('stat-chats').textContent = chatCount;

        // Set up container for streaming
        const avatar = '☁️';
        const msgEl = document.createElement('div');
        msgEl.className = 'chat-message assistant';
        msgEl.innerHTML = `
            <div class="msg-avatar">${avatar}</div>
            <div class="msg-content">
                <div class="stream-text" style="white-space: pre-wrap;"></div>
                <div class="msg-sources" style="display:none; flex-wrap:wrap; gap:0.5rem; margin-top:0.75rem; padding-top:0.75rem; border-top:1px solid var(--border-glass);"></div>
            </div>
        `;
        messagesEl.appendChild(msgEl);
        messagesEl.scrollTop = messagesEl.scrollHeight;

        const streamTextEl = msgEl.querySelector('.stream-text');
        const sourcesEl = msgEl.querySelector('.msg-sources');

        // Read stream chunks
        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let fullText = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // keep last incomplete line

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('data: ')) {
                    const dataStr = trimmed.substring(6).trim();
                    try {
                        const parsed = JSON.parse(dataStr);
                        if (parsed.type === 'token') {
                            fullText += parsed.token;
                            
                            // Smart auto-scroll: only scroll if the user was already near the bottom
                            const isAtBottom = (messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight) < 100;
                            
                            streamTextEl.innerHTML = formatMarkdownSimple(fullText);
                            
                            if (isAtBottom) {
                                messagesEl.scrollTop = messagesEl.scrollHeight;
                            }
                        } else if (parsed.type === 'sources') {
                            if (parsed.sources && parsed.sources.length > 0) {
                                sourcesEl.innerHTML = parsed.sources.map(s => `<span class="source-tag">📄 ${escHtml(s)}</span>`).join('');
                                sourcesEl.style.display = 'flex';
                            }
                        } else if (parsed.type === 'done') {
                            break;
                        }
                    } catch (e) { /* ignore chunk JSON parsing errors */ }
                }
            }
        }

    } catch (e) {
        document.getElementById(typingId)?.remove();
        appendMessage('assistant', 'Network error. Please check if the server is running.');
    }
    sendBtn.disabled = false;
}

function appendMessage(role, content, sources) {
    const messagesEl = document.getElementById('chat-messages');
    const avatar = role === 'user'
        ? (currentUser?.full_name?.charAt(0) || '👤')
        : '☁️';

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = `<div class="msg-sources" style="display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:0.75rem; padding-top:0.75rem; border-top:1px solid var(--border-glass);">${sources.map(s => `<span class="source-tag">📄 ${escHtml(s)}</span>`).join('')}</div>`;
    }

    const msgContentHtml = role === 'user' ? escHtml(content) : formatMarkdownSimple(content);

    const msgEl = document.createElement('div');
    msgEl.className = `chat-message ${role}`;
    msgEl.innerHTML = `
        <div class="msg-avatar">${avatar}</div>
        <div class="msg-content">
            <div style="white-space: pre-wrap;">${msgContentHtml}</div>
            ${sourcesHtml}
        </div>
    `;
    messagesEl.appendChild(msgEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function formatMarkdownSimple(text) {
    let html = escHtml(text);
    
    // Replace multiline code blocks (do this first to prevent formatting inside code blocks)
    html = html.replace(/```([a-zA-Z0-9-+]+)?\n([\s\S]*?)\n?```/g, (match, lang, code) => {
        const displayLang = lang ? lang.toUpperCase() : 'CODE';
        return `
            <div style="margin: 0.75rem 0; border: 1px solid var(--border-glass); border-radius: var(--radius-md); overflow: hidden; background: rgba(10, 14, 26, 0.4);">
                <div style="background: rgba(255, 255, 255, 0.03); border-bottom: 1px solid var(--border-glass); padding: 0.375rem 0.75rem; font-size: 0.6875rem; font-family: var(--font-mono); color: var(--text-muted); display: flex; justify-content: space-between; align-items: center;">
                    <span>${displayLang}</span>
                    <span style="cursor: pointer; color: var(--accent-primary-hover);" onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.innerText).then(() => showToast('Copied code block!', 'success'))">Copy</span>
                </div>
                <pre style="margin:0; font-family:var(--font-mono); font-size:0.8125rem; padding:0.75rem; overflow-x:auto; color:var(--accent-success); line-height:1.4;"><code style="color:inherit; white-space:pre;">${code}</code></pre>
            </div>
        `;
    });
    
    // Replace inline code blocks
    html = html.replace(/`([^`]+)`/g, '<code style="font-family:var(--font-mono); font-size:0.85em; background:rgba(255,255,255,0.06); padding:0.125rem 0.25rem; border-radius:var(--radius-sm); border:1px solid var(--border-glass); color:var(--accent-primary-hover);">$1</code>');
    
    // Replace headers
    html = html.replace(/^### (.*?)$/gm, '<h3 style="font-size:1rem; font-weight:600; margin-top:0.75rem; margin-bottom:0.375rem; color:var(--text-primary);">$1</h3>');
    // Replace bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color:var(--text-primary);">$1</strong>');
    // Replace italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Replace blockquotes
    html = html.replace(/^&gt; (.*?)$/gm, '<blockquote style="border-left:3px solid var(--accent-primary); padding-left:0.75rem; color:var(--text-secondary); margin:0.5rem 0; font-style:italic;">$1</blockquote>');
    return html;
}

/* ═══════════════════════════════════════════════════════════════
   SYSTEM MONITOR TELEMETRY
   ═══════════════════════════════════════════════════════════════ */

let monitorInterval = null;

async function fetchLiveMonitorMetrics() {
    // 1. Fetch readiness check
    try {
        const readyResp = await fetch(`${API}/ready`);
        if (readyResp.ok) {
            const data = await readyResp.json();
            const dbStatus = data.checks?.database || 'unavailable';
            const redisStatus = data.checks?.redis || 'unavailable';

            updateStatusBadge('monitor-db-status', 'monitor-db-change', dbStatus);
            updateStatusBadge('monitor-redis-status', 'monitor-redis-change', redisStatus);
        } else {
            updateStatusBadge('monitor-db-status', 'monitor-db-change', 'unknown');
            updateStatusBadge('monitor-redis-status', 'monitor-redis-change', 'unknown');
        }
    } catch (e) {
        updateStatusBadge('monitor-db-status', 'monitor-db-change', 'offline');
        updateStatusBadge('monitor-redis-status', 'monitor-redis-change', 'offline');
    }

    // 2. Fetch Prometheus metrics text
    try {
        const metricsResp = await fetch(`${API}/metrics`);
        if (metricsResp.ok) {
            const rawText = await metricsResp.text();
            document.getElementById('monitor-terminal').textContent = rawText;
            parseAndRenderPrometheusMetrics(rawText);
        } else {
            document.getElementById('monitor-terminal').textContent = 'Error: Failed to load /metrics (' + metricsResp.status + ')';
        }
    } catch (e) {
        document.getElementById('monitor-terminal').textContent = 'Error: Failed to connect to telemetry service';
    }
}

function updateStatusBadge(valId, changeId, status) {
    const valEl = document.getElementById(valId);
    const changeEl = document.getElementById(changeId);
    if (!valEl || !changeEl) return;

    valEl.textContent = status.toUpperCase();
    if (status === 'ok') {
        valEl.style.color = 'var(--accent-success)';
        changeEl.textContent = '● Operational';
        changeEl.style.color = 'var(--accent-success)';
    } else if (status.startsWith('mocked')) {
        valEl.style.color = 'var(--accent-info)';
        changeEl.textContent = '◌ Emulated (Local Dev)';
        changeEl.style.color = 'var(--accent-info)';
    } else if (status === 'unavailable') {
        valEl.style.color = 'var(--accent-danger)';
        changeEl.textContent = '○ Unavailable';
        changeEl.style.color = 'var(--accent-danger)';
    } else {
        valEl.style.color = 'var(--accent-warning)';
        changeEl.textContent = '⚠ Off-line';
        changeEl.style.color = 'var(--accent-warning)';
    }
}

function parseAndRenderPrometheusMetrics(text) {
    const lines = text.split('\n');
    let totalRequests = 0;
    let totalLatencySum = 0;
    let totalLatencyCount = 0;
    const routesMap = {}; // key: endpoint + method + status

    // Regexes for parsing:
    // http_requests_total{endpoint="/health",method="GET",status="200"} 1.0
    // http_request_duration_seconds_sum{endpoint="/health"} 0.005
    // http_request_duration_seconds_count{endpoint="/health"} 1.0
    
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;

        const spaceIdx = trimmed.lastIndexOf(' ');
        if (spaceIdx === -1) continue;

        const metricWithLabels = trimmed.substring(0, spaceIdx);
        const valStr = trimmed.substring(spaceIdx + 1);
        const val = parseFloat(valStr);
        if (isNaN(val)) continue;

        if (metricWithLabels.startsWith('http_requests_total')) {
            totalRequests += val;
            // Extract labels
            const labels = parsePrometheusLabels(metricWithLabels);
            const endpoint = labels.endpoint || '/';
            const method = labels.method || 'GET';
            const status = labels.status || '200';
            const key = `${method} ${endpoint} [${status}]`;
            
            if (!routesMap[key]) {
                routesMap[key] = { endpoint, method, status, count: 0 };
            }
            routesMap[key].count += val;
        } else if (metricWithLabels.startsWith('http_request_duration_seconds_sum')) {
            totalLatencySum += val;
        } else if (metricWithLabels.startsWith('http_request_duration_seconds_count')) {
            totalLatencyCount += val;
        }
    }

    // Update summary UI
    document.getElementById('monitor-api-calls').textContent = totalRequests;
    
    const avgLatencyEl = document.getElementById('monitor-avg-latency');
    if (totalLatencyCount > 0) {
        const avgMs = (totalLatencySum / totalLatencyCount) * 1000;
        avgLatencyEl.textContent = avgMs.toFixed(1) + ' ms';
    } else {
        avgLatencyEl.textContent = '-- ms';
    }

    // Render routes table
    const tableBody = document.getElementById('monitor-routes-body');
    if (!tableBody) return;

    const routesArray = Object.values(routesMap);
    if (routesArray.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="4" style="padding: 2rem; text-align: center; color: var(--text-muted);">No metrics collected yet. Make some requests to populate telemetry!</td></tr>`;
        return;
    }

    // Sort by count descending
    routesArray.sort((a, b) => b.count - a.count);

    tableBody.innerHTML = routesArray.map(r => {
        let statusClass = 'doc-status indexed';
        if (r.status.startsWith('5')) statusClass = 'doc-status queued'; // red equivalent
        else if (r.status.startsWith('4')) statusClass = 'doc-status uploaded'; // orange
        
        return `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.04); transition: background-color 0.2s;">
                <td style="padding: 0.875rem 1.5rem; font-family: var(--font-mono); font-size: 0.8125rem; color: var(--accent-primary-hover);">${escHtml(r.endpoint)}</td>
                <td style="padding: 0.875rem 1.5rem; font-weight:600;">${escHtml(r.method)}</td>
                <td style="padding: 0.875rem 1.5rem;">
                    <span class="${statusClass}" style="padding: 0.125rem 0.5rem; border-radius: var(--radius-sm); font-size: 0.75rem;">${escHtml(r.status)}</span>
                </td>
                <td style="padding: 0.875rem 1.5rem; font-family: var(--font-mono);">${r.count}</td>
            </tr>
        `;
    }).join('');
}

function parsePrometheusLabels(str) {
    const startBracket = str.indexOf('{');
    const endBracket = str.lastIndexOf('}');
    if (startBracket === -1 || endBracket === -1) return {};

    const labelContent = str.substring(startBracket + 1, endBracket);
    const labelPairs = labelContent.split(',');
    const labels = {};

    for (const pair of labelPairs) {
        const eqIdx = pair.indexOf('=');
        if (eqIdx === -1) continue;
        const key = pair.substring(0, eqIdx).trim();
        let val = pair.substring(eqIdx + 1).trim();
        // Strip quotes
        if (val.startsWith('"') && val.endsWith('"')) {
            val = val.substring(1, val.length - 1);
        }
        labels[key] = val;
    }
    return labels;
}

function startTelemetryPolling() {
    if (monitorInterval) clearInterval(monitorInterval);
    monitorInterval = setInterval(() => {
        const activeView = document.querySelector('.view.active');
        if (activeView && activeView.id === 'view-monitor') {
            fetchLiveMonitorMetrics();
        }
    }, 5000);
}

/* ═══════════════════════════════════════════════════════════════
   PREVIEW MODAL DIALOG MANAGEMENT
   ═══════════════════════════════════════════════════════════════ */
let currentPreviewBlobUrl = null;
let currentPreviewTab = 'pipeline';
let currentPreviewData = {
    docId: null,
    filename: '',
    status: '',
    chunks: [],
    rawText: '',
    blob: null,
    metadata: {}
};

async function openPreviewModal(docId, filename, status) {
    const modal = document.getElementById('preview-modal');
    modal.classList.add('active');

    const titleEl = document.getElementById('preview-doc-title');
    titleEl.innerHTML = `📄 Preview: ${escHtml(filename)}`;

    const metaEl = document.getElementById('preview-doc-meta');
    metaEl.innerHTML = `ID: ${docId} · Status: <span class="doc-status ${status}">${status}</span>`;

    // Revoke previous URL to prevent memory leaks
    if (currentPreviewBlobUrl) {
        URL.revokeObjectURL(currentPreviewBlobUrl);
        currentPreviewBlobUrl = null;
    }

    const downloadBtn = document.getElementById('preview-download-btn');
    downloadBtn.style.display = 'none';

    // Show initial loader in viewport
    const contentArea = document.getElementById('preview-content-area');
    contentArea.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; flex:1; min-height:250px; gap:1rem; color:var(--text-muted);">
            <span class="spinner" style="width:36px; height:36px; border-width:3px; color:var(--accent-primary);"></span>
            <span>Fetching document payload and processing state...</span>
        </div>
    `;

    // Reset default preview tab
    currentPreviewTab = 'pipeline';
    document.querySelectorAll('#preview-tabs-container .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    const pipelineTabBtn = document.getElementById('p-tab-pipeline');
    if (pipelineTabBtn) pipelineTabBtn.classList.add('active');

    try {
        // Parallel retrieval of file chunks & raw binary stream
        const [chunksResp, downloadResp] = await Promise.all([
            api(`/api/v1/documents/${docId}/chunks`),
            api(`/api/v1/documents/${docId}/download`)
        ]);

        let chunksData = null;
        let fileBlob = null;
        let rawText = '';

        if (chunksResp.ok) {
            chunksData = await chunksResp.json();
        }

        if (downloadResp.ok) {
            fileBlob = await downloadResp.blob();
            currentPreviewBlobUrl = URL.createObjectURL(fileBlob);

            downloadBtn.href = currentPreviewBlobUrl;
            downloadBtn.download = filename;
            downloadBtn.style.display = 'inline-flex';

            // Decode plain-text content
            const fnLower = filename.toLowerCase();
            if (fnLower.endsWith('.txt') || fnLower.endsWith('.md') || fnLower.endsWith('.json') || fnLower.endsWith('.py') || fnLower.endsWith('.js') || fileBlob.type.startsWith('text/')) {
                try {
                    rawText = await fileBlob.text();
                } catch (e) {
                    rawText = 'Error decoding plain text stream.';
                }
            }
        }

        // Aggregate metadata properties
        const metadata = {
            document_id: docId,
            filename: filename,
            status: status,
            tenant_id: 'default',
            storage_provider: 'S3_LocalFallback',
            bucket_name: 'cloudgod-platform-data',
            object_s3_key: `uploads/default/${docId}_${filename}`,
            content_type: fileBlob ? fileBlob.type : 'text/plain',
            file_size_bytes: fileBlob ? fileBlob.size : 0,
            extracted_chunks_count: chunksData ? (chunksData.total_chunks || chunksData.chunks.length) : 0,
            db_schema: 'sqlite3_main',
            indexed_timestamp: new Date().toISOString()
        };

        // Cache document payload globally
        currentPreviewData = {
            docId,
            filename,
            status,
            chunks: chunksData ? (chunksData.chunks || []) : [],
            rawText,
            blob: fileBlob,
            metadata
        };

        renderActiveTabContent();

    } catch (err) {
        contentArea.innerHTML = `
            <div class="empty-state" style="padding:2rem;">
                <div class="empty-icon">⚠️</div>
                <h3>Failed to load document preview</h3>
                <p style="color:var(--text-muted);font-size:0.875rem;margin-top:0.5rem;">${escHtml(err.message || 'Check database and file connection.')}</p>
            </div>
        `;
    }
}

function closePreviewModal() {
    document.getElementById('preview-modal').classList.remove('active');
    if (currentPreviewBlobUrl) {
        URL.revokeObjectURL(currentPreviewBlobUrl);
        currentPreviewBlobUrl = null;
    }
}

function switchPreviewTab(tabId) {
    currentPreviewTab = tabId;

    // Toggle active state on buttons
    document.querySelectorAll('#preview-tabs-container .btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const activeBtn = document.getElementById(`p-tab-${tabId}`);
    if (activeBtn) activeBtn.classList.add('active');

    renderActiveTabContent();
}

function renderActiveTabContent() {
    const container = document.getElementById('preview-content-area');
    if (!container) return;

    switch (currentPreviewTab) {
        case 'pipeline':
            container.innerHTML = getPipelineHtml();
            break;
        case 'chunks':
            container.innerHTML = getChunksHtml();
            break;
        case 'raw':
            container.innerHTML = getRawHtml();
            break;
        case 'metadata':
            container.innerHTML = getMetadataHtml();
            break;
        default:
            container.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted);">Select a tab to view document details.</div>';
    }
}

function getPipelineHtml() {
    const status = currentPreviewData.status;
    const step1Class = 'flow-step active';
    const step2Class = (status === 'queued' || status === 'indexed') ? 'flow-step active' : 'flow-step';
    const step3Class = (status === 'indexed') ? 'flow-step active' : 'flow-step';
    const step4Class = (status === 'indexed') ? 'flow-step active' : 'flow-step';

    let charCount = 0;
    let wordCount = 0;
    if (currentPreviewData.chunks && currentPreviewData.chunks.length > 0) {
        currentPreviewData.chunks.forEach(c => {
            charCount += c.text.length;
            wordCount += c.text.split(/\s+/).filter(Boolean).length;
        });
    } else if (currentPreviewData.rawText) {
        charCount = currentPreviewData.rawText.length;
        wordCount = currentPreviewData.rawText.split(/\s+/).filter(Boolean).length;
    }
    const tokenEst = Math.round(charCount / 4);
    const avgChunkSize = currentPreviewData.chunks && currentPreviewData.chunks.length > 0
        ? Math.round(charCount / currentPreviewData.chunks.length)
        : 0;

    return `
        <div style="overflow-y:auto; flex:1; padding-right:4px; display:flex; flex-direction:column; gap:1.25rem;">
            <div class="pipeline-flow" style="flex-shrink:0;">
                <div class="${step1Class}">
                    <span class="flow-step-icon">📤</span>
                    <span class="flow-step-name">Document Uploaded</span>
                    <span class="flow-step-desc">Raw file saved to S3 fallback</span>
                </div>
                <div class="flow-arrow">➔</div>
                <div class="${step2Class}">
                    <span class="flow-step-icon">⚙️</span>
                    <span class="flow-step-name">Text Extractor</span>
                    <span class="flow-step-desc">Parsing PDF/Docx/Txt format</span>
                </div>
                <div class="flow-arrow">➔</div>
                <div class="${step3Class}">
                    <span class="flow-step-icon">✂️</span>
                    <span class="flow-step-name">Semantic Splitter</span>
                    <span class="flow-step-desc">Recursive character splitting</span>
                </div>
                <div class="flow-arrow">➔</div>
                <div class="${step4Class}">
                    <span class="flow-step-icon">🗄️</span>
                    <span class="flow-step-name">SQLite Indexed</span>
                    <span class="flow-step-desc">TF-IDF vectors stored for RAG</span>
                </div>
            </div>

            <h3 style="margin-bottom:0.25rem;font-size:0.9375rem;font-weight:600;color:var(--text-primary);flex-shrink:0;">📊 Indexing & Extraction Metrics</h3>
            <div class="preview-stats" style="flex-shrink:0;">
                <div class="preview-stat-card">
                    <div class="preview-stat-val">${currentPreviewData.chunks ? currentPreviewData.chunks.length : 0}</div>
                    <div class="preview-stat-lbl">Total Chunks</div>
                </div>
                <div class="preview-stat-card">
                    <div class="preview-stat-val">${charCount.toLocaleString()}</div>
                    <div class="preview-stat-lbl">Character Count</div>
                </div>
                <div class="preview-stat-card">
                    <div class="preview-stat-val">${wordCount.toLocaleString()}</div>
                    <div class="preview-stat-lbl">Word Count</div>
                </div>
                <div class="preview-stat-card">
                    <div class="preview-stat-val">~${tokenEst.toLocaleString()}</div>
                    <div class="preview-stat-lbl">Estimated Tokens</div>
                </div>
                <div class="preview-stat-card">
                    <div class="preview-stat-val">${avgChunkSize.toLocaleString()}</div>
                    <div class="preview-stat-lbl">Avg Chunk Chars</div>
                </div>
            </div>

            <div style="background:var(--bg-glass); border:1px solid var(--border-glass); border-radius:var(--radius-md); padding:1rem; font-size:0.8125rem; color:var(--text-secondary); line-height:1.6; flex-shrink:0; margin-top:0.25rem;">
                <p><strong>💡 FAANG Pipeline Explanation:</strong> When a file is uploaded, the platform stores its binary stream using AWS S3 API patterns. A background daemon intercepts the event (via local SQS emulation), extracts the raw layout text, and splits it recursively into overlapping context chunks. Finally, these chunks are tokenized and indexed using an optimized SQLite inverted index (TF-IDF schema) for low-latency retrieval.</p>
            </div>
        </div>
    `;
}

function getChunksHtml(filterQuery = '') {
    const chunks = currentPreviewData.chunks || [];

    if (chunks.length === 0) {
        return `
            <div class="empty-state" style="padding: 2rem; flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                <div class="empty-icon">📭</div>
                <h3>No chunks indexed yet</h3>
                <p style="color:var(--text-muted);font-size:0.875rem;margin-top:0.5rem;">This document is still in status: ${currentPreviewData.status}. Add seed text or wait for processing to finish.</p>
            </div>
        `;
    }

    const queryLower = filterQuery.toLowerCase().trim();
    const filteredChunks = queryLower === ''
        ? chunks
        : chunks.filter(c => c.text.toLowerCase().includes(queryLower));

    const highlightText = (text, query) => {
        if (!query) return escHtml(text);
        const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'gi'));
        return parts.map(part =>
            part.toLowerCase() === query.toLowerCase()
                ? `<mark class="chunk-highlight">${escHtml(part)}</mark>`
                : escHtml(part)
        ).join('');
    };

    const cardsHtml = filteredChunks.map(c => `
        <div class="chunk-detail-card">
            <div class="chunk-detail-header">
                <span>📦 Chunk #${c.chunk_index + 1}</span>
                <span>Length: ${c.text.length} chars · Words: ${c.text.split(/\s+/).filter(Boolean).length}</span>
            </div>
            <div class="chunk-detail-body">${highlightText(c.text, queryLower)}</div>
        </div>
    `).join('');

    return `
        <div style="display:flex; flex-direction:column; flex:1; overflow:hidden; min-height:0;">
            <div class="chunk-search-container" style="flex-shrink: 0; margin-bottom:0.75rem;">
                <input type="text" class="chunk-search-input" id="chunk-local-search" placeholder="Search and filter terms inside document chunks..." value="${escHtml(filterQuery)}" oninput="handleChunkLocalSearch(this.value)">
                <button class="btn btn-ghost btn-sm" onclick="handleChunkLocalSearch('')" style="padding:0.375rem 0.75rem;">Clear</button>
            </div>

            <div style="margin-bottom:0.75rem; font-size:0.75rem; color:var(--text-muted); display:flex; justify-content:space-between; flex-shrink:0;">
                <span>Showing ${filteredChunks.length} of ${chunks.length} chunks</span>
                <span>Highlighting match instances</span>
            </div>

            <div class="chunks-list-view" style="overflow-y:auto; flex:1; padding-right:4px; display:flex; flex-direction:column; gap:1rem;">
                ${filteredChunks.length > 0 ? cardsHtml : '<div style="text-align:center; padding:3rem; color:var(--text-muted)">No chunks match your search term.</div>'}
            </div>
        </div>
    `;
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function handleChunkLocalSearch(val) {
    const container = document.getElementById('preview-content-area');
    const chunksTabContent = getChunksHtml(val);
    container.innerHTML = chunksTabContent;

    const input = document.getElementById('chunk-local-search');
    if (input) {
        input.focus();
        input.setSelectionRange(val.length, val.length);
    }
}

function getRawHtml() {
    const blobUrl = currentPreviewBlobUrl;
    const filename = currentPreviewData.filename.toLowerCase();

    if (!blobUrl) {
        return `
            <div class="empty-state" style="padding: 2rem; flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                <div class="empty-icon">📭</div>
                <h3>No raw document binary available</h3>
                <p style="color:var(--text-muted);font-size:0.875rem;margin-top:0.5rem;">Status: ${currentPreviewData.status}. Text chunks might be seeded directly without a file backing.</p>
            </div>
        `;
    }

    let innerContent = "";
    if (filename.endsWith('.pdf')) {
        innerContent = `<iframe src="${blobUrl}" style="width:100%; height:100%; min-height:450px; border:none; background:var(--bg-secondary); border-radius:var(--radius-md);"></iframe>`;
    } else if (filename.endsWith('.png') || filename.endsWith('.jpg') || filename.endsWith('.jpeg') || filename.endsWith('.webp') || filename.endsWith('.gif')) {
        innerContent = `<img src="${blobUrl}" style="max-width:100%; max-height:100%; border-radius:var(--radius-md); box-shadow:var(--shadow-md); border:1px solid var(--border-glass); object-fit:contain;">`;
    } else if (filename.endsWith('.txt') || filename.endsWith('.md') || filename.endsWith('.json') || filename.endsWith('.py') || filename.endsWith('.js')) {
        innerContent = `<pre class="raw-preview-text" style="margin:0; font-family:var(--font-mono); white-space:pre-wrap; overflow-y:auto; height:100%; width:100%;">${escHtml(currentPreviewData.rawText)}</pre>`;
    } else {
        const extension = filename.split('.').pop().toUpperCase();
        innerContent = `
            <div style="display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; height:100%; gap:0.5rem; padding:2rem;">
                <div style="font-size:3.5rem; margin-bottom:0.5rem; opacity:0.8;">📁</div>
                <h3 style="margin-bottom:0.25rem; color:var(--text-primary); font-weight:600;">.${extension} File Preview Unsupported</h3>
                <p style="color:var(--text-muted); max-width:400px; margin-bottom:1.25rem; font-size:0.8125rem; line-height:1.5;">Native browser embedding is not supported for Microsoft Office or binary archive formats. You can download the raw file directly using the button below.</p>
                <a class="btn btn-primary btn-sm" href="${blobUrl}" download="${escHtml(currentPreviewData.filename)}" style="display:inline-flex; width:auto; border-radius:var(--radius-md);">📥 Download Raw file (${extension})</a>
            </div>
        `;
    }

    return `
        <div class="raw-preview-container" style="flex:1; display:flex; flex-direction:column; overflow:hidden; min-height:450px; background:rgba(17, 24, 39, 0.4); border:1px solid var(--border-glass); border-radius:var(--radius-md); padding:1rem; justify-content:center; align-items:center; width:100%;">
            ${innerContent}
        </div>
    `;
}

function getMetadataHtml() {
    const rawJson = JSON.stringify(currentPreviewData.metadata, null, 2);

    const highlightedJson = rawJson.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
        function (match) {
            let cls = 'json-number';
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'json-key';
                } else {
                    cls = 'json-string';
                }
            } else if (/true|false/.test(match)) {
                cls = 'json-boolean';
            } else if (/null/.test(match)) {
                cls = 'json-null';
            }
            return `<span class="${cls}">${match}</span>`;
        }
    );

    return `
        <div style="display:flex; flex-direction:column; flex:1; overflow:hidden; min-height:0;">
            <h3 style="margin-bottom:0.75rem;font-size:0.9375rem;font-weight:600;color:var(--text-primary);flex-shrink:0;">🛡️ PostgreSQL/SQLite Database Metadata Record</h3>
            <div class="json-viewer-container" style="flex:1; overflow-y:auto; font-family:var(--font-mono); font-size:0.8125rem;">
                <code>${highlightedJson}</code>
            </div>
        </div>
    `;
}

/* ═══════════════════════════════════════════════════════════════
   UTILITIES
   ═══════════════════════════════════════════════════════════════ */

function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

/* ── Init on page load ────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', async () => {
    if (accessToken) {
        try {
            const resp = await fetch(`${API}/api/v1/auth/me`, {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            });
            if (resp.ok) {
                await enterApp();
                return;
            }
        } catch (e) { /* token invalid, show login */ }
    }
    // Show login screen
    document.getElementById('auth-screen').style.display = 'flex';
});
