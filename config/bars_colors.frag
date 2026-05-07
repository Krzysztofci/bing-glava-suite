in vec4 gl_FragCoord;

#request uniform "screen" screen
uniform ivec2 screen;

#request uniform "audio_sz" audio_sz
uniform int audio_sz;

#include "@bars.glsl"
// Redefine parameters that may be overridden by user config.
// GLava processes @bars.glsl (system) before :bars.glsl (user),
// so #define from system wins. We #undef here to allow user values.
#ifdef C_LINE
#undef C_LINE
#endif
#include ":bars.glsl"

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
#include ":util/smooth.glsl"

#define TWOPI 6.28318530718
#define PI 3.14159265359

#if DISABLE_MONO == 1
#define _CHANNELS 2
#endif

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM KOLORÓW — ZGODNY Z GUI
// ─────────────────────────────────────────────────────────────────────────────
vec3 bottom = vec3(0.18, 0.16, 0.40);
vec3 mid = vec3(0.71, 0.24, 0.80);
vec3 top = vec3(0.05, 0.76, 0.11);

#define HSV_MODE 1  // 0 = RGB, 1 = HSV
#define USE_OUTLINE 1   // 1 = outline włączony, 0 = wyłączony

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

    #if MIRROR_YX == 0
    #define AREA_WIDTH  screen.x
    #define AREA_HEIGHT screen.y
    #define AREA_X      gl_FragCoord.x
    #define AREA_Y      gl_FragCoord.y
    #else
    #define AREA_WIDTH  screen.y
    #define AREA_HEIGHT screen.x
    #define AREA_X      gl_FragCoord.y
    #define AREA_Y      gl_FragCoord.x
    #endif

    #if _CHANNELS == 2
    float dx = (AREA_X - (AREA_WIDTH / 2));
    #else
    #if INVERT == 1
    float dx = AREA_WIDTH - AREA_X;
    #else
    float dx = AREA_X;
    #endif
    #endif

    #if FLIP == 0
    float d = AREA_Y;
    #else
    float d = AREA_HEIGHT - AREA_Y;
    #endif

    float section = BAR_WIDTH + BAR_GAP;
    float center  = section / 2.0F;
    float m       = abs(mod(dx, section));
    float md      = m - center;
    float nbars   = floor((AREA_WIDTH * 0.5F) / section) * 2;
    float p, s;

    if (md < ceil(float(BAR_WIDTH) / 2) && md >= -floor(float(BAR_WIDTH) / 2)) {
        s = dx / section;
        p = (sign(s) == 1.0 ? ceil(s) : floor(s));
        #if _CHANNELS == 2
        p /= float(nbars / 2);
        #else
        p /= float(nbars);
        #endif
        p += sign(p) * ((0.5F + center) / AREA_WIDTH);

        #define smooth_f(tex, p) smooth_audio(tex, audio_sz, p)
        float v;
        if (p > 1.0F || p < -1.0F) {
            fragment = vec4(0, 0, 0, 0);
            return;
        }
        if (p > 0.0F) {
            #if DIRECTION == 1
            p = 1.0F - p;
            #endif
            #if _CHANNELS == 1
            v = smooth_f(audio_l, p);
            #elif INVERT > 0
            v = smooth_f(audio_l, p);
            #else
            v = smooth_f(audio_r, p);
            #endif
        } else {
            p = abs(p);
            #if DIRECTION == 1
            p = 1.0F - p;
            #endif
            #if _CHANNELS == 1
            v = smooth_f(audio_l, p);
            #elif INVERT > 0
            v = smooth_f(audio_r, p);
            #else
            v = smooth_f(audio_l, p);
            #endif
        }
        #undef smooth_f

        v *= AMPLIFY;
        #if C_LINE > 0
        if (v > 0.0 && d > v * 0.1 && d < v * 0.9 && abs(md) <= float(C_LINE) * 0.5) {
            float t_peak = clamp(v / float(AREA_HEIGHT), 0.0, 1.0);
            fragment = outline_color(gradient_color(t_peak));
            return;
        }
        #endif

        float t = clamp(d / v, 0.0, 1.0);
        vec4 base = gradient_color(t);

        if (d < v - BAR_OUTLINE_WIDTH) {
        #if USE_OUTLINE && BAR_OUTLINE_WIDTH > 0
            if (md < ceil(float(BAR_WIDTH) / 2) - BAR_OUTLINE_WIDTH &&
                md >= -floor(float(BAR_WIDTH) / 2) + BAR_OUTLINE_WIDTH)
                fragment = base;
            else
                fragment = outline_color(base);
        #else
            fragment = base;
        #endif
            return;
        }

        #if USE_OUTLINE && BAR_OUTLINE_WIDTH > 0
        if (d <= v) {
            fragment = outline_color(base);
            return;
        }
        #endif
    }

    fragment = vec4(0, 0, 0, 0);
}
