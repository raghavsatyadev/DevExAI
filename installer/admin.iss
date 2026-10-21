; DevExAI Admin: the bot, the dashboard and the devexai command for the machine that hosts them.
; Built by tools/build_setup.py, which passes /DVersion and /DRoot. No admin rights needed.
;
; The build is unpacked to a temporary folder and its own `devexai install` copies it into the usual layout
; (%LOCALAPPDATA%\DevExAI\app-<version>, current.txt, devexai.cmd, data\), the one the built-in updater
; also uses. The folder holding devexai.cmd goes on this user's PATH.

[Setup]
AppId={{A3F0B6D2-8E4C-4B19-A7C5-0D9E2B6F4A18}
AppName=DevExAI Admin
AppVersion={#Version}
AppVerName=DevExAI Admin {#Version}
AppPublisher=DevExAI
DefaultDirName={localappdata}\DevExAI
DisableDirPage=yes
DisableProgramGroupPage=yes
DirExistsWarning=no
PrivilegesRequired=lowest
ChangesEnvironment=yes
CloseApplications=no
OutputDir={#Root}\dist
OutputBaseFilename=DevExAI-Admin-Setup-{#Version}
SetupIconFile={#Root}\assets\logo\devexai.ico
UninstallDisplayIcon={app}\app-{#Version}\devexai.exe
UninstallDisplayName=DevExAI Admin
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Messages]
FinishedLabelNoIcons=DevExAI is installed.%n%nIn a new terminal:%n    devexai start admin    starts the bot and opens the dashboard (again: just opens it)%n    devexai install <tool>    installs a published tool, as developers do%n%nOr start it from the Start menu: DevExAI.
FinishedLabel=DevExAI is installed.%n%nIn a new terminal:%n    devexai start admin    starts the bot and opens the dashboard (again: just opens it)%n    devexai install <tool>    installs a published tool, as developers do%n%nOr start it from the Start menu: DevExAI.

[Files]
Source: "{#Root}\dist\devexai\*"; DestDir: "{tmp}\devexai"; Flags: recursesubdirs ignoreversion deleteafterinstall

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsPath(ExpandConstant('{app}'))

[Run]
Filename: "{app}\devexai.cmd"; Parameters: "start admin"; Description: "Start DevExAI and open the dashboard"; Flags: postinstall nowait runhidden skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app-*"
Type: filesandordirs; Name: "{app}\.trash"
Type: files; Name: "{app}\current.txt"
Type: files; Name: "{app}\devexai.cmd"
Type: files; Name: "{userprograms}\DevExAI.lnk"

[Code]
#include "path.iss"

const
  STOP_REQUEST = 32771;  // WM_APP + 3, see src/devexai/tray.py

// Ask a running tray icon to quit, and wait for it. False if it is still running.
function StopBot(): Boolean;
var Wnd: HWND; I: Integer;
begin
  Result := True;
  Wnd := FindWindowByClassName('devexai.tray');
  if Wnd = 0 then
    exit;
  PostMessage(Wnd, STOP_REQUEST, 0, 0);
  for I := 1 to 75 do begin
    Sleep(200);
    if FindWindowByClassName('devexai.tray') = 0 then begin
      Sleep(1000);  // let the process finish closing its files
      exit;
    end;
  end;
  Result := False;
end;

// DevExAI for developers puts another devexai on PATH; the Admin one already has its commands.
procedure RemoveUserEdition();
var Uninstaller: string; Code: Integer;
begin
  Uninstaller := ExpandConstant('{localappdata}\DevExAI-User\unins000.exe');
  if FileExists(Uninstaller) then
    Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not StopBot() then
    Result := 'DevExAI is still running. Quit it from its icon in the notification area, then run this setup again.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Code: Integer;
begin
  if CurStep <> ssPostInstall then
    exit;
  RemoveUserEdition();
  if not Exec(ExpandConstant('{tmp}\devexai\devexai.exe'), 'install', '', SW_HIDE, ewWaitUntilTerminated, Code)
     or (Code <> 0) then
    RaiseException('Copying DevExAI into ' + ExpandConstant('{app}') + ' failed (code ' + IntToStr(Code) + ').');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then begin
    if not StopBot() then
      SuppressibleMsgBox('DevExAI is still running; some files may stay behind. Quit it from its icon next time.',
        mbInformation, MB_OK, IDOK);
    if SuppressibleMsgBox('Also delete DevExAI''s data: settings, the database, the blog posts and the TLS files in '
         + ExpandConstant('{app}\data') + '?' + #13#10#13#10 + 'Choose No to keep them for a later install.',
         mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      DelTree(ExpandConstant('{app}\data'), True, True, True);
  end;
  if CurUninstallStep = usPostUninstall then
    RemovePath(ExpandConstant('{app}'));
end;
