in vec4 gl_FragCoord;

#request uniform "screen" screen
uniform ivec2 screen;

#request uniform "audio_sz" audio_sz
uniform int audio_sz;

#include ":util/smooth.glsl"
#include "@radial.glsl"
#include ":radial.glsl"

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

    #if _USE_ALPHA > 0
    #define APPLY_FRAG(f, c) f = vec4(f.rgb * f.a + c.rgb * (1 - clamp(f.a, 0, 1)), max(c.a, f.a))
    fragment = #00000000;
    #else
    #define APPLY_FRAG(f, c) f = c
    #endif

    float
        dx = gl_FragCoord.x - (screen.x / 2) + CENTER_OFFSET_X,
        dy = gl_FragCoord.y - (screen.y / 2) + CENTER_OFFSET_Y;
    float theta = atan(dy, dx);
    float d     = sqrt((dx * dx) + (dy * dy));

    if (d > C_RADIUS - (float(C_LINE) / 2.0F) && d < C_RADIUS + (float(C_LINE) / 2.0F)) {
        // okrąg bazowy — kolor środkowy
        APPLY_FRAG(fragment, vec4(mid, 1.0));
        #if _USE_ALPHA > 0
        fragment.a *= clamp(((C_LINE / 2) - abs(C_RADIUS - d)) * C_ALIAS_FACTOR, 0, 1);
        #else
        return;
        #endif
    }
    if (d > C_RADIUS) {
        const float section = (TWOPI / NBARS);
        const float center  = ((TWOPI / NBARS) / 2.0F);
        float m   = mod(theta, section);
        float ym  = d * sin(center - m);
        if (abs(ym) < BAR_WIDTH / 2) {
            float idx = theta + ROTATE;
            float dir = mod(abs(idx), TWOPI);
            if (dir > PI)
                idx = -sign(idx) * (TWOPI - dir);
            #if INVERT == 0
            idx = -idx;
            #endif
            float pos = int(abs(idx) / section) / float(NBARS / 2);
            #define smooth_f(tex) smooth_audio(tex, audio_sz, pos)
            float v;
            if (idx > 0) v = smooth_f(audio_l);
            else         v = smooth_f(audio_r);
            v *= AMPLIFY;
            #undef smooth_f

            #if _USE_ALPHA > 0
            #define ALIAS_FACTOR (((BAR_WIDTH / 2) - abs(ym)) * BAR_ALIAS_FACTOR)
            d -= C_RADIUS;
            #else
            #define ALIAS_FACTOR 1
            d -= C_RADIUS + (float(C_LINE) / 2.0F);
            #endif

            if (d <= v - BAR_OUTLINE_WIDTH) {
                vec4 r;
                #if BAR_OUTLINE_WIDTH > 0
                if (abs(ym) < (BAR_WIDTH / 2) - BAR_OUTLINE_WIDTH)
                    r = gradient_color(clamp(d / 80.0, 0.0, 1.0));
                else
                    r = gradient_color(0.5) * 1.5;   // outline = rozjaśniony mid
                #else
                r = gradient_color(clamp(d / 80.0, 0.0, 1.0));
                #endif
                #if _USE_ALPHA > 0
                r.a *= ALIAS_FACTOR;
                #endif
                APPLY_FRAG(fragment, r);
                return;
            }
            #if BAR_OUTLINE_WIDTH > 0
            if (d <= v) {
                #if _USE_ALPHA > 0
                vec4 r = gradient_color(0.5) * 1.5;
                r.a *= ALIAS_FACTOR;
                APPLY_FRAG(fragment, r);
                #else
                APPLY_FRAG(fragment, gradient_color(0.5) * 1.5);
                #endif
                return;
            }
            #endif
        }
    }
    APPLY_FRAG(fragment, vec4(0, 0, 0, 0));
}
