layout(pixel_center_integer) in vec4 gl_FragCoord;

#request uniform "screen" screen
uniform ivec2 screen;

#request uniform "audio_l" audio_l
#request transform audio_l "window"
#request transform audio_l "wrange"
uniform sampler1D audio_l;

out vec4 fragment;

#include "@wave.glsl"
#include ":wave.glsl"

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM KOLORÓW — ZGODNY Z GUI
// ─────────────────────────────────────────────────────────────────────────────
vec3 bottom = vec3(0.91, 0.31, 0.14);
vec3 mid    = vec3(0.91, 0.18, 0.85);
vec3 top    = vec3(0.13, 0.92, 0.22);

#define HSV_MODE 1  // 0 = RGB, 1 = HSV

vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}
vec4 gradient_color(float t) {
#if HSV_MODE == 1
    vec3 hsv_a = rgb2hsv(t < 0.5 ? bottom : mid);
    vec3 hsv_b = rgb2hsv(t < 0.5 ? mid    : top);
    float lt   = t < 0.5 ? t * 2.0 : (t - 0.5) * 2.0;
    float dh = hsv_b.x - hsv_a.x;
    if (dh > 0.5)  dh -= 1.0;
    if (dh < -0.5) dh += 1.0;
    vec3 hsv = vec3(hsv_a.x + dh * lt, mix(hsv_a.y, hsv_b.y, lt), mix(hsv_a.z, hsv_b.z, lt));
    return vec4(hsv2rgb(hsv), 1.0);
#else
    vec3 col = t < 0.5
        ? mix(bottom, mid, t * 2.0)
        : mix(mid, top, (t - 0.5) * 2.0);
    return vec4(col, 1.0);
#endif
}
// ─────────────────────────────────────────────────────────────────────────────

void main() {
    fragment = vec4(0.0, 0.0, 0.0, 0.0);

    // ── 1. Środek fali (centrum rotacji i pozycjonowania) ─────────────────────
    vec2 wave_center = vec2(
        float(screen.x) * 0.5 + float(CENTER_OFFSET_X),
        float(screen.y) * 0.5 + float(CENTER_OFFSET_Y)
    );

    // ── 2. Współrzędna fragmentu względem środka fali ─────────────────────────
    vec2 p = gl_FragCoord.xy - wave_center;

    // ── 3. Rotacja (obrót wokół środka fali) ─────────────────────────────────
    float sA = sin(ROTATE);
    float cA = cos(ROTATE);
    vec2 r = vec2(
        p.x * cA + p.y * sA,   // oś wzdłuż fali (lokalne X)
       -p.x * sA + p.y * cA    // oś prostopadła do fali (lokalne Y)
    );

    // ── 4. Przycinanie do długości fali ───────────────────────────────────────
    // WAVE_LENGTH = 0 → pełna szerokość ekranu
    float half_len = (WAVE_LENGTH > 0)
        ? float(WAVE_LENGTH) * 0.5
        : float(screen.x) * 0.5;

    if (abs(r.x) > half_len) return;  // fragment poza długością fali

    // ── 5. Próbkowanie audio w przestrzeni po rotacji ─────────────────────────
    // Normalizacja pozycji wzdłuż fali do zakresu [0, 1]
    float tex_pos = (r.x + half_len) / (half_len * 2.0);

    float os   = (texture(audio_l, tex_pos           ).r - 0.5) * AMPLIFY;
    float adj0 = (texture(audio_l, tex_pos - 1.0 / (half_len * 2.0)).r - 0.5) * AMPLIFY;
    float adj1 = (texture(audio_l, tex_pos + 1.0 / (half_len * 2.0)).r - 0.5) * AMPLIFY;

    // ── 6. Wysokość fali w lokalnym Y ─────────────────────────────────────────
    float wave_y = os;   // oś Y fali (0 = środek fali)

    float s0 = adj0 - os;
    float s1 = adj1 - os;
    float dmax = max(s0, s1);
    float dmin = min(s0, s1);

    float diff = r.y - wave_y;

    // ── 7. Grubość linii ──────────────────────────────────────────────────────
    float thickness = clamp(abs(wave_y) * 6.0, MIN_THICKNESS, MAX_THICKNESS);

    if (abs(diff) < thickness || (diff <= dmax && diff >= dmin)) {
        float t = clamp(wave_y / (AMPLIFY * 0.5) + 0.5, 0.0, 1.0);
        fragment = gradient_color(t);
    }
}
