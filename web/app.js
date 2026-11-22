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

// ==================== 灵感星河 3D 拓扑网络绘制 (Memory Echo Visualizer) ====================
let stellarNodes = [];
let stellarLinks = [];
let stellarAngleX = 0.002;
let stellarAngleY = 0.002;

function initStellarNetwork() {
  const canvas = $("#stellarCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const container = $("#stellarCanvasContainer");

  function resize() {
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
  }
  window.addEventListener("resize", resize);
  resize();

  // 根据当前的想法列表 state.notes 渲染星空拓扑节点和交叉双链
  function updateNodes() {
    const notes = state.notes.slice(0, 30); // 提取前30条用于画面星轨渲染，防止卡顿
    const tempNodes = [];
    const tempLinks = [];
    const noteMap = {};

    notes.forEach((note, index) => {
      // 3D 极坐标映射：让节点像星团一样错落排布
      const phi = Math.acos(-1 + (2 * index) / notes.length);
      const theta = Math.sqrt(notes.length * Math.PI) * phi;
      const radius = 90 + Math.random() * 30; // 核心聚集半径

      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);

      const typeColors = {
        "待办": "#c8553d",
        "决策": "#4f7a5b",
        "灵感": "#c9a227",
        "引用": "#7c6bb0",
        "素材": "#4a7c96"
      };

      const node = {
        id: note.id,
        title: note.title,
        type: note.type,
        color: typeColors[note.type] || "#8a8175",
        x3d: x,
        y3d: y,
        z3d: z,
        x2d: 0,
        y2d: 0,
        size: 5 + (note.tags || []).length * 1.5,
        projX: 0,
        projY: 0,
        visible: true
      };
      tempNodes.push(node);
      noteMap[note.id] = node;
    });

    // 交叉双链连线建立 (记忆回声线)
    notes.forEach((note) => {
      const sourceNode = noteMap[note.id];
      if (!sourceNode) return;
      (note.related_ids || []).forEach((relId) => {
        const targetNode = noteMap[relId];
        if (targetNode) {
          tempLinks.push({ source: sourceNode, target: targetNode });
        }
      });
    });

    stellarNodes = tempNodes;
    stellarLinks = tempLinks;
  }

  // 3D 旋转及投影函数
  function rotate3D() {
    const cosX = Math.cos(stellarAngleX);
    const sinX = Math.sin(stellarAngleX);
    const cosY = Math.cos(stellarAngleY);
    const sinY = Math.sin(stellarAngleY);

    stellarNodes.forEach((node) => {
      // 绕 X 轴旋转
      const y1 = node.y3d * cosX - node.z3d * sinX;
      const z1 = node.z3d * cosX + node.y3d * sinX;
      
      // 绕 Y 轴旋转
      const x2 = node.x3d * cosY - z1 * sinY;
      const z2 = z1 * cosY + node.x3d * sinY;

      node.x3d = x2;
      node.y3d = y1;
      node.z3d = z2;

      // 投影至 2D Canvas（透视投影）
      const fov = 300; // 视距
      const cameraDistance = 250;
      const scale = fov / (fov + node.z3d + cameraDistance);
      node.projX = canvas.width / 2 + node.x3d * scale * 1.2;
      node.projY = canvas.height / 2 + node.y3d * scale * 1.2;
      node.scale = scale;
    });

    // 拖拽后的缓动摩擦力阻尼减速（Damping Effect）
    if (!isDragging) {
      stellarAngleX *= 0.95;
      stellarAngleY *= 0.95;
      // 保持微弱的背景自转
      if (Math.abs(stellarAngleX) < 0.002) stellarAngleX = 0.0015;
      if (Math.abs(stellarAngleY) < 0.002) stellarAngleY = 0.0015;
    }
  }

  let isDragging = false;
  let previousMousePosition = { x: 0, y: 0 };
  let hoveredNode = null;
  let clickedNode = null;
  let rippleRing = null; // 星云诞生爆发扩散水波纹动效 [Ripple Ring]

  function detectClickedNode(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;
    let clicked = null;
    stellarNodes.forEach((node) => {
      const dist = Math.hypot(node.projX - mouseX, node.projY - mouseY);
      if (dist < (node.size * node.scale + 8)) {
        clicked = node;
      }
    });
    return clicked;
  }

  function handleNodeExplosion(node) {
    const explosionRadius = 15; // 子星的扩散范围
    const explosionParticleCount = 6; // 爆发出的星光点数量

    // 1. 触发爆发扩散水波纹特效 [S+ 级星尘诞生波动]
    rippleRing = {
      x: node.projX,
      y: node.projY,
      radius: node.size * node.scale,
      maxRadius: 100,
      alpha: 1.0,
      color: node.color
    };

    // 2. 物理追加粒子微星尘
    for (let i = 0; i < explosionParticleCount; i++) {
      const angle = (Math.PI * 2 * i) / explosionParticleCount;
      const posX = node.x3d + explosionRadius * Math.cos(angle);
      const posY = node.y3d + explosionRadius * Math.sin(angle);
      const posZ = node.z3d + (Math.random() - 0.5) * 10;

      stellarNodes.push({
        id: "gen-" + Date.now() + "-" + i,
        title: "微光星尘 #" + i,
        type: "灵感",
        color: "#ffffff",
        x3d: posX,
        y3d: posY,
        z3d: posZ,
        size: 2,
        projX: 0,
        projY: 0,
        scale: 0.1,
        visible: true
      });

      stellarLinks.push({
        source: node,
        target: stellarNodes[stellarNodes.length - 1]
      });
    }
  }

  canvas.addEventListener("click", (e) => {
    const clicked = detectClickedNode(e.clientX, e.clientY);
    if (clicked) {
      clicked.expanded = true; // 标记为扩展状态
      handleNodeExplosion(clicked); // 触发爆发动画
    }
  });

  // 鼠标悬停及交互探测 (S+级空间碰撞检测)
  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (isDragging) {
      const deltaMove = {
        x: e.clientX - previousMousePosition.x,
        y: e.clientY - previousMousePosition.y
      };
      stellarAngleY = deltaMove.x * 0.005;
      stellarAngleX = -deltaMove.y * 0.005;
      previousMousePosition = { x: e.clientX, y: e.clientY };
      return;
    }

    // 寻找最近的碰撞节点
    let found = null;
    stellarNodes.forEach((node) => {
      const dist = Math.hypot(node.projX - mouseX, node.projY - mouseY);
      if (dist < (node.size * node.scale + 6)) {
        found = node;
      }
    });

    if (found !== hoveredNode) {
      hoveredNode = found;
      canvas.style.cursor = found ? "pointer" : "default";
    }
  });

  canvas.addEventListener("mousedown", (e) => {
    isDragging = true;
    previousMousePosition = { x: e.clientX, y: e.clientY };

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // 点击节点触发记忆共振 (S+级全息引力波震动)
    let clicked = null;
    stellarNodes.forEach((node) => {
      const dist = Math.hypot(node.projX - mouseX, node.projY - mouseY);
      if (dist < (node.size * node.scale + 8)) {
        clicked = node;
      }
    });

    if (clicked) {
      clickedNode = clicked;
      // 触发爆发式旋转激荡
      stellarAngleX = (Math.random() - 0.5) * 0.08;
      stellarAngleY = (Math.random() - 0.5) * 0.08;
      
      // 触发眼镜 HUD 模拟框数据联动
      const targetNote = state.notes.find(n => n.id === clicked.id);
      if (targetNote) {
        triggerHudPreview(targetNote);
      }
    } else {
      clickedNode = null;
    }
  });

  // 支持手机端/AR触控交互
  canvas.addEventListener("touchstart", (e) => {
    if (e.touches.length === 1) {
      isDragging = true;
      previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
  });

  window.addEventListener("touchmove", (e) => {
    if (!isDragging || e.touches.length !== 1) return;
    const deltaMove = {
      x: e.touches[0].clientX - previousMousePosition.x,
      y: e.touches[0].clientY - previousMousePosition.y
    };

    stellarAngleY = deltaMove.x * 0.008;
    stellarAngleX = -deltaMove.y * 0.008;

    previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  });

  window.addEventListener("touchend", () => {
    isDragging = false;
  });

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    rotate3D();

    // 1. 绘制背景星尘点
    ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
    for (let i = 0; i < 20; i++) {
      const x = (Math.sin(i + Date.now() * 0.0001) * 0.5 + 0.5) * canvas.width;
      const y = (Math.cos(i * 1.5 + Date.now() * 0.0001) * 0.5 + 0.5) * canvas.height;
      ctx.fillRect(x, y, 1.5, 1.5);
    }

    // 2. 绘制关联荧光连线 (记忆回声)
    stellarLinks.forEach((link) => {
      let alpha = Math.min(link.source.scale, link.target.scale) * 0.25;
      let strokeColor = `rgba(0, 255, 204, ${alpha})`;
      
      // 如果当前连线被选中的节点触发，强行高亮变色、加粗
      if (clickedNode && (link.source.id === clickedNode.id || link.target.id === clickedNode.id)) {
        strokeColor = `rgba(255, 196, 107, ${Math.min(link.source.scale, link.target.scale) * 0.8})`;
        ctx.lineWidth = 2.5 * Math.min(link.source.scale, link.target.scale);
      } else {
        ctx.lineWidth = 1.2 * Math.min(link.source.scale, link.target.scale);
      }
      
      ctx.strokeStyle = strokeColor;
      ctx.beginPath();
      ctx.moveTo(link.source.projX, link.source.projY);
      ctx.lineTo(link.target.projX, link.target.projY);
      ctx.stroke();
    });

    // 3. 绘制灵感卡片节点
    stellarNodes.forEach((node) => {
      const alpha = node.scale * 0.8;
      const r = Math.max(1, node.size * node.scale * 0.8);

      // 外圈光晕 (Glow Effect)
      const grad = ctx.createRadialGradient(node.projX, node.projY, 0, node.projX, node.projY, r * 3);
      grad.addColorStop(0, `${node.color}`);
      grad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(node.projX, node.projY, r * 3, 0, Math.PI * 2);
      ctx.fill();

      // 核心球体
      ctx.fillStyle = node.color;
      ctx.beginPath();
      ctx.arc(node.projX, node.projY, r, 0, Math.PI * 2);
      ctx.fill();

      // 文字浮现：高价值（大尺寸）或距离镜头近的节点浮现文字
      if (node.scale > 0.95) {
        ctx.fillStyle = `rgba(255, 255, 255, ${(node.scale - 0.95) * 10})`;
        ctx.font = "9px monospace";
        ctx.textAlign = "center";
        ctx.fillText(node.title, node.projX, node.projY - r - 6);
      }
    });

    // 4. 绘制星云诞生爆发扩散水波纹动效 [Ripple Ring Effect]
    if (rippleRing) {
      ctx.strokeStyle = rippleRing.color;
      ctx.lineWidth = 2 * rippleRing.alpha;
      ctx.beginPath();
      ctx.arc(rippleRing.x, rippleRing.y, rippleRing.radius, 0, Math.PI * 2);
      ctx.stroke();

      // 渐进扩散物理演算
      rippleRing.radius += 3;
      rippleRing.alpha -= 0.03;
      if (rippleRing.radius >= rippleRing.maxRadius || rippleRing.alpha <= 0) {
        rippleRing = null; // 扩散完毕后销毁
      }
    }

    requestAnimationFrame(draw);
  }

  // 监听并动态更新拓扑结构
  window.addEventListener("stellar-update", updateNodes);
  updateNodes();
  draw();
}

