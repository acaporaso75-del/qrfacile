(() => {
  const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canvas = document.getElementById('mx');
  const hero = document.getElementById('hero');
  const vid = document.getElementById('heroVid');
  if (!canvas || !hero || prefersReduced) return;

  const ctx = canvas.getContext('2d', { alpha: true });

  function resize() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const r = hero.getBoundingClientRect();
    canvas.width = Math.max(1, Math.floor(r.width * dpr));
    canvas.height = Math.max(1, Math.floor(r.height * dpr));
    canvas.style.width = r.width + 'px';
    canvas.style.height = r.height + 'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }

  const cols = 54, rows = 54;
  let t0 = performance.now();

  const pattern = new Array(cols * rows);
  let seed = 1337;
  function rnd() { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; }

  for (let y=0; y<rows; y++){
    for (let x=0; x<cols; x++){
      const inTL = (x<9 && y<9);
      const inTR = (x>cols-10 && y<9);
      const inBL = (x<9 && y>rows-10);
      let v = rnd() > 0.58 ? 1 : 0;
      if (inTL || inTR || inBL) v = 1;
      pattern[y*cols+x] = v;
    }
  }

  function draw(now){
    const dt = (now - t0) / 1000;
    resize();

    const w = hero.clientWidth;
    const h = hero.clientHeight;
    ctx.clearRect(0,0,w,h);

    const videoOk = vid && vid.readyState >= 2 && !vid.paused;
    const alphaBase = videoOk ? 0.25 : 0.55;

    const size = Math.min(w,h) * 0.62;
    const ox = w*0.62 - size/2;
    const oy = h*0.52 - size/2;

    const cell = size / cols;
    const scan = (dt * 1.2) % 1;

    ctx.save();
    ctx.globalAlpha = alphaBase;
    const g = ctx.createRadialGradient(w*0.62,h*0.52,10,w*0.62,h*0.52,size*0.9);
    g.addColorStop(0,'rgba(15,118,110,0.65)');
    g.addColorStop(1,'rgba(15,118,110,0.00)');
    ctx.fillStyle = g;
    ctx.fillRect(0,0,w,h);
    ctx.restore();

    for (let y=0; y<rows; y++){
      for (let x=0; x<cols; x++){
        const v = pattern[y*cols+x];
        if (!v) continue;

        const yy = y / rows;
        const on = (yy < scan) || (yy > scan && yy < scan + 0.05);
        if (!on) continue;

        const px = ox + x*cell;
        const py = oy + y*cell;

        const glow = Math.max(0, 1 - Math.abs(yy - scan) / 0.05);
        const a = alphaBase + glow*0.35;

        ctx.fillStyle = `rgba(15,118,110,${a.toFixed(3)})`;
        ctx.fillRect(px, py, cell*0.86, cell*0.86);

        if (glow > 0.6){
          ctx.fillStyle = `rgba(34,197,94,${(a*0.55).toFixed(3)})`;
          ctx.fillRect(px+cell*0.18, py+cell*0.18, cell*0.18, cell*0.18);
        }
      }
    }

    ctx.save();
    ctx.globalAlpha = videoOk ? 0.45 : 0.75;
    const yScanPx = oy + scan*size;
    ctx.fillStyle = 'rgba(34,197,94,0.45)';
    ctx.fillRect(ox, yScanPx, size, 2);
    ctx.restore();

    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', resize, { passive: true });
  requestAnimationFrame(draw);
})();

