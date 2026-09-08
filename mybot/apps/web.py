"""Демо 5: веб-приложение для генерации картинок из текста.

Запуск::

    python -m mybot web              # http://0.0.0.0:8000
    python -m mybot web --port 5000

Открой страницу, введи описание — и увидишь сгенерированную картинку.
Работает на стандартном ``http.server``, без Flask и прочих зависимостей.
"""

from __future__ import annotations

import argparse
import io
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..imaging.generator import render_scene
from ..imaging.prompt import OBJECT_WORDS, parse

EXAMPLES = [
    "закат над горами и море, лодка",
    "звёздная ночь, полная луна и лес",
    "неоновый город ночью, киберпанк",
    "зимний лес, снег и домик",
    "космос, планета с кольцами и звёзды",
    "радуга над полем с цветами",
    "гроза над городом, молния",
    "рассвет в горах, туман",
]

PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MyBot — картинка из текста</title>
<style>
  :root { --bg:#0e1020; --card:#191c33; --accent:#7c5cff; --text:#e8e8f0; --muted:#9aa0c0; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: radial-gradient(1200px 600px at 50% -10%, #26234d, var(--bg));
         color: var(--text); min-height:100vh; }
  .wrap { max-width: 860px; margin: 0 auto; padding: 32px 20px 60px; }
  h1 { font-size: 28px; margin: 0 0 4px; }
  .sub { color: var(--muted); margin: 0 0 24px; font-size: 15px; }
  .card { background: var(--card); border:1px solid #2a2e50; border-radius:16px; padding:20px;
          box-shadow: 0 20px 60px rgba(0,0,0,.35); }
  .row { display:flex; gap:10px; flex-wrap:wrap; }
  input[type=text]{ flex:1 1 320px; padding:14px 16px; border-radius:12px; border:1px solid #33385f;
         background:#0f1226; color:var(--text); font-size:16px; outline:none; }
  input[type=text]:focus{ border-color: var(--accent); }
  button { padding:14px 22px; border:none; border-radius:12px; cursor:pointer;
           background: var(--accent); color:white; font-size:16px; font-weight:600; }
  button:disabled{ opacity:.6; cursor:wait; }
  .opts { display:flex; gap:16px; align-items:center; margin-top:12px; color:var(--muted); font-size:14px; flex-wrap:wrap;}
  select { background:#0f1226; color:var(--text); border:1px solid #33385f; border-radius:8px; padding:6px 8px; }
  .examples { margin-top:16px; display:flex; gap:8px; flex-wrap:wrap; }
  .chip { background:#23264a; border:1px solid #33385f; color:var(--muted); padding:7px 12px;
          border-radius:999px; cursor:pointer; font-size:13px; }
  .chip:hover { color:var(--text); border-color:var(--accent); }
  .stage { margin-top:22px; text-align:center; }
  .stage img { max-width:100%; border-radius:14px; border:1px solid #2a2e50; background:#000;
               box-shadow:0 16px 50px rgba(0,0,0,.5); }
  .meta { margin-top:12px; color:var(--muted); font-size:13px; min-height:18px; }
  .foot { margin-top:28px; color:var(--muted); font-size:12px; text-align:center; }
  a { color: var(--accent); }
</style>
</head>
<body>
<div class="wrap">
  <h1>🧠 MyBot — картинка из текста</h1>
  <p class="sub">Опиши сцену словами (русский или английский). Генератор написан на чистом
     Python — без нейросетей-гигантов, API и зависимостей.</p>

  <div class="card">
    <div class="row">
      <input id="prompt" type="text" placeholder="например: закат над горами и море, лодка"
             value="закат над горами и море, лодка" autocomplete="off">
      <button id="go">Сгенерировать</button>
    </div>
    <div class="opts">
      <label>Размер:
        <select id="size">
          <option value="384">384</option>
          <option value="512" selected>512</option>
          <option value="640">640</option>
          <option value="768">768</option>
        </select>
      </label>
      <label><input type="checkbox" id="caption" checked> подпись</label>
      <label><input type="checkbox" id="random"> случайный вид</label>
    </div>
    <div class="examples" id="examples"></div>
  </div>

  <div class="stage">
    <img id="img" alt="здесь появится картинка" />
    <div class="meta" id="meta"></div>
  </div>

  <p class="foot">Движок понимает: %OBJECTS%.<br>
     Часть проекта <b>MyBot</b> — нейросети и графика на чистом Python.</p>
</div>

<script>
const EXAMPLES = %EXAMPLES%;
const ex = document.getElementById('examples');
EXAMPLES.forEach(t => {
  const c = document.createElement('span');
  c.className = 'chip'; c.textContent = t;
  c.onclick = () => { document.getElementById('prompt').value = t; generate(); };
  ex.appendChild(c);
});

const img = document.getElementById('img');
const meta = document.getElementById('meta');
const btn = document.getElementById('go');

async function generate() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) return;
  const size = document.getElementById('size').value;
  const caption = document.getElementById('caption').checked ? 1 : 0;
  const rnd = document.getElementById('random').checked;
  btn.disabled = true; meta.textContent = 'рисую...';
  const params = new URLSearchParams({prompt, size, caption});
  if (rnd) params.set('seed', Math.floor(Math.random()*1e9));
  try {
    const r = await fetch('/api/generate?' + params.toString());
    if (!r.ok) throw new Error(await r.text());
    const info = JSON.parse(r.headers.get('X-Scene') || '{}');
    const blob = await r.blob();
    img.src = URL.createObjectURL(blob);
    meta.textContent = `палитра: ${info.palette} · объекты: ${(info.objects||[]).join(', ') || '—'} · стиль: ${info.style}`;
  } catch(e) {
    meta.textContent = 'ошибка: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}
btn.onclick = generate;
document.getElementById('prompt').addEventListener('keydown', e => { if (e.key === 'Enter') generate(); });
window.addEventListener('load', generate);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # тише в консоли
        pass

    def _page(self) -> bytes:
        html = (PAGE
                .replace("%EXAMPLES%", json.dumps(EXAMPLES, ensure_ascii=False))
                .replace("%OBJECTS%", ", ".join(sorted(OBJECT_WORDS))))
        return html.encode("utf-8")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = self._page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/generate":
            qs = urllib.parse.parse_qs(parsed.query)
            prompt = (qs.get("prompt", [""])[0]).strip()
            if not prompt:
                self.send_error(400, "empty prompt")
                return
            try:
                size = max(128, min(1024, int(qs.get("size", ["512"])[0])))
            except ValueError:
                size = 512
            caption = qs.get("caption", ["1"])[0] not in ("0", "false", "no")
            seed = None
            if "seed" in qs:
                try:
                    seed = int(qs["seed"][0])
                except ValueError:
                    seed = None

            scene = parse(prompt, seed=seed)
            canvas = render_scene(scene, size, int(size * 0.75), caption=caption)
            png = canvas.to_png_bytes()
            info = json.dumps({"palette": scene.palette.name,
                               "objects": scene.objects,
                               "style": scene.style}, ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.send_header("X-Scene", info)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(png)
            return

        self.send_error(404, "not found")


def cli() -> None:
    parser = argparse.ArgumentParser(description="Веб-приложение для генерации картинок из текста")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("MyBot image server: http://%s:%d" % (args.host, args.port))
    print("Ctrl+C для остановки.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")
        server.shutdown()


if __name__ == "__main__":
    cli()
