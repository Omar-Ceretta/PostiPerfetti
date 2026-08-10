@echo off
setlocal
title PostiPerfetti - Build installer Windows

echo.
echo ============================================================
echo  PostiPerfetti - creazione installer Windows
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0crea_installer_windows.ps1" -MantieniAmbienteBuild
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo Operazione conclusa con successo.
) else (
    echo ERRORE: la build si e' interrotta. Codice: %EXITCODE%
)

echo.
pause
exit /b %EXITCODE%