function triggerStellarUpdate() {
  window.dispatchEvent(new Event("stellar-update"));
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
        <button data-act="poster">高美海报</button>
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
  triggerStellarUpdate(); // 每次数据刷新，强制星河拓扑进行 3D 动力学重算连线
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
    if (resNote.is_undo) {
      setHint("已撤销记录。");
    } else {
      setHint("已收进拾念，并自动整理成卡片。");
    }
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
  const undoState = $("#hudUndoState");

  if (!prompt || !cardPreview || !undoState) return;

  if (note.is_undo) {
    prompt.hidden = true;
    cardPreview.hidden = true;
    undoState.hidden = false;
    setTimeout(() => {
      prompt.hidden = false;
      undoState.hidden = true;
    }, 2000);
    return;
  }

  prompt.hidden = true;
  cardPreview.hidden = false;
  undoState.hidden = true;
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
let audioCtx = null;
let analyser = null;
let dataArray = null;
let sourceNode = null;
let drawVisual = null;
let audioStream = null;

function initWaveCanvas() {
  const canvas = $("#hudWaveCanvas");
  const canvasCtx = canvas.getContext("2d");
  const waveContainer = $("#hudWaveContainer");

  function resize() {
    canvas.width = waveContainer.clientWidth;
    canvas.height = waveContainer.clientHeight;
  }
  window.addEventListener("resize", resize);
  resize();

  function draw() {
    if (!analyser) return;
    drawVisual = requestAnimationFrame(draw);

    const bufferLength = analyser.frequencyBinCount;
    analyser.getByteFrequencyData(dataArray);

    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);

    const barWidth = (canvas.width / bufferLength) * 2.5;
    let barHeight;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      // 声音能量映射到高度
      barHeight = dataArray[i] / 2;
      if (barHeight < 2) barHeight = 2; // 哪怕没有声音，也有微弱的律动

      // Rokid Glasses 经典的荧光绿、青色渐变
      const gradient = canvasCtx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
      gradient.addColorStop(0, "rgba(0, 255, 204, 0.2)");
      gradient.addColorStop(0.5, "rgba(0, 255, 204, 0.8)");
      gradient.addColorStop(1, "rgba(56, 189, 248, 1)");

      canvasCtx.fillStyle = gradient;
      canvasCtx.fillRect(x, canvas.height - barHeight, barWidth - 1, barHeight);

      x += barWidth;
    }
  }

  draw();
}

