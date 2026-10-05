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

  // Same shader as the Ghostty one, minus the terminal texture/mask.
  // Outputs premultiplied stars on a transparent canvas.
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
  const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: false });
  if (!gl) return;

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
    html body { background-color: transparent !important; }
  `;
  document.documentElement.appendChild(style);
  document.documentElement.appendChild(canvas);

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(window.innerWidth * dpr);
    canvas.height = Math.round(window.innerHeight * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform3f(uRes, canvas.width, canvas.height, 1);
  }
  window.addEventListener("resize", resize);
  resize();

  const start = performance.now();
  function frame(now) {
    gl.uniform1f(uTime, ((now - start) / 1000) % 32000); // wrap: see PERIOD in shader
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
