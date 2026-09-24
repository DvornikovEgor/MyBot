// Отрисовка лягушки в скафандре (canvas). Используется и в игре, и в меню, и в карточках голосования.

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function bodyPath(ctx) {
  ctx.beginPath();
  ctx.moveTo(0, -19);
  ctx.bezierCurveTo(16, -19, 21, -7, 18, 6);
  ctx.bezierCurveTo(16, 16, 9, 21, 0, 21);
  ctx.bezierCurveTo(-9, 21, -16, 16, -18, 6);
  ctx.bezierCurveTo(-21, -7, -16, -19, 0, -19);
  ctx.closePath();
}

/**
 * o: { x, y, suit, dir, walk, dead, ghost, t, scale, vented, suspect, human }
 */
export function drawFrog(ctx, o) {
  const { suit, dir = 1, walk = 0, dead = false, ghost = false, t = 0, scale = 1 } = o;
  const bob = dead ? 0 : Math.sin(walk) * 1.8 + Math.sin(t * 2) * 0.6;
  const float = ghost ? Math.sin(t * 2.2) * 4 : 0;

  ctx.save();
  ctx.translate(o.x, o.y + float);
  ctx.globalAlpha = ghost ? 0.5 : 1;

  // тень
  if (!ghost) {
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    ctx.beginPath();
    ctx.ellipse(0, 22, 17, 6, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.scale(dir * scale, scale);
  ctx.translate(0, bob);

  if (dead) {
    // лужа слизи
    ctx.fillStyle = 'rgba(122,205,90,0.5)';
    ctx.beginPath();
    ctx.ellipse(2, 20, 26, 9, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.rotate(Math.PI / 2);
    ctx.scale(1, 0.62);
  }

  const foot = Math.sin(walk) * 4;

  // лапки
  ctx.fillStyle = suit.dark;
  ctx.beginPath();
  ctx.ellipse(-10, 19 + (dead ? 0 : foot * 0.4), 7, 4.4, -0.25, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(10, 19 - (dead ? 0 : foot * 0.4), 7, 4.4, 0.25, 0, Math.PI * 2);
  ctx.fill();

  // рюкзак-кислородный баллон (кувшинка за спиной)
  ctx.fillStyle = suit.dark;
  roundRect(ctx, -27, -12, 12, 20, 5);
  ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,0.25)';
  roundRect(ctx, -25, -9, 4, 12, 2);
  ctx.fill();

  // тело
  bodyPath(ctx);
  ctx.fillStyle = suit.body;
  ctx.fill();
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = ghost ? 'rgba(255,255,255,0.7)' : suit.dark;
  ctx.stroke();

  // животик
  ctx.beginPath();
  ctx.ellipse(0, 6, 11, 11, 0, 0, Math.PI * 2);
  ctx.fillStyle = suit.belly;
  ctx.globalAlpha = ghost ? 0.35 : 0.55;
  ctx.fill();
  ctx.globalAlpha = ghost ? 0.5 : 1;

  // пятна
  ctx.fillStyle = 'rgba(0,0,0,0.14)';
  ctx.beginPath();
  ctx.ellipse(-11, -2, 3.4, 4.6, 0.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(12, 4, 2.6, 3.4, -0.3, 0, Math.PI * 2);
  ctx.fill();

  // глаза
  const blink = Math.sin(t * 1.7 + (o.x % 7)) > 0.985 ? 0.25 : 1;
  const eyeY = -16;
  for (const ex of [-7.5, 7.5]) {
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.ellipse(ex, eyeY, 6.2, 6.2 * blink, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.35)';
    ctx.lineWidth = 1;
    ctx.stroke();
    if (dead) {
      ctx.strokeStyle = '#222';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(ex - 3.4, eyeY - 3.4);
      ctx.lineTo(ex + 3.4, eyeY + 3.4);
      ctx.moveTo(ex + 3.4, eyeY - 3.4);
      ctx.lineTo(ex - 3.4, eyeY + 3.4);
      ctx.stroke();
    } else {
      ctx.fillStyle = '#1d2b1f';
      ctx.beginPath();
      ctx.ellipse(ex + 1.6, eyeY + 0.6, 2.9, 3.2 * blink, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.9)';
      ctx.beginPath();
      ctx.arc(ex + 0.4, eyeY - 1.6, 1.1, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // стекло шлема
  ctx.beginPath();
  roundRect(ctx, -16, -24, 32, 16, 8);
  ctx.fillStyle = 'rgba(160,235,255,0.28)';
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = 'rgba(20,40,45,0.55)';
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(-11, -21);
  ctx.quadraticCurveTo(-4, -24, 3, -22);
  ctx.strokeStyle = 'rgba(255,255,255,0.55)';
  ctx.lineWidth = 1.6;
  ctx.stroke();

  // рот
  ctx.beginPath();
  if (dead) {
    ctx.arc(0, -2, 5, 0.15 * Math.PI, 0.85 * Math.PI);
    ctx.strokeStyle = '#3a1414';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(3, 2);
    ctx.quadraticCurveTo(11, 5, 14, 1);
    ctx.strokeStyle = '#e0555b';
    ctx.lineWidth = 2.6;
    ctx.stroke();
  } else {
    ctx.arc(0, -5, 6, 0.2 * Math.PI, 0.8 * Math.PI);
    ctx.strokeStyle = 'rgba(20,40,25,0.7)';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  ctx.restore();
}

/** Квадратная аватарка для карточек голосования и меню. */
export function drawFrogAvatar(canvas, suit, opts = {}) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const size = opts.size || 64;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  canvas.style.width = `${size}px`;
  canvas.style.height = `${size}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, size, size);
  drawFrog(ctx, {
    x: size / 2,
    y: size / 2 + 2,
    suit,
    dir: 1,
    t: opts.t || 0,
    walk: opts.walk || 0,
    scale: size / 78,
    ghost: opts.ghost || false,
    dead: opts.dead || false,
  });
}
