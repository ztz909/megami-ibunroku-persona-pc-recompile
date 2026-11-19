/* persona_mod.h - helpers for hand-written replacements of game functions.
 *
 * A replacement takes the place of one recompiled function (func_XXXXXXXX in
 * generated/). It gets the same CPUState the game uses: arguments in the MIPS
 * registers, game memory through cpu->read_* / cpu->write_*. When done it sets
 * cpu->pc to the return address, exactly like the original "jr ra".
 *
 * Which function replaces which: mods/overrides.txt, applied to the generated
 * dispatch table by tools/apply_overrides.py (also run by tools/regen_recomp.py).
 */
#pragma once
#include "psx_runtime.h"

/* MIPS register numbers (cpu->gpr[...]) */
enum {
    R_ZERO = 0, R_AT = 1, R_V0 = 2, R_V1 = 3,
    R_A0 = 4, R_A1 = 5, R_A2 = 6, R_A3 = 7,
    R_T0 = 8, R_T1 = 9, R_T2 = 10, R_T3 = 11, R_T4 = 12, R_T5 = 13, R_T6 = 14, R_T7 = 15,
    R_S0 = 16, R_S1 = 17, R_S2 = 18, R_S3 = 19, R_S4 = 20, R_S5 = 21, R_S6 = 22, R_S7 = 23,
    R_T8 = 24, R_T9 = 25, R_K0 = 26, R_K1 = 27, R_GP = 28, R_SP = 29, R_FP = 30, R_RA = 31
};

static inline uint8_t  mem_u8(CPUState* cpu, uint32_t addr)  { return cpu->read_byte(addr); }
static inline uint16_t mem_u16(CPUState* cpu, uint32_t addr) { return cpu->read_half(addr); }
static inline uint32_t mem_u32(CPUState* cpu, uint32_t addr) { return cpu->read_word(addr); }
static inline void mem_set_u8(CPUState* cpu, uint32_t addr, uint8_t v)   { cpu->write_byte(addr, v); }
static inline void mem_set_u16(CPUState* cpu, uint32_t addr, uint16_t v) { cpu->write_half(addr, v); }
static inline void mem_set_u32(CPUState* cpu, uint32_t addr, uint32_t v) { cpu->write_word(addr, v); }

/* "jr ra": continue in the caller */
static inline void return_to_caller(CPUState* cpu) { cpu->pc = cpu->gpr[R_RA]; }

/* Debug switches read once from the environment (set NAME=1 before starting the exe). */
int persona_mod_flag(const char* name);
