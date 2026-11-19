/* options_menu.c - player options for the native exe (F10; controller: Guide, or Select+L1+R1).
 *
 * Opens over the game (host menu hook added to psxrecomp by tools/patch_framework.py); the game is paused
 * while it is open. Keys: Up/Down select, Left/Right change, Enter change / rebind, Esc or F10 close.
 * Controller: d-pad or left stick, A = Enter, B = close. The first row switches page.
 *
 *   DISPLAY & SOUND  screen mode, resolution (next start), picture options, volume, skip movies
 *   CONTROLS         keyboard and controller button for each PlayStation button, stick deadzone
 *
 * Every change applies at once and is saved straight away:
 *   - display options, deadzone -> settings.toml next to the exe (psxrecomp's own settings file)
 *   - volume                    -> persona_options.txt next to the exe (read back when the exe starts)
 *   - keyboard binds            -> keybinds.ini,   controller binds -> input.ini  (psxrecomp's own files)
 * The game's own options (message speed, mono/stereo, button functions) stay in its System > Config screen.
 */
#include <stdio.h>
#include <string.h>
#include "mod_plugins.h"
#include "menu_draw.h"

#define OPTIONS_FILE "persona_options.txt"
#define ROW_H 18                            /* compact rows: the controls page has 20 */
#define ROW_Y0 (MENU_Y0 + MENU_LINE + 6)

enum { PAGE_DISPLAY, PAGE_CONTROLS, PAGE_COUNT };
static const char* const PAGES[PAGE_COUNT] = {"DISPLAY & SOUND", "CONTROLS"};

/* ---- display & sound page (row 0 is the page tab) ---- */
enum { O_TAB, O_SCREEN, O_RES, O_SMOOTH, O_TEXFILTER, O_GEOMETRY, O_COLOUR, O_SCANLINES, O_VOLUME, O_SKIP_FMV,
       O_RESET, O_ROWS };

static const char* const LABELS[O_ROWS] = {
    "PAGE", "SCREEN MODE", "RESOLUTION *", "SMOOTH PICTURE", "TEXTURES", "LESS WOBBLE", "SCREEN COLOUR",
    "SCANLINES", "VOLUME", "SKIP MOVIES", "RESET TO DEFAULTS"};

static const char* const HELP[O_ROWS] = {
    "LEFT/RIGHT: OTHER PAGE",
    "WINDOWED, BORDERLESS OR FULLSCREEN",
    "INTERNAL RESOLUTION; AT THE NEXT START",
    "SMOOTH SCALING OF THE WHOLE PICTURE",
    "SHARP OR SMOOTHED TEXTURES",
    "STEADIER 3D (BEST AT 2X AND UP)",
    "COLOUR OF AN OLD TV: RAW = AS IS",
    "TV LINE EFFECT AND ITS STRENGTH",
    "MASTER VOLUME (ALSO KEYPAD +/-)",
    "SKIP THE GAME'S MOVIES",
    "ENTER: THIS PAGE BACK TO DEFAULT"};

/* host setting id and range of each row (step = change per Left/Right) */
static const struct { int id, min, max, step; } ROW[O_ROWS] = {
    {0, 0, 0, 0},
    {PSX_MOD_HOST_FULLSCREEN, 0, 2, 1},     {PSX_MOD_HOST_SUPERSAMPLING, 1, 4, 1},
    {PSX_MOD_HOST_ANTIALIASING, 0, 1, 1},   {PSX_MOD_HOST_TEXTURE_FILTER, 0, 1, 1},
    {PSX_MOD_HOST_GEOMETRY, 0, 1, 1},       {PSX_MOD_HOST_SCREEN_KIND, 0, 3, 1},
    {PSX_MOD_HOST_SCANLINES, 0, 100, 10},   {PSX_MOD_HOST_VOLUME, 0, 100, 5},
    {PSX_MOD_HOST_SKIP_FMV, 0, 1, 1},       {0, 0, 0, 0}};

/* psxrecomp's defaults (config_loader.h UserSettings), volume full */
static const int DEFAULTS[O_ROWS] = {0, 0, 1, 1, 0, 0, 0, 0, 100, 0, 0};

