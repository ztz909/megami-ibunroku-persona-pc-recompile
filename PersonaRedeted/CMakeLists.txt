cmake_minimum_required(VERSION 3.20)
set(PSXRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/psxrecomp")
if(NOT EXISTS "${PSXRECOMP_ROOT}/runtime/runtime.cmake")
  message(FATAL_ERROR
    "PSXRecomp runtime is missing: ${PSXRECOMP_ROOT}/runtime/runtime.cmake\n"
    "This generated project needs the psxrecomp framework tree at ${PSXRECOMP_ROOT}.\n"
    "If this project came from git, run: git submodule update --init --recursive\n"
    "If this project came from psxrecomp.exe, regenerate it from the full CLI zip and keep the generated psxrecomp/ folder.")
endif()
project(Megami_Ibunroku_PersonaRecomp C CXX)
set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)
set(PSX_RECOMP_UI OFF CACHE BOOL "" FORCE)
# PERSONA_RELEASE (build_release.cmd): the build players get. Only the bundled, MIT-licensed OpenBIOS (the
# retail Sony BIOS may not be distributed) and the C runtime linked in (no Visual C++ redistributable needed).
option(PERSONA_RELEASE "Release build: bundled OpenBIOS only, static C runtime" OFF)
if(PERSONA_RELEASE)
  set(PSXRECOMP_BIOS_STEMS "OpenBIOS" CACHE STRING "" FORCE)
  set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded" CACHE STRING "" FORCE)
else()
  set(PSXRECOMP_BIOS_STEMS "SCPH1001" CACHE STRING "" FORCE)
endif()
include("${PSXRECOMP_ROOT}/runtime/runtime.cmake")
file(GLOB GAME_FULL CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/generated/*_full.c"
  "${CMAKE_CURRENT_SOURCE_DIR}/generated/*_full_*.c")
file(GLOB GAME_DISPATCH "${CMAKE_CURRENT_SOURCE_DIR}/generated/*_dispatch.c")
psxrecomp_add_runtime_target(psx-runtime
  GAME_GENERATED_FULL_C "${GAME_FULL}"
  GAME_GENERATED_DISPATCH_C "${GAME_DISPATCH}"
  WINDOW_TITLE "Megami Ibunroku Persona Recompiled"
  DEFAULT_GAME_CONFIG_PATH "game.toml"
)
# Hand-written replacements of game functions (mods/overrides.txt, tools/apply_overrides.py)
file(GLOB PERSONA_MODS CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/mods/*.c")
target_sources(psx-runtime PRIVATE ${PERSONA_MODS})
target_include_directories(psx-runtime PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/mods")
# The xdelta patcher (mods/xdelta_decode.c) uses libchdr's LZMA decoder.
if(NOT TARGET chdr-lzma)
  message(FATAL_ERROR "chdr-lzma (libchdr's LZMA decoder) not found; mods/xdelta_decode.c needs it")
endif()
get_target_property(PERSONA_LZMA_DIR chdr-lzma SOURCE_DIR)
target_link_libraries(psx-runtime PRIVATE chdr-lzma)
target_include_directories(psx-runtime PRIVATE "${PERSONA_LZMA_DIR}/include")
