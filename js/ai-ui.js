// MyBot AI UI — чат-интерфейс, стриминг, рендер markdown, память, голос, управление музыкой

import { MyBotAI, MODELS } from './ai-engine.js';

const $ = (id) => document.getElementById(id);

let ai = null;
let abortCtrl = null;
let isGenerating = false;

// простая markdown → html (поддержка заголовков, жирного, курсива, кода, списков, цитат, ссылок)
function mdToHtml(md) {
  let html = escapeHtml(md);

  // мыслительный блок <thinking>
  html = html.replace(/&lt;thinking&gt;([\s\S]*?)&lt;\/thinking&gt;/g, (_, inner) => {
    return `<details class="thinking"><summary>🧠 Размышления модели</summary><pre>${inner.trim()}</pre></details>`;
  });

  // code blocks ```lang code ```
  html = html.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, lang, code) => {
    const cls = lang ? ` class="lang-${lang}"` : "";
    return `<pre><code${cls}>${code.trim()}</code><button class="copy-btn" data-copy="${encodeURIComponent(code.trim())}">копировать</button></pre>`;
  });

  // inline code `code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // headers ###, ##, #
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // bold **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // italic *text* (осторожно)
  html = html.replace(/(^|[^*])\*([^*\n]+)\*([^*]|$)/g, '$1<em>$2</em>$3');

  // цитаты > ...
  html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>');

  // списки - item / 1. item
  html = html.replace(/^\s*[-•]\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/^\s*\d+\.\s+(.+)$/gm, '<li>$1</li>');
  // оборачиваем подряд идущие li в ul (упрощённо)
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);

  // ссылки [text](url) — но экранированы, поэтому ищем &lt;a&gt;?
  // оставим как есть: http(s)://
  html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');

  // параграфы: двойной перенос → <p>, одинарный → <br>
  html = html.split(/\n{2,}/).map(block => {
    if (/^\s*<(h[1-3]|ul|pre|blockquote|details)/.test(block.trim())) return block;
    if (block.trim() === "") return "";
    return `<p>${block.replace(/\n/g, "<br>")}</p>`;
  }).join("\n");

  return html;
}

function escapeHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function saveHistory() {
  try {
    localStorage.setItem("mybot_ai_history", JSON.stringify(ai.history));
    localStorage.setItem("mybot_ai_model", ai.model.id);
  } catch {}
}

function loadHistory() {
  try {
    const h = localStorage.getItem("mybot_ai_history");
    const m = localStorage.getItem("mybot_ai_model");
    if (m && MODELS[m]) ai.setModel(m);
    if (h) ai.importHistory(h);
  } catch {}
}

function renderHistory() {
  const cont = $("chatHistory");
  cont.innerHTML = "";
  if (ai.history.length === 0) {
    cont.innerHTML = `
      <div class="welcome">
        <div class="welcome-icon">🤖</div>
        <h2>MyBot AI — настоящий ИИ в браузере</h2>
        <p>Работает <b>полностью офлайн</b> — без серверов, без отправки данных. Понимает контекст, пишет код, решает задачи, сочиняет и управляет музыкой.</p>
        <div class="chips">
          <button class="chip" data-prompt="Объясни как работает трансформер простыми словами">🧠 Трансформер просто</button>
          <button class="chip" data-prompt="Напиши телеграм-бота на Python с кнопками">🤖 Телеграм-бот</button>
          <button class="chip" data-prompt="Сделай тёмный synthwave трек на 90 секунд в ля миноре">🎵 Тёмный синтвейв</button>
          <button class="chip" data-prompt="Реши уравнение 2x + 5 = 15 по шагам">🧮 Реши уравнение</button>
          <button class="chip" data-prompt="Придумай киберпанк историю про одинокого робота">✨ Киберпанк история</button>
          <button class="chip" data-prompt="Что такое чёрная дыра?">🌌 Чёрная дыра</button>
        </div>
        <p class="welcome-hint">Попробуй сказать: «сделай весёлый техно на 2 минуты» — и я соберу трек!</p>
      </div>`;
    cont.querySelectorAll(".chip").forEach(b => {
      b.addEventListener("click", () => {
        $("chatInput").value = b.dataset.prompt;
        $("chatInput").focus();
        sendMessage();
      });
    });
    return;
  }
  for (const msg of ai.history) {
    const div = document.createElement("div");
    div.className = `msg ${msg.role}`;
    div.innerHTML = `
      <div class="avatar">${msg.role==="user" ? "🧑" : "🤖"}</div>
      <div class="bubble">${msg.role==="user" ? escapeHtml(msg.content).replace(/\n/g,"<br>") : mdToHtml(msg.content)}</div>
    `;
    cont.appendChild(div);
  }
  // copy buttons
  cont.querySelectorAll(".copy-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const text = decodeURIComponent(btn.dataset.copy);
      navigator.clipboard.writeText(text).then(()=>{
        btn.textContent = "скопировано ✓";
        setTimeout(()=>btn.textContent="копировать",1500);
      });
    });
  });
  cont.scrollTop = cont.scrollHeight;
}

