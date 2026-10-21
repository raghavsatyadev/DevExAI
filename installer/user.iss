; DevExAI for developers: the `devexai` command (devexai_cli only, no admin code) for this Windows user.
; Built by tools/build_setup.py, which passes /DVersion and /DRoot. No admin rights needed.
;
; It asks for the DevExAI server, prefilled from /SERVER=, from the address the setup was downloaded from
; (the dashboard's /get page), or from the last one used; then runs `devexai connect <server>`, which trusts
; the company certificate authority and remembers the server.

[Setup]
AppId={{6C1E3E0B-4C7A-4D52-9B7E-2F1D7A1C5E31}
AppName=DevExAI for developers
AppVersion={#Version}
AppVerName=DevExAI for developers {#Version}
AppPublisher=DevExAI
DefaultDirName={localappdata}\DevExAI-User
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ChangesEnvironment=yes
CloseApplications=no
OutputDir={#Root}\dist\user
OutputBaseFilename=DevExAI-User-Setup
SetupIconFile={#Root}\assets\logo\devexai.ico
UninstallDisplayIcon={app}\devexai.exe
UninstallDisplayName=DevExAI for developers
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Messages]
FinishedLabelNoIcons=The devexai command is installed.%n%nOpen a new terminal (terminals that are already open do not see it yet) and copy the install command from any post on the DevExAI blog, for example:%n%n    devexai install <tool>

[Files]
Source: "{#Root}\dist\user\devexai.exe"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsPath(ExpandConstant('{app}'))

[Code]
#include "path.iss"

var
  ServerPage: TInputQueryWizardPage;

function Trimmed(S: string): string;
begin
  Result := Trim(S);
  while (Length(Result) > 0) and (Result[Length(Result)] = '/') do
    Delete(Result, Length(Result), 1);
end;

// "HostUrl=https://devexai.corp:8765/get/DevExAI-User-Setup.exe" -> "https://devexai.corp:8765"
function DownloadedFrom(): string;
var Lines: TArrayOfString; I, P: Integer; Url: string;
begin
  Result := '';
  if not LoadStringsFromFile(ExpandConstant('{srcexe}') + ':Zone.Identifier', Lines) then
    exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
    if Pos('HostUrl=', Lines[I]) = 1 then begin
      Url := Copy(Lines[I], 9, Length(Lines[I]));
      P := Pos('/get/', Url);
      if P > 0 then
        Result := Copy(Url, 1, P - 1);
    end;
end;

function SavedServer(): string;
var S: AnsiString;
begin
  Result := '';
  if LoadStringFromFile(ExpandConstant('{%USERPROFILE}\.devex\server.txt'), S) then
    Result := Trimmed(String(S));
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if FileExists(ExpandConstant('{localappdata}\DevExAI\devexai.cmd')) then begin
    SuppressibleMsgBox('DevExAI Admin is installed for this user and already has the devexai commands '
      + '(devexai install <tool>, list, uninstall). Nothing to do.', mbInformation, MB_OK, IDOK);
    Result := False;
  end;
end;

procedure InitializeWizard();
var Server: string;
begin
  ServerPage := CreateInputQueryPage(wpWelcome, 'DevExAI server',
    'Which DevExAI server does your company use?',
    'It is the address of the DevExAI blog, without /blog. Your DevExAI admin can tell you.');
  ServerPage.Add('Server address:', False);
  Server := Trimmed(ExpandConstant('{param:SERVER|}'));
  if Server = '' then Server := DownloadedFrom();
  if Server = '' then Server := SavedServer();
  if Server = '' then Server := 'https://';
  ServerPage.Values[0] := Server;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var S: string;
begin
  Result := True;
  if CurPageID = ServerPage.ID then begin
    S := Lowercase(Trimmed(ServerPage.Values[0]));
    if ((Pos('https://', S) <> 1) and (Pos('http://', S) <> 1)) or (Length(S) < 10) then begin
      SuppressibleMsgBox('Type the address like https://devexai.example:8765', mbError, MB_OK, IDOK);
      Result := False;
    end;
  end;
end;

// `devexai update` runs this setup while the old devexai.exe is exiting: wait until it can be replaced.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var Exe: string; I: Integer;
begin
  Result := '';
  Exe := ExpandConstant('{app}\devexai.exe');
  for I := 1 to 50 do begin
    if (not FileExists(Exe)) or DeleteFile(Exe) then
      exit;
    Sleep(200);
  end;
  Result := 'devexai.exe is still running. Close the terminal that runs it, then run this setup again.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Server: string; Code: Integer;
begin
  if CurStep <> ssPostInstall then
    exit;
  Server := Trimmed(ServerPage.Values[0]);
  if (Pos('http', Lowercase(Server)) <> 1) or (Length(Server) < 10) then
    exit;
  if not Exec(ExpandConstant('{app}\devexai.exe'), 'connect "' + Server + '"', '', SW_HIDE,
              ewWaitUntilTerminated, Code) or (Code <> 0) then
    SuppressibleMsgBox('Could not connect to ' + Server + '. Check the address, then open a new terminal and run:'
      + #13#10#13#10 + '    devexai connect ' + Server, mbError, MB_OK, IDOK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemovePath(ExpandConstant('{app}'));
end;
