[CmdletBinding()]
param(
    # Esegue l'intera pipeline, ma non richiede che il CHANGELOG
    # sia già stato chiuso con la data definitiva della Release.
    [switch]$Collaudo
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest


# ============================================================================
# Funzioni
# ============================================================================

function Scrivi-Passo {
    param([string]$Testo)

    Write-Host ""
    Write-Host "=== $Testo ===" -ForegroundColor Cyan
}


function Scrivi-OK {
    param([string]$Testo)

    Write-Host "OK  $Testo" -ForegroundColor Green
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

    throw "Python 3 non trovato."
}


function Trova-InnoSetup {
    $candidati = @(
        (Join-Path ${env:ProgramFiles} "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    )

    return $candidati |
        Where-Object {
            $_ -and (Test-Path $_ -PathType Leaf)
        } |
        Select-Object -First 1
}


function Estrai-Versione {
    param([string]$Testo)

    if (-not $Testo) {
        return $null
    }

    $match = [regex]::Match(
        $Testo,
        '\d+\.\d+(?:\.\d+){0,2}'
    )

    if (-not $match.Success) {
        return $null
    }

    return $match.Value
}


function Ottieni-VersioneInnoSetup {
    param([string]$ISCC)

    $tempDir = Join-Path `
        ([System.IO.Path]::GetTempPath()) `
        ("PostiPerfetti-Inno-" + [guid]::NewGuid().ToString("N"))

    New-Item `
        -ItemType Directory `
        -Path $tempDir `
        -Force |
        Out-Null

    try {
        $probePath = Join-Path $tempDir "version_probe.iss"
        $versionPath = Join-Path $tempDir "version.txt"

        # Il percorso viene inserito in una stringa Pascal dell'ISPP.
        $versionPathIss = $versionPath.Replace("'", "''")

        $probe = @"
#call SaveStringToFile('$versionPathIss', Str(PREPROCVER), 0, 0)

[Setup]
AppName=PostiPerfetti Inno Version Probe
AppVersion=1
DefaultDirName={tmp}\PostiPerfettiInnoVersionProbe
Output=no
"@

        [System.IO.File]::WriteAllText(
            $probePath,
            $probe,
            [System.Text.Encoding]::ASCII
        )

        $output = & $ISCC /Q $probePath 2>&1
        $exitCode = $LASTEXITCODE

        if ($exitCode -ne 0) {
            throw (
                "Impossibile interrogare la versione di Inno Setup. " +
                ($output -join [Environment]::NewLine)
            )
        }

        if (-not (Test-Path $versionPath -PathType Leaf)) {
            throw (
                "Inno Setup non ha restituito la propria versione."
            )
        }

        $packedText = (
            [System.IO.File]::ReadAllText(
                $versionPath,
                [System.Text.Encoding]::ASCII
            )
        ).Trim()

        try {
            $packed = [int64]$packedText
        } catch {
            throw (
                "Versione Inno Setup non interpretabile: " +
                "'$packedText'."
            )
        }

        $major = ($packed -shr 24) -band 0xFF
        $minor = ($packed -shr 16) -band 0xFF
        $revision = ($packed -shr 8) -band 0xFF
        $build = $packed -band 0xFF

        return "$major.$minor.$revision.$build"
    } finally {
        Remove-Item `
            $tempDir `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }
}


function Verifica-VersioneArtefatto {
    param(
        [string]$Percorso,
        [string]$Nome,
        [string]$Versione,
        [string]$VersioneQuad
    )

    $info = (Get-Item $Percorso).VersionInfo

    $fileVersion = Estrai-Versione $info.FileVersion
    $productVersion = Estrai-Versione $info.ProductVersion

    if ($fileVersion -ne $VersioneQuad) {
        throw (
            "${Nome}: FileVersion non corretta. " +
            "Attesa $VersioneQuad, trovata $fileVersion."
        )
    }

    if (
        $productVersion -ne $Versione -and
        $productVersion -ne $VersioneQuad
    ) {
        throw (
            "${Nome}: ProductVersion non corretta. " +
            "Attesa $Versione o $VersioneQuad, " +
            "trovata $productVersion."
        )
    }

    Scrivi-OK (
        "${Nome}: FileVersion=$fileVersion; " +
        "ProductVersion=$productVersion"
    )
}


function Verifica-FileSha256 {
    param(
        [string]$FileSha,
        [string]$FileVero
    )

    if (-not (Test-Path $FileSha -PathType Leaf)) {
        throw "File SHA-256 assente: $FileSha"
    }

    $riga = (Get-Content $FileSha -Raw).Trim()

    if (
        $riga -notmatch
        '^([0-9a-fA-F]{64})\s{2,}(.+)$'
    ) {
        throw "Formato SHA-256 non valido: $FileSha"
    }

    $atteso = $Matches[1].ToLowerInvariant()

    $ottenuto = (
        Get-FileHash -Path $FileVero -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if ($atteso -ne $ottenuto) {
        throw (
            "SHA-256 non corrispondente per " +
            "$(Split-Path $FileVero -Leaf)."
        )
    }

    Scrivi-OK (
        "SHA-256 verificato: " +
        "$(Split-Path $FileVero -Leaf)"
    )
}


# ============================================================================
# 1. Root e identità della build
# ============================================================================

if (
    [Environment]::OSVersion.Platform -ne
    [PlatformID]::Win32NT
) {
    throw "CREA_RELEASE va eseguito su Windows."
}

$PackagingDir = $PSScriptRoot
$Root = (
    Resolve-Path (
        Join-Path $PackagingDir "..\.."
    )
).Path

Set-Location $Root

Write-Host ""
Write-Host "============================================================" `
    -ForegroundColor Green
Write-Host " PostiPerfetti - pipeline di Release" `
    -ForegroundColor Green
Write-Host "============================================================" `
    -ForegroundColor Green
Write-Host ""
Write-Host "Root: $Root"

if ($Collaudo) {
    Write-Host "Modalità: COLLAUDO" -ForegroundColor Yellow
} else {
    Write-Host "Modalità: RELEASE FINALE" -ForegroundColor Green
}


# ============================================================================
# 2. Controllo struttura
# ============================================================================

Scrivi-Passo "Controllo dei file necessari"

$fileNecessari = @(
    "postiperfetti.py",
    "requirements.txt",
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "moduli\versione.py",
    "documentazione\DATI_PRIVACY_E_SICUREZZA.md",
    "documentazione\sviluppo\requirements-dev.txt",
    "documentazione\sviluppo\test",
    "packaging\linux\install.sh",
    "packaging\linux\uninstall.sh",
    "packaging\linux\crea_release_linux.py",
    "packaging\windows\requirements-build-windows.txt",
    "packaging\windows\crea_installer_windows.ps1",
    "packaging\windows\build_windows.ps1",
    "packaging\windows\PostiPerfetti.spec",
    "packaging\windows\postiperfetti_setup.iss",
    "packaging\windows\info_pre_installazione.txt",
    "packaging\windows\info_dopo_installazione.txt"
)

$mancanti = @()

foreach ($relativo in $fileNecessari) {
    $percorso = Join-Path $Root $relativo

    if (-not (Test-Path $percorso)) {
        $mancanti += $relativo
    }
}

if ($mancanti.Count -gt 0) {
    Write-Host "Mancano:" -ForegroundColor Red

    foreach ($mancante in $mancanti) {
        Write-Host "  - $mancante" -ForegroundColor Red
    }

    throw "Struttura della Release incompleta."
}

Scrivi-OK "Struttura minima presente"


# ============================================================================
# 3. Python di sistema e versione PostiPerfetti
# ============================================================================

Scrivi-Passo "Controllo Python e versione della Release"

$Python = Trova-Python
$PythonExe = $Python.Exe
$PythonBaseArgs = @($Python.Args)

$comandoVersionePython = $PythonBaseArgs + @(
    "-c",
    (
        "import sys; " +
        "print(sys.version.split()[0]); " +
        "raise SystemExit(" +
        "0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)"
    )
)

$versionePython = (
    & $PythonExe @comandoVersionePython |
    Select-Object -Last 1
).Trim()

if ($LASTEXITCODE -ne 0) {
    throw (
        "Python $versionePython non è compatibile. " +
        "Sono supportati Python 3.10-3.14."
    )
}

$comandoBit = $PythonBaseArgs + @(
    "-c",
    "import struct; print(struct.calcsize('P') * 8)"
)

$bitPython = (
    & $PythonExe @comandoBit |
    Select-Object -Last 1
).Trim()

if ($bitPython -ne "64") {
    throw "La build Windows richiede Python a 64 bit."
}

$comandoVersione = $PythonBaseArgs + @(
    "-c",
    (
        "from moduli.versione import VERSIONE; " +
        "print(VERSIONE)"
    )
)

$Versione = (
    & $PythonExe @comandoVersione |
    Select-Object -Last 1
).Trim()

$comandoVersioneWindows = $PythonBaseArgs + @(
    "-c",
    (
        "from moduli.versione import VERSIONE_WINDOWS; " +
        "print('.'.join(str(x) for x in VERSIONE_WINDOWS))"
    )
)

$VersioneWindows = (
    & $PythonExe @comandoVersioneWindows |
    Select-Object -Last 1
).Trim()

$comandoTag = $PythonBaseArgs + @(
    "-c",
    (
        "from moduli.versione import TAG_RELEASE; " +
        "print(TAG_RELEASE)"
    )
)

$TagRelease = (
    & $PythonExe @comandoTag |
    Select-Object -Last 1
).Trim()

Write-Host "Python        : $versionePython ($bitPython bit)"
Write-Host "PostiPerfetti : $Versione"
Write-Host "Versione Win  : $VersioneWindows"
Write-Host "Tag Release   : $TagRelease"

Scrivi-OK "Identità della Release letta dalla fonte unica"


# ============================================================================
# 4. CHANGELOG
# ============================================================================

Scrivi-Passo "Controllo CHANGELOG"

$ChangelogPath = Join-Path $Root "CHANGELOG.md"
$Changelog = Get-Content $ChangelogPath -Raw

$versioneRegex = [regex]::Escape($Versione)

if ($Collaudo) {
    if (
        $Changelog -notmatch
        "(?m)^##\s+$versioneRegex\b"
    ) {
        throw (
            "CHANGELOG.md non contiene una sezione " +
            "per la versione $Versione."
        )
    }

    Write-Host (
        "COLLAUDO: è ammessa la dicitura " +
        "«in preparazione»."
    ) -ForegroundColor Yellow
} else {
    if (
        $Changelog -match
        "(?m)^##\s+$versioneRegex\s+[—-]\s+in preparazione\s*$"
    ) {
        throw (
            "CHANGELOG.md indica ancora $Versione " +
            "come «in preparazione»."
        )
    }

    if (
        $Changelog -notmatch
        "(?m)^##\s+$versioneRegex\s+[—-]\s+\d{4}-\d{2}-\d{2}\s*$"
    ) {
        throw (
            "La Release finale richiede nel CHANGELOG una " +
            "riga nel formato: " +
            "'## $Versione — YYYY-MM-DD'."
        )
    }
}

Scrivi-OK "CHANGELOG coerente con la modalità richiesta"


# ============================================================================
# 5. Inno Setup
# ============================================================================

Scrivi-Passo "Controllo Inno Setup"

$ISCC = Trova-InnoSetup

if (-not $ISCC) {
    throw "Inno Setup 6/7 non trovato."
}

$InnoVersionText = Ottieni-VersioneInnoSetup -ISCC $ISCC
$InnoVersion = [version]$InnoVersionText

if ($InnoVersion -lt [version]"6.6.0") {
    throw (
        "Inno Setup $InnoVersionText non è supportato. " +
        "Serve almeno 6.6.0."
    )
}

Write-Host "Inno Setup: $InnoVersionText"
Write-Host "Percorso   : $ISCC"

Scrivi-OK "Toolchain Inno Setup compatibile"


# ============================================================================
# 6. Pulizia della precedente Release
# ============================================================================

Scrivi-Passo "Pulizia della precedente area Release"

$DistRelease = Join-Path $Root "dist-release"

if (Test-Path $DistRelease) {
    Remove-Item $DistRelease -Recurse -Force
}

# La Release deve nascere anche da un ambiente Windows pulito.
$BuildVenv = Join-Path $Root ".venv-build-windows"

if (Test-Path $BuildVenv) {
    Remove-Item $BuildVenv -Recurse -Force
}

Scrivi-OK "Area Release e ambiente di build precedente rimossi"


# ============================================================================
# 7. Build Windows pulita
# ============================================================================

Scrivi-Passo "Build Windows da ambiente pulito"

$CreaInstaller = Join-Path `
    $PackagingDir `
    "crea_installer_windows.ps1"

# INTENZIONALMENTE non passiamo -MantieniAmbienteBuild.
& $CreaInstaller -NonAprireCartella

if ($LASTEXITCODE -ne 0) {
    throw (
        "La pipeline Windows è terminata con codice " +
        "$LASTEXITCODE."
    )
}

Scrivi-OK "Build Windows completata"


# ============================================================================
# 8. Toolchain realmente utilizzata
# ============================================================================

Scrivi-Passo "Verifica della toolchain realmente utilizzata"

$PythonBuild = Join-Path `
    $Root `
    ".venv-build-windows\Scripts\python.exe"

if (-not (Test-Path $PythonBuild -PathType Leaf)) {
    throw (
        "L'ambiente pulito di build non contiene Python: " +
        "$PythonBuild"
    )
}

$PythonBuildVersion = (
    & $PythonBuild -c "import sys; print(sys.version.split()[0])"
).Trim()

$PyInstallerVersion = (
    & $PythonBuild -c (
        "import PyInstaller; " +
        "print(PyInstaller.__version__)"
    )
).Trim()

$PytestVersion = (
    & $PythonBuild -c (
        "from importlib.metadata import version; " +
        "print(version('pytest'))"
    )
).Trim()

$RuffVersioneCompleta = (
    & $PythonBuild -m ruff --version
).Trim()

$RequirementsBuild = Join-Path `
    $PackagingDir `
    "requirements-build-windows.txt"

$MatchPyInstaller = Select-String `
    -Path $RequirementsBuild `
    -Pattern '^PyInstaller==(.+)$'

if (-not $MatchPyInstaller) {
    throw (
        "requirements-build-windows.txt non congela " +
        "PyInstaller con ==."
    )
}

$PyInstallerAtteso = (
    $MatchPyInstaller.Matches[0].Groups[1].Value
).Trim()

if ($PyInstallerVersion -ne $PyInstallerAtteso) {
    throw (
        "PyInstaller installato: $PyInstallerVersion; " +
        "atteso: $PyInstallerAtteso."
    )
}

Write-Host "Python build : $PythonBuildVersion"
Write-Host "PyInstaller  : $PyInstallerVersion"
Write-Host "pytest       : $PytestVersion"
Write-Host "Ruff         : $RuffVersioneCompleta"

Scrivi-OK "Toolchain Python conforme ai requisiti congelati"


# ============================================================================
# 9. Ruff
# ============================================================================

Scrivi-Passo "Controllo Ruff della Release"

& $PythonBuild -m ruff check `
    "postiperfetti.py" `
    "moduli" `
    "packaging\linux\crea_release_linux.py" `
    --select F401,F841,RUF013

if ($LASTEXITCODE -ne 0) {
    throw "Ruff ha trovato uno o più problemi."
}

Scrivi-OK "Ruff completamente verde"


# ============================================================================
# 10. Verifica metadati Windows
# ============================================================================

Scrivi-Passo "Verifica delle versioni negli artefatti Windows"

$Exe = Join-Path `
    $Root `
    "dist\PostiPerfetti\PostiPerfetti.exe"

# Il nome del Setup contiene la versione, come già il pacchetto Linux.
$NomeSetup = "PostiPerfetti-$Versione-setup.exe"

$Setup = Join-Path `
    $Root `
    "dist-installer\$NomeSetup"

$SetupSha = "$Setup.sha256"

if (-not (Test-Path $Exe -PathType Leaf)) {
    throw "PostiPerfetti.exe non trovato."
}

if (-not (Test-Path $Setup -PathType Leaf)) {
    throw "$NomeSetup non trovato."
}

Verifica-VersioneArtefatto `
    -Percorso $Exe `
    -Nome "PostiPerfetti.exe" `
    -Versione $Versione `
    -VersioneQuad $VersioneWindows

Verifica-VersioneArtefatto `
    -Percorso $Setup `
    -Nome $NomeSetup `
    -Versione $Versione `
    -VersioneQuad $VersioneWindows

Verifica-FileSha256 `
    -FileSha $SetupSha `
    -FileVero $Setup


# ============================================================================
# 11. Asset Linux
# ============================================================================

Scrivi-Passo "Generazione degli asset Linux della stessa Release"

$GeneratoreLinux = Join-Path `
    $Root `
    "packaging\linux\crea_release_linux.py"

& $PythonBuild $GeneratoreLinux

if ($LASTEXITCODE -ne 0) {
    throw (
        "La generazione degli asset Linux è terminata " +
        "con codice $LASTEXITCODE."
    )
}

$DistLinux = Join-Path $Root "dist-linux"

$NomePacchettoLinux = (
    "PostiPerfetti-" +
    $Versione +
    "-linux.tar.gz"
)

$PacchettoLinux = Join-Path `
    $DistLinux `
    $NomePacchettoLinux

$InstallerLinux = Join-Path `
    $DistLinux `
    "install.sh"

$ShaLinux = Join-Path `
    $DistLinux `
    "SHA256SUMS"

foreach ($file in @(
    $PacchettoLinux,
    $InstallerLinux,
    $ShaLinux
)) {
    if (-not (Test-Path $file -PathType Leaf)) {
        throw "Asset Linux mancante: $file"
    }
}

$TestoInstallerLinux = Get-Content `
    $InstallerLinux `
    -Raw

if (
    $TestoInstallerLinux -notmatch
    '(?m)^MODALITA_RELEASE=1$'
) {
    throw (
        "L'install.sh generato non è in modalità Release."
    )
}

if (
    $TestoInstallerLinux -notmatch
    (
        '(?m)^VERSIONE_RELEASE="' +
        [regex]::Escape($Versione) +
        '"$'
    )
) {
    throw (
        "L'install.sh Linux non contiene la versione " +
        "attesa."
    )
}

if (
    $TestoInstallerLinux -notmatch
    [regex]::Escape(
        "/releases/download/$TagRelease/$NomePacchettoLinux"
    )
) {
    throw (
        "L'install.sh Linux non punta all'asset " +
        "della Release $TagRelease."
    )
}

Scrivi-OK "Asset Linux coerenti con la stessa Release"


# ============================================================================
# 12. Verifica SHA256SUMS Linux
# ============================================================================

Scrivi-Passo "Verifica degli SHA-256 Linux"

$righeSha = Get-Content $ShaLinux

foreach ($riga in $righeSha) {
    if (-not $riga.Trim()) {
        continue
    }

    if (
        $riga -notmatch
        '^([0-9a-fA-F]{64})\s{2,}(.+)$'
    ) {
        throw "Riga non valida in SHA256SUMS: $riga"
    }

    $hashAtteso = $Matches[1].ToLowerInvariant()
    $nomeFile = $Matches[2].Trim()
    $file = Join-Path $DistLinux $nomeFile

    if (-not (Test-Path $file -PathType Leaf)) {
        throw (
            "SHA256SUMS fa riferimento a un file assente: " +
            "$nomeFile"
        )
    }

    $hashReale = (
        Get-FileHash $file -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if ($hashAtteso -ne $hashReale) {
        throw "SHA-256 Linux errato per $nomeFile."
    }

    Scrivi-OK "SHA-256 Linux: $nomeFile"
}


# ============================================================================
# 13. Cartella finale
# ============================================================================

Scrivi-Passo "Preparazione della cartella finale"

if ($Collaudo) {
    $NomeRelease = "COLLAUDO-$TagRelease"
    $NomeAssetDir = "ARTEFATTI_DI_COLLAUDO"
} else {
    $NomeRelease = $TagRelease
    $NomeAssetDir = "DA_CARICARE"
}

$ReleaseDir = Join-Path `
    $DistRelease `
    $NomeRelease

$AssetDir = Join-Path `
    $ReleaseDir `
    $NomeAssetDir

New-Item `
    -ItemType Directory `
    -Force `
    -Path $AssetDir |
    Out-Null

Copy-Item $Setup $AssetDir -Force
Copy-Item $SetupSha $AssetDir -Force
Copy-Item $PacchettoLinux $AssetDir -Force
Copy-Item $InstallerLinux $AssetDir -Force
Copy-Item $ShaLinux $AssetDir -Force


# ============================================================================
# 14. Manifest tecnico locale
# ============================================================================

Scrivi-Passo "Scrittura manifest della Release"

$ManifestPath = Join-Path `
    $ReleaseDir `
    "MANIFEST_RELEASE.txt"

$modalitaTesto = if ($Collaudo) {
    "COLLAUDO - NON PUBBLICARE"
} else {
    "RELEASE FINALE"
}

$righeManifest = @(
    "PostiPerfetti - Manifest Release"
    "================================"
    ""
    "Modalità: $modalitaTesto"
    "Versione: $Versione"
    "Tag: $TagRelease"
    "Versione Windows: $VersioneWindows"
    ""
    "Toolchain Windows"
    "-----------------"
    "Python: $PythonBuildVersion - 64 bit"
    "PyInstaller: $PyInstallerVersion"
    "pytest: $PytestVersion"
    "Ruff: $RuffVersioneCompleta"
    "Inno Setup: $InnoVersionText"
    "ISCC: $ISCC"
    ""
    "Firma digitale Windows: NON PRESENTE"
    ""
    "Asset"
    "-----"
)

$assetProdotti = Get-ChildItem `
    $AssetDir `
    -File |
    Sort-Object Name

foreach ($asset in $assetProdotti) {
    $hash = (
        Get-FileHash `
            $asset.FullName `
            -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    $righeManifest += (
        "$hash  $($asset.Name)"
    )
}

$righeManifest |
    Set-Content `
        -Path $ManifestPath `
        -Encoding UTF8

Scrivi-OK "Manifest tecnico creato"


# ============================================================================
# 15. Istruzioni di pubblicazione
# ============================================================================

$IstruzioniPath = Join-Path `
    $ReleaseDir `
    "PUBBLICAZIONE_GITHUB.txt"

if ($Collaudo) {
    $righeIstruzioni = @(
        "COLLAUDO DELLA PIPELINE DI RELEASE"
        "==================================="
        ""
        "NON pubblicare questi artefatti."
        ""
        "La pipeline completa è terminata con successo."
        "Quando vorrai produrre la Release vera:"
        ""
        "1. aggiorna CHANGELOG.md sostituendo"
        "   «$Versione — in preparazione» con la data reale;"
        "2. esegui CREA_RELEASE.cmd SENZA l'argomento COLLAUDO;"
        "3. segui le istruzioni prodotte dalla build finale."
    )
} else {
    $righeIstruzioni = @(
        "PUBBLICAZIONE MANUALE DELLA RELEASE $TagRelease"
        "================================================"
        ""
        "1. Carica sul repository GitHub tutti i sorgenti aggiornati."
        ""
        "2. Verifica nella scheda Actions che la matrice di test"
        "   Python 3.10-3.14 sia completamente verde."
        ""
        "3. In GitHub apri Releases e crea una nuova Release."
        ""
        "4. Crea o seleziona il tag:"
        "   $TagRelease"
        ""
        "5. Usa come titolo, per esempio:"
        "   PostiPerfetti $Versione"
        ""
        "6. Usa CHANGELOG.md come base per le note della Release."
        ""
        "7. Carica TUTTI e SOLTANTO i file presenti nella cartella:"
        "   $NomeAssetDir"
        ""
        "8. Pubblica la Release."
        ""
        "9. Dopo la pubblicazione esegui i collaudi finali:"
        "   - installazione Windows da $NomeSetup;"
        "   - verifica Proprietà -> Dettagli dell'EXE e del Setup;"
        "   - installazione Linux usando l'install.sh pubblicato;"
        "   - avvio reale del programma;"
        "   - disinstallazione/reinstallazione conservativa."
        ""
        "Il codice sorgente corrispondente alla Release deve essere"
        "disponibile nel repository sotto il tag $TagRelease."
    )
}

$righeIstruzioni |
    Set-Content `
        -Path $IstruzioniPath `
        -Encoding UTF8


# ============================================================================
# 16. Riepilogo
# ============================================================================

Write-Host ""
Write-Host "============================================================" `
    -ForegroundColor Green

if ($Collaudo) {
    Write-Host " COLLAUDO RELEASE COMPLETATO CON SUCCESSO" `
        -ForegroundColor Green
} else {
    Write-Host " RELEASE PREPARATA CON SUCCESSO" `
        -ForegroundColor Green
}

Write-Host "============================================================" `
    -ForegroundColor Green
Write-Host ""

Write-Host "Versione:"
Write-Host "  $Versione"
Write-Host ""

Write-Host "Tag:"
Write-Host "  $TagRelease"
Write-Host ""

Write-Host "Cartella:"
Write-Host "  $ReleaseDir"
Write-Host ""

Write-Host "Asset:"
Write-Host "  $AssetDir"
Write-Host ""

Write-Host "Manifest:"
Write-Host "  $ManifestPath"
Write-Host ""

Write-Host "Istruzioni:"
Write-Host "  $IstruzioniPath"
Write-Host ""

if ($Collaudo) {
    Write-Host (
        "Gli artefatti sono di COLLAUDO: " +
        "non pubblicarli."
    ) -ForegroundColor Yellow
} else {
    Write-Host (
        "La cartella DA_CARICARE contiene " +
        "gli asset della Release ufficiale."
    ) -ForegroundColor Yellow
}

Write-Host ""

Start-Process explorer.exe `
    -ArgumentList $ReleaseDir
