/* debug_menu.c - Persona debug menu for the native exe (F9).
 *
 * Opens over the game with F9 (hook added to psxrecomp by tools/patch_framework.py); the game is paused
 * while it is open. Keys: Up/Down select, Left/Right change (PageUp/PageDown by 10), Enter run,
 * Esc or F9 close. The first row is the page tab: Left/Right there switches page.
 *
 * Pages: WARP LIST (named arrival points from tools/warp_points.py, back to title, go to 2D map),
 * WARP (numbers by hand), BATTLE CHEATS.
 *
 * On the 2D map a warp writes the same game variables the developers' own debug menu uses (it is still in
 * S2D.BIN, switched off). In a 3D area it sends the dungeon code down its own door-exit path (see
 * dungeon_exit). Details and addresses: research/DEBUG_MENU.md. Checked against the Redeted-patched disc.
 *
 *   0x801F5350 u16  target map number (also the event number for "go to event")
 *   0x801F5352 u8   target X (0-199)          0x801F5353 u8  target Y (0-199)
 *   0x801F5354 u8   target floor              0x801F5355 u8  target direction
 *   0x801F15A0..    position in a 3D area: u16 map, u16 floor, u8 X @15A4, u8 Y @15A6, u8 direction @15A7
 *   0x80055C5C s32  next state of the SLPS main loop (-1 title, 0 dungeon, 1 battle, 2 2D map, 3 story ...)
 *   0x800643C4 u32  id of the loaded module (4 dungeon, 5 battle, 6 2D map, 7 story, 8 casino, 9 name entry)
 *   S2D only: 0x800A540C s16 next mode (-1 stay, 0 2D map, 1 3D dungeon, 2 battle, 3 story event),
 *             0x800B6660 u32 cleared together with it, 0x800B1620 u32 the "ENC" toggle
 *   0x8004E284 u8[32] battle debug flags (resident; BTLP reads 0-14)
 */
#include <stdio.h>
#include <string.h>
#include "persona_mod.h"
#include "mod_plugins.h"
#include "warp_points.h"
#include "menu_draw.h"

#define W MENU_W
#define H MENU_H
#define CH MENU_CH
#define LINE MENU_LINE
#define X0 MENU_X0
#define Y0 MENU_Y0

#define MODULE_ID       0x800643C4u
#define MAP_NUM         0x801F5350u
#define POS_X           0x801F5352u
#define POS_Y           0x801F5353u
#define FLOOR_NUM       0x801F5354u
#define DIRECTION       0x801F5355u
#define S2D_NEXT_MODE   0x800A540Cu
#define S2D_RUN         0x800B6660u
#define S2D_ENC         0x800B1620u
#define S2D_SIGNATURE   0x8008C288u     /* scene-change input function: addiu sp, sp, -0x18 */
#define BATTLE_FLAGS    0x8004E284u
#define NEXT_STATE      0x80055C5Cu     /* gp + 0x68 of the SLPS main loop */
#define DNG_MAP         0x801F15A0u
#define DNG_FLOOR       0x801F15A2u
#define DNG_X           0x801F15A4u
#define DNG_Y           0x801F15A6u
#define DNG_DIR         0x801F15A7u
/* DNG.BIN code */
#define DNG_LOOP          0x80065240u   /* jal 0x80067D40 (per-step function), top of the main loop */
#define DNG_STEP_PATCH    0x80067D64u   /* in the per-step function, after its prologue: lw v0, 0x1580(a1); nop */
#define DNG_EXIT_TO_2D    0x80068204u   /* door exit paths inside 0x80067D40: to the 2D map, */
#define DNG_EXIT_RELOAD   0x8006833Cu   /*   to another dungeon (load it), */
#define DNG_EXIT_TO_EVENT 0x800680F4u   /*   to a story event; all end with return -1 */
#define DNG_STEP_EPILOGUE 0x80068730u
#define J(t)   (0x08000000u | (((t) >> 2) & 0x03FFFFFFu))
#define JAL(t) (0x0C000000u | (((t) >> 2) & 0x03FFFFFFu))



static const char* const CHEATS[] = {   /* the battle debug menu's own names (BTLP.BIN), in English */
    "ALWAYS ESCAPE", "NEVER DIE", "ALWAYS KILL", "ENEMIES DON'T MOVE", "SP DOESN'T DROP",
    "NO PERSONA M.ATK/M.DEF", "NO BAD STATUS", "FIX THE GROUP", "NO GAME OVER", "FLAG 9 (?)",
    "DEMONS ONLY DEFEND", "FLAG 11 (?)", "FLAG 12 (?)", "NO EVENT BATTLES", "FLAG 14 (?)"};
