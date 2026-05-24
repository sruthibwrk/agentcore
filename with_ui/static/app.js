const agentId = document.getElementById("agentId");
const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const chatLog = document.getElementById("chatLog");
const turnCounter = document.getElementById("turnCounter");
let localTurns = 0;

function cleanChatText(value) {
  let text = "";

  if (typeof value === "string") {
    text = value;
  } else if (value && typeof value.answer === "string") {
    text = value.answer;
  } else if (value) {
    text = JSON.stringify(value);
  }

  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed.answer === "string") {
      text = parsed.answer;
    }
  } catch {
    // The value is already plain text.
  }

  return text
    .replace(/\r\n/g, "\n")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "- ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function addMessage(kind, text) {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.textContent = cleanChatText(text);
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function sendMessage() {
  const prompt = promptInput.value.trim();
  if (!prompt) return;
  addMessage("user", prompt);
  promptInput.value = "";
  sendBtn.disabled = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        actor_id: "web-user",
        thread_id: "web-chat",
        agent_id: agentId.value.trim(),
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      addMessage("agent", `Error: ${data.detail || "Unknown error"}`);
      return;
    }
    addMessage("agent", data.answer || "No response.");
    localTurns += 1;
    turnCounter.textContent = `Turns: ${localTurns}`;
  } catch (err) {
    addMessage("agent", `Network error: ${err}`);
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", sendMessage);
promptInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.querySelectorAll(".prompt-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    promptInput.value = btn.textContent || "";
    promptInput.focus();
  });
});

addMessage("agent", "Hi, ask me a question and I will keep the answer clear.");