/* ---- controls page: buttons 0..15 in keybinds.ini order, then deadzone and the two resets ---- */
#define N_BUTTONS 16
static const char* const BTN_INI[N_BUTTONS] = {
    "up", "down", "left", "right", "cross", "circle", "square", "triangle",
    "l1", "r1", "l2", "r2", "l3", "r3", "start", "select"};
static const char* const BTN_LABEL[N_BUTTONS] = {
    "UP", "DOWN", "LEFT", "RIGHT", "CROSS", "CIRCLE", "SQUARE", "TRIANGLE",
    "L1", "R1", "L2", "R2", "L3", "R3", "START", "SELECT"};
enum { C_TAB, C_FIRST_BUTTON, C_DEADZONE = C_FIRST_BUTTON + N_BUTTONS, C_RESET_KEYS, C_RESET_PAD, C_ROWS };

static uint32_t s_px[MENU_W * MENU_H];
static int s_page, s_row;
static int s_col;                           /* controls page: 0 keyboard, 1 controller */
static int s_capturing = -1;                /* button being rebound, -1 = none */
static char s_msg[64];

/* ---- saving ---- */
static void save_volume(void) {
    char path[512];
    FILE* f;
    if (!psx_mod_host_path(OPTIONS_FILE, path, sizeof path) || !(f = fopen(path, "w"))) return;
    fprintf(f, "# Persona options menu (F10). settings.toml holds the display options.\nvolume = %d\n",
            psx_mod_host_get(PSX_MOD_HOST_VOLUME));
    fclose(f);
}

static void load_volume(void) {
    char path[512], line[128];
    int v;
    FILE* f;
    if (!psx_mod_host_path(OPTIONS_FILE, path, sizeof path) || !(f = fopen(path, "r"))) return;
    while (fgets(line, sizeof line, f))
        if (sscanf(line, " volume = %d", &v) == 1 && v >= 0 && v <= 100)
            psx_mod_host_set(PSX_MOD_HOST_VOLUME, v);
    fclose(f);
}

static void save_all(void) {
    save_volume();
    if (!psx_mod_host_save_settings())
        snprintf(s_msg, sizeof s_msg, "COULD NOT SAVE SETTINGS.TOML");
}

/* ---- names ---- */
/* input.ini source name -> short label (Xbox names: A = bottom face button) */
static void pad_label(const char* src, char* out, size_t n) {
    static const char* const MAP[][2] = {
        {"a", "A"}, {"b", "B"}, {"x", "X"}, {"y", "Y"}, {"back", "BACK"}, {"start", "START"},
        {"leftstick", "LS CLICK"}, {"rightstick", "RS CLICK"}, {"leftshoulder", "LB"}, {"rightshoulder", "RB"},
        {"lefttrigger", "LT"}, {"righttrigger", "RT"}, {"dpup", "DPAD UP"}, {"dpdown", "DPAD DOWN"},
        {"dpleft", "DPAD LEFT"}, {"dpright", "DPAD RIGHT"}, {"leftx-", "LS LEFT"}, {"leftx+", "LS RIGHT"},
        {"lefty-", "LS UP"}, {"lefty+", "LS DOWN"}, {"rightx-", "RS LEFT"}, {"rightx+", "RS RIGHT"},
        {"righty-", "RS UP"}, {"righty+", "RS DOWN"}};
    char buf[64];
    size_t used = 0;
    out[0] = 0;
    snprintf(buf, sizeof buf, "%s", src);
    for (char* tok = strtok(buf, ","); tok; tok = strtok(NULL, ",")) {
        const char* name = tok;
        for (size_t i = 0; i < sizeof MAP / sizeof MAP[0]; i++)
            if (strcmp(tok, MAP[i][0]) == 0) name = MAP[i][1];
        used += (size_t)snprintf(out + used, used < n ? n - used : 0, "%s%s", used ? "/" : "", name);
        if (used >= n) break;
    }
    if (!out[0]) snprintf(out, n, "NONE");
}

static void key_label(int button, char* out, size_t n) { psx_mod_key_name(psx_mod_key_get(button), out, (int)n); }

/* ---- drawing ---- */
static int row_y(int r) { return ROW_Y0 + r * ROW_H; }

