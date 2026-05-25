const App = {
  state: { sessionId: "", ws: null, loading: false, config: {} },

  async init() {
    await this.loadConfig();
    this.bindEvents();
    this.connect();
    this.loadSessions();
  },

  async loadConfig() {
    const config = await fetch("/api/config").then(r => r.json());
    this.state.config = config;
    document.title = config.name;
    document.getElementById("brandIcon").textContent = config.icon_text || "M";
    document.getElementById("brandName").textContent = config.name;
    document.getElementById("brandSubtitle").textContent = config.subtitle;
    document.getElementById("emptyIcon").textContent = config.icon_text || "M";
    document.getElementById("emptyTitle").textContent = config.name;
    document.getElementById("emptyDescription").textContent = config.description;
    document.getElementById("workspaceLabel").textContent = config.workspace;
    document.getElementById("modelLabel").textContent = config.model;
    document.getElementById("profileLabel").textContent = config.profile;
  },

  bindEvents() {
    const input = document.getElementById("messageInput");
    const send = document.getElementById("sendButton");
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 180) + "px";
      send.disabled = !input.value.trim() || this.state.loading;
    });
    input.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        this.send();
      }
    });
    send.addEventListener("click", () => this.send());
    document.getElementById("newChat").addEventListener("click", () => this.newChat());
    document.getElementById("sidebarToggle").addEventListener("click", () => {
      document.querySelector(".sidebar").classList.toggle("open");
    });
  },

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
    if (data.type === "tool_call") {
      this.addActivity(data.name, "running");
    } else if (data.type === "tool_result") {
      this.addActivity(data.result || data.name, "error");
    } else if (data.type === "done") {
      this.state.sessionId = data.session_id || this.state.sessionId;
      this.appendMessage("assistant", data.content || `[${data.status}]`);
      this.finishLoading();
      this.loadSessions();
    } else if (data.type === "error") {
      this.appendMessage("assistant", data.error || "Error");
      this.finishLoading();
    }
  },

  send() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();
    if (!message || this.state.loading) return;
    this.clearEmpty();
    this.appendMessage("user", message);
    input.value = "";
    input.style.height = "auto";
    this.state.loading = true;
    document.getElementById("sendButton").disabled = true;
    this.setStatus("Running");
    if (this.state.ws && this.state.ws.readyState === WebSocket.OPEN) {
      this.state.ws.send(JSON.stringify({ message, session_id: this.state.sessionId }));
    } else {
      this.sendHttp(message);
    }
  },

  async sendHttp(message) {
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: this.state.sessionId })
      }).then(r => r.json());
      this.state.sessionId = response.session_id || this.state.sessionId;
      this.appendMessage("assistant", response.response || `[${response.status}]`);
      this.loadSessions();
    } catch (error) {
      this.appendMessage("assistant", error.message);
    } finally {
      this.finishLoading();
    }
  },

  appendMessage(role, text) {
    const messages = document.getElementById("messages");
    const node = document.createElement("div");
    node.className = `message ${role}`;
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "U" : (this.state.config.icon_text || "M");
    const body = document.createElement("div");
    body.className = "bubble";
    body.textContent = text;
    node.appendChild(avatar);
    node.appendChild(body);
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
  },

  addActivity(text, state) {
    const messages = document.getElementById("messages");
    const node = document.createElement("div");
    node.className = `activity ${state}`;
    node.textContent = text;
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
  },

  async loadSessions() {
    const data = await fetch("/api/sessions").then(r => r.json()).catch(() => ({ sessions: [] }));
    const list = document.getElementById("sessions");
    list.innerHTML = "";
    for (const session of data.sessions) {
      const item = document.createElement("button");
      item.className = "session";
      item.innerHTML = "";
      const title = document.createElement("span");
      title.className = "session-title";
      title.textContent = session.title || "Untitled";
      const meta = document.createElement("span");
      meta.className = "session-meta";
      meta.textContent = `${session.message_count || 0} messages | ${session.tool_call_count || 0} tools | ${session.evidence_count || 0} evidence`;
      item.appendChild(title);
      item.appendChild(meta);
      item.onclick = () => this.loadSession(session.id);
      list.appendChild(item);
    }
  },

  async loadSession(sessionId) {
    const detail = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`).then(r => r.json());
    this.state.sessionId = sessionId;
    const messages = document.getElementById("messages");
    messages.innerHTML = "";
    for (const message of detail.messages || []) {
      this.appendMessage(message.role || "assistant", message.content || "");
      if (message.errors && message.errors.length) {
        this.addActivity(message.errors.join("; "), "error");
      }
    }
    for (const tool of detail.tool_calls || []) {
      this.addActivity(`${tool.name || "tool"}: ${tool.status || "unknown"}`, tool.status === "ok" ? "ok" : "error");
    }
    for (const evidence of detail.evidence || []) {
      this.addActivity(`evidence ${evidence.id || ""} from ${evidence.source || "unknown"}`, "ok");
    }
  },

  newChat() {
    this.state.sessionId = "";
    document.getElementById("messages").innerHTML = "";
    this.loadConfig();
  },

  finishLoading() {
    this.state.loading = false;
    document.getElementById("sendButton").disabled = !document.getElementById("messageInput").value.trim();
    this.setStatus("Ready");
  },

  clearEmpty() {
    const empty = document.querySelector(".empty");
    if (empty) empty.remove();
  },

  setStatus(text) {
    document.getElementById("statusLabel").textContent = text;
  }
};

window.addEventListener("DOMContentLoaded", () => App.init());
