@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64_x86 >nul
cd /d "%~dp0"
rc /nologo /fo dsound.res dsound.rc || exit /b 1
cl /nologo /O1 /GS- /LD /W3 bof4_loader.c dsound.res /Fe:dsound.dll /link /NOLOGO /DEF:dsound.def /NODEFAULTLIB /ENTRY:DllMain kernel32.lib user32.lib || exit /b 1
del *.obj *.exp *.lib *.res 2>nul
