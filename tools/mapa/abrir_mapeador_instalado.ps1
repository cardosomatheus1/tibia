<#
    Launcher do Mapeador de Hunts instalado.

    Roda dentro da pasta do programa e nao depende de nada estar no PATH: o
    interpretador vem junto, em python\. O que ele precisa achar sao duas
    coisas que NAO viajam no instalador:

      o mapa      176 MB, de uma release publica do opentibiabr/canary. Fica
                  em dados\ na primeira vez e nunca mais e' baixado.
      os sprites  a pasta assets do client de Tibia ja instalado na maquina.
                  Arte da CipSoft nao se redistribui.

    Feche esta janela para encerrar o mapeador.
#>
[CmdletBinding()]
param(
    [string] $Assets,
    [string] $Mapa,
    [string] $Planilha,
    [int]    $Porta = 8100,
    [string] $MapaUrl = "https://github.com/opentibiabr/canary/releases/download/v3.6.1/otservbr.otbm",
    [switch] $LimparCache
)

$ErrorActionPreference = 'Stop'
$aqui = $PSScriptRoot
$host.UI.RawUI.WindowTitle = "Mapeador de Hunts"

function Passo($t) { Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t)    { Write-Host "    ok: $t" -ForegroundColor Green }
function Erro($t)  { Write-Host "    ERRO: $t" -ForegroundColor Red }

$py     = Join-Path $aqui 'python\python.exe'
$script = Join-Path $aqui 'app\servidor_mapeador.py'
$dados  = Join-Path $aqui 'dados'
$cache  = Join-Path $aqui 'cache_tiles'

if (-not (Test-Path $py))     { Erro "instalacao incompleta: falta python\python.exe"; pause; exit 1 }
if (-not (Test-Path $script)) { Erro "instalacao incompleta: falta app\servidor_mapeador.py"; pause; exit 1 }

# --- sprites do client -------------------------------------------------------
# Vem no pacote. A busca pela maquina fica so como rede de seguranca, para
# quem montou o pacote com -SemAssets.
if (-not $Assets) {
    $doPacote = Join-Path $aqui 'assets'
    if (Test-Path (Join-Path $doPacote 'catalog-content.json')) {
        $Assets = $doPacote
    } else {
        $procura = @(
            "$env:LOCALAPPDATA\Tibia rhapsodyyy\assets",
            "$env:LOCALAPPDATA\Tibia\packages\Tibia\assets",
            "$env:USERPROFILE\Desktop",
            "$env:USERPROFILE\Downloads"
        )
        foreach ($p in $procura) {
            if (Test-Path (Join-Path $p 'catalog-content.json')) { $Assets = $p; break }
            $achado = Get-ChildItem $p -Recurse -Filter 'catalog-content.json' `
                -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($achado) { $Assets = $achado.DirectoryName; break }
        }
    }
}
if (-not $Assets -or -not (Test-Path (Join-Path $Assets 'catalog-content.json'))) {
    Erro @"
Nao achei os sprites do jogo.

Sao a pasta 'assets' do client de Tibia (a que tem catalog-content.json,
appearances-*.dat e os sprites-*.bmp.lzma). Instale o client rhapsodyyy, ou
abra este atalho passando o caminho:

    abrir.ps1 -Assets "C:\caminho\do\client\assets"
"@
    pause; exit 1
}
Ok "sprites: $Assets"

# --- mapa --------------------------------------------------------------------
if (-not $Mapa) {
    $Mapa = Join-Path $dados 'otservbr.otbm'
}
if (-not (Test-Path $Mapa)) {
    Passo "Baixando o mapa (176 MB, so na primeira vez)"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Mapa) | Out-Null
    $tmp = "$Mapa.parcial"
    try {
        # ProgressPreference default deixa o Invoke-WebRequest lentissimo em
        # arquivo grande: ele redesenha a barra a cada bloco.
        $antes = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $MapaUrl -OutFile $tmp -UseBasicParsing
        $ProgressPreference = $antes
        Move-Item $tmp $Mapa -Force
    } catch {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        Erro "download falhou: $($_.Exception.Message)"
        Write-Host "Baixe manualmente de:" -ForegroundColor Yellow
        Write-Host "  $MapaUrl"
        Write-Host "e salve como:" -ForegroundColor Yellow
        Write-Host "  $Mapa"
        pause; exit 1
    }
}
Ok ("mapa: {0} ({1} MB)" -f $Mapa, [math]::Round((Get-Item $Mapa).Length / 1MB))

# --- planilha (opcional) -----------------------------------------------------
if (-not $Planilha) {
    $Planilha = Get-ChildItem "$env:USERPROFILE\Downloads", $dados `
        -Filter 'catalogo_hunts*.xlsx' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if ($Planilha) { Ok "planilha: $(Split-Path -Leaf $Planilha)" }

# --- cache -------------------------------------------------------------------
if ($LimparCache -and (Test-Path $cache)) {
    Remove-Item -Recurse -Force $cache
    Ok "cache apagado"
}

# --- subir -------------------------------------------------------------------
Write-Host ""
Write-Host "Mapeador em http://127.0.0.1:$Porta/" -ForegroundColor Green
Write-Host "  Mover     arrasta o mapa; Esc ou botao direito solta a ferramenta"
Write-Host "  Amarelo   obelisco, uma vez por hunt"
Write-Host "  Azul      onde a hunt comeca, uma vez por hunt"
Write-Host "  Vermelho  pincel: segure e arraste para pintar os limites"
Write-Host ""
Write-Host "Marque, clique em 'Baixar JSON' e mande o arquivo." -ForegroundColor Gray
Write-Host "FECHE ESTA JANELA para encerrar o mapeador." -ForegroundColor DarkGray
Write-Host ""

# -u para a saida do servidor aparecer na hora: sem isso o Python bufferiza e
# a janela fica muda ate encher o buffer, dando impressao de travado
$argumentos = @('-u', $script, $Mapa,
                '--assets',   $Assets,
                '--spawns',   (Join-Path $dados 'otservbr-monster.xml'),
                '--monstros', (Join-Path $dados 'monster'),
                '--cache',    $cache,
                '--porta',    $Porta)
if ($Planilha) { $argumentos += @('--planilha', $Planilha) }

& $py @argumentos