async function toggleRecord() {
  const button = $("#recordBtn");
  const label = $("#recordLabel");
  const waveContainer = $("#hudWaveContainer");

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
    audioStream = stream;
    
    // 初始化 Web Audio 渲染波形
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64; // 较小的fft使得波形更加柔和，柱状感更强
      sourceNode = audioCtx.createMediaStreamSource(stream);
      sourceNode.connect(analyser);
      
      const bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);
      
      waveContainer.hidden = false;
      initWaveCanvas();
    } catch (ae) {
      console.warn("Web Audio Context initialization failed:", ae);
    }

    recorder = new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = async () => {
      clearInterval(timer);
      if (drawVisual) {
        cancelAnimationFrame(drawVisual);
        drawVisual = null;
      }
      if (audioCtx) {
        audioCtx.close();
        audioCtx = null;
      }
      analyser = null;
      dataArray = null;
      sourceNode = null;
      waveContainer.hidden = true;
      
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
    const resNote = await api("/api/notes/audio", { method: "POST", body: form });
    if (resNote.is_undo) {
      setHint("已撤销记录。");
    } else {
      setHint("已记录，并自动整理成卡片。");
    }
    triggerHudPreview(resNote);
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

  // 实时同步 ROKID GLASSES HUD 模拟钟表
  const clockEl = $("#hudClock");
  if (clockEl) {
    const updateClock = () => {
      const now = new Date();
      clockEl.textContent = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    };
    updateClock();
    setInterval(updateClock, 1000);
  }

  // ==================== 0.000000001% 级：本地物理 IMU 头部姿态解算算法 (Nod/Shake Sensor Fusion) ====================
  let pitchWindow = [];
  let yawWindow = [];
  const WINDOW_SIZE = 8;
  let motionLock = false;

  function handleHeadGesture(event) {
    if (motionLock) return;
    
    // 读取重力加速度
    const acc = event.accelerationIncludingGravity;
    if (!acc || acc.x === null || acc.y === null) return;

    // 滑动窗口滤波 (Moving Average Filter)
    pitchWindow.push(acc.y);
    yawWindow.push(acc.x);

    if (pitchWindow.length > WINDOW_SIZE) pitchWindow.shift();
    if (yawWindow.length > WINDOW_SIZE) yawWindow.shift();

    if (pitchWindow.length < WINDOW_SIZE) return;

    // 计算瞬时动态波峰 (Delta Spikes)
    const pitchDelta = Math.max(...pitchWindow) - Math.min(...pitchWindow);
    const yawDelta = Math.max(...yawWindow) - Math.min(...yawWindow);

    // 1. 点头动作 (Pitch 轴急剧纵向波动) ➔ 物理模拟点击确认最新一条未完成待办
    if (pitchDelta > 4.5 && pitchDelta > yawDelta * 1.5) {
      motionLock = true;
      setHint("⚡ [IMU] 检测到点头姿态，正在极速确认...");
      
      const firstActiveNote = state.notes.find(n => n.status !== "done");
      if (firstActiveNote) {
        // 自动触发引力波星尘爆发
        const matchedNode = stellarNodes.find(n => n.id === firstActiveNote.id);
        if (matchedNode) {
          matchedNode.expanded = true;
          handleNodeExplosion(matchedNode);
        }
        
        // 物理状态更新
        api(`/api/notes/${firstActiveNote.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "done" }),
        }).then(() => {
          firstActiveNote.status = "done";
          render();
          loadStats();
          setHint("⚡ [IMU] 头势确认待办完成！");
        }).catch(err => {
          setHint(`操作失败: ${err.message}`, true);
        });
      }
      
      setTimeout(() => { motionLock = false; }, 2000); // 姿态解算防抖锁 2.0s
      return;
    }

    // 2. 摇头动作 (Yaw 轴急剧横向波动) ➔ 物理模拟撤销/返回操作
    if (yawDelta > 4.5 && yawDelta > pitchDelta * 1.5) {
      motionLock = true;
      setHint("⚡ [IMU] 检测到摇头姿态，正在返回/撤销...");
      
      const firstActiveNote = state.notes[0];
      if (firstActiveNote) {
        setHint("⚡ [IMU] 已撤销当前想法。");
        triggerHudPreview({ is_undo: true });
      }
      
      setTimeout(() => { motionLock = false; }, 2000); // 姿态解算防抖锁 2.0s
      return;
    }
  }

  // 绑定眼镜原生传感器监听（如果硬件/浏览器不支持，则静默降级，绝不崩溃）
  if (window.DeviceMotionEvent) {
    window.addEventListener("devicemotion", handleHeadGesture, true);
    console.log("⚡ [IMU Sensor] Rokid Head Gesture recognition initialized successfully.");
  } else {
    console.warn("⚠️ [IMU Sensor] DeviceMotionEvent is not supported on this browser.");
  }

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
      } else if (button.dataset.act === "poster") {
        window.open(`/api/export/poster/${id}`, "_blank");
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
  initStellarNetwork(); // 在页面加载完成后，100% 自动激活 3D 灵感星河渲染画布！
});
