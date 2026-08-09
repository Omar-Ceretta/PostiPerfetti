[CmdletBinding()]
param(
    # Se specificato, riusa .venv-build-windows invece di ricrearlo da zero.
    [switch]$MantieniAmbienteBuild,

    # Se specificato, non apre dist-installer al termine.
    [switch]$NonAprireCartella
)

$ErrorActionPreference = "Stop"

function Scrivi-Passo {
    param([string]$Testo)
    Write-Host ""
    Write-Host "=== $Testo ===" -ForegroundColor Cyan
}

function Trova-Python {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return @{
            Exe  = $py.Source
            Args = @("-3")
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return @{
            Exe  = $python.Source
            Args = @()
        }
    }

    throw "Python 3 non trovato. Installa Python a 64 bit e riprova."
}

function Trova-InnoSetup {
    $candidati = @(
        (Join-Path ${env:ProgramFiles} "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    )

    return $candidati |
        Where-Object { $_ -and (Test-Path $_ -PathType Leaf) } |
        Select-Object -First 1
}

# ---------------------------------------------------------------------------
# 1. Individuazione root
# ---------------------------------------------------------------------------

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "Questo script va eseguito su Windows."
}

$PackagingDir = $PSScriptRoot
$Root = (Resolve-Path (Join-Path $PackagingDir "..\..")).Path

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " PostiPerfetti - creazione automatica installer Windows" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Root progetto: $Root"

Set-Location $Root

# ---------------------------------------------------------------------------
# 2. Controlli preliminari
# ---------------------------------------------------------------------------

Scrivi-Passo "Controllo file necessari"

$fileNecessari = @(
    "postiperfetti.py",
    "requirements.txt",
    "LICENSE",
    "classi\Classe-BASE_esempio.txt",
    "classi\Classe-COMPLETO_esempio.txt",
    "packaging\windows\build_windows.ps1",
    "packaging\windows\PostiPerfetti.spec",
    "packaging\windows\postiperfetti_setup.iss",
    "packaging\windows\version_info.txt",
    "packaging\windows\postiperfetti.ico",
    "packaging\windows\info_pre_installazione.txt",
    "packaging\windows\info_dopo_installazione.txt"
)

$mancanti = @(
    $fileNecessari | Where-Object {
        -not (Test-Path (Join-Path $Root $_) -PathType Leaf)
    }
)

if ($mancanti.Count -gt 0) {
    Write-Host "File mancanti:" -ForegroundColor Red
    $mancanti | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    throw "Build interrotta: la root non contiene tutti i file necessari."
}

Write-Host "OK: struttura minima del progetto presente." -ForegroundColor Green

Scrivi-Passo "Controllo Python"

$Python = Trova-Python

$PythonExe = $Python.Exe
$PythonBaseArgs = @($Python.Args)

$VersionArgs = $PythonBaseArgs + @("-c", "import sys; print(sys.version.split()[0])")
$versionePython = (& $PythonExe @VersionArgs | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Python è stato trovato, ma non è stato possibile eseguirlo."
}

$BitArgs = $PythonBaseArgs + @("-c", "import struct; print(struct.calcsize('P') * 8)")
$bitPython = (& $PythonExe @BitArgs | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Impossibile determinare l'architettura di Python."
}

Write-Host "Python: $versionePython ($bitPython bit)"

if ($bitPython -ne "64") {
    throw "Serve Python a 64 bit. È stato rilevato Python a $bitPython bit."
}

Scrivi-Passo "Controllo Inno Setup"

$ISCC = Trova-InnoSetup
if (-not $ISCC) {
    throw "Inno Setup 7/6 non trovato. Installalo e rilancia questo script."
}

Write-Host "Inno Setup: $ISCC" -ForegroundColor Green

# Controllo anche il nome concordato per l'installer.
$IssPath = Join-Path $PackagingDir "postiperfetti_setup.iss"
$IssText = Get-Content $IssPath -Raw

if ($IssText -notmatch '(?m)^\s*OutputBaseFilename=PostiPerfetti_setup\s*$') {
    throw "postiperfetti_setup.iss non contiene 'OutputBaseFilename=PostiPerfetti_setup'. Verifica il packaging prima di proseguire."
}

# ---------------------------------------------------------------------------
# 3. Pulizia controllata
# ---------------------------------------------------------------------------

Scrivi-Passo "Pulizia artefatti di build precedenti"

$daPulire = @(
    "build",
    "dist",
    "dist-installer"
)

if (-not $MantieniAmbienteBuild) {
    $daPulire += ".venv-build-windows"
}

foreach ($relativo in $daPulire) {
    $percorso = Join-Path $Root $relativo

    if (Test-Path $percorso) {
        Write-Host "Rimuovo: $relativo"
        Remove-Item $percorso -Recurse -Force
    } else {
        Write-Host "Già assente: $relativo"
    }
}

# ---------------------------------------------------------------------------
# 4. Build vera e propria
# ---------------------------------------------------------------------------

Scrivi-Passo "Build PyInstaller + Inno Setup"

$BuildScript = Join-Path $PackagingDir "build_windows.ps1"

# Lo script già collaudato rimane l'unica fonte della logica di packaging.
# L'orchestratore si limita a preparare l'ambiente e verificarne il risultato.
& $BuildScript

if ($LASTEXITCODE -ne 0) {
    throw "build_windows.ps1 è terminato con codice $LASTEXITCODE."
}

# ---------------------------------------------------------------------------
# 5. Verifica automatica degli artefatti
# ---------------------------------------------------------------------------

Scrivi-Passo "Verifica artefatti prodotti"

$Exe = Join-Path $Root "dist\PostiPerfetti\PostiPerfetti.exe"
$Internal = Join-Path $Root "dist\PostiPerfetti\_internal"
$ClasseBase = Join-Path $Root "dist\PostiPerfetti\classi\Classe-BASE_esempio.txt"
$ClasseCompleta = Join-Path $Root "dist\PostiPerfetti\classi\Classe-COMPLETO_esempio.txt"
$Setup = Join-Path $Root "dist-installer\PostiPerfetti_setup.exe"

$attesi = @(
    @{ Nome = "EXE";              Percorso = $Exe;            Tipo = "Leaf" },
    @{ Nome = "_internal";        Percorso = $Internal;       Tipo = "Container" },
    @{ Nome = "Classe BASE";      Percorso = $ClasseBase;     Tipo = "Leaf" },
    @{ Nome = "Classe COMPLETO";  Percorso = $ClasseCompleta; Tipo = "Leaf" },
    @{ Nome = "Setup";            Percorso = $Setup;          Tipo = "Leaf" }
)

$problemi = @()

foreach ($elemento in $attesi) {
    $ok = if ($elemento.Tipo -eq "Leaf") {
        Test-Path $elemento.Percorso -PathType Leaf
    } else {
        Test-Path $elemento.Percorso -PathType Container
    }

    if ($ok) {
        Write-Host ("OK  {0}" -f $elemento.Nome) -ForegroundColor Green
    } else {
        Write-Host ("KO  {0}: {1}" -f $elemento.Nome, $elemento.Percorso) -ForegroundColor Red
        $problemi += $elemento.Nome
    }
}

if ($problemi.Count -gt 0) {
    throw "Build terminata, ma mancano uno o più artefatti attesi: $($problemi -join ', ')."
}

# ---------------------------------------------------------------------------
# 6. SHA-256
# ---------------------------------------------------------------------------

Scrivi-Passo "Calcolo SHA-256 del Setup"

$hash = Get-FileHash -Path $Setup -Algorithm SHA256
$hashMinuscolo = $hash.Hash.ToLowerInvariant()
$ShaFile = "$Setup.sha256"

"$hashMinuscolo  PostiPerfetti_setup.exe" |
    Set-Content -Path $ShaFile -Encoding Ascii

$dimensioneMB = [Math]::Round((Get-Item $Setup).Length / 1MB, 2)

# ---------------------------------------------------------------------------
# 7. Riepilogo
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " BUILD WINDOWS COMPLETATA CON SUCCESSO" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "EXE:"
Write-Host "  $Exe"
Write-Host ""
Write-Host "INSTALLER:"
Write-Host "  $Setup"
Write-Host "  Dimensione: $dimensioneMB MB"
Write-Host ""
Write-Host "SHA-256:"
Write-Host "  $hashMinuscolo"
Write-Host "  Salvato anche in: $ShaFile"
Write-Host ""
Write-Host "Prossimo passo MANUALE:" -ForegroundColor Yellow
Write-Host "  doppio clic su PostiPerfetti_setup.exe e collaudo dell'installazione."
Write-Host ""

if (-not $NonAprireCartella) {
    Start-Process explorer.exe -ArgumentList (Join-Path $Root "dist-installer")
}
