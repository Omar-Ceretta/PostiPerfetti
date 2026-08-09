param(
    [switch]$SoloExe,
    [switch]$SaltaTest
)

$ErrorActionPreference = "Stop"

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $PackagingDir "..\..")).Path
$BuildVenv = Join-Path $Root ".venv-build-windows"
$PythonVenv = Join-Path $BuildVenv "Scripts\python.exe"

Write-Host ""
Write-Host "=== PostiPerfetti - build Windows ===" -ForegroundColor Cyan
Write-Host "Root: $Root"

Set-Location $Root

function Get-SystemPython {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @("py", "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @("python")
    }

    throw "Python 3 non trovato. Installalo da python.org e riapri PowerShell."
}

if (-not (Test-Path $PythonVenv)) {
    Write-Host ""
    Write-Host "Creazione ambiente di build..." -ForegroundColor Cyan
    $cmd = Get-SystemPython
    if ($cmd.Count -eq 2) {
        & $cmd[0] $cmd[1] -m venv $BuildVenv
    } else {
        & $cmd[0] -m venv $BuildVenv
    }
}

Write-Host ""
Write-Host "Installazione/aggiornamento dipendenze di build..." -ForegroundColor Cyan
& $PythonVenv -m pip install --disable-pip-version-check --upgrade pip
& $PythonVenv -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements.txt")
& $PythonVenv -m pip install --disable-pip-version-check "pyinstaller>=6.21,<7"

if (-not $SaltaTest) {
    Write-Host ""
    Write-Host "Esecuzione test rapidi della root..." -ForegroundColor Cyan
    & $PythonVenv -m pip install --disable-pip-version-check pytest
    & $PythonVenv -m pytest -q
}

Write-Host ""
Write-Host "Creazione bundle PyInstaller onedir..." -ForegroundColor Cyan
& $PythonVenv -m PyInstaller `
    --clean `
    --noconfirm `
    --distpath (Join-Path $Root "dist") `
    --workpath (Join-Path $Root "build\pyinstaller") `
    (Join-Path $PackagingDir "PostiPerfetti.spec")

$Exe = Join-Path $Root "dist\PostiPerfetti\PostiPerfetti.exe"
if (-not (Test-Path $Exe)) {
    throw "Build PyInstaller terminata senza trovare $Exe"
}

$ClassiDist = Join-Path $Root "dist\PostiPerfetti\classi"
New-Item -ItemType Directory -Force -Path $ClassiDist | Out-Null

Copy-Item `
    (Join-Path $Root "classi\Classe-BASE_esempio.txt") `
    (Join-Path $ClassiDist "Classe-BASE_esempio.txt") `
    -Force

Copy-Item `
    (Join-Path $Root "classi\Classe-COMPLETO_esempio.txt") `
    (Join-Path $ClassiDist "Classe-COMPLETO_esempio.txt") `
    -Force

Write-Host ""
Write-Host "EXE creato: $Exe" -ForegroundColor Green

if ($SoloExe) {
    Write-Host "Opzione -SoloExe: compilazione Inno Setup saltata."
    exit 0
}

$CandidatiISCC = @(
    (Join-Path ${env:ProgramFiles} "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
)

$ISCC = $CandidatiISCC | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $ISCC) {
    Write-Host ""
    Write-Host "Inno Setup non trovato." -ForegroundColor Yellow
    Write-Host "L'EXE è pronto per il collaudo."
    Write-Host "Installa Inno Setup 7 e poi riesegui questo script per creare il Setup."
    exit 0
}

Write-Host ""
Write-Host "Compilazione installer con Inno Setup..." -ForegroundColor Cyan
& $ISCC (Join-Path $PackagingDir "postiperfetti_setup.iss")

$Setup = Join-Path $Root "dist-installer\PostiPerfetti_setup.exe"
if (Test-Path $Setup) {
    Write-Host ""
    Write-Host "Installer creato: $Setup" -ForegroundColor Green
} else {
    throw "Inno Setup è terminato ma l'installer atteso non è stato trovato."
}
