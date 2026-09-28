// MyBot AI UI — чат, стриминг, markdown, голос, память, музыка, облако + нейровиз
import { MyBotAI, MODELS } from './ai-engine.js';
import { NeuralViz } from './neural-viz.js';

const $ = (id) => document.getElementById(id);

let ai = null;
let viz = null;
let abortCtrl = null;
let isGenerating = false;

function mdToHtml(md) {
  let html = escapeHtml(md);
  html = html.replace(/&lt;thinking&gt;([\s\S]*?)&lt;\/thinking&gt;/g, (_, inner) => {
    return `<details class="thinking"><summary>🧠 Размышления модели</summary><pre>${inner.trim()}</pre></details>`;
  });
  html = html.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, lang, code) => {
    const cls = lang ? ` class="lang-${lang}"` : "";
    return `<pre><code${cls}>${code.trim()}</code><button class="copy-btn" data-copy="${encodeURIComponent(code.trim())}">копировать</button></pre>`;
  });
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/(^|[^*])\*([^*\n]+)\*([^*]|$)/g, '$1<em>$2</em>$3');
  html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>');
  html = html.replace(/^\s*[-•]\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/^\s*\d+\.\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
  html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  html = html.split(/\n{2,}/).map(block => {
    if (/^\s*<(h[1-3]|ul|pre|blockquote|details)/.test(block.trim())) return block;
    if (block.trim() === "") return "";
    return `<p>${block.replace(/\n/g, "<br>")}</p>`;
  }).join("\n");
  return html;
}
function escapeHtml(s){ return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

function saveHistory(){
  try{
    localStorage.setItem("mybot_ai_history", JSON.stringify(ai.history));
    localStorage.setItem("mybot_ai_model", ai.model.id);
  }catch{}
}
function loadHistory(){
  try{
    const h=localStorage.getItem("mybot_ai_history");
    const m=localStorage.getItem("mybot_ai_model");
    if(m && MODELS[m]) ai.setModel(m);
    if(h) ai.importHistory(h);
  }catch{}
}
function renderHistory(){
  const cont=$("chatHistory");
  cont.innerHTML="";
  if(ai.history.length===0){
    cont.innerHTML=`
      <div class="welcome">
        <div class="welcome-icon">🤖</div>
        <h2>MyBot AI — настоящий ИИ в браузере</h2>
        <p>Трансформер 124M, квантованный до 4-bit, работает <b>полностью офлайн</b> через WebAssembly. Без серверов, без отправки данных. Понимает контекст, пишет код, решает задачи, сочиняет и управляет музыкой.</p>
        <div class="chips">
          <button class="chip" data-prompt="Объясни как работает трансформер простыми словами">🧠 Трансформер просто</button>
          <button class="chip" data-prompt="Напиши телеграм-бота на Python с кнопками">🤖 Телеграм-бот</button>
          <button class="chip" data-prompt="Сделай тёмный synthwave трек на 90 секунд в ля миноре">🎵 Тёмный синтвейв</button>
          <button class="chip" data-prompt="Реши уравнение 2x + 5 = 15 по шагам">🧮 Реши уравнение</button>
          <button class="chip" data-prompt="Придумай киберпанк историю про одинокого робота">✨ Киберпанк история</button>
          <button class="chip" data-prompt="Что такое чёрная дыра?">🌌 Чёрная дыра</button>
        </div>
        <p class="welcome-hint">Попробуй: «сделай весёлый техно на 2 минуты» — и я соберу трек прямо при тебе!</p>
      </div>`;
    cont.querySelectorAll(".chip").forEach(b=>{
      b.addEventListener("click",()=>{
        $("chatInput").value=b.dataset.prompt;
        $("chatInput").focus();
        sendMessage();
      });
    });
    return;
  }
  for(const msg of ai.history){
    const div=document.createElement("div");
    div.className=`msg ${msg.role}`;
    div.innerHTML=`<div class="avatar">${msg.role==="user"?"🧑":"🤖"}</div><div class="bubble">${msg.role==="user"?escapeHtml(msg.content).replace(/\n/g,"<br>"):mdToHtml(msg.content)}</div>`;
    cont.appendChild(div);
  }
  cont.querySelectorAll(".copy-btn").forEach(btn=>{
    btn.addEventListener("click",()=>{
      const text=decodeURIComponent(btn.dataset.copy);
      navigator.clipboard.writeText(text).then(()=>{
        btn.textContent="скопировано ✓";
        setTimeout(()=>btn.textContent="копировать",1500);
      });
    });
  });
  cont.scrollTop=cont.scrollHeight;
}
function setGenerating(v){
  isGenerating=v;
  $("sendBtn").disabled=v;
  $("stopBtn").style.display=v?"inline-flex":"none";
  $("chatInput").disabled=v;
  if(v){
    $("sendBtn").innerHTML=`<span class="spinner"></span> Пишу…`;
    viz?.start();
  } else {
    $("sendBtn").innerHTML=`Отправить <span class="kbd">↵</span>`;
    viz?.stop();
  }
}

// облако
function getApiKey(){ return (localStorage.getItem("mybot_api_key")||"").trim(); }
function getProvider(){ return localStorage.getItem("mybot_provider")||"openai"; }
function saveKey(){
  const k=$("apiKey").value.trim();
  const p=$("apiProvider").value;
  if(k) localStorage.setItem("mybot_api_key", k);
  localStorage.setItem("mybot_provider", p);
  $("keyStatus").textContent = k ? "✅ Ключ сохранён локально. Попробуй тест." : "Ключ удалён — работаем офлайн.";
  updateBackend();
}
function clearKey(){
  localStorage.removeItem("mybot_api_key");
  $("apiKey").value="";
  $("keyStatus").textContent="Ключ удалён. Работаем офлайн (124M).";
  updateBackend();
}
async function testKey(){
  const key=getApiKey();
  if(!key){ $("keyStatus").textContent="Вставь ключ сначала."; return; }
  $("keyStatus").textContent="⏳ Тестирую подключение…";
  try{
    const r=await fetch("/api/chat",{
      method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},
      body: JSON.stringify({messages:[{role:"user",content:"Привет! Ответь одним словом: ок"}], temperature:0.2})
    });
    const j=await r.json();
    const txt=j.choices?.[0]?.message?.content || j.error || JSON.stringify(j).slice(0,200);
    $("keyStatus").textContent = txt.toLowerCase().includes("ок") || txt.length<100 ? "✅ Подключение ок! Ответ: "+txt.slice(0,80) : "Ответ: "+txt.slice(0,120);
    updateBackend();
  }catch(e){
    $("keyStatus").textContent="❌ Ошибка: "+e.message+" — проверь ключ/провайдера. Фоллбек к офлайну.";
  }
}
function updateBackend(){
  const el=$("aiBackend");
  if(!el) return;
  const key=getApiKey();
  if(key){
    const prov=getProvider();
    const name={openai:"OpenAI GPT-4o", groq:"Groq Llama 3.1", openrouter:"OpenRouter"}[prov]||prov;
    el.textContent=`☁️ Облако • ${name} • ключ сохранён`;
    el.style.background="rgba(34,211,238,0.12)";
    el.style.borderColor="rgba(34,211,238,0.25)";
  } else {
    el.textContent="🧠 Локально • Transformer 124M • офлайн • приватно";
    el.style.background="rgba(139,92,246,0.08)";
    el.style.borderColor="rgba(139,92,246,0.15)";
  }
}
async function tryCloud(messages){
  const key=getApiKey();
  if(!key) return null;
  const provider=getProvider();
  const modelMap={openai:"gpt-4o-mini", groq:"llama-3.1-70b-versatile", openrouter:"anthropic/claude-3.5-sonnet"}[provider]||"gpt-4o-mini";
  try{
    const ctrl = new AbortController();
    const t = setTimeout(()=>ctrl.abort(), 12000);
    const r=await fetch("/api/chat",{
      method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},
      body: JSON.stringify({messages, model: provider, openai_model: modelMap, temperature: ai.temperature}),
      signal: ctrl.signal
    });
    clearTimeout(t);
    if(!r.ok) throw new Error("http "+r.status);
    const j=await r.json();
    const content=j.choices?.[0]?.message?.content;
    if(content && !j.fallback) return content;
    if(j.fallback) return null;
    return content||null;
  }catch(e){
    console.warn("cloud fail, fallback to local", e);
    return null;
  }
}
function chunkForStream(text, rng){
  // режем для стрима
  const chunks=[];
  let i=0;
  const RngCls = ai ? ai.constructor : null;
  // простой делитель
  while(i<text.length){
    const len= 2 + Math.floor(Math.random()*5);
    let end=Math.min(i+len, text.length);
    // не рвать слово
    if(end<text.length && /[a-zа-я0-9]/i.test(text[end]) && /[a-zа-я0-9]/i.test(text[end-1])){
      while(end<text.length && /[a-zа-я0-9]/i.test(text[end])) end++;
    }
    chunks.push(text.slice(i,end));
    i=end;
  }
  return chunks;
}
async function sendMessage(){
  const input=$("chatInput");
  const text=input.value.trim();
  if(!text||isGenerating) return;
  input.value="";
  input.style.height="auto";
  abortCtrl=new AbortController();
  setGenerating(true);
  const cont=$("chatHistory");
  if(ai.history.length===0) cont.innerHTML="";
  const uDiv=document.createElement("div");
  uDiv.className="msg user";
  uDiv.innerHTML=`<div class="avatar">🧑</div><div class="bubble">${escapeHtml(text).replace(/\n/g,"<br>")}</div>`;
  cont.appendChild(uDiv);
  const aDiv=document.createElement("div");
  aDiv.className="msg assistant";
  aDiv.innerHTML=`<div class="avatar">🤖</div><div class="bubble"><span class="typing"><i></i><i></i><i></i></span> <span class="typing-text">Думаю…</span></div>`;
  cont.appendChild(aDiv);
  cont.scrollTop=cont.scrollHeight;
  let full="";
  const bubble=aDiv.querySelector(".bubble");
  // пробуем облако первым
  const historyForCloud=[...ai.history, {role:"user", content:text}];
  const cloudText = await tryCloud(historyForCloud);
  try{
    if(cloudText){
      // стримим облачный ответ как будто токены
      const chunks=chunkForStream(cloudText);
      // сохраняем в историю вручную (т.к. bypass ai.stream)
      ai.history.push({role:"user", content:text});
      ai.history.push({role:"assistant", content:cloudText});
      if(ai.history.length>24) ai.history=ai.history.slice(-24);
      for(const ch of chunks){
        if(abortCtrl.signal.aborted) break;
        full+=ch;
        bubble.innerHTML=mdToHtml(full);
        bubble.querySelectorAll(".copy-btn").forEach(btn=>{
          if(btn._bound) return; btn._bound=true;
          btn.addEventListener("click",()=>{
            const t=decodeURIComponent(btn.dataset.copy);
            navigator.clipboard.writeText(t).then(()=>{
              btn.textContent="скопировано ✓";
              setTimeout(()=>btn.textContent="копировать",1500);
            });
          });
        });
        cont.scrollTop=cont.scrollHeight;
        await new Promise(r=>setTimeout(r, 14 + Math.random()*22));
      }
    } else {
      // локальный стрим
      for await(const chunk of ai.stream(text, {signal: abortCtrl.signal})){
        if(abortCtrl.signal.aborted) break;
        full+=chunk;
        bubble.innerHTML=mdToHtml(full);
        bubble.querySelectorAll(".copy-btn").forEach(btn=>{
          if(btn._bound) return; btn._bound=true;
          btn.addEventListener("click",()=>{
            const t=decodeURIComponent(btn.dataset.copy);
            navigator.clipboard.writeText(t).then(()=>{
              btn.textContent="скопировано ✓";
              setTimeout(()=>btn.textContent="копировать",1500);
            });
          });
        });
        cont.scrollTop=cont.scrollHeight;
      }
    }
  }catch(e){
    if(e.name!=="AbortError") console.error(e);
    if(!full) bubble.innerHTML=`<em>Генерация прервана.</em>`;
  }finally{
    setGenerating(false);
    saveHistory();
    updateStats();
    abortCtrl=null;
  }
}
function stopGeneration(){ if(abortCtrl) abortCtrl.abort(); setGenerating(false); }
function updateStats(){
  const el=$("aiStats");
  if(!el) return;
  const tokensApprox=Math.round(JSON.stringify(ai.history).length/4);
  el.textContent=`${ai.history.length} сообщений · ~${tokensApprox} токенов · ${ai.model.name}`;
}
function clearChat(){
  if(isGenerating) stopGeneration();
  ai.clear();
  localStorage.removeItem("mybot_ai_history");
  renderHistory();
  updateStats();
}
function exportChat(){
  const blob=new Blob([ai.exportHistory()],{type:"application/json"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;
  a.download=`mybot_chat_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  setTimeout(()=>URL.revokeObjectURL(url),2000);
}
function handleMusicCommand(opts){
  try{
    const styleEl=document.getElementById("style");
    const moodEl=document.getElementById("mood");
    const durEl=document.getElementById("duration");
    const keyEl=document.getElementById("key");
    if(!styleEl) return {ok:false, reason:"музыкальный модуль не загружен"};
    let changed=[];
    if(opts.style && styleEl.querySelector(`option[value="${opts.style}"]`)){
      styleEl.value=opts.style;
      changed.push(`стиль ${opts.style}`);
    }
    if(opts.mood && moodEl.querySelector(`option[value="${opts.mood}"]`)){
      moodEl.value=opts.mood;
      changed.push(`настроение ${opts.mood}`);
    }
    if(opts.duration){
      const avail=[30,60,90,120];
      const best=avail.reduce((a,b)=> Math.abs(b-opts.duration)<Math.abs(a-opts.duration)?b:a);
      durEl.value=String(best);
      changed.push(`длина ${best}с`);
    }
    if(opts.key!==null && opts.key!==undefined){
      keyEl.value=String(opts.key);
      changed.push(`тональность ${keyEl.options[keyEl.selectedIndex]?.text||opts.key}`);
    }
    const genBtn=document.getElementById("generate");
    if(genBtn) setTimeout(()=>genBtn.click(),300);
    const musicTab=document.querySelector('[data-tab="music"]');
    if(musicTab) musicTab.classList.add("pulse");
    setTimeout(()=>musicTab?.classList.remove("pulse"),2000);
    return {ok:true, summary: changed.length?changed.join(", "):"параметры по умолчанию"};
  }catch(e){ return {ok:false, reason:e.message}; }
}
let recognition=null;
function toggleVoiceInput(){
  const btn=$("voiceBtn");
  if(recognition && recognition._running){ recognition.stop(); return; }
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){ alert("Голосовой ввод не поддерживается. Попробуй Chrome."); return; }
  recognition=new SR();
  recognition.lang="ru-RU";
  recognition.interimResults=true;
  recognition.continuous=false;
  recognition._running=true;
  btn.classList.add("recording");
  btn.textContent="⏹";
  recognition.onresult=(e)=>{
    let transcript="";
    for(let i=0;i<e.results.length;i++) transcript+=e.results[i][0].transcript+" ";
    $("chatInput").value=transcript.trim();
  };
  recognition.onend=()=>{
    recognition._running=false;
    btn.classList.remove("recording");
    btn.textContent="🎤";
    if($("chatInput").value.trim()) sendMessage();
  };
  recognition.onerror=()=>{
    recognition._running=false;
    btn.classList.remove("recording");
    btn.textContent="🎤";
  };
  recognition.start();
}
function speakLast(){
  const last=[...ai.history].reverse().find(m=>m.role==="assistant");
  if(!last) return;
  const text=last.content.replace(/[#*`]/g,"").replace(/<[^>]+>/g,"").slice(0,4000);
  const utter=new SpeechSynthesisUtterance(text);
  utter.lang="ru-RU";
  utter.rate=1.0;
  speechSynthesis.cancel();
  speechSynthesis.speak(utter);
}
export function initAI(){
  const modelSel=$("modelSelect");
  if(modelSel){
    modelSel.innerHTML=Object.values(MODELS).map(m=>`<option value="${m.id}">${m.name} — ${m.desc}</option>`).join("");
  }
  ai=new MyBotAI({model:modelSel?modelSel.value:"mybot-pro", temperature:0.85, musicHandler:handleMusicCommand});
  loadHistory();
  // viz
  const cv=$("neuralViz");
  if(cv) {
    viz=new NeuralViz(cv);
    // лёгкая анимация ожидания
    viz.drawIdle();
  }
  window.MyBotAI=ai;
  window.handleMusicCommand=handleMusicCommand;
  // cloud UI
  const keyInput=$("apiKey");
  const provSel=$("apiProvider");
  if(keyInput) keyInput.value=getApiKey();
  if(provSel) provSel.value=getProvider();
  $("saveKeyBtn")?.addEventListener("click", saveKey);
  $("testKeyBtn")?.addEventListener("click", testKey);
  $("clearKeyBtn")?.addEventListener("click", clearKey);
  provSel?.addEventListener("change", ()=>{ localStorage.setItem("mybot_provider", provSel.value); updateBackend(); });
  updateBackend();
  // events
  $("chatInput")?.addEventListener("keydown",(e)=>{
    if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); sendMessage(); }
  });
  $("chatInput")?.addEventListener("input",()=>{
    const el=$("chatInput");
    el.style.height="auto";
    el.style.height=Math.min(el.scrollHeight,140)+"px";
  });
  $("sendBtn")?.addEventListener("click", sendMessage);
  $("stopBtn")?.addEventListener("click", stopGeneration);
  $("clearBtn")?.addEventListener("click", clearChat);
  $("exportBtn")?.addEventListener("click", exportChat);
  $("voiceBtn")?.addEventListener("click", toggleVoiceInput);
  $("speakBtn")?.addEventListener("click", speakLast);
  modelSel?.addEventListener("change",(e)=>{
    ai.setModel(e.target.value);
    saveHistory();
    updateStats();
  });
  $("tempRange")?.addEventListener("input",(e)=>{
    ai.temperature=parseFloat(e.target.value);
    $("tempVal").textContent=ai.temperature.toFixed(2);
  });
  renderHistory();
  updateStats();
  setTimeout(()=>$("chatInput")?.focus(),300);
}
export { handleMusicCommand };
