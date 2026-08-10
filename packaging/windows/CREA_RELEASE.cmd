@echo off
setlocal
title PostiPerfetti - Release ufficiale

set "ARGOMENTO="

if /I "%~1"=="COLLAUDO" (
    set "ARGOMENTO=-Collaudo"
) else if not "%~1"=="" (
    echo.
    echo Uso:
    echo   CREA_RELEASE.cmd
    echo   CREA_RELEASE.cmd COLLAUDO
    echo.
    pause
    exit /b 2
)

echo.
echo ============================================================
echo  PostiPerfetti - preparazione Release
echo ============================================================
echo.

if /I "%~1"=="COLLAUDO" (
    echo MODALITA': COLLAUDO COMPLETO DELLA PIPELINE
    echo Gli artefatti prodotti NON sono destinati alla pubblicazione.
) else (
    echo MODALITA': RELEASE FINALE
    echo Verranno applicati tutti i controlli di pubblicazione.
)

echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0crea_release_windows.ps1" %ARGOMENTO%

set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo ============================================================
    echo  PROCEDURA CONCLUSA CON SUCCESSO
    echo ============================================================
) else (
    echo ============================================================
    echo  RELEASE NON PRODOTTA
    echo ============================================================
    echo.
    echo Uno o piu' controlli non sono stati superati.
    echo Codice: %EXITCODE%
)

echo.
pause
exit /b %EXITCODE%