#define N_CHEATS 15

enum { PAGE_LIST, PAGE_WARP, PAGE_CHEATS, PAGE_COUNT };
static const char* const PAGES[PAGE_COUNT] = {"WARP LIST", "WARP", "BATTLE CHEATS"};

/* rows (row 0 is the page tab on every page) */
enum { L_TAB, L_TITLE, L_TO_2D, L_FIRST, L_VISIBLE = 12, L_ROWS = L_FIRST + L_VISIBLE };
enum { W_TAB, W_MAP, W_FLOOR, W_X, W_Y, W_DIR, W_GO_2D, W_GO_3D, W_GO_EVENT, W_GO_BATTLE, W_ENC, W_ROWS };

/* where the game goes next (the SLPS main loop reads it when the loaded module returns) */
enum { NEXT_DUNGEON = 0, NEXT_2D = 2, NEXT_EVENT = 3, NEXT_TITLE = -1 };

static uint32_t s_px[W * H];
static int s_page, s_row;
static int s_map, s_floor, s_x, s_y, s_dir;     /* warp target, taken from the game when the menu opens */
static int s_pick, s_top;                       /* WARP LIST: selected entry, first entry shown */
static char s_msg[64];

static uint32_t module_id(void) { return psx_mod_read_word(MODULE_ID); }

static int on_2d_map(void) {
    return module_id() == 6 && psx_mod_read_word(S2D_SIGNATURE) == 0x27BDFFE8u;
}

static int in_dungeon(void) {
    uint32_t step = psx_mod_read_word(DNG_STEP_PATCH);
    return module_id() == 4 && psx_mod_read_word(DNG_LOOP) == JAL(0x80067D40u) &&
           (step == 0x8CA21580u || (step & 0xFC000000u) == 0x08000000u) &&   /* original, or a warp pending */
           psx_mod_read_word(DNG_EXIT_TO_2D) == JAL(0x8006F3DCu) &&
           psx_mod_read_word(DNG_STEP_EPILOGUE) == 0x8FBF0064u;      /* lw ra, 0x64(sp) */
}

static const char* module_name(void) {
    switch (module_id()) {
    case 4: return "3D DUNGEON";
    case 5: return "BATTLE";
    case 6: return "2D MAP";
    case 7: return "STORY (ADV)";
    case 8: return "CASINO";
    case 9: return "NAME ENTRY";
    default: return "?";
    }
}

/* ---- drawing ---- */
static void fill(int x0, int y0, int w, int h, uint32_t c) { menu_fill(s_px, x0, y0, w, h, c); }
static void text(int x, int y, const char* s, uint32_t col) { menu_text(s_px, x, y, s, col); }

#define WHITE  MENU_WHITE
#define GREY   MENU_GREY
#define YELLOW MENU_YELLOW
#define GREEN  MENU_GREEN
#define RED    MENU_RED

static int rows(void) {
    return s_page == PAGE_LIST ? L_ROWS : s_page == PAGE_WARP ? W_ROWS : 1 + N_CHEATS;
}

static void row_at(int r, int col, const char* label, const char* value, uint32_t c) {
    int y = Y0 + 2 * LINE + r * LINE;
    if (r == s_row) fill(X0 - 8, y - 3, W - 2 * X0 + 16, LINE, 0xFF2C3E5Cu);
    text(X0, y, label, c);
    if (value) text(X0 + col * CH, y, value, c);
}

static void row(int r, const char* label, const char* value, uint32_t col) { row_at(r, 17, label, value, col); }

static void warp_point_text(const WarpPoint* p, char* out, size_t n) {
    if (p->is_3d) snprintf(out, n, "3D %X F%u %u,%u", p->map, p->floor, p->x, p->y);
    else          snprintf(out, n, "2D %u %u,%u", p->map, p->x, p->y);
}

