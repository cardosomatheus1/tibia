; ============================================================
; Instalador do client rhapsodyyy (otclient / mehah).
;
; Empacota a pasta do client montado (otclient.exe + assets 15.25 + modulos
; proprios + minimapa) e instala. O atalho NAO abre o otclient.exe direto:
; abre o launcher.ps1, que verifica atualizacoes no servidor, baixa so o que
; mudou e entao abre o jogo.
;
; Antes de compilar:
;   1. Monte o client com tools\preparar_mehah.ps1 (gera C:\otclient-mehah,
;      ja com o launcher.ps1 dentro).
;   2. Gere o icone com tools\installer\extrair_icone.ps1.
;   3. Abra este arquivo no Inno Setup Compiler e aperte Compile (Ctrl+F9).
;
; Ajuste SourceFolder se o client estiver em outro caminho.
; ============================================================

#define MyAppName "Tibia rhapsodyyy"
#define MyAppVersion "1.0"
#define LauncherVbs "launcher.vbs"
#define SourceFolder "C:\otclient-mehah"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=TibiaInstaller-rhapsodyyy
OutputDir=.
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
SetupIconFile={#SourceFolder}\tibia.ico
; O client tem varias milhares de arquivos (assets); mostra progresso real.
ShowLanguageDialog=no

[Files]
; Excludes: arquivos de runtime da pasta de trabalho nao entram no pacote --
; o log fica preso pelo client aberto e aborta a compilacao, e a marca de versao
; do launcher tem de comecar ausente para o primeiro arranque conferir tudo.
Source: "{#SourceFolder}\*"; DestDir: "{app}"; \
    Excludes: "otclient.log,launcher.log,.versao_instalada,*.bak,*.console-bak"; \
    Flags: recursesubdirs createallsubdirs
; Runtime do Visual C++ (x64). O otclient.exe e' compilado com MSVC e nao abre
; sem ele -- e' a causa classica de "abre e fecha sem nada" em PC que nao tem o
; runtime. Instalado silenciosamente; se ja existir, o proprio instalador da
; Microsoft detecta e pula.
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
; O atalho roda o launcher.vbs via wscript: ele dispara o PowerShell TOTALMENTE
; oculto (sem piscar janela de terminal). O launcher atualiza e abre o jogo.
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "wscript.exe"; \
    Parameters: """{app}\{#LauncherVbs}"""; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\tibia.ico"
Name: "{group}\{#MyAppName}"; \
    Filename: "wscript.exe"; \
    Parameters: """{app}\{#LauncherVbs}"""; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\tibia.ico"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; 1. instala o runtime do Visual C++ (silencioso; pula se ja instalado)
Filename: "{tmp}\vc_redist.x64.exe"; \
    Parameters: "/install /quiet /norestart"; \
    StatusMsg: "Instalando componentes necessarios (Visual C++)..."; \
    Flags: waituntilterminated

; 2. oferece abrir o jogo ao terminar (via o mesmo launcher oculto)
Filename: "wscript.exe"; \
    Parameters: """{app}\{#LauncherVbs}"""; \
    WorkingDir: "{app}"; \
    Description: "Abrir {#MyAppName} agora"; \
    Flags: nowait postinstall skipifsilent
