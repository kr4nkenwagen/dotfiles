// ==UserScript==
// @name         Starfield background
// @description  Drifting starfield behind pages, ported from ~/.config/ghostty/starfield.glsl
// @match        *://*/*
// @match        file:///*
// @run-at       document-end
// @noframes
// ==/UserScript==

(function () {
  "use strict";

  // starfield-toggle: starfield.css (a user stylesheet config.py adds only while the
  // effect is on) sets --qb-starfield on html. Poll it so a toggle applies to open tabs.
  function enabled() {
    return getComputedStyle(document.documentElement).getPropertyValue("--qb-starfield").trim() === "on";
  }
  let running = null;
  function sync() {
    const on = enabled();
    if (on && !running) running = start();
    else if (!on && running) { running.stop(); running = null; }
  }
  setInterval(sync, 2000);
  sync();

  function start() {

  // Same shader as the Ghostty one, minus the terminal texture/mask.
  // Outputs only star light with alpha (premultiplied); the page's own
  // (possibly translucent) root background shows through between stars.
  const FRAG = `
precision highp float;
uniform vec3 iResolution;
uniform float iTime;

const float SPEED = 0.02;      // drift speed
const float BRIGHTNESS = 0.8;  // overall star brightness
const int LAYERS = 3;          // parallax depth layers
// Pattern repeats every CELLS cells; after PERIOD seconds every layer has
// drifted a whole number of repeats, so wrapping time there is seamless and
// keeps float precision from degrading over long uptimes.
const float CELLS = 256.0;
const float PERIOD = 32000.0;

float hash(vec2 p) {
    p = mod(p, CELLS); // wrap so inputs stay small and precise
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float starLayer(vec2 uv, float scale, vec2 shift, float t) {
    uv = uv * scale + shift;
    vec2 id = floor(uv);
    vec2 gv = fract(uv) - 0.5;

    float n = hash(id);
    if (n < 0.85) return 0.0; // most cells stay empty

    vec2 offset = vec2(hash(id + 1.7), hash(id + 3.1)) - 0.5;
    float d = length(gv - offset * 0.8);
    float size = mix(0.02, 0.06, hash(id + 5.3));
    float star = 1.0 - smoothstep(0.0, size, d);

    // gentle twinkle
    float twinkle = 0.6 + 0.4 * sin(t * (1.0 + 3.0 * hash(id + 9.1)) + n * 6.2831);
    return star * twinkle;
}

void main() {
    vec2 uv = gl_FragCoord.xy / iResolution.y;
    float t = mod(iTime, PERIOD);

    float stars = 0.0;
    for (int i = 0; i < LAYERS; i++) {
        float depth = float(i + 1);
        float scale = 18.0 + depth * 14.0;
        vec2 shift = mod(t * SPEED * depth * scale * vec2(1.0, 0.3), CELLS);
        stars += starLayer(uv, scale, shift, t) / depth;
    }

    float a = clamp(stars * BRIGHTNESS, 0.0, 1.0);
    gl_FragColor = vec4(vec3(0.85, 0.9, 1.0) * a, a);
}
`;

  const VERT = `
attribute vec2 pos;
void main() { gl_Position = vec4(pos, 0.0, 1.0); }
`;

  const canvas = document.createElement("canvas");
  canvas.id = "qb-starfield";
  const gl = canvas.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: false });
  if (!gl) return { stop() {} };

  function compile(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      console.warn("starfield:", gl.getShaderInfoLog(s));
      return null;
    }
    return s;
  }

  const vs = compile(gl.VERTEX_SHADER, VERT);
  const fs = compile(gl.FRAGMENT_SHADER, FRAG);
  if (!vs || !fs) return;
  const prog = gl.createProgram();
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
  gl.useProgram(prog);

  // One triangle covering the whole screen
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const posLoc = gl.getAttribLocation(prog, "pos");
  gl.enableVertexAttribArray(posLoc);
  gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

  const uRes = gl.getUniformLocation(prog, "iResolution");
  const uTime = gl.getUniformLocation(prog, "iTime");

  const style = document.createElement("style");
  style.textContent = `
    #qb-starfield {
      position: fixed !important; inset: 0 !important;
      width: 100vw !important; height: 100vh !important;
      z-index: -2147483647 !important; pointer-events: none !important;
      display: block !important; margin: 0 !important; padding: 0 !important;
    }
    html { background-image: none !important; }
    body { background-color: transparent !important; background-image: none !important; }
    ytd-app, ytd-masthead, #masthead-container, ytd-masthead #container, ytd-masthead #background { background: transparent !important; }
  `;
  document.documentElement.appendChild(style);
  document.documentElement.appendChild(canvas);
  // Root background carries the terminal-like alpha (--bg_translucent from
  // all.css). Inline !important outranks site rules on html that the injected
  // user stylesheet alone does not beat (YouTube).
  document.documentElement.style.setProperty("background-color", "var(--bg_translucent, transparent)", "important");

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(window.innerWidth * dpr);
    canvas.height = Math.round(window.innerHeight * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform3f(uRes, canvas.width, canvas.height, 1);
  }
  window.addEventListener("resize", resize);
  resize();

  // Many sites (YouTube, Gemini, claude.ai) paint opaque backgrounds on
  // inner wrappers that hide the canvas. Find big painted elements stacked
  // over the viewport and clear their backgrounds.
  const SKIP = new Set(["VIDEO", "CANVAS", "IMG", "IFRAME", "SVG", "PICTURE", "CANVAS"]);
  const POINTS = [[0.5, 0.5], [0.1, 0.1], [0.9, 0.1], [0.1, 0.9], [0.9, 0.9], [0.5, 0.05], [0.5, 0.95], [0.05, 0.5], [0.95, 0.5], [0.02, 0.25], [0.02, 0.75], [0.12, 0.5], [0.98, 0.5]];

  // computedStyleMap avoids sites that proxy getComputedStyle (YouTube).
  function computed(el, prop, camel) {
    try { return String(el.computedStyleMap().get(prop)); } catch (e) {}
    try { return window.getComputedStyle(el)[camel]; } catch (e) {}
    return "";
  }

  function clearBackgrounds() {
    const vw = window.innerWidth, vh = window.innerHeight;
    const pts = POINTS.map(([x, y]) => [x * vw, y * vh]);
    // Pixel offsets so thin top/bottom bars (headers, footers) are sampled too.
    for (const x of [0.2, 0.5, 0.8]) pts.push([x * vw, 6], [x * vw, 28], [x * vw, vh - 6]);
    for (const [px, py] of pts) {
      for (const el of document.elementsFromPoint(px, py)) {
        // The root keeps its (translucent) background from all.css; only site wrappers are cleared.
        if (el === canvas || el === document.documentElement || el.dataset.qbStarfield || SKIP.has(el.tagName.toUpperCase())) continue;
        const r = el.getBoundingClientRect();
        const wide = r.width >= vw * 0.7 && r.height >= vh * 0.5;
        const sidePanel = r.width >= 120 && r.height >= vh * 0.8; // sidebars, drawers
        const bar = r.width >= vw * 0.7 && r.height >= 30 && r.height <= 200 && (r.top <= 2 || r.bottom >= vh - 2); // sticky headers/footers
        if (!wide && !sidePanel && !bar) continue;
        const img = computed(el, "background-image", "backgroundImage");
        const color = computed(el, "background-color", "backgroundColor");
        const painted = (img && img !== "none") ||
          (color && color !== "transparent" && !/,\s*0\)$/.test(color));
        if (!painted) continue;
        el.dataset.qbStarfield = "1";
        el.style.setProperty("background", "transparent", "important");
      }
    }
  }

  let scanTimer = 0;
  function scheduleScan() {
    if (scanTimer) return;
    scanTimer = setTimeout(() => { scanTimer = 0; clearBackgrounds(); }, 300);
  }
  const observer = new MutationObserver(scheduleScan);
  observer.observe(document.documentElement, {
    childList: true, subtree: true, attributes: true, attributeFilter: ["class", "style", "hidden"],
  });
  window.addEventListener("resize", scheduleScan);
  window.addEventListener("load", scheduleScan);
  window.addEventListener("scroll", scheduleScan, { passive: true });
  scheduleScan();

  const t0 = performance.now();
  let raf = 0;
  function frame(now) {
    gl.uniform1f(uTime, ((now - t0) / 1000) % 32000); // wrap: see PERIOD in shader
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    raf = requestAnimationFrame(frame);
  }
  raf = requestAnimationFrame(frame);

  return {
    stop() {  // undo what start() added; site backgrounds cleared by clearBackgrounds come back on reload
      cancelAnimationFrame(raf);
      observer.disconnect();
      window.removeEventListener("resize", resize);
      window.removeEventListener("resize", scheduleScan);
      window.removeEventListener("load", scheduleScan);
      window.removeEventListener("scroll", scheduleScan);
      canvas.remove();
      style.remove();
      document.documentElement.style.removeProperty("background-color");
    },
  };
  }
})();