static int image(const uint32_t** pixels, int* w, int* h) {
    char v[64];
    int dng = module_id() == 4;
    fill(0, 0, W, H, 0xE00C1018u);
    snprintf(v, sizeof v, "DEBUG MENU  [%s]", module_name());
    text(X0, Y0, v, YELLOW);
    if (dng)        /* in a dungeon the current position is the saved one (0x801F15A0..) */
        snprintf(v, sizeof v, "MAP %X FLOOR %u X %u Y %u", (unsigned)psx_mod_read_half(DNG_MAP),
                 (unsigned)psx_mod_read_half(DNG_FLOOR), (unsigned)psx_mod_read_byte(DNG_X),
                 (unsigned)psx_mod_read_byte(DNG_Y));
    else
        snprintf(v, sizeof v, "MAP %u FLOOR %u X %u Y %u DIR %u", (unsigned)psx_mod_read_half(MAP_NUM),
                 (unsigned)psx_mod_read_byte(FLOOR_NUM), (unsigned)psx_mod_read_byte(POS_X),
                 (unsigned)psx_mod_read_byte(POS_Y), (unsigned)psx_mod_read_byte(DIRECTION));
    text(X0, Y0 + LINE, v, GREY);

    snprintf(v, sizeof v, "< %s >", PAGES[s_page]);
    row(0, "PAGE", v, WHITE);
    int can_go = on_2d_map() || in_dungeon();
    uint32_t go = can_go ? WHITE : GREY;
    if (s_page == PAGE_LIST) {
        row(L_TITLE, "BACK TO TITLE (LOAD GAME)", NULL, go);
        row(L_TO_2D, "GO TO 2D MAP", NULL, go);
        for (int i = 0; i < L_VISIBLE && s_top + i < WARP_POINT_COUNT; i++) {
            const WarpPoint* p = &k_warp_points[s_top + i];
            char name[24];
            snprintf(name, sizeof name, "%.21s", p->name);
            warp_point_text(p, v, sizeof v);
            row_at(L_FIRST + i, 22, name, v, s_top + i == s_pick && s_row >= L_FIRST ? YELLOW : go);
        }
        snprintf(v, sizeof v, "%d/%d", s_pick + 1, WARP_POINT_COUNT);
        text(W - X0 - 9 * CH, Y0 + LINE, v, GREY);
    } else if (s_page == PAGE_WARP) {
        int s2d = on_2d_map();
        snprintf(v, sizeof v, "%d", s_map);   row(W_MAP, "MAP NUMBER", v, WHITE);
        snprintf(v, sizeof v, "%d", s_floor); row(W_FLOOR, "FLOOR", v, WHITE);
        snprintf(v, sizeof v, "%d", s_x);     row(W_X, "X POSITION", v, WHITE);
        snprintf(v, sizeof v, "%d", s_y);     row(W_Y, "Y POSITION", v, WHITE);
        snprintf(v, sizeof v, "%d", s_dir);   row(W_DIR, "DIRECTION", v, WHITE);
        row(W_GO_2D, "GO: 2D MAP", NULL, go);
        row(W_GO_3D, "GO: 3D DUNGEON", NULL, go);
        row(W_GO_EVENT, "GO: STORY EVENT", "EVENT = MAP NO.", go);
        row(W_GO_BATTLE, "GO: BATTLE", "2D MAP ONLY", s2d ? WHITE : GREY);
        row(W_ENC, "ENC FLAG", s2d ? (psx_mod_read_word(S2D_ENC) ? "ON" : "OFF") : "-", s2d ? WHITE : GREY);
    } else {
        for (int i = 0; i < N_CHEATS; i++) {
            int on = psx_mod_read_byte(BATTLE_FLAGS + (uint32_t)i) != 0;
            row(1 + i, CHEATS[i], on ? "ON" : "OFF", on ? GREEN : WHITE);
        }
    }
    if (s_page != PAGE_CHEATS && !can_go)
        text(X0, H - 3 * LINE, "WARPS WORK ON THE 2D MAP OR IN 3D AREAS", RED);
    if (s_msg[0]) text(X0, H - 2 * LINE, s_msg, YELLOW);
    text(X0, H - LINE, "ARROWS PGUP/PGDN ENTER  ESC/F9 CLOSE", GREY);
    *pixels = s_px;
    *w = W;
    *h = H;
    return 1;
}

/* ---- actions ---- */
static const uint8_t DNG_DIR_TO_TARGET[4] = {3, 0, 2, 1};   /* inverse of SLPS table 0x8004DA38 */

static void on_open(void) {
    if (module_id() == 4) {
        s_map = psx_mod_read_half(DNG_MAP);
        s_floor = psx_mod_read_half(DNG_FLOOR);
        s_x = psx_mod_read_byte(DNG_X);
        s_y = psx_mod_read_byte(DNG_Y);
        s_dir = DNG_DIR_TO_TARGET[psx_mod_read_byte(DNG_DIR) & 3];
    } else {
        s_map = psx_mod_read_half(MAP_NUM);
        s_floor = psx_mod_read_byte(FLOOR_NUM);
        s_x = psx_mod_read_byte(POS_X);
        s_y = psx_mod_read_byte(POS_Y);
        s_dir = psx_mod_read_byte(DIRECTION);
    }
    s_msg[0] = 0;
}

