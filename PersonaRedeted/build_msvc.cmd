@echo off
rem Build the native exe with MSVC + Ninja (the MinGW gcc on PATH is 32-bit and unusable).
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
set "ROOT=%~dp0."
cmake -S "%ROOT%" -B "%ROOT%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DPSX_RECOMP_UI=OFF -DPSX_REWIND=OFF -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl || exit /b 1
cmake --build "%ROOT%\build" --config Release --parallel
