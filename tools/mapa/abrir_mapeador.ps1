<#
.SYNOPSIS
    Gera o atlas do mapa e abre o mapeador de hunts no navegador.

.DESCRIPTION
    O mapeador precisa de duas coisas: os PNGs do atlas (um por no de area do
    OTBM) e o dados.js com monstros e catalogo. Este script cuida das duas e
    abre a pagina.

    Roda so uma vez por versao do mapa. Depois disso e' so abrir o
    mapeador.html direto -- o atlas fica em tools/mapa/atlas/.

    O mapa e' baixado no boot do servidor e nao esta no repositorio. Se voce
    nao tiver uma copia local, passe -BaixarDoVps para trazer do servidor.

.EXAMPLE
    .\tools\mapa\abrir_mapeador.ps1
    .\tools\mapa\abrir_mapeador.ps1 -BaixarDoVps
    .\tools\mapa\abrir_mapeador.ps1 -Regerar
#>
[CmdletBinding()]
param(
    [string] $Mapa,
    [string] $Planilha,
    [switch] $BaixarDoVps,
    [string] $Vps = "root@209.126.8.53",
    [switch] $Regerar
)

$ErrorActionPreference = 'Stop'
function Passo($t) { Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t)    { Write-Host "    ok: $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "    ATENCAO: $t" -ForegroundColor Yellow }

$aqui  = $PSScriptRoot
$raiz  = Split-Path -Parent (Split-Path -Parent $aqui)
$atlas = Join-Path $aqui 'atlas'
$pagina = Join-Path $aqui 'mapeador.html'

# --- python ------------------------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { throw "python nao encontrado no PATH." }

Passo "Conferindo dependencias do python"
& $py.Source -c "import PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Aviso "Pillow ausente - instalando"
    & $py.Source -m pip install --quiet Pillow
}
& $py.Source -c "import openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Aviso "openpyxl ausente - instalando (so para ler a planilha)"
    & $py.Source -m pip install --quiet openpyxl
}
Ok "dependencias prontas"

# --- mapa --------------------------------------------------------------------
if (-not $Mapa) {
    $candidatos = @(
        (Join-Path $raiz 'data-otservbr-global\world\otservbr.otbm'),
        (Join-Path $env:TEMP 'otservbr.otbm')
    )
    $Mapa = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if ((-not $Mapa -or -not (Test-Path $Mapa)) -and $BaixarDoVps) {
    $Mapa = Join-Path $env:TEMP 'otservbr.otbm'
    Passo "Baixando o mapa do VPS (176 MB, uma vez so)"
    & scp "${Vps}:/root/tibia/data-otservbr-global/world/otservbr.otbm" $Mapa
    if ($LASTEXITCODE -ne 0) { throw "scp falhou" }
    Ok "mapa em $Mapa"
}

if (-not $Mapa -or -not (Test-Path $Mapa)) {
    throw @"
Mapa nao encontrado. O otservbr.otbm e baixado no boot do servidor e nao fica
no repositorio. Rode com -BaixarDoVps, ou passe -Mapa <caminho>.
"@
}

# --- planilha (opcional) -----------------------------------------------------
if (-not $Planilha) {
    $Planilha = Get-ChildItem (Join-Path $env:USERPROFILE 'Downloads') `
        -Filter 'catalogo_hunts*.xlsx' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if ($Planilha) { Ok "planilha: $(Split-Path -Leaf $Planilha)" }
else { Aviso "planilha nao encontrada - o campo de nome da hunt fica vazio" }

# --- atlas -------------------------------------------------------------------
$dados = Join-Path $atlas 'dados.js'
if ((Test-Path $dados) -and -not $Regerar) {
    $n = (Get-ChildItem (Join-Path $atlas 'tiles') -Recurse -Filter *.png -ErrorAction SilentlyContinue).Count
    Ok "atlas ja existe ($n PNGs). Use -Regerar para refazer."
} else {
    Passo "Gerando o atlas (alguns minutos: ~1200 areas de 256x256)"
    $args = @((Join-Path $aqui 'gerar_atlas.py'), $Mapa, '--saida', $atlas)
    if ($Planilha) { $args += @('--planilha', $Planilha) }
    & $py.Source @args
    if ($LASTEXITCODE -ne 0) { throw "gerar_atlas.py falhou" }
    Ok "atlas gerado"
}

# --- abrir -------------------------------------------------------------------
Passo "Abrindo o mapeador"
Start-Process $pagina
Write-Host ""
Write-Host "Mapeador aberto." -ForegroundColor Green
Write-Host "  Amarelo  obelisco, uma vez por hunt"
Write-Host "  Azul     onde a hunt comeca, uma vez por hunt"
Write-Host "  Vermelho pincel: segure e arraste para pintar os limites"
Write-Host ""
Write-Host "Digite o ID da hunt (o nome vem da planilha), marque, e clique"
Write-Host "em 'Baixar JSON'. O JSON sai com obelisco, inicio, limites por"
Write-Host "andar e os monstros que caem dentro deles."
