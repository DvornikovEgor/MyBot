// NeuralViz — визуализация "мозга" ИИ: слои, нейроны, внимание
// Рисует анимированную сеть на canvas, пульсирует при генерации

export class NeuralViz {
  constructor(canvas) {
    this.cv = canvas;
    this.ctx = canvas.getContext('2d');
    this.active = false;
    this.t = 0;
    this.raf = null;
    this.layers = [6, 8, 8, 6, 4]; // кол-во нейронов по слоям
    this._resize();
    window.addEventListener('resize', () => this._resize());
    this.drawIdle();
  }

  _resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.cv.getBoundingClientRect();
    this.cv.width = Math.max(120, rect.width * dpr);
    this.cv.height = Math.max(80, rect.height * dpr);
    this.ctx.setTransform(dpr,0,0,dpr,0,0);
    this.W = rect.width;
    this.H = rect.height;
  }

  drawIdle() {
    this._draw(0, false);
  }

  start() {
    this.active = true;
    this.t = 0;
    if (this.raf) cancelAnimationFrame(this.raf);
    const loop = () => {
      this.t += 0.06;
      this._draw(this.t, true);
      this.raf = requestAnimationFrame(loop);
    };
    loop();
  }

  stop() {
    this.active = false;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = null;
    // плавно затухаем
    let fade = 0;
    const fadeLoop = () => {
      fade += 0.08;
      this._draw(this.t, false, 1 - fade);
      if (fade < 1) requestAnimationFrame(fadeLoop);
      else this.drawIdle();
    };
    fadeLoop();
  }

  _draw(t, anim, alpha = 1) {
    const g = this.ctx;
    const W = this.W, H = this.H;
    g.clearRect(0,0,W,H);

    // фон
    g.fillStyle = 'rgba(13,16,48,0.9)';
    g.fillRect(0,0,W,H);

    const layerX = [];
    const gap = W / (this.layers.length + 1);
    for (let i=0;i<this.layers.length;i++) layerX.push(gap * (i+1));

    const neurons = []; // [{x,y,layer,idx}]
    for (let li=0; li<this.layers.length; li++) {
      const n = this.layers[li];
      const x = layerX[li];
      for (let ni=0; ni<n; ni++) {
        const y = (H / (n+1)) * (ni+1);
        neurons.push({x,y,layer:li,idx:ni});
      }
    }

    // связи
    for (let li=0; li<this.layers.length-1; li++) {
      const cur = neurons.filter(n=>n.layer===li);
      const nxt = neurons.filter(n=>n.layer===li+1);
      for (const a of cur) {
        for (const b of nxt) {
          // прореживаем чтобы не перегружать
          if ((a.idx + b.idx) % 2 === 1 && !anim) continue;
          const pulse = anim ? 0.3 + 0.5 * Math.sin(t*1.2 + a.idx*0.7 + b.idx*0.4 + li) : 0.08;
          const op = (anim ? pulse : 0.06) * alpha;
          g.beginPath();
          g.moveTo(a.x, a.y);
          // кривая
          const mx = (a.x + b.x)/2;
          g.bezierCurveTo(mx, a.y, mx, b.y, b.x, b.y);
          g.strokeStyle = `rgba(139,92,246,${op})`;
          g.lineWidth = 1;
          g.stroke();
          // бегущая точка при активности
          if (anim && Math.random() < 0.04) {
            const p = (Math.sin(t*2 + a.idx) + 1)/2;
            const ix = a.x + (b.x - a.x) * p;
            const iy = a.y + (b.y - a.y) * p + Math.sin(p*Math.PI)* -6;
            g.beginPath();
            g.arc(ix, iy, 1.8, 0, Math.PI*2);
            g.fillStyle = `rgba(34,211,238,${0.9*alpha})`;
            g.fill();
          }
        }
      }
    }

    // нейроны
    for (const n of neurons) {
      const isInput = n.layer===0;
      const isOutput = n.layer===this.layers.length-1;
      const base = isInput ? '#22d3ee' : isOutput ? '#e879f9' : '#8b5cf6';
      const pulse = anim ? 0.6 + 0.4*Math.sin(t*1.5 + n.idx*0.9 + n.layer) : 0.35;
      const r = (isInput||isOutput ? 5 : 4) * (anim ? pulse : 1) * (0.7 + 0.3*alpha);
      // свечение
      g.beginPath();
      g.arc(n.x, n.y, r+3, 0, Math.PI*2);
      g.fillStyle = `rgba(139,92,246,${0.15*alpha})`;
      g.fill();
      // ядро
      g.beginPath();
      g.arc(n.x, n.y, r, 0, Math.PI*2);
      g.fillStyle = base;
      g.globalAlpha = alpha;
      g.fill();
      g.globalAlpha = 1;
      // блик
      g.beginPath();
      g.arc(n.x-1, n.y-1, r*0.35, 0, Math.PI*2);
      g.fillStyle = 'rgba(255,255,255,0.6)';
      g.fill();
    }

    // подпись
    g.fillStyle = `rgba(154,160,195,${0.9*alpha})`;
    g.font = '10px system-ui, sans-serif';
    g.textAlign = 'center';
    g.fillText(anim ? '⚡ инференс...' : '🧠 ожидание', W/2, H-6);

    // лейблы слоёв
    const labels = ['вход','вним. 1','вним. 2','скрытый','выход'];
    g.font = '8px system-ui, sans-serif';
    g.fillStyle = `rgba(255,255,255,${0.35*alpha})`;
    for (let i=0;i<layerX.length;i++) {
      g.fillText(labels[i]||'', layerX[i], 10);
    }
  }
}