static void draw_row_bg(int r) {
    if (r == s_row) menu_fill(s_px, MENU_X0 - 8, row_y(r) - 1, MENU_W - 2 * MENU_X0 + 16, ROW_H, MENU_SELECT);
}

static void value_text(int r, char* out, size_t n) {
    static const char* const SCREEN[] = {"WINDOWED", "BORDERLESS", "FULLSCREEN"};
    static const char* const COLOUR[] = {"RAW", "CRT", "COMPOSITE", "TRINITRON"};
    int v = ROW[r].id ? psx_mod_host_get(ROW[r].id) : 0;
    switch (r) {
    case O_TAB:       snprintf(out, n, "< %s >", PAGES[s_page]); break;
    case O_SCREEN:    snprintf(out, n, "< %s >", SCREEN[v < 0 || v > 2 ? 0 : v]); break;
    case O_RES:       snprintf(out, n, "< %dX >", v); break;
    case O_COLOUR:    snprintf(out, n, "< %s >", COLOUR[v < 0 || v > 3 ? 0 : v]); break;
    case O_TEXFILTER: snprintf(out, n, "< %s >", v ? "SMOOTH" : "SHARP"); break;
    case O_SCANLINES:
        if (v) snprintf(out, n, "< %d%% >", v);
        else   snprintf(out, n, "< OFF >");
        break;
    case O_VOLUME: {
        char bar[21];
        for (int i = 0; i < 20; i++) bar[i] = i < v / 5 ? '#' : '-';
        bar[20] = 0;
        snprintf(out, n, "%s %d%%", bar, v);
        break;
    }
    case O_RESET:     out[0] = 0; break;
    default:          snprintf(out, n, "< %s >", v ? "ON" : "OFF"); break;
    }
}

static void draw_display_page(void) {
    char v[64];
    for (int r = 0; r < O_ROWS; r++) {
        draw_row_bg(r);
        menu_text(s_px, MENU_X0, row_y(r), LABELS[r], MENU_WHITE);
        value_text(r, v, sizeof v);
        menu_text(s_px, MENU_X0 + 15 * MENU_CH, row_y(r), v, MENU_WHITE);
    }
    menu_text(s_px, MENU_X0, MENU_H - 3 * MENU_LINE, HELP[s_row], MENU_GREY);
}

static void draw_controls_page(void) {
    char v[64], name[48];
    snprintf(v, sizeof v, "< %s >", PAGES[s_page]);
    draw_row_bg(C_TAB);
    menu_text(s_px, MENU_X0, row_y(C_TAB), "PAGE", MENU_WHITE);
    menu_text(s_px, MENU_X0 + 9 * MENU_CH, row_y(C_TAB), v, MENU_WHITE);
    for (int b = 0; b < N_BUTTONS; b++) {
        const int r = C_FIRST_BUTTON + b, y = row_y(r);
        draw_row_bg(r);
        menu_text(s_px, MENU_X0, y, BTN_LABEL[b], MENU_WHITE);
        key_label(b, v, 13);
        menu_text(s_px, MENU_X0 + 9 * MENU_CH, y, v, r == s_row && s_col == 0 ? MENU_YELLOW : MENU_WHITE);
        if (psx_mod_pad_get(BTN_INI[b], name, sizeof name)) pad_label(name, v, 15);
        else snprintf(v, sizeof v, "-");
        menu_text(s_px, MENU_X0 + 22 * MENU_CH, y, v, r == s_row && s_col == 1 ? MENU_YELLOW : MENU_WHITE);
    }
    draw_row_bg(C_DEADZONE);
    menu_text(s_px, MENU_X0, row_y(C_DEADZONE), "STICK DEADZONE", MENU_WHITE);
    snprintf(v, sizeof v, "< %d%% >", psx_mod_host_get(PSX_MOD_HOST_DEADZONE));
    menu_text(s_px, MENU_X0 + 22 * MENU_CH, row_y(C_DEADZONE), v, MENU_WHITE);
    draw_row_bg(C_RESET_KEYS);
    menu_text(s_px, MENU_X0, row_y(C_RESET_KEYS), "RESET KEYBOARD", MENU_WHITE);
    draw_row_bg(C_RESET_PAD);
    menu_text(s_px, MENU_X0, row_y(C_RESET_PAD), "RESET CONTROLLER", MENU_WHITE);

    const char* help;
    if (s_capturing >= 0)
        help = s_col == 0 ? "PRESS A KEY  (ESC: CANCEL)" : "PRESS A BUTTON  (ESC / 6 S: CANCEL)";
    else if (s_row >= C_FIRST_BUTTON && s_row < C_DEADZONE)
        help = "LEFT/RIGHT: COLUMN  ENTER: REBIND";
    else if (s_row == C_DEADZONE)
        help = "STICK MOVEMENT IGNORED NEAR THE CENTRE";
    else if (s_row == C_TAB)
        help = "LEFT/RIGHT: OTHER PAGE";
    else
        help = "ENTER: BACK TO THE DEFAULT BUTTONS";
    menu_text(s_px, MENU_X0, MENU_H - 3 * MENU_LINE, help, s_capturing >= 0 ? MENU_YELLOW : MENU_GREY);
}

