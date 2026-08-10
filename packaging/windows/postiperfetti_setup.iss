#ifndef MyAppVersion
  #error MyAppVersion non definita: compilare tramite build_windows.ps1
#endif

#ifndef MyAppVersionQuad
  #error MyAppVersionQuad non definita: compilare tramite build_windows.ps1
#endif

#define MyAppName "PostiPerfetti"
#define MyAppPublisher "Omar Ceretta"
#define MyAppURL "https://github.com/Omar-Ceretta/PostiPerfetti"
#define MyAppExeName "PostiPerfetti.exe"

[Setup]
; AppId deve rimanere IDENTICO nelle versioni future: consente a Inno Setup
; di riconoscere gli aggiornamenti della stessa applicazione.
AppId={{0A0175B6-B6EF-48EA-A9B6-0FFA116A8C4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases/latest
AppContact=ceretta.omar@ictombologalliera.edu.it

; Installazione PER UTENTE: niente UAC, cartella scrivibile e dati isolati.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; La build PyInstaller prevista è x64.
SetupArchitecture=x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

; Aspetto e metadati.
WizardStyle=modern dynamic
DisableWelcomePage=no
SetupIconFile=postiperfetti.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\..\LICENSE
InfoBeforeFile=info_pre_installazione.txt
InfoAfterFile=info_dopo_installazione.txt

; Output dell'installer, sempre relativo alla root del repository.
OutputDir=..\..\dist-installer
OutputBaseFilename=PostiPerfetti_setup
Compression=lzma2
SolidCompression=yes

; Versione del Setup.exe stesso, ricevuta dalla fonte unica tramite lo script di build.
VersionInfoVersion={#MyAppVersionQuad}
VersionInfoProductVersion={#MyAppVersionQuad}
VersionInfoDescription=Installer di PostiPerfetti
VersionInfoProductName=PostiPerfetti

; Aiuta Setup a sostituire i file runtime quando l'app è aperta.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul Desktop"; GroupDescription: "Collegamenti aggiuntivi:"; Flags: unchecked

; Prima di un aggiornamento ripuliamo SOLO il runtime PyInstaller precedente.
; classi/, stato/ e log/ non vengono mai toccati qui.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\{#MyAppExeName}"

[Dirs]
; Queste tre directory appartengono all'utente e non vanno rimosse
; automaticamente dall'uninstaller.
Name: "{app}\classi"; Flags: uninsneveruninstall
Name: "{app}\stato"; Flags: uninsneveruninstall
Name: "{app}\log"; Flags: uninsneveruninstall

[Files]
; Bundle PyInstaller onedir: PostiPerfetti.exe + _internal\...
Source: "..\..\dist\PostiPerfetti\*"; DestDir: "{app}"; Excludes: "\classi\*"; Flags: ignoreversion recursesubdirs createallsubdirs

; Licenza leggibile anche nella cartella installata.
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

; I file di esempio vengono seminati senza sovrascrivere eventuali copie
; già modificate dall'utente e restano dopo la disinstallazione normale.
Source: "..\..\classi\Classe-BASE_esempio.txt"; DestDir: "{app}\classi"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\..\classi\Classe-COMPLETO_esempio.txt"; DestDir: "{app}\classi"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\PostiPerfetti"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Apri cartella PostiPerfetti"; Filename: "{app}"
Name: "{group}\Disinstalla PostiPerfetti"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PostiPerfetti"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia PostiPerfetti"; Flags: nowait postinstall skipifsilent

[Code]
var
  EliminaDatiUtente: Boolean;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    { Scelta volutamente prudente: NO è il pulsante predefinito.
      Anche in disinstallazione silenziosa i dati vengono conservati. }
    EliminaDatiUtente :=
      SuppressibleMsgBox(
        'Vuoi eliminare anche i dati personali di PostiPerfetti?' + #13#10 + #13#10 +
        'Verranno cancellate definitivamente le cartelle:' + #13#10 +
        '  • classi' + #13#10 +
        '  • stato' + #13#10 +
        '  • log' + #13#10 + #13#10 +
        'Scegli «No» per conservarle in vista di una futura reinstallazione.',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2,
        IDNO
      ) = IDYES;
  end
  else if (CurUninstallStep = usPostUninstall) and EliminaDatiUtente then
  begin
    { Cancelliamo soltanto le aree dati conosciute: eventuali file estranei
      lasciati nella cartella PostiPerfetti non vengono rimossi. }
    DelTree(ExpandConstant('{app}\classi'), True, True, True);
    DelTree(ExpandConstant('{app}\stato'), True, True, True);
    DelTree(ExpandConstant('{app}\log'), True, True, True);
    RemoveDir(ExpandConstant('{app}'));
  end;
end;