static void adjust(int* value, int delta, int max) {
    *value += delta;
    if (*value < 0) *value = max;
    if (*value > max) *value = 0;
}

/* Dungeon: the per-step function 0x80067D40 runs once per iteration of the DNG main loop. Overwrite the
 * instruction right after its prologue with a jump into one of its own exit paths (the code that runs when
 * you walk through a door: fade out, call the next module's loader, return -1). The main loop then leaves
 * (0x80065248 bnez v0 -> 0x80065938) and the SLPS main loop loads what NEXT_STATE says. The patched words
 * are gone as soon as the next module is loaded over the dungeon code.
 * (Not in the main loop itself: the game is paused inside a call from that loop, and its return address
 * points into the loop, so code written there runs half-way through. Nothing returns into 0x80067D64.) */
static void dungeon_exit(uint32_t exit_path) {
    psx_mod_write_code_word(DNG_STEP_PATCH, J(exit_path));
    psx_mod_write_code_word(DNG_STEP_PATCH + 4, 0x00000000u);     /* delay slot: nop (it is already) */
}

/* Go somewhere. next = NEXT_2D / NEXT_DUNGEON / NEXT_EVENT / NEXT_TITLE, or 'B' for a battle (2D map only).
 * Returns 0 (close the menu) when the game will leave on its next frame. */
static int warp(int next, int map, int floor, int x, int y, int dir) {
    int s2d = on_2d_map(), dng = in_dungeon();
    if (!s2d && !dng) {
        snprintf(s_msg, sizeof s_msg, "NOT HERE: ONLY ON THE 2D MAP OR IN 3D");
        return 1;
    }
    if (next == 'B' && !s2d) {
        snprintf(s_msg, sizeof s_msg, "BATTLE: ONLY FROM THE 2D MAP");
        return 1;
    }
    /* the 2D map loader (SLPS 0x80015784) builds the file name 2D/2DLTS0<map>.BIN: anything above 6 has no file.
     * It also runs on the way to the title screen, so that warp passes map 0 as well. */
    if ((next == NEXT_2D || next == NEXT_TITLE) && map > 6) {
        snprintf(s_msg, sizeof s_msg, "2D MAP NUMBER MUST BE 0-6");
        return 1;
    }
    psx_mod_write_half(MAP_NUM, (uint16_t)map);
    psx_mod_write_byte(FLOOR_NUM, (uint8_t)floor);
    psx_mod_write_byte(POS_X, (uint8_t)x);
    psx_mod_write_byte(POS_Y, (uint8_t)y);
    psx_mod_write_byte(DIRECTION, (uint8_t)dir);
    if (s2d) {
        /* the developers' scene-change page (S2D 0x8008C288): next mode 0 2D / 1 3D / 2 battle / 3 event.
         * Back to title: the 2D->2D change, with the main loop's next state set to -1 (title screen). */
        int mode = next == NEXT_2D || next == NEXT_TITLE ? 0 : next == NEXT_DUNGEON ? 1 : next == 'B' ? 2 : 3;
        if (next == NEXT_TITLE)
            psx_mod_write_word(NEXT_STATE, (uint32_t)NEXT_TITLE);
        psx_mod_write_half(S2D_NEXT_MODE, (uint16_t)mode);
        psx_mod_write_word(S2D_RUN, 0);
        return 0;
    }
    psx_mod_write_word(NEXT_STATE, (uint32_t)next);
    dungeon_exit(next == NEXT_DUNGEON ? DNG_EXIT_RELOAD : next == NEXT_EVENT ? DNG_EXIT_TO_EVENT : DNG_EXIT_TO_2D);
    return 0;
}

/* "Go to 2D map": outside the current dungeon if one of its doors leads out, else the new-game start */
static int go_to_2d(void) {
    int from = in_dungeon() ? psx_mod_read_half(DNG_MAP) : -1;
    const WarpPoint* home = NULL;
    for (int i = 0; i < WARP_POINT_COUNT; i++) {
        const WarpPoint* p = &k_warp_points[i];
        if (p->is_3d) continue;
        if (p->from_dungeon == from) return warp(NEXT_2D, p->map, 0, p->x, p->y, p->dir);
        if (p->map == 0 && p->x == 0x68 && p->y == 0x69) home = p;
    }
    return warp(NEXT_2D, 0, 0, home ? home->x : 0x68, home ? home->y : 0x69, 0);
}

static void list_move(int delta) {
    s_pick += delta;
    if (s_pick < 0) s_pick = delta == -1 ? WARP_POINT_COUNT - 1 : 0;
    if (s_pick >= WARP_POINT_COUNT) s_pick = delta == 1 ? 0 : WARP_POINT_COUNT - 1;
    if (s_pick < s_top) s_top = s_pick;
    if (s_pick >= s_top + L_VISIBLE) s_top = s_pick - L_VISIBLE + 1;
    s_row = L_FIRST + (s_pick - s_top);
}

