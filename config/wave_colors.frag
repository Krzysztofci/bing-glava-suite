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

#define index(offset) ((texture(audio_l, (gl_FragCoord.x + offset) / screen.x).r - 0.5) * AMPLIFY) + 0.5F

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
    float
        os   = index(0),
        adj0 = index(-1),
        adj1 = index(1);
    float
        s0 = adj0 - os,
        s1 = adj1 - os;
    float
        dmax = max(s0, s1),
        dmin = min(s0, s1);

    float s    = (os + (screen.y * 0.5F) - 0.5F);
    float diff = gl_FragCoord.y - s;
    float dev  = abs(s - (screen.y * 0.5F));  // odchylenie od środka

    if (abs(diff) < clamp(dev * 6, MIN_THICKNESS, MAX_THICKNESS)
        || (diff <= dmax && diff >= dmin)) {
        fragment = gradient_color(clamp(dev / (float(screen.y) * 0.25), 0.0, 1.0));
    } else {
        fragment = vec4(0, 0, 0, 0);
    }
}
