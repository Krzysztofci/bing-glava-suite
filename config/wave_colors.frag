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
// SYSTEM KOLORÓW — ZGODNY Z TWOIM GUI
// GRADIENT_MODE: rgb
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
// ─────────────────────────────────────────────────────────────────────────────

#define index(offset) ((texture(audio_l, (gl_FragCoord.x + offset) / screen.x).r - 0.5) * AMPLIFY) + 0.5F

void main() {
    float os   = index(0);
    float adj0 = index(-1);
    float adj1 = index(1);

    float s0 = adj0 - os;
    float s1 = adj1 - os;

    float dmax = max(s0, s1);
    float dmin = min(s0, s1);

    float s = (os + (screen.y * 0.5F) - 0.5F);
    float diff = gl_FragCoord.y - s;

    if (abs(diff) < clamp(abs(s - (screen.y * 0.5)) * 6, MIN_THICKNESS, MAX_THICKNESS)
        || (diff <= dmax && diff >= dmin)) {

        float t = clamp(abs((screen.y * 0.5F) - s) / (screen.y * 0.5F), 0.0, 1.0);
        fragment = gradient_color(t);

    } else {
        fragment = vec4(0, 0, 0, 0);
    }
}

