/* ==============================
   IMCARPA PORTFOLIO — script.js
   ============================== */

/* ===== NAVBAR SCROLL ===== */
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 30);
});

/* ===== TYPING EFFECT ===== */
const phrases = [
  'Discord Developer',
  'Bot Developer',
  'Web Developer',
  'Minecraft Builder',
  'Full Stack Dev',
];

const typedEl = document.getElementById('typed');
let pIdx = 0, cIdx = 0, deleting = false;

function type() {
  const phrase = phrases[pIdx];
  typedEl.textContent = deleting
    ? phrase.substring(0, --cIdx)
    : phrase.substring(0, ++cIdx);

  let wait = deleting ? 32 : 62;
  if (!deleting && cIdx === phrase.length) { wait = 2000; deleting = true; }
  else if (deleting && cIdx === 0) { deleting = false; pIdx = (pIdx + 1) % phrases.length; wait = 400; }
  setTimeout(type, wait);
}
type();

/* ===== TERMINAL ANIMATION ===== */
const terminalLines = [
  { type: 'comment', text: '# imcarpa.dev — loading profile...' },
  { type: 'prompt',  text: '$ ', cmd: 'whoami' },
  { type: 'output',  text: 'imcarpa · developer · 14y' },
  { type: 'blank' },
  { type: 'prompt',  text: '$ ', cmd: 'cat skills.json' },
  { type: 'output',  text: '{' },
  { type: 'kv',      key: '  "languages"',  val: '["Python","JS","HTML","CSS","Node"]' },
  { type: 'kv',      key: '  "experience"', val: '"2 years"' },
  { type: 'kv',      key: '  "focus"',      val: '"Discord bots, Web, Minecraft"' },
  { type: 'output',  text: '}' },
  { type: 'blank' },
  { type: 'prompt',  text: '$ ', cmd: 'git log --oneline -3' },
  { type: 'output',  text: 'a3f91c2 feat: All-In bot v2.0' },
  { type: 'output',  text: 'b12e4d1 fix: VoltMC plugin crash' },
  { type: 'output',  text: 'c7809fa init: portfolio site' },
  { type: 'blank' },
  { type: 'prompt',  text: '$ ', cmd: 'npm run dev' },
  { type: 'string',  text: '  ✓ Server running at localhost:3000' },
  { type: 'cursor' },
];

const body = document.getElementById('terminal-body');

async function renderTerminal() {
  for (let i = 0; i < terminalLines.length; i++) {
    const l = terminalLines[i];
    const span = document.createElement('span');
    span.classList.add('t-line');

    if (l.type === 'blank') {
      span.innerHTML = '&nbsp;';
      body.appendChild(span);
      continue;
    }
    if (l.type === 'comment') {
      span.innerHTML = `<span class="t-comment">${l.text}</span>`;
      body.appendChild(span);
      await delay(120);
      continue;
    }
    if (l.type === 'prompt') {
      span.innerHTML = `<span class="t-prompt">${l.text}</span><span class="t-cmd"></span>`;
      body.appendChild(span);
      const cmdEl = span.querySelector('.t-cmd');
      await typeText(cmdEl, l.cmd, 58);
      await delay(200);
      continue;
    }
    if (l.type === 'output') {
      span.innerHTML = `<span class="t-output">${escHtml(l.text)}</span>`;
      body.appendChild(span);
      await delay(55);
      continue;
    }
    if (l.type === 'kv') {
      span.innerHTML = `<span class="t-key">${escHtml(l.key)}</span><span class="t-output">: </span><span class="t-val">${escHtml(l.val)}</span>`;
      body.appendChild(span);
      await delay(70);
      continue;
    }
    if (l.type === 'string') {
      span.innerHTML = `<span class="t-string">${escHtml(l.text)}</span>`;
      body.appendChild(span);
      await delay(80);
      continue;
    }
    if (l.type === 'cursor') {
      span.innerHTML = `<span class="t-prompt">$ </span><span class="t-cursor-end"></span>`;
      body.appendChild(span);
      continue;
    }

    body.appendChild(span);
    await delay(60);
  }
}

function typeText(el, text, charDelay) {
  return new Promise(resolve => {
    let i = 0;
    function next() {
      if (i >= text.length) { resolve(); return; }
      el.textContent += text[i++];
      setTimeout(next, charDelay + Math.random() * 25);
    }
    next();
  });
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }
function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

renderTerminal();

/* ===== SCROLL REVEAL ===== */
const revealEls = document.querySelectorAll('.reveal');
const revealObs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('visible'); revealObs.unobserve(e.target); }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
revealEls.forEach(el => revealObs.observe(el));

/* ===== STAFF TABS ===== */
document.querySelectorAll('.staff-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.staff-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.staff-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
  });
});

/* ===== STAFF ACCORDION ===== */
document.querySelectorAll('.staff-row').forEach(row => {
  row.addEventListener('click', () => {
    const entry = row.closest('.staff-entry');
    const isOpen = entry.classList.contains('open');

    // Close all siblings
    entry.closest('.staff-list').querySelectorAll('.staff-entry').forEach(e => e.classList.remove('open'));

    // Toggle clicked
    if (!isOpen) entry.classList.add('open');
  });
});

/* ===== VISITOR COUNTER ===== */
(async function initVisitorCounter() {
  const NS   = 'imcarpa-portfolio-2026';
  const BASE = 'https://api.countapi.xyz';

  const elTotal  = document.getElementById('vc-total');
  const elOnline = document.getElementById('vc-online');
  if (!elTotal || !elOnline) return;

  function fmt(n) {
    return Number(n).toLocaleString('it-IT');
  }

  function setVal(el, val) {
    el.classList.remove('loading');
    el.textContent = val;
  }

  // -- Total visits (hit = increment + return new value) --
  try {
    const res  = await fetch(`${BASE}/hit/${NS}/pageviews`);
    const data = await res.json();
    setVal(elTotal, fmt(data.value));
  } catch {
    setVal(elTotal, '—');
  }

  // -- Online ora: finestra di 5 minuti --
  // Tutti che aprono la pagina nello stesso slot di 5 min incrementano lo stesso counter.
  // Approssimazione onesta: stima quante persone stanno guardando adesso.
  try {
    const slot = Math.floor(Date.now() / 300000); // cambia ogni 5 minuti
    const res  = await fetch(`${BASE}/hit/${NS}/online-${slot}`);
    const data = await res.json();
    setVal(elOnline, data.value);
  } catch {
    setVal(elOnline, '—');
  }
})();

