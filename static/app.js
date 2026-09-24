/* MyBot AI — логика фронтенда: рисование, предсказание, чат. */
(function () {
  "use strict";

  // ------------------------------------------------------------------ //
  //  Холст для рисования
  // ------------------------------------------------------------------ //
  const pad = document.getElementById("pad");
  const ctx = pad.getContext("2d");
  const mini = document.getElementById("mini");
  const miniCtx = mini.getContext("2d");
  const badge = document.getElementById("prediction-badge");
  const barsEl = document.getElementById("bars");
  const confEl = document.getElementById("confidence");
  const sampleInfo = document.getElementById("sample-info");

  let drawing = false;
  let last = null;
  let predictTimer = null;

  const BRUSH = 18;

  function clearPad() {
    ctx.clearRect(0, 0, pad.width, pad.height);
    miniCtx.clearRect(0, 0, mini.width, mini.height);
    badge.classList.add("hidden");
    sampleInfo.classList.add("hidden");
    confEl.textContent = "";
    renderBars(null);
  }

  function pos(e) {
    const r = pad.getBoundingClientRect();
    const p = e.touches ? e.touches[0] : e;
    return { x: (p.clientX - r.left) * pad.width / r.width,
             y: (p.clientY - r.top) * pad.height / r.height };
  }

  function stroke(p) {
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = BRUSH;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  }

  function start(e) {
    e.preventDefault();
    drawing = true;
    last = pos(e);
    stroke(last);
    schedulePredict();
  }
  function move(e) {
    if (!drawing) return;
    e.preventDefault();
    stroke(pos(e));
    schedulePredict();
  }
  function end() { drawing = false; predictNow(); }

  pad.addEventListener("mousedown", start);
  pad.addEventListener("mousemove", move);
  window.addEventListener("mouseup", end);
  pad.addEventListener("touchstart", start, { passive: false });
  pad.addEventListener("touchmove", move, { passive: false });
  pad.addEventListener("touchend", end);

  function schedulePredict() {
    clearTimeout(predictTimer);
    predictTimer = setTimeout(predictNow, 180); // предсказываем «на лету»
  }

  // ------------------------------------------------------------------ //
  //  Предсказание
  // ------------------------------------------------------------------ //
  function padToDataUrl() {
    return pad.toDataURL("image/png");
  }

  async function predictNow() {
    const isBlank = !ctx.getImageData(0, 0, pad.width, pad.height).data.some(
      (v, i) => i % 4 === 3 && v > 0
    );
    if (isBlank) return;
    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: padToDataUrl() }),
      });
      const data = await res.json();
      if (data.error) { confEl.textContent = "⚠ " + data.error; return; }
      showResult(data, null);
    } catch (err) {
      confEl.textContent = "⚠ Сервер недоступен: " + err.message;
    }
  }

  function renderMini() {
    miniCtx.imageSmoothingEnabled = true;
    miniCtx.imageSmoothingQuality = "high";
    miniCtx.clearRect(0, 0, mini.width, mini.height);
    miniCtx.drawImage(pad, 0, 0, mini.width, mini.height);
  }

  function renderBars(probs, extraDigitImg) {
    barsEl.innerHTML = "";
    if (!probs) return;
    let top = 0;
    probs.forEach((p, i) => { if (p > probs[top]) top = i; });
    probs.forEach((p, i) => {
      const row = document.createElement("div");
      row.className = "bar-row" + (i === top ? " top" : "");
      row.innerHTML =
        `<span class="digit">${i}</span>` +
        `<div class="bar-track"><div class="bar-fill" style="width:${(p * 100).toFixed(1)}%"></div></div>` +
        `<span class="pct">${(p * 100).toFixed(1)}%</span>`;
      barsEl.appendChild(row);
    });
  }

  function showResult(data, sampleMeta) {
    badge.textContent = data.prediction;
    badge.classList.remove("hidden");
    renderMini();
    renderBars(data.probs);
    confEl.textContent = `Уверенность: ${(data.confidence * 100).toFixed(1)}%`;
    if (sampleMeta) {
      sampleInfo.innerHTML =
        `<img class="sample-img" src="${sampleMeta.image}" alt="пример">` +
        `Пример <b>№${sampleMeta.idx}</b> из обучающего датасета — ` +
        `правильный ответ: <b>${sampleMeta.true}</b>. ` +
        (data.prediction === sampleMeta.true
          ? "Модель угадала! ✓"
          : `Модель ответила <b>${data.prediction}</b> ✗`);
      sampleInfo.classList.remove("hidden");
    }
  }

  // ------------------------------------------------------------------ //
  //  Кнопки
  // ------------------------------------------------------------------ //
  document.getElementById("btn-clear").addEventListener("click", clearPad);

  document.getElementById("btn-sample").addEventListener("click", async () => {
    try {
      const res = await fetch("/api/sample");
      const s = await res.json();
      if (s.error) { confEl.textContent = "⚠ " + s.error; return; }
      showResult(s, s);
    } catch (err) {
      confEl.textContent = "⚠ Сервер недоступен: " + err.message;
    }
  });

  // ------------------------------------------------------------------ //
  //  Чат с ИИ-ассистентом (если настроен ключ)
  // ------------------------------------------------------------------ //
  const chatLog = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const history = [];

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    addMsg(text, "user");
    history.push({ role: "user", content: text });
    const thinking = addMsg("…", "bot");
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      const data = await res.json();
      if (data.error) {
        thinking.className = "msg error";
        thinking.textContent = data.error;
      } else {
        thinking.textContent = data.answer;
        history.push({ role: "assistant", content: data.answer });
      }
    } catch (err) {
      thinking.className = "msg error";
      thinking.textContent = "Сервер недоступен: " + err.message;
    }
    chatLog.scrollTop = chatLog.scrollHeight;
  });

  function addMsg(text, cls) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
    return div;
  }

  clearPad();
})();
