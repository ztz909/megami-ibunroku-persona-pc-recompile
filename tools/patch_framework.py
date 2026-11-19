"""Add host menus (F-keys) and host settings services to a psxrecomp framework copy.

Usage: patch_framework.py <psxrecomp dir> [...]

psxrecomp lets trusted plugins run every frame but gives them no way to show a menu or change the host's own
settings. This adds both, generic and small, so game plugins (PersonaRedeted/mods/debug_menu.c on F9,
options_menu.c on F10) can own full-screen menus:
  - include/mod_plugins.h   PSXModMenu, psx_mod_register_menu[_hotkey](), PSX_MOD_KEY_* codes,
                            psx_mod_host_get/set/save_settings/path and the PSX_MOD_HOST_* setting ids
  - src/mod_runtime.cpp     the menu registry: which menu is open, key routing, overlay image
  - src/main.cpp            an F-key with a registered menu opens it (controller: Guide, or Select+L1+R1 = F10,
                            Select+L2+R2 = F9); while it is open the guest is paused (same pause loop as the
                            save-state menu) and keys / the first controller's d-pad, stick, A, B, L1, R1 go to
                            the plugin. Key / button capture for rebinding. The host settings, keyboard binds and
                            controller mapping services live here because they are main.cpp's own statics.
                            Player 1 reads the keyboard AND every connected controller (psxrecomp's
                            PSX_DEV_INPUT merge, made the default; PSX_DEV_INPUT=0 turns it off): without
                            psxrecomp's launcher nothing would assign a controller to player 1.
                            Disc hook: every disc image the runtime is about to use (game.toml, disc.cfg,
                            --disc, the file picker) goes through the plugin's check first, which may
                            replace it (e.g. a patched copy) or refuse it (the picker opens again); the
                            plugin can also supply the picker's explanation text.
  - src/gpu_gl_renderer.c   draws the menu image over the frame (OpenGL renderer; Vulkan/software: not yet)
  - src/host_osd.c          keeps presenting while a menu is open
Safe to run again: a file that already has this version is left alone. A file with the older F9-only version
(marker psx_mod_menu, no psx_mod_disc_prepare) is first restored from the unpatched copy in PersonaRecomp/psxrecomp.
tools/recomp_patched.py runs this on the framework it copies.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRISTINE = os.path.join(os.path.dirname(HERE), "PersonaRecomp", "psxrecomp")
MARK = "psx_mod_disc_prepare"      # this version
OLD_MARK = "psx_mod_menu"          # any version

HEADER = r'''
/*
 * Host menus: trusted plugins may own full-screen menus, each opened with its own F-key (added by this
 * repository's tools/patch_framework.py; psx_mod_register_menu() = F9). While one is open the guest is
 * paused; keys arrive as PSX_MOD_KEY_* in on_key (return 0 to close) and image() supplies the ARGB8888
 * picture drawn over the frame. Guest memory: the psx_mod_read_* / psx_mod_write_* services above.
 */
enum {
    PSX_MOD_KEY_UP = 1, PSX_MOD_KEY_DOWN, PSX_MOD_KEY_LEFT, PSX_MOD_KEY_RIGHT,
    PSX_MOD_KEY_ENTER, PSX_MOD_KEY_BACK, PSX_MOD_KEY_PAGE_UP, PSX_MOD_KEY_PAGE_DOWN,
    PSX_MOD_KEY_MENU,                   /* the menu's own F-key again */
    PSX_MOD_KEY_CAPTURED                /* a capture started with psx_mod_capture_begin() ended */
};
typedef struct PSXModMenu {
    void (*on_open)(void);
    int  (*on_key)(int key);
    int  (*image)(const uint32_t** pixels, int* w, int* h);
} PSXModMenu;
int  psx_mod_register_menu(const PSXModMenu* menu);                    /* F9 */
int  psx_mod_register_menu_hotkey(const PSXModMenu* menu, int fkey);   /* fkey 1..12 = F1..F12 */
int  psx_mod_menu_registered(void);
int  psx_mod_menu_is_open(void);
int  psx_mod_menu_open_hotkey(void);    /* F-key of the open menu, 0 = none */
int  psx_mod_menu_hotkey(int fkey);     /* open the menu of that F-key; 0 = none registered */
void psx_mod_menu_set_open(int open);   /* open the F9 menu / close the open one */
void psx_mod_menu_key(int key);
int  psx_mod_menu_overlay_image(const uint32_t** pixels, int* w, int* h);

/*
 * Host settings for an options menu. get/set act on the running game where the runtime allows it;
 * psx_mod_host_save_settings() merges them into settings.toml next to the exe (read at the next start).
 */
enum {
    PSX_MOD_HOST_FULLSCREEN = 1,   /* 0 windowed, 1 borderless fullscreen, 2 exclusive fullscreen (live) */
    PSX_MOD_HOST_SUPERSAMPLING,    /* 1..4 internal resolution (saved; applies at the next start) */
    PSX_MOD_HOST_ANTIALIASING,     /* 0/1 smooth (linear) picture scaling (live) */
    PSX_MOD_HOST_TEXTURE_FILTER,   /* 0 nearest, 1 bilinear (live) */
    PSX_MOD_HOST_GEOMETRY,         /* 0/1 sub-pixel geometry correction (live; visible at 2x and up) */
    PSX_MOD_HOST_SCREEN_KIND,      /* 0 raw, 1 crt, 2 composite, 3 trinitron colour model (live) */
    PSX_MOD_HOST_SCANLINES,        /* 0 off, 1..100 = on at that strength in percent (live) */
    PSX_MOD_HOST_VOLUME,           /* 0..100 host master volume (live; not in settings.toml) */
    PSX_MOD_HOST_SKIP_FMV,         /* 0/1 skip movies (live) */
    PSX_MOD_HOST_DEADZONE          /* 1..50 percent, analog stick deadzone of player 1 (live) */
};
int  psx_mod_host_get(int id);
int  psx_mod_host_set(int id, int value);
int  psx_mod_host_save_settings(void);
int  psx_mod_host_path(const char* name, char* out, int size);   /* <exe dir>/<name> */

/*
 * Rebinding (player 1; controller = the first connected one). Buttons 0..15 in keybinds.ini order: up down left right cross circle square triangle
 * l1 r1 l2 r2 l3 r3 start select. Keyboard: SDL scancodes, live, saved to keybinds.ini. Controller: input.ini
 * source names ("a", "dpup", "lefttrigger", "leftx-" ...), live, saved to input.ini (the per-model section
 * of the connected controller when input.ini has one, else [mapping]).
 * Capture: psx_mod_capture_begin(1 = next key, 2 = next controller button / axis); when it ends the menu gets
 * PSX_MOD_KEY_CAPTURED and psx_mod_capture_result() returns 0 cancelled (Esc, 6 s timeout), 1 key, 2 pad.
 */
int  psx_mod_capture_begin(int kind);
int  psx_mod_capture_result(int* scancode, char* source, int size);
int  psx_mod_key_get(int button);
void psx_mod_key_set(int button, int scancode);
void psx_mod_keys_reset(void);
void psx_mod_keys_save(void);
int  psx_mod_key_name(int scancode, char* out, int size);
int  psx_mod_pad_get(const char* psx_button, char* out, int size);
int  psx_mod_pad_set(const char* psx_button, const char* source);
void psx_mod_pad_reset(void);
int  psx_mod_pad_save(void);
int  psx_mod_pad_connected(char* name, int size);                /* 1 + name when player 1 has a controller */

/*
 * Disc check: fn(disc, out, size) returns 1 and the image to use in out (the same one, or e.g. a patched copy),
 * or 0 to refuse it (after telling the player why). prompt: the text shown before the file picker (NULL = the
 * runtime's own). psx_mod_disc_prepare() runs the registered check (none registered: out = disc).
 */
typedef int (*PSXModDiscPrepare)(const char* disc, char* out, int size);
void        psx_mod_register_disc_prepare(PSXModDiscPrepare fn, const char* prompt);
int         psx_mod_disc_prepare(const char* disc, char* out, int size);
const char* psx_mod_disc_prompt(void);

#ifdef __cplusplus
}
#endif
'''

RUNTIME = r'''

/* ---- Host menus (tools/patch_framework.py) ---- */
struct PsxModMenuSlot { const PSXModMenu* menu; int fkey; };
static PsxModMenuSlot g_psx_mod_menus[8];
static int g_psx_mod_menu_count = 0;
static int g_psx_mod_menu_open = -1;     /* index into g_psx_mod_menus, -1 = none */

extern "C" int psx_mod_register_menu_hotkey(const PSXModMenu* menu, int fkey) {
    if (!menu || !menu->on_key || !menu->image || fkey < 1 || fkey > 12) return 0;
    for (int i = 0; i < g_psx_mod_menu_count; i++)
        if (g_psx_mod_menus[i].fkey == fkey) { g_psx_mod_menus[i].menu = menu; return 1; }
    if (g_psx_mod_menu_count == 8) return 0;
    g_psx_mod_menus[g_psx_mod_menu_count++] = PsxModMenuSlot{menu, fkey};
    return 1;
}

extern "C" int psx_mod_register_menu(const PSXModMenu* menu) { return psx_mod_register_menu_hotkey(menu, 9); }

extern "C" int psx_mod_menu_registered(void) { return g_psx_mod_menu_count > 0; }

extern "C" int psx_mod_menu_is_open(void) { return g_psx_mod_menu_open >= 0; }

extern "C" int psx_mod_menu_open_hotkey(void) {
    return g_psx_mod_menu_open >= 0 ? g_psx_mod_menus[g_psx_mod_menu_open].fkey : 0;
}

extern "C" int psx_mod_menu_hotkey(int fkey) {
    for (int i = 0; i < g_psx_mod_menu_count; i++) {
        if (g_psx_mod_menus[i].fkey != fkey) continue;
        if (g_psx_mod_menu_open < 0) {
            if (g_psx_mod_menus[i].menu->on_open) g_psx_mod_menus[i].menu->on_open();
            g_psx_mod_menu_open = i;
        }
        return 1;
    }
    return 0;
}

extern "C" void psx_mod_menu_set_open(int open) {
    if (open) (void)psx_mod_menu_hotkey(9);
    else g_psx_mod_menu_open = -1;
}

extern "C" void psx_mod_menu_key(int key) {
    if (g_psx_mod_menu_open >= 0 && !g_psx_mod_menus[g_psx_mod_menu_open].menu->on_key(key))
        g_psx_mod_menu_open = -1;
}

extern "C" int psx_mod_menu_overlay_image(const uint32_t** pixels, int* w, int* h) {
    if (g_psx_mod_menu_open < 0) return 0;
    return g_psx_mod_menus[g_psx_mod_menu_open].menu->image(pixels, w, h);
}

/* ---- Disc check (tools/patch_framework.py) ---- */
static PSXModDiscPrepare g_psx_mod_disc_prepare = nullptr;
static const char* g_psx_mod_disc_prompt = nullptr;

extern "C" void psx_mod_register_disc_prepare(PSXModDiscPrepare fn, const char* prompt) {
    g_psx_mod_disc_prepare = fn;
    g_psx_mod_disc_prompt = prompt;
}

extern "C" int psx_mod_disc_prepare(const char* disc, char* out, int size) {
    if (!disc || !out || size <= 0) return 0;
    if (g_psx_mod_disc_prepare) return g_psx_mod_disc_prepare(disc, out, size);
    std::snprintf(out, (size_t)size, "%s", disc);
    return 1;
}

extern "C" const char* psx_mod_disc_prompt(void) { return g_psx_mod_disc_prompt; }
'''

MAIN_LOOP = r'''
/* Host menus of trusted plugins (tools/patch_framework.py): guest paused, keys to the plugin. */
static int mod_menu_key_code(SDL_Keycode key) {
    if (key >= SDLK_F1 && key <= SDLK_F12)
        return (int)(key - SDLK_F1) + 1 == psx_mod_menu_open_hotkey() ? PSX_MOD_KEY_MENU : 0;
    switch (key) {
    case SDLK_UP:        return PSX_MOD_KEY_UP;
    case SDLK_DOWN:      return PSX_MOD_KEY_DOWN;
    case SDLK_LEFT:      return PSX_MOD_KEY_LEFT;
    case SDLK_RIGHT:     return PSX_MOD_KEY_RIGHT;
    case SDLK_RETURN:
    case SDLK_KP_ENTER:
    case SDLK_SPACE:     return PSX_MOD_KEY_ENTER;
    case SDLK_ESCAPE:
    case SDLK_BACKSPACE: return PSX_MOD_KEY_BACK;
    case SDLK_PAGEUP:    return PSX_MOD_KEY_PAGE_UP;
    case SDLK_PAGEDOWN:  return PSX_MOD_KEY_PAGE_DOWN;
    default:             return 0;
    }
}

/* Controller sources by input.ini name (the names parse_controller_source() reads). */
struct ModPadName { int id; const char* name; };
static const ModPadName kModPadButtons[] = {
    {SDL_CONTROLLER_BUTTON_A, "a"}, {SDL_CONTROLLER_BUTTON_B, "b"}, {SDL_CONTROLLER_BUTTON_X, "x"},
    {SDL_CONTROLLER_BUTTON_Y, "y"}, {SDL_CONTROLLER_BUTTON_BACK, "back"}, {SDL_CONTROLLER_BUTTON_START, "start"},
    {SDL_CONTROLLER_BUTTON_LEFTSTICK, "leftstick"}, {SDL_CONTROLLER_BUTTON_RIGHTSTICK, "rightstick"},
    {SDL_CONTROLLER_BUTTON_LEFTSHOULDER, "leftshoulder"}, {SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, "rightshoulder"},
    {SDL_CONTROLLER_BUTTON_DPAD_UP, "dpup"}, {SDL_CONTROLLER_BUTTON_DPAD_DOWN, "dpdown"},
    {SDL_CONTROLLER_BUTTON_DPAD_LEFT, "dpleft"}, {SDL_CONTROLLER_BUTTON_DPAD_RIGHT, "dpright"},
};
static const ModPadName kModPadAxes[] = {
    {SDL_CONTROLLER_AXIS_LEFTX, "leftx"}, {SDL_CONTROLLER_AXIS_LEFTY, "lefty"},
    {SDL_CONTROLLER_AXIS_RIGHTX, "rightx"}, {SDL_CONTROLLER_AXIS_RIGHTY, "righty"},
    {SDL_CONTROLLER_AXIS_TRIGGERLEFT, "lefttrigger"}, {SDL_CONTROLLER_AXIS_TRIGGERRIGHT, "righttrigger"},
};
static const int kModPadButtonCount = (int)(sizeof(kModPadButtons) / sizeof(kModPadButtons[0]));
static const int kModPadAxisCount = (int)(sizeof(kModPadAxes) / sizeof(kModPadAxes[0]));
static const int kModAxisPress = 20000;

/* every capturable source of a controller as one bit: buttons, then axis-, axis+ */
static uint64_t mod_pad_sources_down(SDL_GameController* h) {
    uint64_t m = 0;
    if (!h) return 0;
    for (int i = 0; i < kModPadButtonCount; i++)
        if (SDL_GameControllerGetButton(h, (SDL_GameControllerButton)kModPadButtons[i].id))
            m |= 1ull << i;
    for (int i = 0; i < kModPadAxisCount; i++) {
        const int v = SDL_GameControllerGetAxis(h, (SDL_GameControllerAxis)kModPadAxes[i].id);
        if (v < -kModAxisPress) m |= 1ull << (kModPadButtonCount + 2 * i);
        if (v > kModAxisPress)  m |= 1ull << (kModPadButtonCount + 2 * i + 1);
    }
    return m;
}

static std::string mod_pad_source_name(int bit) {
    if (bit < kModPadButtonCount) return kModPadButtons[bit].name;
    const int a = (bit - kModPadButtonCount) / 2, plus = (bit - kModPadButtonCount) & 1;
    const std::string n = kModPadAxes[a].name;
    if (kModPadAxes[a].id == SDL_CONTROLLER_AXIS_TRIGGERLEFT || kModPadAxes[a].id == SDL_CONTROLLER_AXIS_TRIGGERRIGHT)
        return n;
    return n + (plus ? "+" : "-");
}

/* The first connected controller (player 1 reads every controller, see dev_any_input_enabled). */
static SDL_GameController* mod_first_controller(std::string* guid) {
    const int n = SDL_NumJoysticks();
    for (int i = 0; i < n; i++) {
        if (!SDL_IsGameController(i)) continue;
        SDL_GameController* h = SDL_GameControllerFromInstanceID(SDL_JoystickGetDeviceInstanceID(i));
        if (!h) h = SDL_GameControllerOpen(i);
        if (!h) continue;
        if (guid) {
            char g[40];
            SDL_JoystickGetGUIDString(SDL_JoystickGetDeviceGUID(i), g, (int)sizeof g);
            *guid = g;
        }
        return h;
    }
    return nullptr;
}

/* capture state (psx_mod_capture_begin) */
static int      g_mod_cap_kind = 0;         /* 0 none, 1 key, 2 controller */
static int      g_mod_cap_result = 0;       /* 0 cancelled, 1 key, 2 controller */
static int      g_mod_cap_scancode = 0;
static char     g_mod_cap_source[32];
static uint64_t g_mod_cap_held = 0;         /* sources already down when the capture began */
static Uint32   g_mod_cap_start = 0;

static void mod_capture_end(int result) {
    g_mod_cap_kind = 0;
    g_mod_cap_result = result;
    psx_mod_menu_key(PSX_MOD_KEY_CAPTURED);
}

extern "C" int psx_mod_capture_begin(int kind) {
    if (kind == 2 && !mod_first_controller(nullptr)) return 0;
    g_mod_cap_kind = kind == 2 ? 2 : 1;
    g_mod_cap_result = 0;
    g_mod_cap_scancode = 0;
    g_mod_cap_source[0] = 0;
    g_mod_cap_held = mod_pad_sources_down(mod_first_controller(nullptr));
    g_mod_cap_start = SDL_GetTicks();
    return 1;
}

extern "C" int psx_mod_capture_result(int* scancode, char* source, int size) {
    if (scancode) *scancode = g_mod_cap_scancode;
    if (source && size > 0) std::snprintf(source, (size_t)size, "%s", g_mod_cap_source);
    return g_mod_cap_result;
}

/* first controller -> menu keys: d-pad / left stick move (with repeat), A enter, B back, L1/R1 page */
static int mod_menu_pad_nav(SDL_GameController* h) {
    if (!h) return 0;
    const int ly = SDL_GameControllerGetAxis(h, SDL_CONTROLLER_AXIS_LEFTY);
    const int lx = SDL_GameControllerGetAxis(h, SDL_CONTROLLER_AXIS_LEFTX);
    int m = 0;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_DPAD_UP) || ly < -kModAxisPress)    m |= 1 << PSX_MOD_KEY_UP;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_DPAD_DOWN) || ly > kModAxisPress)   m |= 1 << PSX_MOD_KEY_DOWN;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_DPAD_LEFT) || lx < -kModAxisPress)  m |= 1 << PSX_MOD_KEY_LEFT;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_DPAD_RIGHT) || lx > kModAxisPress)  m |= 1 << PSX_MOD_KEY_RIGHT;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_A))             m |= 1 << PSX_MOD_KEY_ENTER;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_B))             m |= 1 << PSX_MOD_KEY_BACK;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_LEFTSHOULDER))  m |= 1 << PSX_MOD_KEY_PAGE_UP;
    if (SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)) m |= 1 << PSX_MOD_KEY_PAGE_DOWN;
    return m;
}

static void mod_menu_host_pause_loop(void) {
    int pad_prev = -1;                      /* -1: take the buttons held at open as already handled */
    Uint32 repeat_at = 0;
    while (psx_mod_menu_is_open()) {
        SDL_Event ev;
        while (SDL_PollEvent(&ev)) {
            if (ev.type == SDL_QUIT) {
                psx_crash_trace_set_exit_origin("sdl_window_close");
                shutdown_runtime();
                std::exit(0);
            } else if (ev.type == SDL_KEYDOWN) {
#if defined(PSX_SDL3)
                const SDL_Keycode key = ev.key.key;
                const SDL_Scancode sc = ev.key.scancode;
                const int repeat = ev.key.repeat ? 1 : 0;
#else
                const SDL_Keycode key = ev.key.keysym.sym;
                const SDL_Scancode sc = ev.key.keysym.scancode;
                const int repeat = ev.key.repeat ? 1 : 0;
#endif
                if (g_mod_cap_kind) {
                    if (repeat) continue;
                    if (key == SDLK_ESCAPE) { mod_capture_end(0); continue; }
                    if (g_mod_cap_kind == 1) { g_mod_cap_scancode = (int)sc; mod_capture_end(1); }
                    continue;
                }
                const int code = mod_menu_key_code(key);
                if (code)
                    psx_mod_menu_key(code);
            }
        }
        SDL_GameController* h = mod_first_controller(nullptr);
        if (g_mod_cap_kind == 2) {
            const uint64_t down = mod_pad_sources_down(h);
            g_mod_cap_held &= down;                          /* released sources count again */
            const uint64_t fresh = down & ~g_mod_cap_held;
            for (int b = 0; fresh && b < 64; b++) {
                if (!(fresh >> b & 1)) continue;
                std::snprintf(g_mod_cap_source, sizeof g_mod_cap_source, "%s", mod_pad_source_name(b).c_str());
                mod_capture_end(2);
                break;
            }
            if (g_mod_cap_kind == 2 && (!h || SDL_GetTicks() - g_mod_cap_start > 6000)) mod_capture_end(0);
            pad_prev = -1;
        } else if (!g_mod_cap_kind) {
            const int now = mod_menu_pad_nav(h);
            if (pad_prev < 0) pad_prev = now;
            const int fresh = now & ~pad_prev;
            const int dirs = (1 << PSX_MOD_KEY_UP) | (1 << PSX_MOD_KEY_DOWN) | (1 << PSX_MOD_KEY_LEFT) | (1 << PSX_MOD_KEY_RIGHT);
            for (int k = PSX_MOD_KEY_UP; k <= PSX_MOD_KEY_PAGE_DOWN && psx_mod_menu_is_open(); k++) {
                if (fresh >> k & 1) {
                    psx_mod_menu_key(k);
                    repeat_at = SDL_GetTicks() + 350;
                } else if ((now & pad_prev) >> k & 1 && (dirs >> k & 1) && SDL_GetTicks() >= repeat_at) {
                    psx_mod_menu_key(k);                     /* held direction repeats */
                    repeat_at = SDL_GetTicks() + 90;
                }
            }
            pad_prev = now;
        }
        rewind_pause_present();
        starvation_watchdog_heartbeat();
        SDL_Delay(8);
    }
    g_mod_cap_kind = 0;
    /* Swallow the close press, like the save-state menu. */
    savestate_input_guard_arm();
}

/* Controller chords that open the menus: Guide or Select+L1+R1 = F10, Select+L2+R2 = F9 */
static void mod_menu_poll_pad_buttons(void) {
    static int was_options, was_debug;
    SDL_GameController* h = mod_first_controller(nullptr);
    int options = 0, debug = 0;
    if (h && !psx_mod_menu_is_open()) {
        const int sel = SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_BACK);
        options = SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_GUIDE) ||
                  (sel && SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_LEFTSHOULDER) &&
                   SDL_GameControllerGetButton(h, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER));
        debug = sel && SDL_GameControllerGetAxis(h, SDL_CONTROLLER_AXIS_TRIGGERLEFT) > kModAxisPress &&
                SDL_GameControllerGetAxis(h, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > kModAxisPress;
        if (options && !was_options) (void)psx_mod_menu_hotkey(10);
        else if (debug && !was_debug) (void)psx_mod_menu_hotkey(9);
    }
    was_options = options;
    was_debug = debug;
}

/* Host settings services (mod_plugins.h). The settings are this file's own statics. */
static int g_psx_mod_pending_scale = 0;   /* supersampling chosen in a menu, applies at the next start */

static int psx_mod_host_fullscreen_now(void) {
    if (!sdl_window || !(SDL_GetWindowFlags(sdl_window) & SDL_WINDOW_FULLSCREEN)) return 0;
    return g_fullscreen == 2 ? 2 : 1;
}

static int psx_mod_deadzone_percent(void) {
    return (controller_deadzone * 100 + 32767 / 2) / 32767;     /* the merged controllers use this one */
}

extern "C" int psx_mod_host_get(int id) {
    switch (id) {
    case PSX_MOD_HOST_FULLSCREEN:     return psx_mod_host_fullscreen_now();
    case PSX_MOD_HOST_SUPERSAMPLING:  return g_psx_mod_pending_scale ? g_psx_mod_pending_scale
                                             : (g_video_scale < 1 ? 1 : g_video_scale);
    case PSX_MOD_HOST_ANTIALIASING:   return g_video_aa ? 1 : 0;
    case PSX_MOD_HOST_TEXTURE_FILTER: return g_video_texfilter ? 1 : 0;
    case PSX_MOD_HOST_GEOMETRY:       return g_video_geometry_correction ? 1 : 0;
    case PSX_MOD_HOST_SCREEN_KIND:    return g_video_screen;
    case PSX_MOD_HOST_SCANLINES: {
        float strength = 0.f;
        return psx_video_get_scanlines(&strength) ? (int)(strength * 100.f + 0.5f) : 0;
    }
    case PSX_MOD_HOST_VOLUME:         return host_volume_get();
    case PSX_MOD_HOST_SKIP_FMV:       return g_auto_skip_fmv ? 1 : 0;
    case PSX_MOD_HOST_DEADZONE:       return psx_mod_deadzone_percent();
    default:                          return -1;
    }
}

extern "C" int psx_mod_host_set(int id, int v) {
    switch (id) {
    case PSX_MOD_HOST_FULLSCREEN:
        if (v < 0 || v > 2 || !sdl_window) return 0;
        SDL_SetWindowFullscreen(sdl_window, 0);          /* via windowed, also between the two fullscreen kinds */
        if (v) {
            g_fullscreen = v;
            Uint32 target = psx_fullscreen_flag_for_mode(v);
            if (target == 0) target = SDL_WINDOW_FULLSCREEN_DESKTOP;
            SDL_SetWindowFullscreen(sdl_window, target);
        }
        return 1;
    case PSX_MOD_HOST_SUPERSAMPLING:
        if (v < 1 || v > 4) return 0;
        g_psx_mod_pending_scale = v;
        return 1;
    case PSX_MOD_HOST_ANTIALIASING:
        g_video_aa = v != 0;
        return 1;
    case PSX_MOD_HOST_TEXTURE_FILTER:
        g_video_texfilter = v ? 1 : 0;
        gr_set_texture_filter(g_video_texfilter);
        return 1;
    case PSX_MOD_HOST_GEOMETRY:
        g_video_geometry_correction = v ? 1 : 0;
        gte_geometry_correction_set(g_video_geometry_correction);
        return 1;
    case PSX_MOD_HOST_SCREEN_KIND:
        if (v < 0 || v > 3) return 0;
        g_video_screen = v;
        gpu_set_screen_kind(v);
        return 1;
    case PSX_MOD_HOST_SCANLINES:
        if (v < 0 || v > 100) return 0;
        psx_video_set_scanlines(v > 0, v > 0 ? (float)v / 100.f : -1.f);
        return 1;
    case PSX_MOD_HOST_VOLUME:
        host_volume_set(v);
        return 1;
    case PSX_MOD_HOST_SKIP_FMV:
        g_auto_skip_fmv = v ? 1 : 0;
        return 1;
    case PSX_MOD_HOST_DEADZONE:
        if (v < 1 || v > 50) return 0;
        controller_deadzone = v * 32767 / 100;                 /* saved in input.ini (psx_mod_pad_save) */
        g_players[0].deadzone = controller_deadzone;           /* and settings.toml, for an assigned pad */
        return 1;
    default:
        return 0;
    }
}

extern "C" int psx_mod_host_save_settings(void) {
    const std::filesystem::path path = exe_dir_from_argv("") / "settings.toml";
    PSXRecompV4::UserSettings us = PSXRecompV4::load_user_settings(path);
    if (us.parse_error) return 0;                         /* never overwrite a file the user broke by hand */
    us.fullscreen = psx_mod_host_fullscreen_now();        us.has_fullscreen = true;
    us.supersampling = psx_mod_host_get(PSX_MOD_HOST_SUPERSAMPLING); us.has_supersampling = true;
    us.antialiasing = g_video_aa;                         us.has_antialiasing = true;
    us.texture_filter = g_video_texfilter ? 1 : 0;       us.has_texture_filter = true;
    us.geometry_correction = g_video_geometry_correction != 0; us.has_geometry_correction = true;
    us.screen_kind = g_video_screen;                      us.has_screen_kind = true;
    float strength = 0.5f;
    us.scanlines = psx_video_get_scanlines(&strength) != 0; us.has_scanlines = true;
    us.scanline_strength = strength;                      us.has_scanline_strength = true;
    us.auto_skip_fmv = g_auto_skip_fmv != 0;              us.has_auto_skip_fmv = true;
    if (g_players[0].deadzone > 0) {
        us.p_deadzone[0] = g_players[0].deadzone;         us.has_p_deadzone[0] = true;
        us.deadzone = g_players[0].deadzone;              us.has_deadzone = true;
    }
    return PSXRecompV4::save_user_settings(path, us) ? 1 : 0;
}

extern "C" int psx_mod_host_path(const char* name, char* out, int size) {
    if (!name || !out || size <= 0) return 0;
    const std::string p = (exe_dir_from_argv("") / name).string();
    if ((int)p.size() >= size) return 0;
    std::memcpy(out, p.c_str(), p.size() + 1);
    return 1;
}

/* Keyboard binds of player 1 (psx_keybinds: live map + keybinds.ini). */
extern "C" int  psx_mod_key_get(int button) { return (int)psx_keybinds_get_button(1, button); }
extern "C" void psx_mod_key_set(int button, int sc) { psx_keybinds_set_button(1, button, (SDL_Scancode)sc); }
extern "C" void psx_mod_keys_reset(void) { psx_keybinds_reset_player(1); }
extern "C" void psx_mod_keys_save(void) { psx_keybinds_save(); }
extern "C" int psx_mod_key_name(int sc, char* out, int size) {
    if (!out || size <= 0) return 0;
    const char* n = sc ? SDL_GetScancodeName((SDL_Scancode)sc) : "";
    std::snprintf(out, (size_t)size, "%s", (n && n[0]) ? n : "NONE");
    return 1;
}

/* Controller mapping of player 1: the per-model map when input.ini has one for this controller, else the
 * global [mapping]. Edited live; psx_mod_pad_save() rewrites input.ini with all maps. */
static ControllerMap& mod_pad_map(void) {
    std::string guid;
    if (mod_first_controller(&guid) && !guid.empty()) {
        auto it = controller_maps_by_guid.find(guid);
        if (it != controller_maps_by_guid.end()) return it->second;
    }
    return controller_map;
}

static std::string mod_pad_sources_text(const std::vector<ControllerSource>& sources) {
    std::string out;
    for (const ControllerSource& s : sources) {
        std::string n;
        if (s.kind == ControllerSource::Kind::Button) {
            for (int i = 0; i < kModPadButtonCount; i++)
                if (kModPadButtons[i].id == s.id) n = kModPadButtons[i].name;
        } else if (s.kind != ControllerSource::Kind::None) {
            for (int i = 0; i < kModPadAxisCount; i++)
                if (kModPadAxes[i].id == s.id)
                    n = mod_pad_source_name(kModPadButtonCount + 2 * i +
                                            (s.kind == ControllerSource::Kind::AxisPositive ? 1 : 0));
        }
        if (n.empty()) continue;
        if (!out.empty()) out += ",";
        out += n;
    }
    return out;
}

extern "C" int psx_mod_pad_get(const char* name, char* out, int size) {
    if (!name || !out || size <= 0) return 0;
    for (const auto& e : mod_pad_map())
        if (std::strcmp(e.ini_name, name) == 0) {
            std::snprintf(out, (size_t)size, "%s", mod_pad_sources_text(e.sources).c_str());
            return 1;
        }
    return 0;
}

extern "C" int psx_mod_pad_set(const char* name, const char* source) {
    if (!name || !source) return 0;
    for (auto& e : mod_pad_map())
        if (std::strcmp(e.ini_name, name) == 0) {
            std::vector<ControllerSource> s = parse_source_list(source);
            if (s.empty()) return 0;
            e.sources = s;
            return 1;
        }
    return 0;
}

extern "C" void psx_mod_pad_reset(void) { set_default_controller_mapping_into(mod_pad_map()); }

extern "C" int psx_mod_pad_save(void) {
    const std::filesystem::path path = exe_dir_from_argv("") / "input.ini";
    std::string text = default_input_ini_text();
    text = text.substr(0, text.find("[controller]"));              /* keep the explanatory header */
    text += "[controller]\nenabled = true\ndevice = " + std::to_string(controller_device_index) +
            "\ndeadzone = " + std::to_string(controller_deadzone) + "\n\n[mapping]\n";
    for (const auto& e : controller_map)
        text += std::string(e.ini_name) + " = " + mod_pad_sources_text(e.sources) + "\n";
    for (const auto& kv : controller_maps_by_guid) {
        text += "\n[mapping." + kv.first + "]\n";
        for (const auto& e : kv.second)
            text += std::string(e.ini_name) + " = " + mod_pad_sources_text(e.sources) + "\n";
    }
    std::ofstream f(path, std::ios::binary | std::ios::trunc);
    if (!f) return 0;
    f << text;
    return f.good() ? 1 : 0;
}

extern "C" int psx_mod_pad_connected(char* name, int size) {
    SDL_GameController* h = mod_first_controller(nullptr);
    if (!h) return 0;
    if (name && size > 0) {
        const char* n = SDL_GameControllerName(h);
        std::snprintf(name, (size_t)size, "%s", n ? n : "CONTROLLER");
    }
    return 1;
}
'''

EDITS = {
    "include/mod_plugins.h": [("\n#ifdef __cplusplus\n}\n#endif\n", HEADER, "last")],
    "src/mod_runtime.cpp": [(None, RUNTIME, "append")],
    "src/main.cpp": [
        ("/* Epilogue for netplay admit/pace AFTER all C++ RAII", MAIN_LOOP + "\n/* Epilogue for netplay admit/pace AFTER all C++ RAII", "first"),
        ("""                    savestate_menu_toggle(key);
                }
