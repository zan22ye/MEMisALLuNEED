const state = {memories: []};

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    throw new Error(data.error?.message || `Request failed: ${response.status}`);
  }
  return data;
}

function showError(error) {
  document.querySelector("#error").textContent = error.message || String(error);
}

function clearError() {
  document.querySelector("#error").textContent = "";
}

function renderMemories(memories) {
  const list = document.querySelector("#memory-list");
  list.innerHTML = "";
  for (const memory of memories) {
    const row = document.createElement("div");
    row.className = "memory-row";
    row.innerHTML = `<div>${memory.content}</div><div class="meta">${memory.id.slice(0, 8)} ${memory.type} ${memory.state} confidence=${memory.confidence} usage=${memory.usage_count}</div>`;
    row.addEventListener("click", () => {
      document.querySelector("#memory-detail").textContent = JSON.stringify(memory, null, 2);
    });
    list.appendChild(row);
  }
}

async function loadStatus() {
  const status = await requestJson("/api/status");
  const modelStatus = status.models
    ? Object.entries(status.models)
        .map(([role, model]) => {
          const keyState = model.api_key_set ? "set" : `missing ${model.api_key_env}`;
          return `${role}: ${model.provider}/${model.model} (${keyState})`;
        })
        .join(" | ")
    : status.config_error
      ? `config error: ${status.config_error}`
      : "config not loaded";
  document.querySelector("#status").textContent = `${status.db_path} | ${status.config_path} | ${modelStatus}`;
}

async function loadMemories() {
  const data = await requestJson("/api/memories?limit=50");
  state.memories = data.memories;
  renderMemories(state.memories);
}

async function addMemory(event) {
  event.preventDefault();
  clearError();
  const payload = {
    content: document.querySelector("#memory-content").value,
    type: document.querySelector("#memory-type").value,
    state: document.querySelector("#memory-state").value,
    confidence: Number(document.querySelector("#memory-confidence").value),
    metadata: JSON.parse(document.querySelector("#memory-metadata").value || "{}"),
  };
  await requestJson("/api/memories", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  document.querySelector("#memory-content").value = "";
  await loadMemories();
}

async function searchMemories() {
  clearError();
  const query = encodeURIComponent(document.querySelector("#search-query").value);
  const data = await requestJson(`/api/search?q=${query}&top_k=10`);
  renderMemories(data.results.map((result) => result.memory));
}

async function sendChat() {
  clearError();
  const input = document.querySelector("#chat-input");
  const message = input.value.trim();
  if (!message) return;
  const conversation = document.querySelector("#conversation");
  conversation.textContent += `\nUser: ${message}\n`;
  input.value = "";
  const data = await requestJson("/api/chat/send", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message}),
  });
  conversation.textContent += `Assistant: ${data.assistant_reply}\n`;
  document.querySelector("#used-memories").textContent = JSON.stringify(data.used_memories, null, 2);
  await loadMemories();
}

function setupTabs() {
  for (const button of document.querySelectorAll(".tabs button")) {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelector(`#${button.dataset.tab}-tab`).classList.add("active");
    });
  }
}

async function postSessionAction(path) {
  clearError();
  await requestJson(path, {method: "POST"});
  await loadMemories();
}

async function main() {
  setupTabs();
  document.querySelector("#add-memory-form").addEventListener("submit", (event) => addMemory(event).catch(showError));
  document.querySelector("#search-button").addEventListener("click", () => searchMemories().catch(showError));
  document.querySelector("#reload-memories").addEventListener("click", () => loadMemories().catch(showError));
  document.querySelector("#send-chat").addEventListener("click", () => sendChat().catch(showError));
  document.querySelector("#new-session").addEventListener("click", () => postSessionAction("/api/chat/new-session").catch(showError));
  document.querySelector("#flush-session").addEventListener("click", () => postSessionAction("/api/chat/flush").catch(showError));
  document.querySelector("#clear-session").addEventListener("click", () => postSessionAction("/api/chat/clear").catch(showError));
  await loadStatus();
  await loadMemories();
}

main().catch(showError);