static int image(const uint32_t** pixels, int* w, int* h) {
    char pad[40], v[64];
    menu_fill(s_px, 0, 0, MENU_W, MENU_H, MENU_BG);
    menu_text(s_px, MENU_X0, MENU_Y0, "OPTIONS", MENU_YELLOW);
    if (s_page == PAGE_CONTROLS) {
        menu_text(s_px, MENU_X0 + 9 * MENU_CH, MENU_Y0, "KEYBOARD", MENU_GREY);
        if (psx_mod_pad_connected(pad, sizeof pad)) snprintf(v, sizeof v, "%.15s", pad);
        else snprintf(v, sizeof v, "NO CONTROLLER");
        menu_text(s_px, MENU_X0 + 22 * MENU_CH, MENU_Y0, v, MENU_GREY);
        draw_controls_page();
    } else {
        draw_display_page();
    }
    if (s_msg[0]) menu_text(s_px, MENU_X0, MENU_H - 2 * MENU_LINE, s_msg, MENU_YELLOW);
    menu_text(s_px, MENU_X0, MENU_H - MENU_LINE,
              s_page == PAGE_CONTROLS ? "ENTER/A REBIND  ESC/F10/B CLOSE" : "SAVED AT ONCE. * = NEXT START", MENU_GREY);
    *pixels = s_px;
    *w = MENU_W;
    *h = MENU_H;
    return 1;
}

/* ---- actions ---- */
static void on_open(void) {
    s_msg[0] = 0;
    s_capturing = -1;
}

static void change(int r, int dir) {
    int v = psx_mod_host_get(ROW[r].id) + dir * ROW[r].step;
    if (v > ROW[r].max) v = r == O_VOLUME || r == O_SCANLINES ? ROW[r].max : ROW[r].min;    /* sliders stop, */
    if (v < ROW[r].min) v = r == O_VOLUME || r == O_SCANLINES ? ROW[r].min : ROW[r].max;    /* choices wrap */
    if (!psx_mod_host_set(ROW[r].id, v)) {
        snprintf(s_msg, sizeof s_msg, "NOT AVAILABLE");
        return;
    }
    save_all();
}

/* tell the player when the new key / button already drives another PlayStation button */
static void note_duplicate(int b) {
    char a[48], o[48];
    for (int i = 0; i < N_BUTTONS; i++) {
        if (i == b) continue;
        if (s_col == 0 ? psx_mod_key_get(i) == psx_mod_key_get(b)
                       : psx_mod_pad_get(BTN_INI[i], o, sizeof o) && psx_mod_pad_get(BTN_INI[b], a, sizeof a) &&
                             strcmp(a, o) == 0) {
            snprintf(s_msg, sizeof s_msg, "NOTE: %s HAS IT TOO", BTN_LABEL[i]);
            return;
        }
    }
}