""", """                    savestate_menu_toggle(key);
                }
                else if (!key_repeat && key >= SDLK_F1 && key <= SDLK_F12 &&
                         psx_mod_menu_hotkey((int)(key - SDLK_F1) + 1)) {
                    /* host menu of a plugin (tools/patch_framework.py) */
                }
""", "first"),
        ("""static std::filesystem::path resolve_disc_for_runtime(""",
         """/* The plugin's disc check (tools/patch_framework.py): the image to use, or empty = refused. */
static std::filesystem::path mod_disc_prepare(const std::filesystem::path& disc) {
    char out[4096];
    if (!psx_mod_disc_prepare(disc.string().c_str(), out, (int)sizeof out)) return {};
    return std::filesystem::path(out);
}

static std::filesystem::path resolve_disc_for_runtime(""", "first"),
        ("""        return validate_disc_for_launch(p, game_id) ? p : std::filesystem::path{};""",
         """        return validate_disc_for_launch(p, game_id) ? mod_disc_prepare(p) : std::filesystem::path{};""", "first"),
        ("""        if (std::filesystem::exists(cd) && validate_disc_for_launch(cd, game_id)) {
            return cd;
        }""", """        if (std::filesystem::exists(cd) && validate_disc_for_launch(cd, game_id)) {
            const std::filesystem::path prepared = mod_disc_prepare(cd);
            if (!prepared.empty()) return prepared;
        }""", "first"),
        ("""        validate_disc_for_launch(cached, game_id)) {
        return cached;
    }""", """        validate_disc_for_launch(cached, game_id)) {
        const std::filesystem::path prepared = mod_disc_prepare(cached);
        if (!prepared.empty()) return prepared;
    }""", "first"),
        ("""        if (validate_disc_for_launch(picked, game_id)) {
            write_cached_path(argv0, "disc.cfg", picked);
            return picked;
        }""", """        if (validate_disc_for_launch(picked, game_id)) {
            const std::filesystem::path prepared = mod_disc_prepare(picked);
            if (prepared.empty()) continue;                 /* refused: the plugin said why; pick again */
            write_cached_path(argv0, "disc.cfg", prepared);
            return prepared;
        }""", "first"),
        ("""    launcher_info((s_picker_game_name + " — game disc image needed").c_str(),
        "Step 2 of 2""", """    if (psx_mod_disc_prompt())
        launcher_info((s_picker_game_name + " — game disc image needed").c_str(), psx_mod_disc_prompt());
    else
    launcher_info((s_picker_game_name + " — game disc image needed").c_str(),
        "Step 2 of 2""", "first"),
        ("""        s_picker_game_name + " — Step 2 of 2: select " + s_picker_game_name +""",
         """        s_picker_game_name + " — select " + s_picker_game_name +""", "first"),
        ("""        cached = (value == "1" || value == "true" ||
                  value == "yes" || value == "on") ? 1 : 0;""",
         """        /* on by default (tools/patch_framework.py): player 1 = keyboard + every controller */
        cached = (value == "0" || value == "false" ||
                  value == "no" || value == "off") ? 0 : 1;""", "first"),
        ("""        savestate_menu_poll_toggle_buttons();
""", """        savestate_menu_poll_toggle_buttons();
        mod_menu_poll_pad_buttons();   /* controller chords for the host menus */
""", "first"),
        ("""        if (savestate_menu_open)
            savestate_menu_host_pause_loop();
        if (psx_rewind_is_open())""", """        if (savestate_menu_open)
            savestate_menu_host_pause_loop();
        if (psx_mod_menu_is_open())
            mod_menu_host_pause_loop();
        if (psx_rewind_is_open())""", "first"),
    ],
    "src/gpu_gl_renderer.c": [
        ("""            if (psx_savestate_menu_overlay_image(&px, &ow, &oh) && px)
                gl_draw_osd_image(px, ow, oh, ww, wh, 0, 0, ww, wh);
""", """            if (psx_savestate_menu_overlay_image(&px, &ow, &oh) && px)
                gl_draw_osd_image(px, ow, oh, ww, wh, 0, 0, ww, wh);
            if (psx_mod_menu_overlay_image(&px, &ow, &oh) && px)   /* host menu */
                gl_draw_osd_image(px, ow, oh, ww, wh, 0, 0, ww, wh);
""", "first"),
        ('#include "psx_savestate_menu.h"\n', '#include "psx_savestate_menu.h"\n#include "mod_plugins.h"\n', "first"),
    ],
    "src/host_osd.c": [
        ("    if (psx_savestate_menu_needs_present()) return 1;\n",
         "    if (psx_savestate_menu_needs_present()) return 1;\n    if (psx_mod_menu_is_open()) return 1;   /* host menu */\n", "first"),
        ('#include "psx_savestate_menu.h"\n', '#include "psx_savestate_menu.h"\n#include "mod_plugins.h"\n', "first"),
    ],
}
# files whose new code contains MARK; the others are only checked for OLD_MARK when deciding to restore
HAS_MARK = {"include/mod_plugins.h", "src/main.cpp"}