function setGenerating(v) {
  isGenerating = v;
  $("sendBtn").disabled = v;
  $("stopBtn").style.display = v ? "inline-flex" : "none";
  $("chatInput").disabled = v;
  if (v) {
    $("sendBtn").innerHTML = `<span class="spinner"></span> Пишу…`;
  } else {
    $("sendBtn").innerHTML = `Отправить <span class="kbd">↵</span>`;
  }
}

async function sendMessage() {
  const input = $("chatInput");
  const text = input.value.trim();
  if (!text || isGenerating) return;
  input.value = "";
  // покажем пользователя сразу
  abortCtrl = new AbortController();
  setGenerating(true);

  // если это первое сообщение и есть welcome — очистим и перерендерим
  const cont = $("chatHistory");
  if (ai.history.length === 0) cont.innerHTML = "";

  // создаём пузырь пользователя
  const uDiv = document.createElement("div");
  uDiv.className = "msg user";
  uDiv.innerHTML = `<div class="avatar">🧑</div><div class="bubble">${escapeHtml(text).replace(/\n/g,"<br>")}</div>`;
  cont.appendChild(uDiv);

  // пузырь ассистента с индикатором
  const aDiv = document.createElement("div");
  aDiv.className = "msg assistant";
  aDiv.innerHTML = `<div class="avatar">🤖</div><div class="bubble"><span class="typing"><i></i><i></i><i></i></span> <span class="typing-text">Думаю…</span></div>`;
  cont.appendChild(aDiv);
  cont.scrollTop = cont.scrollHeight;

  let full = "";
  const bubble = aDiv.querySelector(".bubble");

  try {
    for await (const chunk of ai.stream(text, { signal: abortCtrl.signal })) {
      if (abortCtrl.signal.aborted) break;
      full += chunk;
      bubble.innerHTML = mdToHtml(full);
      // обновляем копирование
      bubble.querySelectorAll(".copy-btn").forEach(btn=>{
        if (btn._bound) return; btn._bound=true;
        btn.addEventListener("click", ()=>{
          const t = decodeURIComponent(btn.dataset.copy);
          navigator.clipboard.writeText(t).then(()=>{
            btn.textContent="скопировано ✓";
            setTimeout(()=>btn.textContent="копировать",1500);
          });
        });
      });
      cont.scrollTop = cont.scrollHeight;
    }
  } catch (e) {
    if (e.name !== "AbortError") console.error(e);
    if (!full) bubble.innerHTML = `<em>Генерация прервана.</em>`;
  } finally {
    setGenerating(false);
    saveHistory();
    updateStats();
    // обновляем полную историю рендера для консистентности (чтобы маркдаун был финальный)
    // но оставляем стримовый вариант уже отрендеренным
    abortCtrl = null;
  }
}

function stopGeneration() {
  if (abortCtrl) abortCtrl.abort();
  setGenerating(false);
}

function updateStats() {
  const el = $("aiStats");
  if (!el) return;
  const tokensApprox = Math.round(JSON.stringify(ai.history).length / 4);
  el.textContent = `${ai.history.length} сообщений · ~${tokensApprox} токенов · ${ai.model.name}`;
}

function clearChat() {
  if (isGenerating) stopGeneration();
  ai.clear();
  localStorage.removeItem("mybot_ai_history");
  renderHistory();
  updateStats();
}

