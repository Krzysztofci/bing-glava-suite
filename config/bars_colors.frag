in vec4 gl_FragCoord;

#request uniform "screen" screen
uniform ivec2 screen;

#request uniform "audio_sz" audio_sz
uniform int audio_sz;

#include "@bars.glsl"
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

// ── gradient 3-kolorowy ──────────────────────────────────────────────────────
// GRADIENT_MODE: rgb
vec3 bottom = vec3(0.5, 0.0, 0.0);
vec3 mid    = vec3(0.9, 0.1, 0.1);
vec3 top    = vec3(0.8, 0.8, 0.8);

vec4 gradient_color(float t) {
    // RGB: proste mieszanie kolorów
    vec3 col = t < 0.5
        ? mix(bottom, mid, t * 2.0)
        : mix(mid, top, (t - 0.5) * 2.0);
    return vec4(col, 1.0);
}
// ─────────────────────────────────────────────────────────────────────────────

void main() {

    #if MIRROR_YX == 0
    #define AREA_WIDTH screen.x
    #define AREA_HEIGHT screen.y
    #define AREA_X gl_FragCoord.x
    #define AREA_Y gl_FragCoord.y
    #else
    #define AREA_WIDTH screen.y
    #define AREA_HEIGHT screen.x
    #define AREA_X gl_FragCoord.y
    #define AREA_Y gl_FragCoord.x
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
        if (d < v - BAR_OUTLINE_WIDTH) {
            #if BAR_OUTLINE_WIDTH > 0
            if (md < ceil(float(BAR_WIDTH) / 2) - BAR_OUTLINE_WIDTH &&
                md >= -floor(float(BAR_WIDTH) / 2) + BAR_OUTLINE_WIDTH)
                fragment = gradient_color(clamp(d / float(AREA_HEIGHT), 0.0, 1.0));
            else
                fragment = gradient_color(clamp(d / float(AREA_HEIGHT), 0.0, 1.0)) * 1.5;
            #else
            fragment = gradient_color(clamp(d / float(AREA_HEIGHT), 0.0, 1.0));
            #endif
            return;
        }
        #if BAR_OUTLINE_WIDTH > 0
        if (d <= v) {
            fragment = gradient_color(clamp(d / float(AREA_HEIGHT), 0.0, 1.0)) * 1.5;
            return;
        }
        #endif
    }
    fragment = vec4(0, 0, 0, 0);
}
