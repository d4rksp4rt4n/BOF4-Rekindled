@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64_x86 >nul
cd /d "%~dp0"
cl /nologo /O2 /MT /LD /W3 /D_CRT_SECURE_NO_WARNINGS bof4_reverb.c loops.c fps60.c sprites.c widescreen.c /Fe:bof4_reverb.dll /link /NOLOGO kernel32.lib user32.lib || exit /b 1
cl /nologo /O2 /MT /W3 /DREVERB_TEST bof4_reverb.c /Fe:reverb_test.exe /link user32.lib || exit /b 1
del *.obj *.exp *.lib 2>nul