static void captured(void) {
    int sc = 0;
    char src[32];
    const int kind = psx_mod_capture_result(&sc, src, sizeof src);
    const int b = s_capturing;
    s_capturing = -1;
    if (b < 0) return;
    if (kind == 1) {
        psx_mod_key_set(b, sc);
        psx_mod_keys_save();
    } else if (kind == 2) {
        if (!psx_mod_pad_set(BTN_INI[b], src)) {
            snprintf(s_msg, sizeof s_msg, "COULD NOT USE THAT BUTTON");
            return;
        }
        if (!psx_mod_pad_save()) snprintf(s_msg, sizeof s_msg, "COULD NOT SAVE INPUT.INI");
    } else {
        snprintf(s_msg, sizeof s_msg, "CANCELLED");
        return;
    }
    note_duplicate(b);
}

static int controls_key(int key) {
    switch (key) {
    case PSX_MOD_KEY_LEFT:
    case PSX_MOD_KEY_RIGHT:
        if (s_row >= C_FIRST_BUTTON && s_row < C_DEADZONE) {
            s_col ^= 1;
        } else if (s_row == C_DEADZONE) {
            int v = psx_mod_host_get(PSX_MOD_HOST_DEADZONE) + (key == PSX_MOD_KEY_LEFT ? -5 : 5);
            v = v < 5 ? 5 : v > 50 ? 50 : v;
            psx_mod_host_set(PSX_MOD_HOST_DEADZONE, v);
            save_all();                                 /* settings.toml */
            if (!psx_mod_pad_save()) snprintf(s_msg, sizeof s_msg, "COULD NOT SAVE INPUT.INI");
        }
        return 1;
    case PSX_MOD_KEY_ENTER:
        if (s_row >= C_FIRST_BUTTON && s_row < C_DEADZONE) {
            if (!psx_mod_capture_begin(s_col == 0 ? 1 : 2)) {
                snprintf(s_msg, sizeof s_msg, "NO CONTROLLER CONNECTED");
                return 1;
            }
            s_capturing = s_row - C_FIRST_BUTTON;
        } else if (s_row == C_RESET_KEYS) {
            psx_mod_keys_reset();
            psx_mod_keys_save();
            snprintf(s_msg, sizeof s_msg, "KEYBOARD RESET");
        } else if (s_row == C_RESET_PAD) {
            psx_mod_pad_reset();
            snprintf(s_msg, sizeof s_msg, psx_mod_pad_save() ? "CONTROLLER RESET" : "COULD NOT SAVE INPUT.INI");
        }
        return 1;
    default:
        return 1;
    }
}

static int display_key(int key) {
    if (key != PSX_MOD_KEY_LEFT && key != PSX_MOD_KEY_RIGHT && key != PSX_MOD_KEY_ENTER) return 1;
    if (s_row == O_RESET) {
        if (key != PSX_MOD_KEY_ENTER) return 1;
        for (int r = O_SCREEN; r < O_RESET; r++) psx_mod_host_set(ROW[r].id, DEFAULTS[r]);
        save_all();
        if (!s_msg[0]) snprintf(s_msg, sizeof s_msg, "DEFAULTS RESTORED");
        return 1;
    }
    change(s_row, key == PSX_MOD_KEY_LEFT ? -1 : 1);
    return 1;
}

static int on_key(int key) {
    const int rows = s_page == PAGE_CONTROLS ? C_ROWS : O_ROWS;
    if (key == PSX_MOD_KEY_CAPTURED) {
        captured();
        return 1;
    }
    s_msg[0] = 0;
    switch (key) {
    case PSX_MOD_KEY_BACK:
    case PSX_MOD_KEY_MENU:
        return 0;
    case PSX_MOD_KEY_UP:   s_row = (s_row + rows - 1) % rows; return 1;
    case PSX_MOD_KEY_DOWN: s_row = (s_row + 1) % rows; return 1;
    default: break;
    }
    if (s_row == 0) {                                   /* page tab */
        if (key == PSX_MOD_KEY_LEFT || key == PSX_MOD_KEY_RIGHT || key == PSX_MOD_KEY_ENTER)
            s_page = (s_page + 1) % PAGE_COUNT;
        return 1;
    }
    return s_page == PAGE_CONTROLS ? controls_key(key) : display_key(key);
}

static const PSXModMenu s_menu = {on_open, on_key, image};

PSX_MOD_CONSTRUCTOR(register_persona_options_menu) {
    (void)psx_mod_register_menu_hotkey(&s_menu, 10);
    load_volume();
}