def patch(root):
    upgrade = any(OLD_MARK in open(os.path.join(root, "runtime", rel), encoding="utf-8").read() and
                  MARK not in open(os.path.join(root, "runtime", rel), encoding="utf-8").read()
                  for rel in HAS_MARK)
    for rel, edits in EDITS.items():
        path = os.path.join(root, "runtime", rel)
        if upgrade and OLD_MARK in open(path, encoding="utf-8").read():
            src = os.path.join(PRISTINE, "runtime", rel)
            if OLD_MARK in open(src, encoding="utf-8").read():
                raise SystemExit(f"{src}: not an unpatched copy, cannot upgrade {path}")
            shutil.copyfile(src, path)
            print(f"{rel}: restored from {PRISTINE} (older hook version)")
        eol = "\r\n" if b"\r\n" in open(path, "rb").read() else "\n"     # keep the file's line endings
        text = open(path, encoding="utf-8").read()
        if OLD_MARK in text:
            print(f"{rel}: already patched")
            continue
        for old, new, where in edits:
            if where == "append":
                text = text.rstrip("\n") + "\n" + new
                continue
            n = text.count(old)
            if n == 0 or (where == "first" and n != 1):
                raise SystemExit(f"{path}: anchor found {n} times, expected 1:\n{old}")
            if where == "last":
                i = text.rindex(old)
                text = text[:i] + new + text[i + len(old):]
            else:
                text = text.replace(old, new, 1)
        open(path, "w", encoding="utf-8", newline=eol).write(text)
        print(f"{rel}: patched")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for root in argv[1:]:
        patch(root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
