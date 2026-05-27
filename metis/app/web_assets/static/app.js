/* Metis Agent - ChatGPT-level Web UI */

const App = {
  state: {
    sessionId: "",
    ws: null,
    loading: false,
    config: {},
    thinkingEl: null,
    toolCallQueue: {},
    turnCount: 0,
    hitlPending: [],
    hitlWs: null,
    hitlPollInterval: null,
    streamingBubble: null,
    streamingContent: "",
    streamingRafId: null,
    streamingTurn: 0,
  },

  async init() {
    this.setupMarked();
    await this.loadConfig();
    this.bindEvents();
    this.connect();
    this.loadSessions();
    this.initHitl();
  },

  setupMarked() {
    if (typeof marked === "undefined") return;
    marked.setOptions({
      highlight: (code, lang) => {
        if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return code;
      },
      breaks: true,
      gfm: true,
    });
  },

  renderMarkdown(text) {
    if (typeof marked === "undefined") return this.escapeHtml(text);
    try {
      return marked.parse(text);
    } catch {
      return this.escapeHtml(text);
    }
  },

  escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  },

  async loadConfig() {
    try {
      const config = await fetch("/api/config").then(r => r.json());
      this.state.config = config;
      document.title = config.name;
      const icon = config.icon_text || "M";
      document.getElementById("brandIcon").textContent = icon;
      document.getElementById("brandName").textContent = config.name;
      document.getElementById("brandSubtitle").textContent = config.subtitle;
      document.getElementById("emptyIcon").textContent = icon;
      document.getElementById("emptyTitle").textContent = config.name;
      document.getElementById("emptyDescription").textContent = config.description;
      document.getElementById("workspaceLabel").textContent = config.workspace;
      document.getElementById("modelLabel").textContent = config.model;
      document.getElementById("profileLabel").textContent = config.profile;
      document.getElementById("topbarTitle").textContent = config.name;
      if (config.needs_setup) {
        this.showSetup();
      }
    } catch (e) {
      console.error("Failed to load config:", e);
    }
  },

  showSetup() {
    document.getElementById("setupOverlay").style.display = "flex";
    const submitBtn = document.getElementById("setupSubmit");
    const errorEl = document.getElementById("setupError");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Save & Continue";
    }
    if (errorEl) errorEl.classList.remove("show");
    document.getElementById("setupModel").value = this.state.config.model || "";
    document.getElementById("setupBaseUrl").value = this.state.config.base_url || "";
    const apiKeyInput = document.getElementById("setupApiKey");
    apiKeyInput.value = "";
    // API key is required for first-time setup; optional for reconfiguration
    apiKeyInput.required = !!this.state.config.needs_setup;
    const profileSelect = document.getElementById("setupProfile");
    if (profileSelect) profileSelect.value = this.state.config.profile || "small";
    const hitlCheckbox = document.getElementById("setupHitlEnabled");
    if (hitlCheckbox) hitlCheckbox.checked = !!this.state.config.hitl_enabled;
  },

  hideSetup() {
    document.getElementById("setupOverlay").style.display = "none";
  },

  async submitSetup(e) {
    e.preventDefault();
    const model = document.getElementById("setupModel").value.trim();
    const baseUrl = document.getElementById("setupBaseUrl").value.trim();
    const apiKey = document.getElementById("setupApiKey").value.trim();
    const submitBtn = document.getElementById("setupSubmit");
    const errorEl = document.getElementById("setupError");

    if (!model) {
      errorEl.textContent = "Please enter a model.";
      errorEl.classList.add("show");
      return;
    }

    // API key is required for first-time setup; optional for reconfiguration
    const isFirstSetup = this.state.config.needs_setup;
    if (isFirstSetup && !apiKey) {
      errorEl.textContent = "API key is required.";
      errorEl.classList.add("show");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Saving...";
    errorEl.classList.remove("show");

    const profile = document.getElementById("setupProfile")?.value || "small";
    const hitlEnabled = document.getElementById("setupHitlEnabled")?.checked || false;
    const payload = { model, base_url: baseUrl, profile, hitl_enabled: hitlEnabled };
    if (apiKey) {
      payload.api_key = apiKey;
    } else {
      payload.preserve_key = true;
    }

    try {
      const response = await fetch("/api/v1/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || result.error?.message || "Setup failed");
      }
      this.hideSetup();
      this.showHitlToast("Configuration saved successfully", "success");
      await this.loadConfig();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.classList.add("show");
      submitBtn.disabled = false;
      submitBtn.textContent = "Save & Continue";
    }
  },

  bindEvents() {
    const input = document.getElementById("messageInput");
    const send = document.getElementById("sendButton");
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 180) + "px";
      send.disabled = !input.value.trim() || this.state.loading;
    });
    input.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.send(); }
    });
    send.addEventListener("click", () => this.send());
    document.getElementById("newChat").addEventListener("click", () => this.newChat());
    document.getElementById("sidebarToggle").addEventListener("click", () => {
      document.getElementById("sidebar").classList.toggle("open");
    });
    const setupForm = document.getElementById("setupForm");
    if (setupForm) {
      setupForm.addEventListener("submit", e => this.submitSetup(e));
    }
    const settingsBtn = document.getElementById("settingsButton");
    if (settingsBtn) {
      settingsBtn.addEventListener("click", () => this.showSetup());
    }

    // HITL events
    const hitlBell = document.getElementById("hitlBell");
    if (hitlBell) {
      hitlBell.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggleHitlPanel();
      });
    }
    const hitlHistoryLink = document.getElementById("hitlHistoryLink");
    if (hitlHistoryLink) {
      hitlHistoryLink.addEventListener("click", () => this.showHitlHistory());
    }
    const hitlHistoryClose = document.getElementById("hitlHistoryClose");
    if (hitlHistoryClose) {
      hitlHistoryClose.addEventListener("click", () => this.hideHitlHistory());
    }
    const hitlHistoryOverlay = document.getElementById("hitlHistoryOverlay");
    if (hitlHistoryOverlay) {
      hitlHistoryOverlay.addEventListener("click", (e) => {
        if (e.target === hitlHistoryOverlay) this.hideHitlHistory();
      });
    }
    document.addEventListener("click", (e) => {
      const panel = document.getElementById("hitlPanel");
      const bell = document.getElementById("hitlBell");
      if (panel && !panel.classList.contains("hidden") && !panel.contains(e.target) && e.target !== bell && !bell.contains(e.target)) {
        panel.classList.add("hidden");
      }
    });
  },

  /* ---- WebSocket ---- */
  connect() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${location.host}/api/chat/stream`);
    ws.onopen = () => this.setStatus("Ready");
    ws.onclose = () => {
      this.setStatus("Reconnecting");
      setTimeout(() => this.connect(), 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = event => this.handleEvent(JSON.parse(event.data));
    this.state.ws = ws;
  },

  handleEvent(data) {
    switch (data.type) {
      case "status":
        this.handleStatus(data);
        break;
      case "tool_start":
        this.showToolCard(data.name, data.arguments);
        break;
      case "tool_end":
        this.updateToolCard(data.name, data.status);
        break;
      case "tool_call":
        // analytics event - update duration
        if (data.name && data.duration_ms) {
          this.appendToolDuration(data.name, data.duration_ms);
        }
        break;
      case "turn":
        this.state.turnCount = data.turn;
        this.removeThinking();
        break;
      case "token":
        this.handleToken(data);
        break;
      case "tool_result":
        // tool_result from final result batch
        break;
      case "error":
        this.removeThinking();
        this.appendMessage("assistant", data.error || data.errors?.join("; ") || "Error");
        this.finishLoading();
        break;
      case "done":
        this.handleDone(data);
        break;
    }
  },

  handleStatus(data) {
    switch (data.status) {
      case "started":
        this.state.turnCount = 0;
        this.showThinking("Thinking");
        break;
      case "thinking":
        this.showThinking("Thinking");
        break;
      case "responding":
        this.removeThinking();
        break;
      case "completed":
        this.removeThinking();
        break;
    }
    this.setStatus(data.status === "thinking" ? "Thinking" : data.status === "started" ? "Running" : "Ready");
  },

  handleDone(data) {
    this.removeThinking();
    this.state.sessionId = data.session_id || this.state.sessionId;

    const content = data.content || "";
    if (this.state.streamingBubble) {
      // Streaming path: finalize with the full content from the server
      this._finalizeStreaming(content || this.state.streamingContent);
    } else if (content) {
      // Non-streaming path: append the complete message
      this.appendMessage("assistant", content);
    } else if (data.status && data.status !== "final") {
      this.appendMessage("assistant", `[${data.status}]`);
    }

    this.finishLoading();
    this.loadSessions();
  },

  handleToken(data) {
    if (!this.state.streamingBubble) {
      this.removeThinking();
      this.state.streamingBubble = this._createStreamingBubble();
      this.state.streamingContent = "";
      this.state.streamingTurn = data.turn || 0;
    }
    this.state.streamingContent += data.content || "";
    this._scheduleRender();
  },

  _createStreamingBubble() {
    const messages = document.getElementById("messages");
    const node = document.createElement("div");
    node.className = "message assistant streaming";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = this.state.config.icon_text || "M";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const cursor = document.createElement("span");
    cursor.className = "streaming-cursor";
    cursor.textContent = "▌";

    bubble.appendChild(cursor);
    node.appendChild(avatar);
    node.appendChild(bubble);
    messages.appendChild(node);
    this.scrollToBottom();
    return { node, bubble, cursor };
  },

  _scheduleRender() {
    if (this.state.streamingRafId) return;
    this.state.streamingRafId = requestAnimationFrame(() => {
      this.state.streamingRafId = null;
      this._renderStreaming();
    });
  },

  _renderStreaming() {
    if (!this.state.streamingBubble) return;
    const { bubble, cursor } = this.state.streamingBubble;
    const raw = this.state.streamingContent;
    // Parse markdown and inject before the cursor
    let html = "";
    try {
      html = this.renderMarkdown(raw);
    } catch {
      html = this.escapeHtml(raw);
    }
    // Replace bubble contents, keeping cursor at the end
    bubble.innerHTML = html;
    bubble.appendChild(cursor);
    this.scrollToBottom();
  },

  _finalizeStreaming(finalContent) {
    if (!this.state.streamingBubble) return;
    const { node, bubble } = this.state.streamingBubble;
    node.classList.remove("streaming");
    const raw = finalContent || this.state.streamingContent;
    let html = "";
    try {
      html = this.renderMarkdown(raw);
    } catch {
      html = this.escapeHtml(raw);
    }
    bubble.innerHTML = html;
    // Apply syntax highlighting to code blocks
    bubble.querySelectorAll("pre code").forEach((block) => {
      if (typeof hljs !== "undefined" && block.className) {
        const lang = block.className.replace("language-", "").replace("hljs", "").trim();
        if (lang && hljs.getLanguage(lang)) {
          hljs.highlightElement(block);
        }
      }
    });
    this.addCodeBlockActions(bubble);
    this.state.streamingBubble = null;
    this.state.streamingContent = "";
    this.state.streamingTurn = 0;
    this.scrollToBottom();
  },

  /* ---- Send ---- */
  send() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();
    if (!message || this.state.loading) return;
    this.clearEmpty();
    this.appendMessage("user", message);
    input.value = "";
    input.style.height = "auto";
    document.getElementById("sendButton").disabled = true;
    this.state.loading = true;
    this.state.toolCards = {};
    this.setStatus("Running");

    if (this.state.ws && this.state.ws.readyState === WebSocket.OPEN) {
      this.showThinking("Thinking");
      this.state.ws.send(JSON.stringify({ message, session_id: this.state.sessionId }));
    } else {
      this.sendHttp(message);
    }
  },

  async sendHttp(message) {
    this.showThinking("Thinking");
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: this.state.sessionId }),
      }).then(r => r.json());
      this.state.sessionId = response.session_id || this.state.sessionId;
      this.removeThinking();
      this.appendMessage("assistant", response.response || (response.status ? `[${response.status}]` : "No response"));
      if (response.errors?.length) {
        for (const err of response.errors) {
          this.showInlineError(err);
        }
      }
      this.loadSessions();
    } catch (error) {
      this.removeThinking();
      this.appendMessage("assistant", error.message);
    } finally {
      this.finishLoading();
    }
  },

  /* ---- Messages ---- */
  appendMessage(role, text) {
    const messages = document.getElementById("messages");
    const node = document.createElement("div");
    node.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "U" : (this.state.config.icon_text || "M");

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    if (role === "assistant") {
      bubble.innerHTML = this.renderMarkdown(text);
    } else {
      bubble.textContent = text;
    }

    node.appendChild(avatar);
    node.appendChild(bubble);
    messages.appendChild(node);
    if (role === "assistant") {
      this.addCodeBlockActions(bubble);
    }
    this.scrollToBottom();
  },

  /* ---- Thinking indicator ---- */
  showThinking(label) {
    this.removeThinking();
    const messages = document.getElementById("messages");
    const el = document.createElement("div");
    el.className = "thinking-indicator";
    el.innerHTML = `
      <div class="avatar">${this.state.config.icon_text || "M"}</div>
      <div class="thinking-dots"><span></span><span></span><span></span></div>
      <span class="thinking-label">${label || "Thinking"}</span>
    `;
    messages.appendChild(el);
    this.state.thinkingEl = el;
    this.scrollToBottom();
  },

  removeThinking() {
    if (this.state.thinkingEl) {
      this.state.thinkingEl.remove();
      this.state.thinkingEl = null;
    }
  },

  addCodeBlockActions(container) {
    container.querySelectorAll("pre").forEach((pre) => {
      if (pre.querySelector(".code-block-actions")) return;
      const code = pre.querySelector("code");
      if (!code) return;
      const actions = document.createElement("div");
      actions.className = "code-block-actions";
      const lang = (code.className || "").replace("language-", "").replace("hljs", "").trim() || "text";
      actions.innerHTML = `
        <span class="code-block-lang">${this.escapeHtml(lang)}</span>
        <button class="code-block-btn" data-action="copy" title="Copy">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="2" y="2" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.5"/><path d="M4 4h8v8H4z" stroke="currentColor" stroke-width="1.5"/></svg>
        </button>
        <button class="code-block-btn" data-action="insert" title="Insert at cursor">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7h10M7 2v10" stroke="currentColor" stroke-width="1.5"/></svg>
        </button>
        <button class="code-block-btn" data-action="newfile" title="New file">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2h6l4 4v8H2V2z" stroke="currentColor" stroke-width="1.5"/><path d="M8 2v4h4" stroke="currentColor" stroke-width="1.5"/></svg>
        </button>
      `;
      actions.querySelector('[data-action="copy"]').addEventListener("click", () => {
        const text = code.textContent || "";
        navigator.clipboard.writeText(text).then(() => this.showHitlToast("Copied", "success")).catch(() => this.showHitlToast("Copy failed", "error"));
      });
      actions.querySelector('[data-action="insert"]').addEventListener("click", () => {
        const input = document.getElementById("messageInput");
        const text = code.textContent || "";
        input.value = input.value + (input.value ? "\n" : "") + text;
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 180) + "px";
        input.focus();
        this.showHitlToast("Inserted", "success");
      });
      actions.querySelector('[data-action="newfile"]').addEventListener("click", () => {
        const text = code.textContent || "";
        const defaultName = lang === "text" ? "untitled.txt" : `untitled.${lang}`;
        const filename = prompt("Save as:", defaultName);
        if (!filename) return;
        const blob = new Blob([text], { type: "text/plain" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
        this.showHitlToast("Saved", "success");
      });
      pre.appendChild(actions);
    });
  },

  /* ---- Tool cards ---- */
  showToolCard(name, args) {
    this.removeThinking();
    const messages = document.getElementById("messages");
    const id = `tool-${name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const card = document.createElement("div");
    card.className = "tool-card running";
    card.id = id;
    card.dataset.toolName = name;
    card.innerHTML = `
      <div class="tool-card-header">
        <div class="tool-card-icon"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v4M6 7v4M1 6h4M7 6h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div>
        <span class="tool-card-name">${this.escapeHtml(name)}</span>
        <span class="tool-card-status">Running</span>
        <span class="tool-card-chevron"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M4 2l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
      </div>
      <div class="tool-card-body">
        <div class="tool-card-body-inner">${args ? this.escapeHtml(typeof args === "string" ? args : JSON.stringify(args, null, 2)) : ""}</div>
      </div>
    `;
    card.querySelector(".tool-card-header").addEventListener("click", () => {
      card.classList.toggle("expanded");
    });
    messages.appendChild(card);
    if (!this.state.toolCallQueue[name]) {
      this.state.toolCallQueue[name] = [];
    }
    this.state.toolCallQueue[name].push(card);
    this.scrollToBottom();
  },

  updateToolCard(name, status) {
    const queue = this.state.toolCallQueue[name];
    if (!queue || !queue.length) return;
    // Update the oldest pending tool call (FIFO)
    const card = queue.shift();
    if (!card) return;
    card.classList.remove("running");
    card.classList.add(status === "ok" ? "ok" : "error");
    const statusEl = card.querySelector(".tool-card-status");
    if (statusEl) statusEl.textContent = status === "ok" ? "Done" : status || "Error";

    const iconEl = card.querySelector(".tool-card-icon");
    if (iconEl && status === "ok") {
      iconEl.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    } else if (iconEl) {
      iconEl.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
    }
  },

  appendToolDuration(name, durationMs) {
    const queue = this.state.toolCallQueue[name];
    if (!queue || !queue.length) return;
    // Prefer a running card; otherwise update the most recently completed one
    for (const card of queue) {
      if (card.classList.contains("running")) {
        const statusEl = card.querySelector(".tool-card-status");
        if (statusEl && durationMs > 0) {
          statusEl.textContent += ` · ${durationMs}ms`;
        }
        return;
      }
    }
    // Fallback: update the last completed card
    const lastCard = queue[queue.length - 1];
    const statusEl = lastCard.querySelector(".tool-card-status");
    if (statusEl && durationMs > 0) {
      const baseText = statusEl.textContent.split(" · ")[0];
      statusEl.textContent = `${baseText} · ${durationMs}ms`;
    }
  },

  /* ---- Inline errors ---- */
  showInlineError(text) {
    const messages = document.getElementById("messages");
    const el = document.createElement("div");
    el.className = "status-line";
    el.innerHTML = `<span style="color:var(--error);">⚠ ${this.escapeHtml(text)}</span>`;
    messages.appendChild(el);
    this.scrollToBottom();
  },

  /* ---- Sessions ---- */
  async loadSessions() {
    try {
      const data = await fetch("/api/sessions").then(r => r.json());
      const list = document.getElementById("sessions");
      list.innerHTML = "";
      for (const session of data.sessions) {
        const item = document.createElement("button");
        item.className = "session" + (session.id === this.state.sessionId ? " active" : "");
        const title = document.createElement("span");
        title.className = "session-title";
        title.textContent = session.title || "Untitled";
        const meta = document.createElement("span");
        meta.className = "session-meta";
        const parts = [];
        if (session.message_count) parts.push(`${session.message_count} msg`);
        if (session.tool_call_count) parts.push(`${session.tool_call_count} tools`);
        meta.textContent = parts.join(" · ") || "Empty";
        item.appendChild(title);
        item.appendChild(meta);
        item.onclick = () => this.loadSession(session.id);
        list.appendChild(item);
      }
    } catch (e) {
      console.error("Failed to load sessions:", e);
    }
  },

  async loadSession(sessionId) {
    try {
      const detail = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`).then(r => r.json());
      this.state.sessionId = sessionId;
      const messages = document.getElementById("messages");
      messages.innerHTML = "";

      for (const msg of detail.messages || []) {
        if (msg.role === "user") {
          this.appendMessage("user", msg.content || "");
        } else if (msg.role === "assistant") {
          const content = msg.content || "";
          if (content) this.appendMessage("assistant", content);
          if (msg.errors?.length) {
            for (const err of msg.errors) this.showInlineError(err);
          }
        }
      }

      for (const tc of detail.tool_calls || []) {
        const name = tc.name || tc.tool_name || "tool";
        const status = tc.status || "unknown";
        this.showToolCard(name, null);
        this.updateToolCard(name, status);
      }

      this.loadSessions();
    } catch (e) {
      console.error("Failed to load session:", e);
    }
  },

  /* ---- Utilities ---- */
  newChat() {
    this.state.sessionId = "";
    this.state.toolCallQueue = {};
    const messages = document.getElementById("messages");
    messages.innerHTML = "";
    this.restoreEmpty();
    this.loadConfig();
  },

  finishLoading() {
    this.state.loading = false;
    this.state.toolCallQueue = {};
    if (this.state.streamingRafId) {
      cancelAnimationFrame(this.state.streamingRafId);
      this.state.streamingRafId = null;
    }
    if (this.state.streamingBubble) {
      this._finalizeStreaming(this.state.streamingContent);
    }
    const input = document.getElementById("messageInput");
    document.getElementById("sendButton").disabled = !input.value.trim();
    this.setStatus("Ready");
    input.focus();
  },

  clearEmpty() {
    const empty = document.getElementById("emptyState");
    if (empty) empty.remove();
  },

  restoreEmpty() {
    const messages = document.getElementById("messages");
    if (!document.getElementById("emptyState")) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.id = "emptyState";
      const icon = this.state.config.icon_text || "M";
      empty.innerHTML = `
        <div class="empty-icon">${icon}</div>
        <h1>${this.state.config.name || "Metis Agent"}</h1>
        <p>${this.state.config.description || "Domain-neutral agent harness"}</p>
      `;
      messages.appendChild(empty);
    }
  },

  setStatus(text) {
    const el = document.getElementById("statusLabel");
    el.textContent = text;
    el.classList.toggle("active", text === "Running" || text === "Thinking");
  },

  scrollToBottom() {
    const messages = document.getElementById("messages");
    requestAnimationFrame(() => {
      messages.scrollTop = messages.scrollHeight;
    });
  },

  /* ---- HITL Approval Panel ---- */
  initHitl() {
    this.loadHitlPending();
    this.connectHitlWs();
    // Poll every 5s as fallback
    this.state.hitlPollInterval = setInterval(() => this.loadHitlPending(), 5000);
  },

  async loadHitlPending() {
    try {
      const res = await fetch("/api/v1/hitl/pending");
      if (!res.ok) return;
      const data = await res.json();
      this.state.hitlPending = data.requests || [];
      this.renderHitlBadge();
      this.renderHitlPanel();
    } catch (e) {
      // silently fail on polling errors
    }
  },

  renderHitlBadge() {
    const badge = document.getElementById("hitlBadge");
    if (!badge) return;
    const count = this.state.hitlPending.length;
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.classList.toggle("show", count > 0);
  },

  renderHitlPanel() {
    const listEl = document.getElementById("hitlPanelList");
    if (!listEl) return;
    if (this.state.hitlPending.length === 0) {
      listEl.innerHTML = `<div class="hitl-empty">No pending approvals</div>`;
      return;
    }
    listEl.innerHTML = this.state.hitlPending.map(req => {
      const riskClass = req.risk_level === "high" ? "risk-high" : req.risk_level === "medium" ? "risk-medium" : "risk-low";
      const args = JSON.stringify(req.arguments || {}, null, 2);
      const argsShort = args.length > 200 ? args.slice(0, 200) + "..." : args;
      return `
        <div class="hitl-item ${riskClass}" data-req-id="${req.request_id}">
          <div class="hitl-item-header">
            <span class="hitl-item-tool">${this.escapeHtml(req.tool_name)}</span>
            <span class="hitl-item-risk risk-${req.risk_level}">${req.risk_level}</span>
          </div>
          <div class="hitl-item-args">${this.escapeHtml(argsShort)}</div>
          <div class="hitl-item-actions">
            <button class="hitl-btn-approve" onclick="App.approveHitl('${req.request_id}')">Approve</button>
            <button class="hitl-btn-deny" onclick="App.denyHitl('${req.request_id}')">Deny</button>
          </div>
        </div>`;
    }).join("");
  },

  toggleHitlPanel() {
    const panel = document.getElementById("hitlPanel");
    if (!panel) return;
    panel.classList.toggle("hidden");
    if (!panel.classList.contains("hidden")) {
      this.loadHitlPending();
    }
  },

  async approveHitl(requestId) {
    try {
      const res = await fetch(`/api/v1/hitl/${requestId}/approve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
      if (res.ok) {
        this.showHitlToast("Approved", "success");
        this.state.hitlPending = this.state.hitlPending.filter(r => r.request_id !== requestId);
        this.renderHitlBadge();
        this.renderHitlPanel();
      } else {
        const err = await res.json();
        this.showHitlToast(err.detail || "Failed to approve", "error");
      }
    } catch (e) {
      this.showHitlToast("Network error", "error");
    }
  },

  async denyHitl(requestId) {
    try {
      const res = await fetch(`/api/v1/hitl/${requestId}/deny`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
      if (res.ok) {
        this.showHitlToast("Denied", "success");
        this.state.hitlPending = this.state.hitlPending.filter(r => r.request_id !== requestId);
        this.renderHitlBadge();
        this.renderHitlPanel();
      } else {
        const err = await res.json();
        this.showHitlToast(err.detail || "Failed to deny", "error");
      }
    } catch (e) {
      this.showHitlToast("Network error", "error");
    }
  },

  async showHitlHistory() {
    const overlay = document.getElementById("hitlHistoryOverlay");
    const listEl = document.getElementById("hitlHistoryList");
    if (!overlay || !listEl) return;
    overlay.classList.remove("hidden");
    listEl.innerHTML = `<div class="hitl-empty">Loading...</div>`;
    try {
      const res = await fetch("/api/v1/hitl/history?limit=50");
      if (!res.ok) throw new Error("Failed to load");
      const data = await res.json();
      const items = data.requests || [];
      if (items.length === 0) {
        listEl.innerHTML = `<div class="hitl-empty">No approval history</div>`;
        return;
      }
      listEl.innerHTML = items.map(req => {
        const statusClass = req.status === "approved" ? "approved" : req.status === "denied" ? "denied" : "timeout";
        const time = req.created_at ? new Date(req.created_at).toLocaleString() : "";
        return `
          <div class="hitl-history-item">
            <div class="hitl-history-meta">
              <span class="hitl-history-tool">${this.escapeHtml(req.tool_name)}</span>
              <span class="hitl-history-time">${this.escapeHtml(time)}</span>
            </div>
            <span class="hitl-history-status ${statusClass}">${req.status}</span>
          </div>`;
      }).join("");
    } catch (e) {
      listEl.innerHTML = `<div class="hitl-empty">Failed to load history</div>`;
    }
  },

  hideHitlHistory() {
    const overlay = document.getElementById("hitlHistoryOverlay");
    if (overlay) overlay.classList.add("hidden");
  },

  connectHitlWs() {
    try {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${location.host}/api/v1/hitl/stream`);
      ws.onopen = () => {
        // Send periodic pings
        this._hitlPingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        }, 30000);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "new_pending") {
            this.loadHitlPending();
          } else if (data.type === "pending_list") {
            this.state.hitlPending = data.requests || [];
            this.renderHitlBadge();
            this.renderHitlPanel();
          }
        } catch (e) {}
      };
      ws.onclose = () => {
        if (this._hitlPingInterval) clearInterval(this._hitlPingInterval);
        setTimeout(() => this.connectHitlWs(), 3000);
      };
      ws.onerror = () => ws.close();
      this.state.hitlWs = ws;
    } catch (e) {}
  },

  showHitlToast(message, type) {
    const existing = document.querySelector(".hitl-toast");
    if (existing) existing.remove();
    const toast = document.createElement("div");
    toast.className = `hitl-toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      setTimeout(() => toast.remove(), 300);
    }, 2500);
  },
};

window.addEventListener("DOMContentLoaded", () => App.init());
