/* PRE-MENU: "ImCarpa" costruito a blocchi 3D (three.js). Click / Invio per entrare. */
(() => {
  const root = document.documentElement;
  const el = document.getElementById('intro');
  if (!el) return;
  const finish = () => { root.classList.remove('intro'); root.classList.add('entered'); el.remove(); };
  if (!root.classList.contains('intro') || typeof THREE === 'undefined') { finish(); return; }
  start().catch(finish);

  async function start() {
    try { await Promise.race([document.fonts.load('800 120px Outfit'), new Promise(r => setTimeout(r, 1500))]); } catch (e) {}

    /* 1. campiona il testo su un canvas 2D -> griglia di celle */
    const TEXT = 'ImCarpa', FS = 120, STEP = 5, DEPTH = 3, U = 0.5;
    const font = `800 ${FS}px Outfit, "Arial Black", sans-serif`;
    const c2 = document.createElement('canvas');
    const g = c2.getContext('2d', { willReadFrequently: true });
    g.font = font;
    c2.width = Math.ceil(g.measureText(TEXT).width) + 20;
    c2.height = Math.ceil(FS * 1.3);
    g.font = font; g.fillStyle = '#fff';
    g.fillText(TEXT, 10, FS * 1.02);
    const px = g.getImageData(0, 0, c2.width, c2.height).data;
    const cells = [];
    let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
    for (let y = 0; y < c2.height; y += STEP) for (let x = 0; x < c2.width; x += STEP) {
      const a = px[((y + (STEP >> 1)) * c2.width + x + (STEP >> 1)) * 4 + 3];
      if (a > 110) {
        const ix = x / STEP, iy = y / STEP;
        cells.push([ix, iy]);
        if (ix < minX) minX = ix; if (ix > maxX) maxX = ix;
        if (iy < minY) minY = iy; if (iy > maxY) maxY = iy;
      }
    }
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, W = (maxX - minX + 2) * U;
    const N = cells.length * DEPTH;

    /* 2. scena */
    const canvas = el.querySelector('canvas');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 1);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 400);
    const group = new THREE.Group();
    scene.add(group);
    scene.add(new THREE.AmbientLight(0x6d28d9, 0.95));
    const key = new THREE.DirectionalLight(0xe9d5ff, 1.05); key.position.set(6, 10, 14); scene.add(key);
    const rim = new THREE.DirectionalLight(0x7c3aed, 0.9); rim.position.set(-10, -4, 6); scene.add(rim);
    const pulse = new THREE.PointLight(0xa78bfa, 0, 90); pulse.position.set(0, 0, 14); scene.add(pulse);

    const geo = new THREE.BoxGeometry(U * 0.92, U * 0.92, U * 0.92);
    const mat = new THREE.MeshStandardMaterial({ roughness: 0.4, metalness: 0.2 });
    const mesh = new THREE.InstancedMesh(geo, mat, N);
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    group.add(mesh);

    const size = () => {
      const w = innerWidth, h = innerHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      const d = (W / 2 * 1.2) / (Math.tan(camera.fov * Math.PI / 360) * camera.aspect);
      camera.position.set(0, 0, Math.max(d, 26));
      camera.updateProjectionMatrix();
    };
    size();
    addEventListener('resize', size);

    /* 3. dati per ogni blocco */
    const tx = new Float32Array(N), ty = new Float32Array(N), tz = new Float32Array(N);
    const sx = new Float32Array(N), sy = new Float32Array(N), sz = new Float32Array(N);
    const r0 = new Float32Array(N * 3), delay = new Float32Array(N), dur = new Float32Array(N);
    const cx_ = new Float32Array(N), cy_ = new Float32Array(N), cz_ = new Float32Array(N);
    const rx = new Float32Array(N), ry = new Float32Array(N), rz = new Float32Array(N), sc = new Float32Array(N);
    const vx = new Float32Array(N), vy = new Float32Array(N), vz = new Float32Array(N);
    const wx = new Float32Array(N), wy = new Float32Array(N), wz = new Float32Array(N);
    const shades = [0x3b0764, 0x4c1d95, 0x5b21b6, 0x6d28d9, 0x7c3aed, 0x8b5cf6, 0xa78bfa];
    const col = new THREE.Color();
    const rnd = (a, b) => a + Math.random() * (b - a);
    let i = 0, buildEnd = 0;
    for (const [ix, iy] of cells) {
      for (let k = 0; k < DEPTH; k++, i++) {
        tx[i] = (ix - cx) * U; ty[i] = -(iy - cy) * U; tz[i] = (k - (DEPTH - 1) / 2) * U;
        /* partenza esplosiva: da un punto lontano a caso, davanti o dietro */
        let dx = rnd(-1, 1), dy = rnd(-1, 1), dz = rnd(-0.4, 1.4);
        const l = Math.hypot(dx, dy, dz) || 1, R = rnd(22, 60);
        sx[i] = tx[i] + dx / l * R; sy[i] = ty[i] + dy / l * R; sz[i] = tz[i] + dz / l * R;
        r0[i * 3] = rnd(-9, 9); r0[i * 3 + 1] = rnd(-9, 9); r0[i * 3 + 2] = rnd(-9, 9);
        delay[i] = ((ix - minX) / (maxX - minX)) * 1.5 + Math.random() * 0.5;
        dur[i] = rnd(0.7, 1.15);
        buildEnd = Math.max(buildEnd, delay[i] + dur[i]);
        const s = shades[Math.min(shades.length - 1, Math.floor(Math.pow(Math.random(), 0.8) * (shades.length - 1) + (k === DEPTH - 1 ? 1.2 : 0)))];
        col.setHex(s);
        mesh.setColorAt(i, col);
      }
    }
    mesh.instanceColor.needsUpdate = true;
    buildEnd += 0.15;

    const dummy = new THREE.Object3D();
    const put = j => {
      dummy.position.set(cx_[j], cy_[j], cz_[j]);
      dummy.rotation.set(rx[j], ry[j], rz[j]);
      dummy.scale.setScalar(sc[j]);
      dummy.updateMatrix();
      mesh.setMatrixAt(j, dummy.matrix);
    };
    const easeBack = p => { const c1 = 1.5, c3 = c1 + 1, q = p - 1; return 1 + c3 * q * q * q + c1 * q * q; };
    const easeOut = p => 1 - Math.pow(1 - p, 3);

    /* 4. stato e ciclo */
    let state = 'build', t0 = performance.now(), last = t0, exitT = 0, flash = 0, raf = 0;
    let tRY = 0, tRX = 0;
    const hint = el.querySelector('.intro-hint');
    addEventListener('pointermove', e => {
      tRY = (e.clientX / innerWidth - 0.5) * 0.7;
      tRX = (e.clientY / innerHeight - 0.5) * 0.4;
    }, { passive: true });

    const enter = () => {
      if (state === 'exit') return;
      state = 'exit'; exitT = 0;
      if (hint) hint.classList.remove('show');
      for (let j = 0; j < N; j++) {
        const l = Math.hypot(cx_[j], cy_[j], cz_[j] + 2) || 1, sp = rnd(8, 30);
        vx[j] = cx_[j] / l * sp + rnd(-4, 4);
        vy[j] = cy_[j] / l * sp + rnd(-4, 4);
        vz[j] = rnd(6, 34);
        wx[j] = rnd(-8, 8); wy[j] = rnd(-8, 8); wz[j] = rnd(-8, 8);
      }
      pulse.intensity = 6; flash = 1;
      setTimeout(() => el.classList.add('out'), 650);
      setTimeout(end, 1450);
    };
    const end = () => {
      cancelAnimationFrame(raf);
      removeEventListener('resize', size);
      removeEventListener('keydown', onKey);
      renderer.dispose(); geo.dispose(); mat.dispose();
      finish();
    };
    const onKey = e => { if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') { e.preventDefault(); enter(); } };
    el.addEventListener('pointerdown', enter);
    addEventListener('keydown', onKey);

    const frame = now => {
      const dt = Math.min((now - last) / 1000, 0.05); last = now;
      const t = (now - t0) / 1000;
      if (state === 'build') {
        for (let j = 0; j < N; j++) {
          const p = Math.min(1, Math.max(0, (t - delay[j]) / dur[j]));
          const e = easeBack(p), o = easeOut(p), inv = 1 - e, ir = 1 - o;
          cx_[j] = tx[j] + (sx[j] - tx[j]) * inv;
          cy_[j] = ty[j] + (sy[j] - ty[j]) * inv;
          cz_[j] = tz[j] + (sz[j] - tz[j]) * inv;
          rx[j] = r0[j * 3] * ir; ry[j] = r0[j * 3 + 1] * ir; rz[j] = r0[j * 3 + 2] * ir;
          sc[j] = p <= 0 ? 0 : Math.min(1, p * 5);
          put(j);
        }
        mesh.instanceMatrix.needsUpdate = true;
        if (t >= buildEnd) { state = 'idle'; flash = 1; pulse.intensity = 5; if (hint) hint.classList.add('show'); }
      } else if (state === 'exit') {
        exitT += dt;
        for (let j = 0; j < N; j++) {
          cx_[j] += vx[j] * dt; cy_[j] += vy[j] * dt; cz_[j] += vz[j] * dt;
          rx[j] += wx[j] * dt; ry[j] += wy[j] * dt; rz[j] += wz[j] * dt;
          sc[j] = Math.max(0, 1 - Math.max(0, exitT - 0.25) * 0.9);
          put(j);
        }
        mesh.instanceMatrix.needsUpdate = true;
      }
      /* colpo di luce + scossa quando si chiude la costruzione */
      if (flash > 0) {
        flash = Math.max(0, flash - dt * 1.8);
        pulse.intensity = flash * 5;
        camera.position.x = (Math.random() - 0.5) * flash * 0.7;
        camera.position.y = (Math.random() - 0.5) * flash * 0.7;
      }
      group.rotation.y += (tRY + Math.sin(t * 0.7) * 0.05 - group.rotation.y) * 0.06;
      group.rotation.x += (tRX - group.rotation.x) * 0.06;
      renderer.render(scene, camera);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
  }
})();
