const state = { type: "", q: "", notes: [] };
const $ = (sel) => document.querySelector(sel);

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const raw = await res.text();
  let data = null;
  try { data = raw ? JSON.parse(raw) : null; } catch (_) { data = null; }
  if (!res.ok) {
    const message = (data && data.detail) || raw || res.statusText;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}

function formatTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.slice(5, 16).replace("T", " ");
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const hm = `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  return isToday ? hm : `${date.getMonth() + 1}-${date.getDate()} ${hm}`;
}

function cardHtml(note) {
  const tags = (note.tags || []).map((tag) => `<span class="tag">#${escapeHtml(tag)}</span>`).join("");
  const actions = (note.action_items || []).length
    ? `<p class="action-line">→ ${escapeHtml(note.action_items.join("；"))}</p>`
    : "";
  const done = note.status === "done";
  return `
    <article class="card${done ? " done" : ""}" data-type="${escapeHtml(note.type)}" data-id="${note.id}">
      <div class="card-head">
        <span class="badge">${escapeHtml(note.type)}</span>
        <time>${escapeHtml(formatTime(note.created_at))}</time>
      </div>
      <h3>${escapeHtml(note.title)}</h3>
      <p>${escapeHtml(note.summary)}</p>
      ${actions}
      ${tags ? `<div class="tags">${tags}</div>` : ""}
      <div class="actions">
        <button data-act="toggle">${done ? "恢复待办" : "标记完成"}</button>
        <button data-act="card">分享卡片</button>
        <button data-act="delete">删除</button>
      </div>
    </article>`;
}

function render() {
  const list = $("#list");
  if (!state.notes.length) {
    list.innerHTML = '<div class="empty">还没有想法<br>说一句试试，比如「明天把包装方案发给阿哲」</div>';
    return;
  }
  list.innerHTML = state.notes.map(cardHtml).join("");
}

async function loadNotes() {
  const params = new URLSearchParams({ limit: "100" });
  if (state.type) params.set("type", state.type);
  if (state.q) params.set("q", state.q);
  const data = await api(`/api/notes?${params.toString()}`);
  state.notes = data.items || [];
  render();
}

async function loadStats() {
  const data = await api("/api/stats");
  $("#statToday").textContent = data.today;
  $("#statTodos").textContent = data.open_todos;
  $("#statStreak").textContent = data.streak;
  $("#statTotal").textContent = data.total;
}

function setHint(text, warn = false) {
  const hint = $("#hint");
  hint.textContent = text;
  hint.classList.toggle("warn", warn);
}

async function submitText() {
  const input = $("#text");
  const text = input.value.trim();
  if (!text) {
    setHint("先写一句想记下的话。", true);
    input.focus();
    return;
  }
  const button = $("#submitBtn");
  button.disabled = true;
  try {
    const resNote = await api("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source: "web" }),
    });
    input.value = "";
    setHint("已收进拾念，并自动整理成卡片。");
    triggerHudPreview(resNote);
    await Promise.all([loadNotes(), loadStats()]);
  } catch (error) {
    setHint(`记录失败：${error.message}`, true);
  } finally {
    button.disabled = false;
  }
}

function triggerHudPreview(note) {
  const prompt = $("#hudPrompt");
  const cardPreview = $("#hudCardPreview");
  const tag = $("#hudTag");
  const title = $("#hudTitle");
  const action = $("#hudAction");

  if (!prompt || !cardPreview) return;

  prompt.hidden = true;
  cardPreview.hidden = false;
  tag.textContent = note.type || "灵感";
  title.textContent = note.title || "未命名";
  action.textContent = note.action_items && note.action_items.length ? `→ ${note.action_items[0]}` : "";

  setTimeout(() => {
    prompt.hidden = false;
    cardPreview.hidden = true;
  }, 4500);
}

let recorder = null;
let chunks = [];
let startedAt = 0;
let timer = null;

async function toggleRecord() {
  const button = $("#recordBtn");
  const label = $("#recordLabel");

  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }

  if (!navigator.mediaDevices || !window.MediaRecorder) {
    setHint("当前浏览器不支持录音，请用文字记录。", true);
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = async () => {
      clearInterval(timer);
      stream.getTracks().forEach((track) => track.stop());
      button.classList.remove("recording");
      label.textContent = "开始记录";
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      await uploadAudio(blob);
    };
    recorder.start();
    startedAt = Date.now();
    button.classList.add("recording");
    timer = setInterval(() => {
      const seconds = Math.floor((Date.now() - startedAt) / 1000);
      label.textContent = `停止并整理 ${seconds}s`;
    }, 500);
    label.textContent = "停止并整理 0s";
    setHint("正在听…说完点一下停止。");
  } catch (error) {
    setHint(`无法使用麦克风：${error.message}`, true);
  }
}

async function uploadAudio(blob) {
  const form = new FormData();
  form.append("file", blob, "note.webm");
  setHint("正在转写并整理…");
  try {
    await api("/api/notes/audio", { method: "POST", body: form });
    setHint("已记录，并自动整理成卡片。");
    await Promise.all([loadNotes(), loadStats()]);
  } catch (error) {
    setHint(`语音记录失败：${error.message}`, true);
  }
}

async function openReview() {
  const modal = $("#modal");
  const body = $("#modalBody");
  body.textContent = "正在生成…";
  modal.hidden = false;
  try {
    const [week, day] = await Promise.all([
      api("/api/review/weekly"),
      api("/api/review/daily"),
    ]);
    body.textContent = `${day.markdown}\n\n──────────\n\n${week.markdown}`;
  } catch (error) {
    body.textContent = `生成失败：${error.message}`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("#submitBtn").addEventListener("click", submitText);
  $("#recordBtn").addEventListener("click", toggleRecord);
  $("#reviewBtn").addEventListener("click", openReview);
  $("#closeModal").addEventListener("click", () => { $("#modal").hidden = true; });
  $("#modal").addEventListener("click", (event) => {
    if (event.target.id === "modal") $("#modal").hidden = true;
  });
  $("#copyBtn").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("#modalBody").textContent);
      $("#copyBtn").textContent = "已复制";
      setTimeout(() => { $("#copyBtn").textContent = "复制文案"; }, 1500);
    } catch (_) {
      setHint("复制失败，请手动选择文本。", true);
    }
  });

  $("#exportObsidianBtn").addEventListener("click", () => {
    window.location.href = "/api/export/obsidian";
  });

  $("#text").addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") submitText();
  });

  let searchTimer = null;
  $("#search").addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.q = event.target.value.trim();
      loadNotes();
    }, 220);
  });

  $("#filters").addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    document.querySelectorAll(".chip").forEach((item) => item.classList.remove("active"));
    chip.classList.add("active");
    state.type = chip.dataset.type || "";
    loadNotes();
  });

  $("#list").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-act]");
    if (!button) return;
    const card = button.closest(".card");
    const id = card.dataset.id;
    const note = state.notes.find((item) => String(item.id) === id);
    try {
      if (button.dataset.act === "delete") {
        await api(`/api/notes/${id}`, { method: "DELETE" });
        state.notes = state.notes.filter((item) => String(item.id) !== id);
      } else if (button.dataset.act === "card") {
        window.open(`/api/export/card/${id}`, "_blank");
        return;
      } else if (note) {
        const next = note.status === "done" ? "inbox" : "done";
        await api(`/api/notes/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: next }),
        });
        note.status = next;
      }
      render();
      loadStats();
    } catch (error) {
      setHint(`操作失败：${error.message}`, true);
    }
  });

  loadNotes().catch((error) => setHint(`加载失败：${error.message}`, true));
  loadStats().catch(() => {});
});
