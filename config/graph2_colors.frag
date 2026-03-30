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

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM KOLORÓW — zgodny z Twoim GUI
// outline = ON
// highlight = OFF
// ─────────────────────────────────────────────────────────────────────────────
uniform vec3 bottom;
uniform vec3 mid;
uniform vec3 top;

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

    if (d + 1.5 <= s) {
        float t = clamp(d / max(s, 0.001), 0.0, 1.0);
        vec4 base = gradient_color(t);

        // highlight OFF, outline ON
        fragment = outline_color(base);
    } else {
        fragment = vec4(0, 0, 0, 0);
    }
}

void main() {
    half_w = (screen.x / 2);

    middle = VSCALE * (
        smooth_audio_adj(audio_l, audio_sz, 1, pixel) +
        smooth_audio_adj(audio_r, audio_sz, 0, pixel)
    ) / 2;

    if (gl_FragCoord.x < half_w) {
        render_side(audio_l, half_w - gl_FragCoord.x);
    } else {
        render_side(audio_r, gl_FragCoord.x - half_w);
    }
}
