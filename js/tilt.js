/* CDRA tilt (v1.11.16) — the ONLY script on the site (owner exception to AGENTS.md rule 8).
   What it does: tilts the award block (.s1 .plaque: the award pages and the home «CDRA» block) and, separately, the enlarged cover (.zoom-img)
   with the mouse on a computer and with the gyroscope on a phone. Decoration only: no content, no links, no layout depends on it.
   What it never does: network requests, storage, cookies, tracking, libraries. Nothing runs under prefers-reduced-motion: reduce.
   Motion = a smoothed approach to the target (starts from the value on screen, so it can be interrupted at any moment, no overshoot). */
(function () {
  'use strict';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var coarse = window.matchMedia('(pointer: coarse)');
  var plaque = document.querySelector('.s1 .plaque');
  var zoomBox = document.querySelector('.zoom-img');
  var zoomToggle = document.getElementById('zoom');
  if (!plaque && !zoomBox) return;

  var TAU = 0.14;          /* seconds: how fast the card follows the input */
  var PERSPECTIVE = '60rem';
  var RANGE = 9;           /* v1.13.11: degrees of phone tilt that give the full card tilt (was 20: now about twice as sensitive) */
  var GYRO_BOOST = 2.6;    /* v1.13.11: the gyroscope tilts the card 2.6x further than the mouse does (plaque 4 -> 10.4 deg) */
  var viaGyro = false;
  var BASE_TAU = 4;        /* seconds: the «level» position slowly follows how the phone is held */

  function make(el, max) { return el ? { el: el, max: max, x: 0, y: 0, on: false, seen: true } : null; }
  var cards = { plaque: make(plaque, 4), zoom: make(zoomBox, 5) };   /* v1.13.4: smaller angles = less resampling blur */
  var nx = 0, ny = 0;      /* input, -1..1 (right / down for the mouse) */
  var raf = 0, last = 0, idle = 0;
  var REST_MS = 600;       /* v1.13.4: a mouse that stops lets the card settle flat, so text and cover are razor sharp at rest */

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
    /* pointer-pressed model: the edge nearest the input goes away from you */
    c.el.style.transform = 'perspective(' + PERSPECTIVE + ') rotateX(' + (-c.y * c.max * (viaGyro ? GYRO_BOOST : 1)).toFixed(2) + 'deg) rotateY(' + (c.x * c.max * (viaGyro ? GYRO_BOOST : 1)).toFixed(2) + 'deg)';
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
      if (Math.abs(dx) < 0.002 && Math.abs(dy) < 0.002) {   /* arrived: stop the loop (a resting mouse costs nothing) */
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

  /* ---- mouse / pen (touch is ignored: a finger drag must keep scrolling the page) ---- */
  window.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch' || reduce.matches) return;
    /* v1.13.10: while the pointer is on TEXT of the block the card settles flat, so the text being pointed at (and zooming) is never resampled by the tilt */
    viaGyro = false;
    var t = e.target, onText = !!(plaque && t && t.closest && plaque.contains(t) && !t.closest('.hero-media') && t.closest('p, span, a, dl, dt, dd, li'));
    nx = onText ? 0 : clamp((e.clientX / window.innerWidth - 0.5) * 2);
    ny = onText ? 0 : clamp((e.clientY / window.innerHeight - 0.5) * 2);
    clearTimeout(idle);
    idle = setTimeout(function () { nx = ny = 0; wake(); }, REST_MS);
    wake();
  }, { passive: true });
  document.documentElement.addEventListener('pointerleave', function () { nx = ny = 0; wake(); });
  window.addEventListener('blur', function () { nx = ny = 0; wake(); });

  /* ---- gyroscope (phones, tablets) ---- */
  var baseX = null, baseY = 0, baseT = 0, gyro = false;
  function onTilt(e) {
    if (e.beta == null || e.gamma == null || reduce.matches) return;
    var a = (screen.orientation && screen.orientation.angle) || window.orientation || 0;
    var x = e.gamma, y = e.beta;                           /* upright portrait */
    if (a === 90) { x = e.beta; y = -e.gamma; }
    else if (a === 270 || a === -90) { x = -e.beta; y = e.gamma; }
    else if (a === 180) { x = -e.gamma; y = -e.beta; }
    var t = e.timeStamp / 1000;
    if (baseX === null) { baseX = x; baseY = y; baseT = t; }
    var f = 1 - Math.exp(-Math.max(t - baseT, 0) / BASE_TAU);
    baseX += (x - baseX) * f; baseY += (y - baseY) * f; baseT = t;
    /* «the card stays where it is, the phone moves around it» */
    viaGyro = true;
    nx = clamp(-(x - baseX) / RANGE);
    ny = clamp(-(y - baseY) / RANGE);
    wake();
  }
  function startGyro() {
    if (gyro) return;
    gyro = true;
    window.addEventListener('deviceorientation', onTilt, true);
  }
  function resetBase() { baseX = null; }
  window.addEventListener('orientationchange', resetBase);
  if (screen.orientation && screen.orientation.addEventListener) screen.orientation.addEventListener('change', resetBase);

  var DOE = window.DeviceOrientationEvent;
  if (DOE && (coarse.matches || 'ontouchstart' in window)) {
    if (typeof DOE.requestPermission === 'function') {
      /* iOS asks once, and only from a tap */
      var asked = false;
      var ask = function () {
        if (asked) return;
        asked = true;
        DOE.requestPermission().then(function (s) { if (s === 'granted') startGyro(); }).catch(function () {});
      };
      window.addEventListener('click', ask, { once: true });
      window.addEventListener('touchend', ask, { once: true });
    } else {
      startGyro();
    }
  }

  /* opening or closing the enlarged cover starts from rest; reduced motion switched on later stops everything */
  if (zoomToggle) zoomToggle.addEventListener('change', function () { nx = ny = 0; baseX = null; if (cards.zoom) { clear(cards.zoom); cards.zoom.x = cards.zoom.y = 0; } wake(); });
  if (reduce.addEventListener) reduce.addEventListener('change', function () { nx = ny = 0; wake(); });
})();
