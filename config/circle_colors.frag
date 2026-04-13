layout(pixel_center_integer) in vec4 gl_FragCoord;

#request uniform "screen" screen
uniform ivec2 screen;

#request uniform "audio_sz" audio_sz
uniform int audio_sz;

#include ":util/smooth.glsl"
#include "@circle.glsl"
#include ":circle.glsl"

// C_LINE pochodzi z circle.glsl — sterowany przez GUI

#request uniform "audio_l" audio_l
#request transform audio_l "window"
#request transform audio_l "fft"
#request transform audio_l "gravity"
#request transform audio_l "avg"
uniform sampler1D audio_l;

#request uniform "audio_r" audio_r
#request transform audio_r "window"
#request transform audio_r "fft"
#request transform audio_r "gravity"
#request transform audio_r "avg"
uniform sampler1D audio_r;

out vec4 fragment;

#define TWOPI 6.28318530718
#define PI 3.14159265359




// ─────────────────────────────────────────────────────────────────────────────

float apply_smooth(float theta) {
    // 1. Obliczamy kąt z obrotem i sprowadzamy do zakresu [0, TWOPI]
    float idx = mod(theta + ROTATE, TWOPI);
    
    // 2. Normalizacja do zakresu [-PI, PI] - to rozwiązuje błąd 178-360*
    if (idx > PI)  idx -= TWOPI;
    if (idx < -PI) idx += TWOPI;

    // 3. Obsługa inwersji (jeśli potrzebna)
    if (INVERT > 0)
        idx = -idx;

    // 4. Mapowanie na pozycję w samplerze audio (0.0 do 1.0)
    float pos = clamp(abs(idx) / PI, 0.0, 1.0);

    #define smooth_f(tex) smooth_audio(tex, audio_sz, pos)
    float v;
    if (idx > 0) v = smooth_f(audio_l);
    else         v = smooth_f(audio_r);
    
    v *= AMPLIFY;      
    #undef smooth_f
    return v;
}

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM KOLORÓW — ZGODNY Z GUI
// ─────────────────────────────────────────────────────────────────────────────
vec3 bottom = vec3(0.50, 0.00, 0.00);
vec3 mid = vec3(0.90, 0.10, 0.10);
vec3 top = vec3(0.80, 0.12, 0.80);

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

vec4 outline_color(vec4 base) {
    return vec4(min(base.rgb * 1.5, vec3(1.0)), base.a);
}
// ─────────────────────────────────────────────────────────────────────────────

void main() {
    fragment = vec4(0, 0, 0, 0);

    float dx = gl_FragCoord.x - (screen.x / 2) + CENTER_OFFSET_X;
    float dy = gl_FragCoord.y - (screen.y / 2) + CENTER_OFFSET_Y;

    float theta = atan(dy, dx);
    float d = sqrt((dx * dx) + (dy * dy));

    float adv = (1.0F / d) * (C_LINE * 0.5);
    float adj0 = theta + adv;
    float adj1 = theta - adv;

    d -= C_RADIUS;

    if (d >= -(float(C_LINE) / 2.0F)) {
        float v = apply_smooth(theta);

        adj0 = apply_smooth(adj0) - v;
        adj1 = apply_smooth(adj1) - v;

        float dmax = max(adj0, adj1);
        float dmin = min(adj0, adj1);

        d -= v;

        #if C_FILL > 0
        #define BOUNDS (d < (float(C_LINE) / 2.0F))
        #else
        #define BOUNDS (d > -(float(C_LINE) / 2.0F) && d < (float(C_LINE) / 2.0F)) || (d <= dmax && d >= dmin)
        #endif

        if (BOUNDS) {
            float t = clamp(v / (AMPLIFY * 0.5), 0.0, 1.0);
            vec4 base = gradient_color(t);

        #if USE_OUTLINE
            fragment = outline_color(base);
        #else
            fragment = base;
        #endif
        }
    }
}

