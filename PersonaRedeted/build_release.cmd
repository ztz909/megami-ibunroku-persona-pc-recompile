@echo off
rem Build the release exe (bundled OpenBIOS only, static C runtime) into build_release\. See tools\make_release.py.
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
set "ROOT=%~dp0."
cmake -S "%ROOT%" -B "%ROOT%\build_release" -G Ninja -DCMAKE_BUILD_TYPE=Release -DPERSONA_RELEASE=ON -DPSX_RECOMP_UI=OFF -DPSX_REWIND=OFF -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl || exit /b 1
cmake --build "%ROOT%\build_release" --config Release --parallel
