(() => {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const delay = ms => new Promise(r => setTimeout(r, ms));
  const esc = t => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  /* navbar ombra allo scroll */
  const navbar = $('#navbar');
  addEventListener('scroll', () => navbar.classList.toggle('scrolled', scrollY > 30), { passive: true });

  /* ===== TYPED ===== */
  const typedEl = $('#typed');
  if (typedEl) {
    const phrases = ['Discord Developer', 'Bot Developer', 'Web Developer', 'Minecraft Builder', 'Full Stack Dev'];
    let p = 0, c = 0, del = false;
    (function tick() {
      const ph = phrases[p];
      typedEl.textContent = del ? ph.substring(0, --c) : ph.substring(0, ++c);
      let w = del ? 32 : 62;
      if (!del && c === ph.length) { w = 2000; del = true; }
      else if (del && c === 0) { del = false; p = (p + 1) % phrases.length; w = 400; }
      setTimeout(tick, w);
    })();
  }

  /* ===== TERMINALE ===== */
  const tb = $('#terminal-body');
  if (tb) {
    const L = [
      ['comment', '# imcarpa.dev — loading profile...'],
      ['prompt', 'whoami'], ['output', 'imcarpa · developer · 14y'], ['blank'],
      ['prompt', 'cat skills.json'], ['output', '{'],
      ['kv', '  "languages"', '["Python","JS","HTML","CSS","Node"]'],
      ['kv', '  "experience"', '"2 years"'],
      ['kv', '  "focus"', '"Discord bots, Web, Minecraft"'], ['output', '}'], ['blank'],
      ['prompt', 'git log --oneline -3'],
      ['output', 'a3f91c2 feat: All-In bot v2.0'], ['output', 'b12e4d1 fix: VoltMC plugin crash'], ['output', 'c7809fa init: portfolio site'], ['blank'],
      ['prompt', 'npm run dev'], ['string', '  ✓ Server running at localhost:3000'], ['cursor'],
    ];
    const typeInto = async (el, t) => { for (const ch of t) { el.textContent += ch; await delay(55 + Math.random() * 25); } };
    (async () => {
      for (const [t, a, b] of L) {
        const s = document.createElement('span');
        s.className = 't-line';
        if (t === 'blank') { s.innerHTML = '&nbsp;'; tb.appendChild(s); continue; }
        if (t === 'comment') { s.innerHTML = `<span class="t-comment">${esc(a)}</span>`; tb.appendChild(s); await delay(120); continue; }
        if (t === 'prompt') { s.innerHTML = '<span class="t-prompt">$ </span><span class="t-cmd"></span>'; tb.appendChild(s); await typeInto(s.querySelector('.t-cmd'), a); await delay(200); continue; }
        if (t === 'output') { s.innerHTML = `<span class="t-output">${esc(a)}</span>`; tb.appendChild(s); await delay(55); continue; }
        if (t === 'kv') { s.innerHTML = `<span class="t-key">${esc(a)}</span><span class="t-output">: </span><span class="t-val">${esc(b)}</span>`; tb.appendChild(s); await delay(70); continue; }
        if (t === 'string') { s.innerHTML = `<span class="t-string">${esc(a)}</span>`; tb.appendChild(s); await delay(80); continue; }
        if (t === 'cursor') { s.innerHTML = '<span class="t-prompt">$ </span><span class="t-cursor-end"></span>'; tb.appendChild(s); }
      }
    })();
  }

  /* ===== REVEAL ===== */
  const obs = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
  }), { threshold: .1, rootMargin: '0px 0px -40px 0px' });
  $$('.reveal').forEach(el => obs.observe(el));

  /* ===== STAFF ===== */
  $$('.staff-tab').forEach(tab => tab.addEventListener('click', () => {
    $$('.staff-tab').forEach(t => t.classList.remove('active'));
    $$('.staff-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    $('#tab-' + tab.dataset.tab).classList.add('active');
  }));
  $$('.staff-row').forEach(row => row.addEventListener('click', () => {
    const entry = row.closest('.staff-entry');
    const open = entry.classList.contains('open');
    entry.closest('.staff-list').querySelectorAll('.staff-entry').forEach(e => e.classList.remove('open'));
    if (!open) entry.classList.add('open');
  }));

  /* ===== CONTATORE VISITE ===== */
  (async () => {
    const a = $('#vc-total'), b = $('#vc-online');
    if (!a || !b) return;
    const NS = 'imcarpa-portfolio-2026', BASE = 'https://api.countapi.xyz';
    const hit = async (key, el) => {
      try { const d = await (await fetch(`${BASE}/hit/${NS}/${key}`)).json(); el.textContent = Number(d.value).toLocaleString('it-IT'); }
      catch { el.textContent = '—'; }
    };
    hit('pageviews', a);
    hit('online-' + Math.floor(Date.now() / 300000), b);
  })();

  /* ===== ICE TOOL: codice visibile ===== */
  if (!$('#src')) return;
  const src = window.ICE_SRC || '';
  const lines = src.split('\n').length;
  $('#meta').textContent = lines + ' righe · ' + Math.round(src.length / 1024) + ' KB';
  $('#gut').textContent = Array.from({ length: lines }, (_, i) => i + 1).join('\n');
  const re = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|[fFrRbB]{0,2}"(?:\\.|[^"\\\n])*"|[fFrRbB]{0,2}'(?:\\.|[^'\\\n])*')|\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|in|not|and|or|is|None|True|False|lambda|pass|break|continue|raise|yield|global|nonlocal|assert|del)\b|\b(\d+(?:\.\d+)?)\b/g;
  $('#src').textContent = src;
  (window.requestIdleCallback || setTimeout)(() => {
    $('#src').innerHTML = esc(src).replace(re, (m, c, s, k, n) =>
      c ? `<span class="c">${c}</span>` : s ? `<span class="s">${s}</span>` : k ? `<span class="k">${k}</span>` : `<span class="n">${n}</span>`);
  });
  $('#copy').addEventListener('click', async e => {
    const btn = e.currentTarget;
    try { await navigator.clipboard.writeText(src); btn.textContent = 'Copiato!'; } catch { btn.textContent = 'Copia a mano'; }
    setTimeout(() => (btn.textContent = 'Copia codice'), 1800);
  });
})();
