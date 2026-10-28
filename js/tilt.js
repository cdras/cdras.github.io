/* CDRA script (v1.14.13), the ONLY script on the site (owner exception to AGENTS.md rule 8). Three small jobs, nothing else:
   1) TILT: the award block (.s1 .plaque) and the enlarged cover (.zoom-img) lean toward the MOUSE on a computer. Decoration only; no gyroscope.
   2) THEME COLOUR (v1.14.13): when the footer Light / Dark switch is used, the browser's status-bar colour (meta theme-color) follows it; Auto goes back to the system colour.
   3) PULL TO REFRESH (touch screens): a slow, deliberate pull-down at the very top reloads the page; a quick flick never does.
   Never: network requests, storage, cookies, tracking, libraries. The tilt stops under prefers-reduced-motion: reduce. */
(function () {
  'use strict';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var root = document.documentElement;
  var zoomToggle = document.getElementById('zoom');

  /* ================= 1. tilt (mouse / pen only) ================= */
  var plaque = document.querySelector('.s1 .plaque');
  var zoomBox = document.querySelector('.zoom-img');
  if (plaque || zoomBox) (function () {
    var TAU = 0.14;
    var PERSPECTIVE = '60rem';
    var REST_MS = 600;       /* a resting mouse lets the card settle flat (sharp text) */
    function make(el, max) { return el ? { el: el, max: max, x: 0, y: 0, on: false, seen: true } : null; }
    var cards = { plaque: make(plaque, 4), zoom: make(zoomBox, 5) };
    var nx = 0, ny = 0;      /* pointer -1..1 */
    var raf = 0, last = 0, idle = 0;

    if (cards.plaque && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (e) { cards.plaque.seen = e[e.length - 1].isIntersecting; }).observe(plaque);
    }
    function current() {
      if (zoomToggle && zoomToggle.checked) return cards.zoom;
      return cards.plaque && cards.plaque.seen ? cards.plaque : null;
    }
    function clear(c) {
      if (c && c.on) { c.el.style.transform = ''; c.el.style.willChange = ''; c.on = false; }
    }
    function apply(c) {
      if (!c.on) { c.el.style.willChange = 'transform'; c.on = true; }
      c.el.style.transform = 'perspective(' + PERSPECTIVE + ') rotateX(' + (-c.y * c.max).toFixed(2) + 'deg) rotateY(' + (c.x * c.max).toFixed(2) + 'deg)';
    }
    function frame(t) {
      raf = 0;
      var dt = last ? Math.min((t - last) / 1000, 0.1) : 0.016;
      last = t;
      var active = current(), busy = false;
      var f = 1 - Math.exp(-dt / TAU);
      for (var k in cards) {
        var c = cards[k];
        if (!c) continue;
        var live = !reduce.matches && c === active;
        var tx = live ? nx : 0, ty = live ? ny : 0;
        var dx = tx - c.x, dy = ty - c.y;
        if (Math.abs(dx) < 0.002 && Math.abs(dy) < 0.002) {   /* arrived: stop the loop */
          c.x = tx; c.y = ty;
          if (tx === 0 && ty === 0) clear(c); else apply(c);
          continue;
        }
        c.x += dx * f; c.y += dy * f;
        busy = true;
        apply(c);
      }
      if (busy) { raf = requestAnimationFrame(frame); } else { last = 0; }
    }
    function wake() { if (!raf) raf = requestAnimationFrame(frame); }
    function clamp(v) { return v < -1 ? -1 : v > 1 ? 1 : v; }

    /* touch is ignored: a finger drag scrolls the page */
    window.addEventListener('pointermove', function (e) {
      if (e.pointerType === 'touch' || reduce.matches) return;
      /* on TEXT of the block the card settles flat */
      var t = e.target, onText = !!(plaque && t && t.closest && plaque.contains(t) && !t.closest('.hero-media') && t.closest('p, h1, span, a, dl, dt, dd, li'));
      nx = onText ? 0 : clamp((e.clientX / window.innerWidth - 0.5) * 2);
      ny = onText ? 0 : clamp((e.clientY / window.innerHeight - 0.5) * 2);
      clearTimeout(idle);
      idle = setTimeout(function () { nx = ny = 0; wake(); }, REST_MS);
      wake();
    }, { passive: true });
    root.addEventListener('pointerleave', function () { nx = ny = 0; wake(); });
    window.addEventListener('blur', function () { nx = ny = 0; wake(); });
    /* the enlarged cover starts from rest */
    if (zoomToggle) zoomToggle.addEventListener('change', function () { nx = ny = 0; if (cards.zoom) { clear(cards.zoom); cards.zoom.x = cards.zoom.y = 0; } wake(); });
    if (reduce.addEventListener) reduce.addEventListener('change', function () { nx = ny = 0; wake(); });
  })();

  /* ================= 2. status-bar colour follows the footer theme switch ================= */
  (function () {
    var radios = document.querySelectorAll('input[name="theme"]');
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    if (!radios.length || metas.length < 2) return;
    var light = metas[0], dark = metas[1], lm = light.media, dm = dark.media, lc = light.content, dc = dark.content;
    function sync() {
      var r = document.querySelector('input[name="theme"]:checked'), v = r ? r.value : 'auto';
      if (v === 'auto') { light.media = lm; dark.media = dm; light.content = lc; dark.content = dc; return; }
      light.media = 'all'; light.content = v === 'dark' ? dc : lc; dark.media = 'not all';
    }
    for (var i = 0; i < radios.length; i++) radios[i].addEventListener('change', sync);
    sync();
  })();

  /* ================= 3. pull to refresh (touch screens) ================= */
  if (!('ontouchstart' in window)) return;
  var PULL = 112;    /* px to fill the ring */
  var HOLD = 450;    /* ms the pull must last: a flick never reloads */
  var SLOP = 10;     /* px before the direction is decided */
  var st = null, ring = null, loop = 0;
  root.classList.add('ptr-on');   /* CSS switches off the browser's own pull-to-refresh */

  function top() { return (window.pageYOffset || root.scrollTop) <= 0; }
  function paint() {
    var d = Math.max(st.d, 0);
    var p = Math.min(1, d / PULL, (performance.now() - st.t) / HOLD);
    if (p >= 1) st.armed = true; else if (d < PULL * 0.7) st.armed = false;
    var y = d * 88 / (160 + d * 0.55);   /* rubber band */
    ring.style.setProperty('--ptr-y', y.toFixed(1) + 'px');
    ring.style.setProperty('--p', (st.armed ? 1 : p).toFixed(3));
    ring.style.opacity = Math.min(1, d / 40).toFixed(2);
    ring.classList.toggle('is-armed', st.armed);
  }
  function tick() { loop = 0; if (st && st.on) { paint(); loop = requestAnimationFrame(tick); } }
  function drop() { if (ring) { ring.classList.add('is-back'); ring.style.opacity = '0'; ring.style.setProperty('--ptr-y', '0px'); } }

  document.addEventListener('touchstart', function (e) {
    st = null;
    if (e.touches.length !== 1 || !top() || (zoomToggle && zoomToggle.checked)) return;
    st = { x: e.touches[0].clientX, y: e.touches[0].clientY, t: 0, d: 0, on: false, dead: false, armed: false };
    if (ring) ring.classList.remove('is-back');
  }, { passive: true });
  document.addEventListener('touchmove', function (e) {
    if (!st || st.dead) return;
    var dx = e.touches[0].clientX - st.x, dy = e.touches[0].clientY - st.y;
    if (e.touches.length > 1 || !top()) { st.dead = true; if (st.on) drop(); st.on = false; return; }
    if (!st.on) {
      if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
      if (dy < 0 || Math.abs(dx) > Math.abs(dy)) { st.dead = true; return; }
      st.on = true; st.t = performance.now();
      if (!ring) { ring = document.createElement('div'); ring.className = 'ptr'; ring.setAttribute('aria-hidden', 'true'); document.body.appendChild(ring); }
      ring.classList.remove('is-back');
      if (!loop) loop = requestAnimationFrame(tick);
    }
    st.d = dy;
    paint();
  }, { passive: true });
  function end(e) {
    var s = st; st = null;
    if (!s || !s.on) return;
    s.on = false;
    if (e.type === 'touchend' && s.armed && top()) { ring.classList.add('is-armed'); location.reload(); } else drop();
  }
  document.addEventListener('touchend', end, { passive: true });
  document.addEventListener('touchcancel', end, { passive: true });
})();
