layout(pixel_center_integer) in vec4 gl_FragCoord;
#request uniform "screen" screen
uniform ivec2 screen;
#request uniform "audio_sz" audio_sz
uniform int audio_sz;
#include ":util/smooth.glsl"
#include "@graph.glsl"
#include ":graph.glsl"
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

#define CDIST (abs((screen.x / 2) - gl_FragCoord.x) / screen.x)
#define FDIST (min(gl_FragCoord.x, screen.x - gl_FragCoord.x) / screen.x)
#if DIRECTION < 0
#define LEFT_IDX (gl_FragCoord.x)
#define RIGHT_IDX (-gl_FragCoord.x + screen.x)
#define BDIST FDIST
#define HDIST CDIST
#else
#define LEFT_IDX (half_w - gl_FragCoord.x)
#define RIGHT_IDX (gl_FragCoord.x - half_w)
#define BDIST CDIST
#define HDIST FDIST
#endif
#define TWOPI 6.28318530718

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM KOLORÓW — ZGODNY Z GUI
// ─────────────────────────────────────────────────────────────────────────────
vec3 bottom = vec3(0.08, 0.05, 0.05);
vec3 mid = vec3(0.28, 0.29, 0.27);
vec3 top = vec3(0.51, 0.62, 0.62);

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

float half_w;
float middle;
highp float pixel = 1.0F / float(screen.x);

float get_line_height(in sampler1D tex, float idx) {
    float s = smooth_audio_adj(tex, audio_sz, idx / half_w, pixel);
    s *= VSCALE;
    float fact = clamp((abs((screen.x / 2) - gl_FragCoord.x) / screen.x) * 48, 0.0F, 1.0F);
    #if JOIN_CHANNELS > 0
    fact = -2 * pow(fact, 3) + 3 * pow(fact, 2);
    s = fact * s + (1 - fact) * middle;
    #else
    s *= fact;
    #endif
    s *= clamp((min(gl_FragCoord.x, screen.x - gl_FragCoord.x) / screen.x) * 48, 0.0F, 1.0F);
    return s;
}

void render_side(in sampler1D tex, float idx) {
    float s = get_line_height(tex, idx);
    #if INVERT > 0
    float d = float(screen.y) - gl_FragCoord.y;
    #else
    float d = gl_FragCoord.y;
    #endif
    #define pos d
    if (pos + 1.5 <= s) {
        float t = clamp(pos / s, 0.0, 1.0);
        vec4 base = gradient_color(t);
        // Rozświetlenie od środka (t=0.5) — GRADIENT 0-100%
        float center_dist = abs(t - 0.5) * 2.0;  // 0=środek, 1=krawędź
        float brightness = 1.0 + (1.0 - center_dist) * float(GRADIENT) / 100.0;
        fragment = vec4(clamp(base.rgb * brightness, 0.0, 1.0), base.a);
    } else {
        fragment = vec4(0, 0, 0, 0);
    }
}

void main() {
    half_w = (screen.x / 2);
    middle = VSCALE * (smooth_audio_adj(audio_l, audio_sz, 1, pixel) + smooth_audio_adj(audio_r, audio_sz, 0, pixel)) / 2;
    if (gl_FragCoord.x < half_w) {
        render_side(audio_l, LEFT_IDX);
    } else {
        render_side(audio_r, RIGHT_IDX);
    }
}
