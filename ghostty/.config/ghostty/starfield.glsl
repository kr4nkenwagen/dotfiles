// Drifting parallax starfield drawn behind terminal text.
// Stars only show on dark (background) pixels so text stays readable.

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

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.y;
    vec4 term = texture(iChannel0, fragCoord / iResolution.xy);
    float t = mod(iTime, PERIOD);

    float stars = 0.0;
    for (int i = 0; i < LAYERS; i++) {
        float depth = float(i + 1);
        float scale = 18.0 + depth * 14.0;
        vec2 shift = mod(t * SPEED * depth * scale * vec2(1.0, 0.3), CELLS);
        stars += starLayer(uv, scale, shift, t) / depth;
    }

    // Only draw on dark pixels (the background), fade out near text.
    float luma = dot(term.rgb, vec3(0.299, 0.587, 0.114));
    float mask = 1.0 - smoothstep(0.08, 0.25, luma);

    vec3 starColor = vec3(0.85, 0.9, 1.0) * stars * BRIGHTNESS * mask;
    fragColor = vec4(term.rgb + starColor, term.a);
}
