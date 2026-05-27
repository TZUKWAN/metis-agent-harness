/* Metis Swarm Hub */

const API = "/api/v1";

const App = {
  state: {
    agents: [],
    groups: [],
    trash: [],
    selectedId: null,
    selectedType: null,
    ws: null,
    loading: false,
    currentManifest: null,
    streamingBubble: null,
    streamingContent: "",
    streamingRafId: null,
  },

  async init() {
    this.bindEvents();
    await this.refreshAll();
  },

  async refreshAll() {
    await Promise.all([this.loadAgents(), this.loadGroups(), this.loadTrash()]);
  },

  async loadAgents() {
    const res = await fetch(`${API}/agents?status=active`).then(r => r.json());
    this.state.agents = res.agents || [];
    this.renderAgentList();
  },

  async loadGroups() {
    const res = await fetch(`${API}/groups`).then(r => r.json());
    this.state.groups = res.groups || [];
    this.renderGroupList();
  },

  async loadTrash() {
    const res = await fetch(`${API}/agents?status=trashed`).then(r => r.json());
    this.state.trash = res.agents || [];
    this.renderTrashList();
  },

  renderAgentList() {
    const el = document.getElementById("agentList");
    el.innerHTML = this.state.agents.map(a => `
      <div class="agent-item ${this.isSelected(a.id, 'agent') ? 'active' : ''}" data-id="${a.id}"
           onclick="App.selectAgent('${a.id}')">
        <div class="agent-icon">${a.icon || '🤖'}</div>
        <div class="agent-info">
          <div class="agent-name">${this.escapeHtml(a.name)}</div>
          <div class="agent-desc">${this.escapeHtml(a.description || '')}</div>
        </div>
        <div class="agent-actions" onclick="event.stopPropagation()">
          <button onclick="App.editAgent('${a.id}')" title="Edit">✎</button>
          <button class="danger" onclick="App.trashAgent('${a.id}')" title="Delete">🗑</button>
        </div>
      </div>
    `).join('');
  },

  renderGroupList() {
    const el = document.getElementById("groupList");
    el.innerHTML = this.state.groups.map(g => `
      <div class="group-item ${this.isSelected(g.id, 'group') ? 'active' : ''}" data-id="${g.id}"
           onclick="App.selectGroup('${g.id}')">
        <div class="group-icon">👥</div>
        <div class="group-info">
          <div class="group-name">${this.escapeHtml(g.name)}</div>
          <div class="group-desc">${g.mode} · ${g.agent_ids.length} members</div>
        </div>
      </div>
    `).join('');
  },

  renderTrashList() {
    const el = document.getElementById("trashList");
    el.innerHTML = this.state.trash.map(a => `
      <div class="trash-item">
        <div class="agent-icon">${a.icon || '🤖'}</div>
        <div class="agent-info">
          <div class="agent-name">${this.escapeHtml(a.name)}</div>
          <div class="agent-desc">Trashed ${a.trashed_at?.split('T')[0] || ''}</div>
        </div>
        ${!a.restored_once ? `<span class="trash-restore" onclick="App.restoreAgent('${a.id}')">Restore</span>` : ''}
      </div>
    `).join('');
  },

  isSelected(id, type) {
    return this.state.selectedId === id && this.state.selectedType === type;
  },

  // ---- Selection ----

  async selectAgent(id) {
    this.state.selectedId = id;
    this.state.selectedType = 'agent';
    this.renderAgentList();
    this.renderGroupList();

    const agent = this.state.agents.find(a => a.id === id);
    if (!agent) return;

    const detail = await fetch(`${API}/agents/${id}`).then(r => r.json());
    this.state.currentManifest = detail.manifest;

    this.showChat(agent.name, agent.icon || '🤖', `Model: ${detail.manifest?.model || 'unknown'}`);
    this.clearMessages();
  },

  async selectGroup(id) {
    this.state.selectedId = id;
    this.state.selectedType = 'group';
    this.renderAgentList();
    this.renderGroupList();

    const group = this.state.groups.find(g => g.id === id);
    if (!group) return;

    this.showChat(group.name, '👥', `Mode: ${group.mode} · ${group.agent_ids.length} members`);
    this.clearMessages();
  },

  showChat(name, icon, meta) {
    document.getElementById("emptyState").classList.add("hidden");
    document.getElementById("chatArea").classList.remove("hidden");
    document.getElementById("chatHeader").innerHTML = `
      <div class="chat-header-icon">${icon}</div>
      <div class="chat-header-info">
        <div class="chat-header-name">${this.escapeHtml(name)}</div>
        <div class="chat-header-meta">${this.escapeHtml(meta)}</div>
      </div>
      <div class="chat-header-actions">
        <button onclick="App.clearMessages()">Clear</button>
      </div>
    `;
  },

  clearMessages() {
    document.getElementById("messages").innerHTML = '';
  },

  // ---- Chat ----

  async send() {
    const input = document.getElementById("messageInput");
    const text = input.value.trim();
    if (!text || this.state.loading) return;

    this.appendMessage("user", text);
    input.value = "";
    input.style.height = "auto";
    document.getElementById("sendButton").disabled = true;
    this.state.loading = true;

    if (this.state.selectedType === 'agent') {
      await this.sendAgentChat(text);
    } else {
      await this.sendGroupChat(text);
    }

    this.state.loading = false;
    document.getElementById("sendButton").disabled = !document.getElementById("messageInput").value.trim();
  },

  async sendAgentChat(message) {
    this.showThinking();
    try {
      await this._sendAgentChatWs(message);
    } catch (err) {
      // Fallback to HTTP POST if WebSocket fails
      this.removeThinking();
      try {
        const res = await fetch(`${API}/agents/${this.state.selectedId}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        }).then(r => r.json());
        if (res.response) {
          this.appendMessage("assistant", res.response);
        } else if (res.errors?.length) {
          this.appendMessage("assistant", "**Error:** " + res.errors.join("; "));
        } else {
          this.appendMessage("assistant", `[${res.status}]`);
        }
      } catch (httpErr) {
        this.appendMessage("assistant", "Error: " + httpErr.message);
      }
    }
  },

  _sendAgentChatWs(message) {
    return new Promise((resolve, reject) => {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${location.host}${API}/agents/${this.state.selectedId}/stream`);
      let resolved = false;

      ws.onopen = () => {
        ws.send(JSON.stringify({ message }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this._handleWsEvent(data);
          if (data.type === "done") {
            resolved = true;
            resolve();
            ws.close();
          }
        } catch (e) {}
      };

      ws.onerror = () => {
        if (!resolved) reject(new Error("WebSocket error"));
      };

      ws.onclose = () => {
        if (!resolved) reject(new Error("WebSocket closed"));
      };

      // Timeout fallback
      setTimeout(() => {
        if (!resolved) {
          ws.close();
          reject(new Error("WebSocket timeout"));
        }
      }, 120000);
    });
  },

  _handleWsEvent(data) {
    switch (data.type) {
      case "token":
        this._handleToken(data);
        break;
      case "tool_start":
        this.showToolCard(data.name, data.arguments);
        break;
      case "tool_end":
        this.updateToolCard(data.name, data.status);
        break;
      case "turn":
        this.removeThinking();
        break;
      case "done":
        this._finalizeStreaming();
        this.removeThinking();
        if (data.content && !this.state.streamingBubble) {
          this.appendMessage("assistant", data.content);
        } else if (data.errors?.length) {
          this.appendMessage("assistant", "**Error:** " + data.errors.join("; "));
        }
        break;
    }
  },

  _handleToken(data) {
    if (!this.state.streamingBubble) {
      this.removeThinking();
      this.state.streamingBubble = this._createStreamingBubble();
      this.state.streamingContent = "";
    }
    this.state.streamingContent += data.content || "";
    this._scheduleRender();
  },

  _createStreamingBubble() {
    const messages = document.getElementById("messages");
    const node = document.createElement("div");
    node.className = "message assistant streaming";
    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    const agent = this.state.agents.find(a => a.id === this.state.selectedId);
    avatar.textContent = agent ? (agent.icon || '🤖') : '🤖';
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
    let html = "";
    try {
      html = typeof marked !== "undefined" ? marked.parse(raw) : this.escapeHtml(raw);
    } catch {
      html = this.escapeHtml(raw);
    }
    bubble.innerHTML = html;
    bubble.appendChild(cursor);
    this.scrollToBottom();
  },

  _finalizeStreaming() {
    if (!this.state.streamingBubble) return;
    const { node, bubble } = this.state.streamingBubble;
    node.classList.remove("streaming");
    const raw = this.state.streamingContent;
    let html = "";
    try {
      html = typeof marked !== "undefined" ? marked.parse(raw) : this.escapeHtml(raw);
    } catch {
      html = this.escapeHtml(raw);
    }
    bubble.innerHTML = html;
    bubble.querySelectorAll("pre code").forEach((block) => {
      if (typeof hljs !== "undefined" && block.className) {
        const lang = block.className.replace("language-", "").replace("hljs", "").trim();
        if (lang && hljs.getLanguage(lang)) hljs.highlightElement(block);
      }
    });
    this.state.streamingBubble = null;
    this.state.streamingContent = "";
    this.scrollToBottom();
  },

  showToolCard(name, args) {
    this.removeThinking();
    const messages = document.getElementById("messages");
    const id = `tool-${name}-${Date.now()}`;
    const card = document.createElement("div");
    card.className = "tool-card running";
    card.id = id;
    card.innerHTML = `
      <div class="tool-card-header">
        <span class="tool-card-icon">🔧</span>
        <span class="tool-card-name">${this.escapeHtml(name)}</span>
        <span class="tool-card-status">Running</span>
      </div>
      <div class="tool-card-body">${args ? this.escapeHtml(typeof args === "string" ? args : JSON.stringify(args, null, 2)) : ""}</div>
    `;
    messages.appendChild(card);
    this.scrollToBottom();
  },

  updateToolCard(name, status) {
    const cards = document.querySelectorAll(".tool-card.running");
    for (const card of cards) {
      const nameEl = card.querySelector(".tool-card-name");
      if (nameEl && nameEl.textContent === name) {
        card.classList.remove("running");
        card.classList.add(status === "ok" ? "ok" : "error");
        const statusEl = card.querySelector(".tool-card-status");
        if (statusEl) statusEl.textContent = status === "ok" ? "Done" : status || "Error";
        const iconEl = card.querySelector(".tool-card-icon");
        if (iconEl) iconEl.textContent = status === "ok" ? "✓" : "✗";
        break;
      }
    }
  },

  scrollToBottom() {
    const messages = document.getElementById("messages");
    requestAnimationFrame(() => {
      messages.scrollTop = messages.scrollHeight;
    });
  },

  async sendGroupChat(message) {
    this.showThinking();
    try {
      const res = await fetch(`${API}/groups/${this.state.selectedId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      }).then(r => r.json());
      this.removeThinking();

      if (res.results) {
        if (Array.isArray(res.results)) {
          // parallel / serial
          for (const r of res.results) {
            const title = r.agent_name || r.agent_id;
            const content = r.error ? `**Error:** ${r.error}` : (r.response || "[no response]");
            this.appendResultCard(title, content, r.status);
          }
        } else {
          // coordinator
          if (res.results.decomposition) {
            this.appendResultCard("📋 Decomposition", res.results.decomposition, "ok");
          }
          for (const wr of res.results.worker_results || []) {
            const title = wr.agent_name || wr.agent_id;
            const content = wr.error ? `**Error:** ${wr.error}` : (wr.response || "[no response]");
            this.appendResultCard(`🔧 ${title}`, content, wr.status);
          }
          if (res.results.final_response) {
            this.appendResultCard("🎯 Final Synthesis", res.results.final_response, "ok");
          }
        }
      }
    } catch (err) {
      this.removeThinking();
      this.appendMessage("assistant", "Error: " + err.message);
    }
  },

  // ---- UI Components ----

  appendMessage(role, text) {
    const messages = document.getElementById("messages");
    const node = document.createElement("div");
    node.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    if (role === "user") {
      avatar.textContent = "U";
    } else {
      const agent = this.state.selectedType === 'agent'
        ? this.state.agents.find(a => a.id === this.state.selectedId)
        : null;
      avatar.textContent = agent ? (agent.icon || '🤖') : '👥';
    }

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    if (role === "assistant") {
      bubble.innerHTML = this.renderMarkdown(text);
    } else {
      bubble.textContent = text;
    }

    node.appendChild(avatar);
    node.appendChild(bubble);
    messages.appendChild(node);
    this.scrollToBottom();
  },

  appendResultCard(title, content, status) {
    const messages = document.getElementById("messages");
    const card = document.createElement("div");
    card.className = "result-card";
    const statusColor = status === 'ok' || !status ? 'var(--accent)' : 'var(--error)';
    card.innerHTML = `
      <div class="result-card-header">
        <span style="color:${statusColor}">●</span>
        ${this.escapeHtml(title)}
      </div>
      <div class="result-card-body">${this.renderMarkdown(content)}</div>
    `;
    messages.appendChild(card);
    this.scrollToBottom();
  },

  showThinking() {
    this.removeThinking();
    const messages = document.getElementById("messages");
    const el = document.createElement("div");
    el.className = "thinking";
    el.id = "thinking-indicator";
    el.innerHTML = `
      <div class="thinking-dots"><span></span><span></span><span></span></div>
      <span>Thinking...</span>
    `;
    messages.appendChild(el);
    this.scrollToBottom();
  },

  removeThinking() {
    const el = document.getElementById("thinking-indicator");
    if (el) el.remove();
  },

  renderMarkdown(text) {
    if (typeof marked === "undefined") return this.escapeHtml(text);
    try { return marked.parse(text); } catch { return this.escapeHtml(text); }
  },

  escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  },

  scrollToBottom() {
    const messages = document.getElementById("messages");
    requestAnimationFrame(() => { messages.scrollTop = messages.scrollHeight; });
  },

  // ---- Actions ----

  async scanAgents() {
    const btn = document.getElementById("scanBtn");
    btn.textContent = "Scanning...";
    const res = await fetch(`${API}/agents/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root: "." }),
    }).then(r => r.json());
    btn.textContent = "🔍 Scan";
    await this.refreshAll();
    alert(`Found ${res.found || 0} agent(s)`);
  },

  showAgentModal() {
    document.getElementById("agentModal").classList.remove("hidden");
    document.getElementById("agentForm").reset();
  },

  hideAgentModal() {
    document.getElementById("agentModal").classList.add("hidden");
  },

  async submitAgentForm(e) {
    e.preventDefault();
    const payload = {
      name: document.getElementById("agentName").value.trim(),
      model: document.getElementById("agentModel").value.trim(),
      base_url: document.getElementById("agentBaseUrl").value.trim(),
      api_key: document.getElementById("agentApiKey").value.trim(),
      description: document.getElementById("agentDescription").value.trim(),
      icon: document.getElementById("agentIcon").value.trim(),
    };
    const res = await fetch(`${API}/agents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      this.hideAgentModal();
      await this.loadAgents();
    } else {
      const err = await res.json();
      alert(err.detail || "Failed to create agent");
    }
  },

  showGroupModal() {
    document.getElementById("groupModal").classList.remove("hidden");
    document.getElementById("groupForm").reset();
    const membersEl = document.getElementById("groupMembers");
    membersEl.innerHTML = this.state.agents.map(a => `
      <label class="checkbox-item">
        <input type="checkbox" value="${a.id}">
        <span>${a.icon || '🤖'} ${this.escapeHtml(a.name)}</span>
      </label>
    `).join('');
  },

  hideGroupModal() {
    document.getElementById("groupModal").classList.add("hidden");
  },

  async submitGroupForm(e) {
    e.preventDefault();
    const agentIds = Array.from(document.querySelectorAll('#groupMembers input:checked')).map(cb => cb.value);
    const payload = {
      name: document.getElementById("groupName").value.trim(),
      mode: document.getElementById("groupMode").value,
      agent_ids: agentIds,
    };
    const res = await fetch(`${API}/groups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      this.hideGroupModal();
      await this.loadGroups();
    } else {
      const err = await res.json();
      alert(err.detail || "Failed to create group");
    }
  },

  async editAgent(id) {
    const agent = this.state.agents.find(a => a.id === id);
    if (!agent) return;
    const detail = await fetch(`${API}/agents/${id}`).then(r => r.json());
    const m = detail.manifest || {};

    document.getElementById("editAgentId").value = id;
    document.getElementById("editName").value = m.name || "";
    document.getElementById("editModel").value = m.model || "";
    document.getElementById("editBaseUrl").value = m.base_url || "";
    document.getElementById("editSystemPrompt").value = detail.system_prompt || "";
    document.getElementById("editModal").classList.remove("hidden");
  },

  hideEditModal() {
    document.getElementById("editModal").classList.add("hidden");
  },

  async submitEditForm(e) {
    e.preventDefault();
    const id = document.getElementById("editAgentId").value;
    const payload = {
      name: document.getElementById("editName").value.trim(),
      model: document.getElementById("editModel").value.trim(),
      base_url: document.getElementById("editBaseUrl").value.trim(),
      api_key: document.getElementById("editApiKey").value.trim(),
      system_prompt: document.getElementById("editSystemPrompt").value.trim(),
    };
    const res = await fetch(`${API}/agents/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      this.hideEditModal();
      await this.refreshAll();
      if (this.state.selectedId === id && this.state.selectedType === 'agent') {
        await this.selectAgent(id);
      }
    } else {
      const err = await res.json();
      alert(err.detail || "Failed to update agent");
    }
  },

  async trashAgent(id) {
    if (!confirm("Move this agent to trash?")) return;
    await fetch(`${API}/agents/${id}/trash`, { method: "POST" });
    await this.refreshAll();
    if (this.state.selectedId === id) {
      this.state.selectedId = null;
      this.state.selectedType = null;
      document.getElementById("chatArea").classList.add("hidden");
      document.getElementById("emptyState").classList.remove("hidden");
    }
  },

  async restoreAgent(id) {
    const res = await fetch(`${API}/agents/${id}/restore`, { method: "POST" });
    if (res.ok) {
      await this.refreshAll();
    } else {
      alert("Cannot restore: already restored once or not in trash");
    }
  },

  toggleTrash() {
    document.getElementById("trashList").classList.toggle("hidden");
  },

  // ---- Events ----

  bindEvents() {
    document.getElementById("scanBtn").addEventListener("click", () => this.scanAgents());
    document.getElementById("createAgentBtn").addEventListener("click", () => this.showAgentModal());
    document.getElementById("createGroupBtn").addEventListener("click", () => this.showGroupModal());
    document.getElementById("closeAgentModal").addEventListener("click", () => this.hideAgentModal());
    document.getElementById("closeGroupModal").addEventListener("click", () => this.hideGroupModal());
    document.getElementById("closeEditModal").addEventListener("click", () => this.hideEditModal());
    document.getElementById("trashToggle").addEventListener("click", () => this.toggleTrash());

    document.getElementById("agentForm").addEventListener("submit", e => this.submitAgentForm(e));
    document.getElementById("groupForm").addEventListener("submit", e => this.submitGroupForm(e));
    document.getElementById("editForm").addEventListener("submit", e => this.submitEditForm(e));

    const input = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendButton");
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 160) + "px";
      sendBtn.disabled = !input.value.trim() || this.state.loading;
    });
    input.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.send(); }
    });
    sendBtn.addEventListener("click", () => this.send());

    // Close modals on overlay click
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
      overlay.addEventListener("click", e => {
        if (e.target === overlay) overlay.classList.add("hidden");
      });
    });
  },
};

window.addEventListener("DOMContentLoaded", () => App.init());
