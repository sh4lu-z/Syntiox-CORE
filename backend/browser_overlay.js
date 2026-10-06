() => {
  // Runs in every page. Draws the agent overlay and locks user input while the agent is in control.
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  if (window.top !== window || window.__syntiox) return;

  const EXPIRE_MS = 180000;
  const BLOCKED = ['mousedown', 'mouseup', 'click', 'dblclick', 'auxclick', 'contextmenu',
    'pointerdown', 'pointerup', 'mousemove', 'pointermove', 'mouseover', 'mouseout',
    'touchstart', 'touchmove', 'touchend', 'wheel', 'dragstart', 'keydown', 'keypress', 'keyup'];

  const isAgent = window.name === 'syntiox_controlled';
  const state = { active: isAgent, alive: isAgent, mode: 'work', status: '', cursor: null, handoff_done: false };
  let passing = false;
  let appliedAt = isAgent ? Date.now() : 0;
  let cur = { x: -100, y: -100 };
  let placed = false;
  let host = null;
  let box = null;
  const ui = {};

  try {
    CSS.registerProperty({ name: '--syntiox-angle', syntax: '<angle>', inherits: false, initialValue: '0deg' });
  } catch (e) {}

  const CSS_TEXT = `
    .box {
      position: fixed; inset: 0; pointer-events: none;
      font-family: "Segoe UI Variable", "Segoe UI", system-ui, -apple-system, sans-serif;
      --c1: #8b5cf6; --c2: #22d3ee; --c3: #f472b6;
    }
    .box.handoff { --c1: #f59e0b; --c2: #fde047; --c3: #fb7185; }

    .blocker {
      position: fixed; inset: 0; pointer-events: auto; cursor: not-allowed;
      background: radial-gradient(ellipse at center, transparent 55%, rgba(76, 29, 149, 0.12));
    }
    .box.handoff .blocker { display: none; }

    .glow {
      position: fixed; inset: 0; padding: 3px;
      background: conic-gradient(from var(--syntiox-angle), var(--c1), var(--c2), var(--c3), var(--c1));
      -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      -webkit-mask-composite: xor;
      mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      mask-composite: exclude;
      animation: sx-spin 3.5s linear infinite;
    }
    .inner {
      position: fixed; inset: 0;
      box-shadow:
        inset 0 0 24px 2px color-mix(in srgb, var(--c1) 60%, transparent),
        inset 0 0 80px 8px color-mix(in srgb, var(--c2) 22%, transparent);
      animation: sx-pulse 2.4s ease-in-out infinite;
    }

    .banner {
      position: fixed; bottom: 44px; left: 50%; transform: translateX(-50%);
      display: flex; align-items: center; gap: 10px;
      max-width: min(720px, 90vw); padding: 9px 16px 9px 13px;
      border-radius: 999px; pointer-events: auto;
      background: rgba(17, 14, 32, 0.74);
      backdrop-filter: blur(14px) saturate(150%);
      -webkit-backdrop-filter: blur(14px) saturate(150%);
      border: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow:
        0 10px 30px rgba(0, 0, 0, 0.35),
        0 0 0 1px color-mix(in srgb, var(--c1) 35%, transparent),
        0 0 26px color-mix(in srgb, var(--c1) 40%, transparent);
      color: #f5f3ff; font-size: 13px; line-height: 1.3;
      animation: sx-drop 0.45s cubic-bezier(0.22, 1, 0.36, 1);
    }
    .dot {
      flex: none; width: 10px; height: 10px; border-radius: 50%;
      background: conic-gradient(from var(--syntiox-angle), var(--c1), var(--c2), var(--c3), var(--c1));
      box-shadow: 0 0 10px var(--c1);
      animation: sx-spin 1.4s linear infinite;
    }
    .title {
      font-weight: 600; white-space: nowrap;
      background: linear-gradient(90deg, #ffffff, color-mix(in srgb, var(--c2) 70%, #ffffff));
      -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .status {
      min-width: 0; color: rgba(237, 233, 254, 0.78);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .status:not(:empty)::before { content: "\\00B7"; margin-right: 8px; color: rgba(255, 255, 255, 0.35); }
    .btn {
      display: none; flex: none; align-items: center; margin-left: 4px; padding: 6px 15px;
      border: 0; border-radius: 999px; cursor: pointer;
      font-family: inherit; font-size: 12.5px; font-weight: 700; color: #1c1206;
      background: linear-gradient(135deg, var(--c2), var(--c1));
      box-shadow: 0 4px 14px color-mix(in srgb, var(--c1) 50%, transparent);
      transition: transform 0.15s, filter 0.15s;
    }
    .btn:hover { transform: translateY(-1px); filter: brightness(1.08); }
    .box.handoff .btn { display: inline-flex; }

    .stop-btn {
      display: inline-flex; flex: none; align-items: center; margin-left: 4px; padding: 6px 15px;
      border: 0; border-radius: 999px; cursor: pointer; pointer-events: auto;
      font-family: inherit; font-size: 12.5px; font-weight: 700; color: #fff;
      background: linear-gradient(135deg, #f43f5e, #be123c);
      box-shadow: 0 4px 14px color-mix(in srgb, #f43f5e 50%, transparent);
      transition: transform 0.15s, filter 0.15s;
    }
    .stop-btn:hover { transform: translateY(-1px); filter: brightness(1.1); }
    .box.handoff .stop-btn { display: none; }

    .cursor {
      position: fixed; left: 0; top: 0;
      transform: translate(-100px, -100px);
      transition-property: transform, opacity;
      transition-timing-function: cubic-bezier(0.22, 1, 0.36, 1);
      transition-duration: 0.5s;
      will-change: transform;
      filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.35)) drop-shadow(0 0 8px color-mix(in srgb, var(--c1) 70%, transparent));
    }
    .cursor svg { display: block; transition: transform 0.12s; }
    .cursor path { fill: var(--c1); }
    .cursor.press svg { transform: scale(0.82); }
    .box.handoff .cursor { opacity: 0; }

    .ripple {
      position: fixed; width: 16px; height: 16px; margin: -8px 0 0 -8px;
      border-radius: 50%; border: 2px solid var(--c2);
      box-shadow: 0 0 12px var(--c1);
      animation: sx-ripple 0.6s ease-out forwards;
    }
    .hl {
      position: fixed; border-radius: 8px;
      border: 2px solid var(--c2);
      background: color-mix(in srgb, var(--c2) 8%, transparent);
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--c1) 25%, transparent),
        0 0 18px color-mix(in srgb, var(--c1) 60%, transparent);
      animation: sx-hl 0.25s ease-out;
      transition: opacity 0.35s;
    }

    .powered-by {
      position: fixed; bottom: 12px; left: 50%; transform: translateX(-50%);
      font-size: 10px; font-weight: 600;
      color: #ffd700; text-decoration: none;
      background: rgba(0, 0, 0, 0.55);
      padding: 4px 12px;
      border-radius: 999px;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid rgba(255, 215, 0, 0.3);
      box-shadow: 0 0 8px rgba(255, 215, 0, 0.15);
      pointer-events: auto; cursor: pointer;
      letter-spacing: 0.5px;
      transition: all 0.2s ease;
    }
    .powered-by:hover {
      background: rgba(255, 215, 0, 0.15);
      box-shadow: 0 0 12px rgba(255, 215, 0, 0.3);
      color: #fff;
    }

    @keyframes sx-spin { to { --syntiox-angle: 360deg; } }
    @keyframes sx-pulse { 0%, 100% { opacity: 0.55; } 50% { opacity: 1; } }
    @keyframes sx-drop {
      from { opacity: 0; transform: translate(-50%, 14px) scale(0.96); }
      to { opacity: 1; transform: translate(-50%, 0) scale(1); }
    }
    @keyframes sx-ripple { from { transform: scale(0.4); opacity: 1; } to { transform: scale(3.4); opacity: 0; } }
    @keyframes sx-hl { from { opacity: 0; transform: scale(1.08); } to { opacity: 1; transform: scale(1); } }

    @media (prefers-reduced-motion: reduce) {
      .glow, .inner, .dot { animation: none; }
      .cursor { transition: none !important; }
    }
  `;

  const make = (tag, cls, parent) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (parent) parent.appendChild(node);
    return node;
  };

  // Built with createElement instead of innerHTML so Trusted Types pages don't break it
  function buildCursor(parent) {
    const NS = 'http://www.w3.org/2000/svg';
    const wrap = make('div', 'cursor', parent);
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', '24');
    svg.setAttribute('height', '24');
    svg.setAttribute('viewBox', '0 0 24 24');
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', 'M4 2.5 L20 11.4 L12.6 13.3 L9.2 20.8 Z');
    path.setAttribute('stroke', '#ffffff');
    path.setAttribute('stroke-width', '1.6');
    path.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(path);
    wrap.appendChild(svg);
    return wrap;
  }

  function build() {
    host = document.createElement('syntiox-overlay');
    host.style.setProperty('position', 'fixed', 'important');
    host.style.setProperty('inset', '0', 'important');
    host.style.setProperty('z-index', '2147483647', 'important');
    host.style.setProperty('pointer-events', 'none', 'important');
    host.style.setProperty('display', 'none', 'important');
    const root = host.attachShadow({ mode: 'closed' });
    try {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(CSS_TEXT);
      root.adoptedStyleSheets = [sheet];
    } catch (e) {
      make('style', null, root).textContent = CSS_TEXT;
    }
    box = make('div', 'box', root);
    ui.blocker = make('div', 'blocker', box);
    make('div', 'glow', box);
    make('div', 'inner', box);
    ui.banner = make('div', 'banner', box);
    make('span', 'dot', ui.banner);
    ui.title = make('span', 'title', ui.banner);
    ui.status = make('span', 'status', ui.banner);
    ui.btn = make('button', 'btn', ui.banner);
    ui.btn.type = 'button';
    ui.btn.textContent = 'Continue';
    ui.btn.addEventListener('click', onContinue);
    
    ui.stopBtn = make('button', 'stop-btn', ui.banner);
    ui.stopBtn.type = 'button';
    ui.stopBtn.textContent = 'STOP AGENT';
    ui.stopBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        Object.assign(state, { stopped_by_user: true, status: 'Stopping...' });
        render();
    });
    
    ui.poweredBy = make('a', 'powered-by', box);
    ui.poweredBy.textContent = 'Powered by sh4lu-z';
    ui.poweredBy.href = 'https://www.google.com/search?q=who+is+shaluka+gimhan';
    ui.poweredBy.target = '_blank';
    
    ui.cursor = buildCursor(box);
  }

  function attach() {
    if (!host) build();
    const parent = document.documentElement;
    if (!parent) return false;
    if (host.parentNode !== parent) parent.appendChild(host);
    return true;
  }

  const shown = () => !!(state.active && state.alive);
  const blocking = () => shown() && state.mode === 'work' && !passing;

  function setCursor(x, y) {
    ui.cursor.style.transform = `translate(${x - 4}px, ${y - 3}px)`;
    cur = { x, y };
  }

  function render() {
    if (!attach()) return;
    const on = shown();
    host.style.setProperty('display', on ? 'block' : 'none', 'important');
    if (!on) return;
    const handoff = state.mode === 'handoff';
    box.className = handoff ? 'box handoff' : 'box';
    ui.blocker.style.pointerEvents = passing ? 'none' : 'auto';
    ui.title.textContent = handoff ? 'Your turn' : 'Syntiox Agent is working';
    ui.status.textContent = state.status || (handoff ? 'Finish this step, then press Continue' : '');
    if (!placed) {
      const c = state.cursor || [innerWidth / 2, innerHeight / 2];
      ui.cursor.style.transitionDuration = '0ms';
      setCursor(c[0], c[1]);
      void ui.cursor.offsetWidth;
      placed = true;
    }
  }

  function moveTo(x, y) {
    if (!attach()) return 0;
    if (!shown()) {
      ui.cursor.style.transitionDuration = '0ms';
      setCursor(x, y);
      placed = true;
      return 0;
    }
    const d = Math.hypot(x - cur.x, y - cur.y);
    const ms = Math.round(Math.min(900, Math.max(200, d * 0.7)));
    ui.cursor.style.transitionDuration = ms + 'ms';
    setCursor(x, y);
    placed = true;
    return ms;
  }

  function ripple(x, y) {
    if (!shown()) return;
    ui.cursor.classList.add('press');
    setTimeout(() => ui.cursor.classList.remove('press'), 160);
    const r = make('div', 'ripple');
    r.style.left = x + 'px';
    r.style.top = y + 'px';
    box.insertBefore(r, ui.cursor);
    setTimeout(() => r.remove(), 700);
  }

  function highlight(rect, ms) {
    if (!shown() || !rect) return;
    const pad = 4;
    const wait = ms || 1100;
    const h = make('div', 'hl');
    h.style.left = (rect.x - pad) + 'px';
    h.style.top = (rect.y - pad) + 'px';
    h.style.width = (rect.width + pad * 2) + 'px';
    h.style.height = (rect.height + pad * 2) + 'px';
    box.insertBefore(h, ui.cursor);
    setTimeout(() => { h.style.opacity = '0'; }, wait);
    setTimeout(() => h.remove(), wait + 400);
  }

  function setPass(on) {
    passing = !!on;
    if (ui.blocker) ui.blocker.style.pointerEvents = passing ? 'none' : 'auto';
    return passing;
  }

  function capture(on) {
    if (host) host.style.visibility = on ? 'hidden' : 'visible';
  }

  function apply(s) {
    if (s && typeof s === 'object') Object.assign(state, s);
    appliedAt = Date.now();
    render();
    return Object.assign({}, state);
  }

  async function sync() {
    if (typeof window.__syntioxGet !== 'function') {
      // No manager binding, hide on our own if the agent went quiet
      if (state.alive && Date.now() - appliedAt > EXPIRE_MS) {
        state.alive = false;
        render();
      } else if (shown()) {
        attach();
      }
      return;
    }
    try {
      const s = await window.__syntioxGet();
      if (s) {
        Object.assign(state, s);
        render();
      }
    } catch (e) {}
  }

  function heartbeat() {
    appliedAt = Date.now();
    return Object.assign({}, state);
  }

  async function onContinue(e) {
    e.preventDefault();
    e.stopPropagation();
    const patch = { handoff_done: true, mode: 'work', status: 'Continuing...' };
    Object.assign(state, patch);
    render();
    if (typeof window.__syntioxSet === 'function') {
      try { await window.__syntioxSet(patch); } catch (err) {}
    }
  }

  // Only real user input is dropped, the page's own synthetic events still go through
  function guard(e) {
    if (!e.isTrusted || !blocking()) return;
    e.stopImmediatePropagation();
    if (e.cancelable) e.preventDefault();
  }
  BLOCKED.forEach((t) => window.addEventListener(t, guard, { capture: true, passive: false }));

  Object.defineProperty(window, '__syntiox', {
    value: {
      apply, sync, moveTo, ripple, highlight, capture, heartbeat,
      pass: setPass,
      localState: () => Object.assign({}, state),
    },
    enumerable: false,
    configurable: true,
  });

  sync();
  document.addEventListener('DOMContentLoaded', () => render());
  setInterval(sync, 2000);
}
