layout(pixel_center_integer) in vec4 gl_FragCoord;

#request uniform "screen" screen
uniform ivec2 screen;

#request uniform "audio_sz" audio_sz
uniform int audio_sz;

#include ":util/smooth.glsl"
#include "@circle.glsl"
#include ":circle.glsl"

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
// SYSTEM KOLORÓW — ZGODNY Z TWOIM GUI
// GRADIENT_MODE: rgb
// ─────────────────────────────────────────────────────────────────────────────
uniform vec3 bottom;
uniform vec3 mid;
uniform vec3 top;

#define USE_OUTLINE 1   // 1 = outline włączony, 0 = wyłączony

vec4 gradient_color(float t) {
    vec3 col = t < 0.5
        ? mix(bottom, mid, t * 2.0)
        : mix(mid, top, (t - 0.5) * 2.0);
    return vec4(col, 1.0);
}

vec4 outline_color(vec4 base) {
    return vec4(min(base.rgb * 1.5, vec3(1.0)), base.a);
}
// ─────────────────────────────────────────────────────────────────────────────

float apply_smooth(float theta) {
    float idx = theta + ROTATE;
    float dir = mod(abs(idx), TWOPI);
    if (dir > PI)
        idx = -sign(idx) * (TWOPI - dir);
    if (INVERT > 0)
        idx = -idx;
    
    float pos = abs(idx) / (PI + 0.001F);
    #define smooth_f(tex) smooth_audio(tex, audio_sz, pos)
    float v;
    if (idx > 0) v = smooth_f(audio_l);
    else         v = smooth_f(audio_r);
    v *= AMPLIFY;      
    #undef smooth_f
    return v;
}

void main() {
    fragment = vec4(0, 0, 0, 0);

    float dx = gl_FragCoord.x - (screen.x / 2);
    float dy = gl_FragCoord.y - (screen.y / 2);

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
            float t = clamp((d + v) / (v + C_LINE), 0.0, 1.0);
            vec4 base = gradient_color(t);

        #if USE_OUTLINE
            fragment = outline_color(base);
        #else
            fragment = base;
        #endif
        }
    }
}

