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




// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM KOLORÓW — ZGODNY Z GUI
// ─────────────────────────────────────────────────────────────────────────────
vec3 bottom = vec3(0.00, 0.83, 1.00);
vec3 mid = vec3(0.10, 0.16, 0.42);
vec3 top = vec3(1.00, 0.71, 0.00);

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

    #if _USE_ALPHA > 0
    #define APPLY_FRAG(f, c) f = vec4(f.rgb * f.a + c.rgb * (1 - clamp(f.a, 0, 1)), max(c.a, f.a))
    fragment = #00000000;
    #else
    #define APPLY_FRAG(f, c) f = c
    #endif

    float dx = gl_FragCoord.x - (screen.x / 2) + CENTER_OFFSET_X;
    float dy = gl_FragCoord.y - (screen.y / 2) + CENTER_OFFSET_Y;

    float theta = atan(dy, dx);
    float d = sqrt(dx * dx + dy * dy);

    // ─────────────────────────────────────────────────────────────────────────
    // WYPEŁNIENIE WNĘTRZA OKRĘGU (reaguje na dźwięk)
    // ─────────────────────────────────────────────────────────────────────────
    if (d < C_RADIUS - (float(C_LINE) / 2.0F) && GRADIENT > 0) {
        float fill_r = float(C_RADIUS) * float(GRADIENT) / 100.0;
        float dist_from_edge = float(C_RADIUS) - d;
        if (dist_from_edge < fill_r) {
            float t = clamp(dist_from_edge / fill_r, 0.0, 1.0) * 0.5;
            APPLY_FRAG(fragment, gradient_color(t));
        #if _USE_ALPHA == 0
            return;
        #endif
        }
    }
    // ─────────────────────────────────────────────────────────────────────────
    // WEWNĘTRZNY OKRĄG (OUTLINE)
    // ─────────────────────────────────────────────────────────────────────────
    if (d > C_RADIUS - (float(C_LINE) / 2.0F) &&
        d < C_RADIUS + (float(C_LINE) / 2.0F)) {

        float t = clamp(1.0 - (d - (C_RADIUS - float(C_LINE) / 2.0)) / (float(C_LINE) / 2.0), 0.0, 1.0) * 0.5;
        vec4 base = gradient_color(t);

    #if USE_OUTLINE
        APPLY_FRAG(fragment, outline_color(base));
    #else
        APPLY_FRAG(fragment, base);
    #endif

    #if _USE_ALPHA > 0
        fragment.a *= clamp(((C_LINE / 2) - abs(C_RADIUS - d)) * C_ALIAS_FACTOR, 0, 1);
    #else
        return;
    #endif
    }

    // ─────────────────────────────────────────────────────────────────────────
    // ZEWNĘTRZNE SŁUPKI
    // ─────────────────────────────────────────────────────────────────────────
    if (d > C_RADIUS) {

        const float section = (TWOPI / NBARS);
        const float center = section / 2.0F;

        float m = mod(theta, section);
        float ym = d * sin(center - m);

        if (abs(ym) < BAR_WIDTH / 2) {

            float idx = mod(theta + ROTATE, TWOPI);
            if (idx > PI)  idx -= TWOPI;
            if (idx < -PI) idx += TWOPI;

            #if INVERT == 0
            idx = -idx;
            #endif

            float pos = clamp(int(abs(idx) / section) / float(NBARS / 2), 0.0, 1.0);

            #define smooth_f(tex) smooth_audio(tex, audio_sz, pos)
            float v = (idx > 0) ? smooth_f(audio_l) : smooth_f(audio_r);
            #undef smooth_f

            v *= AMPLIFY;

            #if _USE_ALPHA > 0
            #define ALIAS_FACTOR (((BAR_WIDTH / 2) - abs(ym)) * BAR_ALIAS_FACTOR)
            d -= C_RADIUS;
            #else
            #define ALIAS_FACTOR 1
            d -= C_RADIUS + (float(C_LINE) / 2.0F);
            #endif

            float t = clamp(d / max(v, 0.001), 0.0, 1.0);
            vec4 base = gradient_color(t);

            if (d <= v - BAR_OUTLINE_WIDTH) {

            #if USE_OUTLINE && BAR_OUTLINE_WIDTH > 0
                if (abs(ym) < (BAR_WIDTH / 2) - BAR_OUTLINE_WIDTH)
                    APPLY_FRAG(fragment, base);
                else
                    APPLY_FRAG(fragment, outline_color(base));
            #else
                APPLY_FRAG(fragment, base);
            #endif

            #if _USE_ALPHA > 0
                fragment.a *= ALIAS_FACTOR;
            #endif

                return;
            }

        #if USE_OUTLINE && BAR_OUTLINE_WIDTH > 0
            if (d <= v) {
                vec4 o = outline_color(base);
            #if _USE_ALPHA > 0
                o.a *= ALIAS_FACTOR;
            #endif
                APPLY_FRAG(fragment, o);
                return;
            }
        #endif
        }
    }

    fragment = APPLY_FRAG(fragment, vec4(0, 0, 0, 0));
}