static int on_key(int key) {
    int n = rows();
    s_msg[0] = 0;
    if (key == PSX_MOD_KEY_BACK || key == PSX_MOD_KEY_MENU)
        return 0;
    if (s_page == PAGE_LIST && s_row >= L_FIRST) {      /* moving inside the list scrolls it */
        if (key == PSX_MOD_KEY_UP && s_pick == s_top && s_pick > 0) { list_move(-1); return 1; }
        if (key == PSX_MOD_KEY_DOWN && s_row == L_ROWS - 1 && s_pick < WARP_POINT_COUNT - 1) { list_move(1); return 1; }
        if (key == PSX_MOD_KEY_PAGE_DOWN || key == PSX_MOD_KEY_LEFT) { list_move(key == PSX_MOD_KEY_LEFT ? -1 : 10); return 1; }
        if (key == PSX_MOD_KEY_PAGE_UP || key == PSX_MOD_KEY_RIGHT) { list_move(key == PSX_MOD_KEY_RIGHT ? 1 : -10); return 1; }
    }
    if (key == PSX_MOD_KEY_UP || key == PSX_MOD_KEY_DOWN) {
        s_row = (s_row + (key == PSX_MOD_KEY_UP ? n - 1 : 1)) % n;
        if (s_page == PAGE_LIST && s_row >= L_FIRST) {
            if (s_top + (s_row - L_FIRST) >= WARP_POINT_COUNT) s_row = L_FIRST + (WARP_POINT_COUNT - 1 - s_top);
            s_pick = s_top + (s_row - L_FIRST);
        }
        return 1;
    }
    int step = key == PSX_MOD_KEY_LEFT ? -1 : key == PSX_MOD_KEY_RIGHT ? 1
             : key == PSX_MOD_KEY_PAGE_DOWN ? -10 : key == PSX_MOD_KEY_PAGE_UP ? 10 : 0;
    if (s_row == 0) {
        if (step)
            s_page = (s_page + (step > 0 ? 1 : PAGE_COUNT - 1)) % PAGE_COUNT;
        return 1;
    }
    if (s_page == PAGE_CHEATS) {
        if (key == PSX_MOD_KEY_ENTER || step == 1 || step == -1) {
            uint32_t a = BATTLE_FLAGS + (uint32_t)(s_row - 1);
            psx_mod_write_byte(a, psx_mod_read_byte(a) ? 0 : 1);
        }
        return 1;
    }
    if (s_page == PAGE_LIST) {
        if (key != PSX_MOD_KEY_ENTER) return 1;
        if (s_row == L_TITLE) return warp(NEXT_TITLE, 0, 0, 0x68, 0x69, 0);   /* new-game start */
        if (s_row == L_TO_2D) return go_to_2d();
        const WarpPoint* p = &k_warp_points[s_pick];
        return warp(p->is_3d ? NEXT_DUNGEON : NEXT_2D, p->map, p->floor, p->x, p->y, p->dir);
    }
    switch (s_row) {
    case W_MAP:   adjust(&s_map, step, 0xFFFF); return 1;
    case W_FLOOR: adjust(&s_floor, step, 0xFF); return 1;
    case W_X:     adjust(&s_x, step, 199); return 1;
    case W_Y:     adjust(&s_y, step, 199); return 1;
    case W_DIR:   adjust(&s_dir, step, 0xFF); return 1;
    default:      break;
    }
    if (key != PSX_MOD_KEY_ENTER)
        return 1;
    switch (s_row) {
    case W_GO_2D:     return warp(NEXT_2D, s_map, s_floor, s_x, s_y, s_dir);
    case W_GO_3D:     return warp(NEXT_DUNGEON, s_map, s_floor, s_x, s_y, s_dir);
    case W_GO_BATTLE: return warp('B', s_map, s_floor, s_x, s_y, s_dir);
    case W_GO_EVENT:  return warp(NEXT_EVENT, s_map, s_floor, s_x, s_y, s_dir);
    case W_ENC:
        if (on_2d_map())
            psx_mod_write_word(S2D_ENC, psx_mod_read_word(S2D_ENC) ? 0 : 1);
        return 1;
    default:
        return 1;
    }
}

static const PSXModMenu s_menu = {on_open, on_key, image};

PSX_MOD_CONSTRUCTOR(register_persona_debug_menu) {
    (void)psx_mod_register_menu(&s_menu);
}
