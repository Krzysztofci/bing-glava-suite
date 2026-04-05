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

#define index(offset) ((texture(audio_l, (gl_FragCoord.x + offset) / screen.x).r - 0.5) * AMPLIFY) + 0.5F

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM KOLORÓW — ZGODNY Z GUI
// ─────────────────────────────────────────────────────────────────────────────
vec3 bottom = vec3(0.00, 1.00, 0.00);
vec3 mid = vec3(0.00, 0.00, 1.00);
vec3 top = vec3(1.00, 0.00, 0.00);

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

        float t = clamp((s - (screen.y * 0.5F)) / (AMPLIFY * 0.5) + 0.5, 0.0, 1.0);
        fragment = gradient_color(t);

    } else {
        fragment = vec4(0, 0, 0, 0);
    }
}

