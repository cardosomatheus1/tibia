; ============================================================
; Instalador do Mapeador de Hunts.
;
; Instalar tem de bastar: nada de instalar Python, nada de baixar mapa, nada
; de precisar ja ter o client. Por isso o pacote leva tudo --
;
;   o interpretador  Python embeddable, pasta solta, sem tocar na maquina
;   o mapa           185 MB crus, ~30 MB aqui dentro (OTBM comprime bem)
;   os sprites       a pasta assets do client, ~135 MB (as folhas ja sao LZMA
;                    e nao encolhem mais)
;
; Da uns 180 MB de instalador. E' o preco de "instalou, abriu, funcionou" --
; para enxugar, monte o pacote com -SemAssets ou -SemMapa e o launcher volta
; a procurar na maquina / baixar.
;
; Antes de compilar:
;   1. Rode tools\mapa\preparar_mapeador.ps1 (monta C:\mapeador-hunts-pacote).
;   2. Abra este arquivo no Inno Setup Compiler e aperte Compile (Ctrl+F9),
;      ou rode:  & "C:\Program Files\Inno Setup 7\ISCC.exe" instalador_mapeador.iss
; ============================================================

#define MyAppName "Mapeador de Hunts"
#define MyAppVersion "1.0"
#define SourceFolder "C:\mapeador-hunts-pacote"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=MapeadorDeHunts
OutputDir=.
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
; sem admin: instala no perfil do usuario, e o programa grava o mapa e o cache
; na propria pasta -- por isso ela precisa ser gravavel
PrivilegesRequired=lowest
ShowLanguageDialog=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
; O cache de tiles nasce em uso e nao viaja. O Excludes do Inno casa NOME de
; arquivo e nao caminho, entao "cache_tiles\*" nao pegava e 10 tiles ja
; renderizados foram parar dentro do instalador -- quem garante e' o
; preparar_mapeador.ps1, que apaga a pasta antes. Isto aqui e' so reforco.
Source: "{#SourceFolder}\*"; DestDir: "{app}"; \
    Excludes: "*.parcial,cache_tiles\*"; \
    Flags: recursesubdirs createallsubdirs

[Icons]
; O atalho chama o powershell com o launcher. A janela FICA VISIVEL de
; proposito: e' o servidor rodando, e fecha-la e' como o usuario encerra.
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\abrir.ps1"""; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\mapeador.ico"
Name: "{group}\{#MyAppName}"; \
    Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\abrir.ps1"""; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\mapeador.ico"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\abrir.ps1"""; \
    WorkingDir: "{app}"; \
    Description: "Abrir o {#MyAppName} agora"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; os tiles renderizados nascem depois da instalacao, entao o desinstalador
; nao os conhece -- sem isto ficariam para tras (chegam a alguns GB)
Type: filesandordirs; Name: "{app}\cache_tiles"