function exportChat() {
  const blob = new Blob([ai.exportHistory()], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `mybot_chat_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  setTimeout(()=>URL.revokeObjectURL(url), 2000);
}

function handleMusicCommand(opts) {
  // вызывается из ai-engine когда распознан music_control
  // пытаемся применить к музыкальному генератору, если он загружен
  try {
    const styleEl = document.getElementById("style");
    const moodEl = document.getElementById("mood");
    const durEl = document.getElementById("duration");
    const keyEl = document.getElementById("key");
    if (!styleEl) return { ok: false, reason: "музыкальный модуль не загружен" };
    let changed = [];
    if (opts.style && styleEl.querySelector(`option[value="${opts.style}"]`)) {
      styleEl.value = opts.style;
      changed.push(`стиль ${opts.style}`);
    }
    if (opts.mood && moodEl.querySelector(`option[value="${opts.mood}"]`)) {
      moodEl.value = opts.mood;
      changed.push(`настроение ${opts.mood}`);
    }
    if (opts.duration) {
      // округляем к ближайшему варианту 30/60/90/120
      const avail = [30,60,90,120];
      const best = avail.reduce((a,b)=> Math.abs(b - opts.duration) < Math.abs(a - opts.duration) ? b : a);
      durEl.value = String(best);
      changed.push(`длина ${best}с`);
    }
    if (opts.key !== null && opts.key !== undefined) {
      keyEl.value = String(opts.key);
      changed.push(`тональность ${keyEl.options[keyEl.selectedIndex]?.text || opts.key}`);
    }
    // триггерим генерацию
    const genBtn = document.getElementById("generate");
    if (genBtn) {
      // покажем индикатор и генерируем
      setTimeout(()=> genBtn.click(), 300);
    }
    // переключим вкладку на музыку визуально
    const musicTab = document.querySelector('[data-tab="music"]');
    if (musicTab) musicTab.classList.add("pulse");
    setTimeout(()=> musicTab?.classList.remove("pulse"), 2000);

    return { ok: true, summary: changed.length ? changed.join(", ") : "параметры по умолчанию" };
  } catch (e) {
    return { ok: false, reason: e.message };
  }
}

// Голосовой ввод/вывод
let recognition = null;
function toggleVoiceInput() {
  const btn = $("voiceBtn");
  if (recognition && recognition._running) {
    recognition.stop();
    return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    alert("Голосовой ввод не поддерживается в этом браузере. Попробуй Chrome.");
    return;
  }
  recognition = new SR();
  recognition.lang = "ru-RU";
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition._running = true;
  btn.classList.add("recording");
  btn.textContent = "⏹";

  recognition.onresult = (e) => {
    let transcript = "";
    for (let i=0;i<e.results.length;i++) transcript += e.results[i][0].transcript + " ";
    $("chatInput").value = transcript.trim();
  };
  recognition.onend = () => {
    recognition._running = false;
    btn.classList.remove("recording");
    btn.textContent = "🎤";
    if ($("chatInput").value.trim()) sendMessage();
  };
  recognition.onerror = () => {
    recognition._running = false;
    btn.classList.remove("recording");
    btn.textContent = "🎤";
  };
  recognition.start();
}

function speakLast() {
  const last = [...ai.history].reverse().find(m=>m.role==="assistant");
  if (!last) return;
  // убираем markdown
  const text = last.content.replace(/[#*`]/g,"").replace(/<[^>]+>/g,"").slice(0, 4000);
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "ru-RU";
  utter.rate = 1.0;
  speechSynthesis.cancel();
  speechSynthesis.speak(utter);
}

export function initAI() {
  const modelSel = $("modelSelect");
  // заполняем селект
  if (modelSel) {
    modelSel.innerHTML = Object.values(MODELS).map(m=> `<option value="${m.id}">${m.name} — ${m.desc}</option>`).join("");
  }

  ai = new MyBotAI({
    model: modelSel ? modelSel.value : "mybot-pro",
    temperature: 0.85,
    musicHandler: handleMusicCommand
  });
  loadHistory();

  // expose for debugging / music integration
  window.MyBotAI = ai;
  window.handleMusicCommand = handleMusicCommand;

  // events
  $("chatInput")?.addEventListener("keydown", (e)=>{
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  $("sendBtn")?.addEventListener("click", sendMessage);
  $("stopBtn")?.addEventListener("click", stopGeneration);
  $("clearBtn")?.addEventListener("click", clearChat);
  $("exportBtn")?.addEventListener("click", exportChat);
  $("voiceBtn")?.addEventListener("click", toggleVoiceInput);
  $("speakBtn")?.addEventListener("click", speakLast);
  modelSel?.addEventListener("change", (e)=>{
    ai.setModel(e.target.value);
    saveHistory();
    updateStats();
  });
  $("tempRange")?.addEventListener("input", (e)=>{
    ai.temperature = parseFloat(e.target.value);
    $("tempVal").textContent = ai.temperature.toFixed(2);
  });
  // chip clicks делегируются в renderHistory

  renderHistory();
  updateStats();

  // автофокус
  setTimeout(()=> $("chatInput")?.focus(), 300);
}

// для импорта из app.js
export { handleMusicCommand };
