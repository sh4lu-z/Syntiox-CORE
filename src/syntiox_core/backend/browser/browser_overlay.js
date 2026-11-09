() => {
  // Runs in every page. Draws the agent overlay and locks user input while the agent is in control.
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  if (window.top !== window || window.__syntiox) return;

  const CONFIG = {
    WATERMARK_TEXT: 'sh4lu-z',
    WATERMARK_URL: 'https://www.google.com/search?q=who+is+shaluka+gimhan',
    SYNC_INTERVAL_MS: 2000,
    EXPIRE_MS: 180000,
  };

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
  let syncTimer = null;
  const ui = {};

  try {
    CSS.registerProperty({ name: '--syntiox-angle', syntax: '<angle>', inherits: false, initialValue: '0deg' });
  } catch (e) {}

  const CSS_TEXT = `
    .box {
      position: fixed; inset: 0; pointer-events: none; box-sizing: border-box;
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
      position: fixed; inset: 0; padding: 3px; box-sizing: border-box;
      background: conic-gradient(from var(--syntiox-angle), var(--c1), var(--c2), var(--c3), var(--c1));
      -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      -webkit-mask-composite: xor;
      mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      mask-composite: exclude;
      animation: sx-spin 3.5s linear infinite;
    }
    .inner {
      position: fixed; inset: 0; box-sizing: border-box;
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
      display: flex; flex: none; align-items: center; justify-content: center;
      width: 0; height: 28px; margin-left: 0; padding: 0; overflow: hidden; opacity: 0;
      border: 0; border-radius: 50%; cursor: pointer; pointer-events: auto;
      color: #fff; background: linear-gradient(135deg, #f43f5e, #be123c);
      box-shadow: 0 4px 14px color-mix(in srgb, #f43f5e 50%, transparent);
      transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
    }
    .banner:hover .stop-btn, .banner.shake .stop-btn {
      width: 28px; margin-left: 6px; opacity: 1;
    }
    .stop-btn:hover { transform: translateY(-1px) scale(1.05); filter: brightness(1.1); }
    .box.handoff .stop-btn { display: none; }
    
    @keyframes shake-anim {
      0%, 100% { transform: translateX(-50%); }
      20%, 60% { transform: translateX(calc(-50% - 5px)); }
      40%, 80% { transform: translateX(calc(-50% + 5px)); }
    }
    .banner.shake { animation: shake-anim 0.4s ease-in-out; }
    
    .toast {
      position: absolute; top: 15%; left: 50%; transform: translate(-50%, -20px) scale(0.95);
      display: flex; align-items: center; gap: 12px;
      background: rgba(17, 14, 32, 0.75); color: #fff; padding: 12px 24px;
      border-radius: 99px; font-size: 14px; font-weight: 500; pointer-events: none;
      backdrop-filter: blur(16px) saturate(180%); -webkit-backdrop-filter: blur(16px) saturate(180%);
      border: 1px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 20px 40px rgba(0,0,0,0.5), 0 0 0 1px color-mix(in srgb, var(--c1) 20%, transparent);
      opacity: 0; transition: opacity 0.4s cubic-bezier(0.22, 1, 0.36, 1), transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
      z-index: 10;
    }
    .toast.show { opacity: 1; transform: translate(-50%, 0) scale(1); }
    .toast-icon {
      display: flex; align-items: center; justify-content: center;
      width: 24px; height: 24px; border-radius: 50%;
      background: linear-gradient(135deg, var(--c1), var(--c2));
      color: #fff; font-weight: bold; flex-shrink: 0; font-size: 14px;
      box-shadow: 0 0 10px color-mix(in srgb, var(--c1) 50%, transparent);
    }

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
    }
    .sx-watermark {
      position: fixed; right: 24px; bottom: 24px;
      display: flex; align-items: center; gap: 8px;
      font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;
      text-decoration: none;
      color: rgba(255, 255, 255, 0.35);
      text-shadow: 0 1px 3px rgba(0,0,0,0.8);
      pointer-events: auto;
      transition: color 0.2s, opacity 0.2s;
      z-index: 9999;
      opacity: 0.7;
    }
    .sx-watermark:hover {
      color: rgba(255, 255, 255, 0.9);
      opacity: 1;
    }
    .sx-watermark svg {
      width: 14px; height: 14px; flex: none;
      filter: drop-shadow(0 1px 2px rgba(0,0,0,0.8));
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
    const root = host.attachShadow({ mode: 'open' });
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
    ui.stopBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2"></rect></svg>';
    ui.stopBtn.title = 'Stop Agent';
    ui.stopBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        Object.assign(state, { stopped_by_user: true, status: 'Stopping...' });
        render();
    });
    
    ui.watermark = make('a', 'sx-watermark', box);
    ui.watermark.href = CONFIG.WATERMARK_URL;
    ui.watermark.target = '_blank';
    ui.watermark.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg><span>' + CONFIG.WATERMARK_TEXT + '</span>';
    
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
    // Keep cursor within window bounds to handle resizing nicely
    const clampedX = Math.max(0, Math.min(x, window.innerWidth));
    const clampedY = Math.max(0, Math.min(y, window.innerHeight));
    ui.cursor.style.transform = `translate(${clampedX - 4}px, ${clampedY - 3}px)`;
    cur = { x: clampedX, y: clampedY };
  }

  let renderRequested = false;
  function render() {
    if (renderRequested) return;
    renderRequested = true;
    requestAnimationFrame(_render);
  }

  function _render() {
    renderRequested = false;
    if (!attach()) return;
    const on = shown();
    host.style.setProperty('display', on ? 'block' : 'none', 'important');
    if (!on) return;
    const handoff = state.mode === 'handoff';
    box.className = handoff ? 'box handoff' : 'box';
    ui.blocker.style.pointerEvents = passing ? 'none' : 'auto';
    ui.title.textContent = handoff ? 'Your turn' : 'Syntiox Agent is working';
    ui.status.textContent = state.status || (handoff ? 'Finish this step, then press Continue' : '');
    ui.status.style.display = (handoff || state.status === 'Stopping...') ? '' : 'none';
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
    clearTimeout(syncTimer);
    if (typeof window.__syntioxGet !== 'function') {
      // No manager binding, hide on our own if the agent went quiet
      if (state.alive && Date.now() - appliedAt > CONFIG.EXPIRE_MS) {
        state.alive = false;
        render();
      } else if (shown()) {
        attach();
      }
      if (state.alive) syncTimer = setTimeout(sync, CONFIG.SYNC_INTERVAL_MS);
      return;
    }
    try {
      const s = await window.__syntioxGet();
      if (s) {
        Object.assign(state, s);
        render();
      }
    } catch (e) {}
    syncTimer = setTimeout(sync, CONFIG.SYNC_INTERVAL_MS);
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

  let toastTimer;
  function showToast() {
    if (!ui.toast) {
      ui.toast = make('div', 'toast', box);
      ui.toast.innerHTML = '<div class="toast-icon">!</div><span>Agent is controlling the browser. Click <b>Stop</b> to interrupt.</span>';
    }
    ui.toast.classList.add('show');
    if (ui.banner) ui.banner.classList.add('shake');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      if (ui.toast) ui.toast.classList.remove('show');
      if (ui.banner) ui.banner.classList.remove('shake');
    }, 2500);
  }

  // Only real user input is dropped, the page's own synthetic events still go through
  function guard(e) {
    if (!e.isTrusted || !blocking()) return;
    
    const path = e.composedPath();
    if (ui.banner && path.includes(ui.banner)) return;
    if (ui.watermark && path.includes(ui.watermark)) return;
    
    if (e.type === 'mousedown' || e.type === 'click') {
      showToast();
    }
    
    e.stopImmediatePropagation();
    if (e.cancelable) e.preventDefault();
  }
  BLOCKED.forEach((t) => window.addEventListener(t, guard, { capture: true, passive: false }));

  // Handle resizing gracefully
  window.addEventListener('resize', () => {
    if (shown() && placed) {
      requestAnimationFrame(() => setCursor(cur.x, cur.y));
    }
  }, { passive: true });

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
}
