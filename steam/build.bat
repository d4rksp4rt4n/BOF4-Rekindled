@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64_x86 >nul
cd /d "%~dp0"
cl /nologo /O2 /MT /LD /W3 bof4_loader.c /Fe:version.dll /link /NOLOGO /DEF:version.def kernel32.lib winmm.lib || exit /b 1
del *.obj *.exp *.lib 2>nul
