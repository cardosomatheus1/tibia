<#
.SYNOPSIS
    Abre o mapeador de hunts: o mapa com os sprites do jogo, os monstros nos
    spawns, e as ferramentas de marcar obelisco, inicio e limites.

.DESCRIPTION
    Sobe um servidor local que desenha o mapa sob demanda e abre a pagina no
    navegador. Nao ha etapa de geracao: o primeiro bloco de uma regiao leva
    cerca de um segundo, os vizinhos ja vem prontos, e tudo fica em cache no
    disco -- reabrir na mesma regiao e' instantaneo.

    O mapa e' baixado no boot do servidor e nao esta no repositorio. Se voce
    nao tiver uma copia local, passe -BaixarDoVps para trazer do servidor.

    Feche com Ctrl+C nesta janela.

.EXAMPLE
    .\tools\mapa\abrir_mapeador.ps1
    .\tools\mapa\abrir_mapeador.ps1 -BaixarDoVps
    .\tools\mapa\abrir_mapeador.ps1 -LimparCache
#>
[CmdletBinding()]
param(
    [string] $Mapa,
    [string] $Assets,
    [string] $Planilha,
    [int]    $Porta = 8100,
    [switch] $BaixarDoVps,
    [string] $Vps = "root@209.126.8.53",
    [switch] $LimparCache
)

$ErrorActionPreference = 'Stop'
function Passo($t) { Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t)    { Write-Host "    ok: $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "    ATENCAO: $t" -ForegroundColor Yellow }

$aqui = $PSScriptRoot
$raiz = Split-Path -Parent (Split-Path -Parent $aqui)

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
        (Join-Path $env:TEMP 'otservbr.otbm'),
        (Join-Path $env:USERPROFILE 'Downloads\otservbr.otbm')
    )
    $achado = Get-ChildItem $env:TEMP -Recurse -Filter 'otservbr.otbm' `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($achado) { $candidatos += $achado.FullName }
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
Ok "mapa: $Mapa"

# --- assets do client --------------------------------------------------------
# Sao os sprites de verdade: appearances.dat mais as folhas .bmp.lzma. Sem
# eles o mapeador nao tem o que desenhar.
if (-not $Assets) {
    $procura = @("$env:USERPROFILE\Desktop", "$env:USERPROFILE\Downloads",
                 "$env:LOCALAPPDATA\Tibia\packages\Tibia")
    foreach ($base in $procura) {
        $c = Get-ChildItem $base -Recurse -Filter 'catalog-content.json' `
            -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($c) { $Assets = $c.DirectoryName; break }
    }
}
if (-not $Assets -or -not (Test-Path (Join-Path $Assets 'catalog-content.json'))) {
    throw @"
Pasta de assets do client nao encontrada. E' a pasta com catalog-content.json,
appearances-*.dat e as folhas sprites-*.bmp.lzma -- normalmente
<pasta do client>\assets. Passe -Assets <caminho>.
"@
}
Ok "assets: $Assets"

# --- planilha (opcional) -----------------------------------------------------
if (-not $Planilha) {
    $Planilha = Get-ChildItem (Join-Path $env:USERPROFILE 'Downloads') `
        -Filter 'catalogo_hunts*.xlsx' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if ($Planilha) { Ok "planilha: $(Split-Path -Leaf $Planilha)" }
else { Aviso "planilha nao encontrada - o nome da hunt nao preenche sozinho" }

# --- cache -------------------------------------------------------------------
$cache = Join-Path $aqui 'cache_tiles'
if ($LimparCache -and (Test-Path $cache)) {
    Remove-Item -Recurse -Force $cache
    Ok "cache apagado"
} elseif (Test-Path $cache) {
    $mb = [math]::Round(((Get-ChildItem $cache -Recurse -File |
        Measure-Object Length -Sum).Sum / 1MB))
    Ok "cache de tiles: $mb MB (use -LimparCache para refazer)"
}

# --- subir -------------------------------------------------------------------
Write-Host ""
Write-Host "Mapeador em http://127.0.0.1:$Porta/" -ForegroundColor Green
Write-Host "  Mover     arrasta o mapa; Esc ou botao direito solta a ferramenta"
Write-Host "  Amarelo   obelisco, uma vez por hunt"
Write-Host "  Azul      onde a hunt comeca, uma vez por hunt"
Write-Host "  Vermelho  pincel: segure e arraste para pintar os limites"
Write-Host ""
Write-Host "Digite o ID da hunt (o nome vem da planilha), marque, e clique em"
Write-Host "'Baixar JSON'. O JSON sai com obelisco, inicio, limites por andar e"
Write-Host "os monstros que caem dentro deles."
Write-Host ""
Write-Host "Ctrl+C para encerrar." -ForegroundColor DarkGray
Write-Host ""

$argumentos = @((Join-Path $aqui 'servidor_mapeador.py'), $Mapa,
                '--assets', $Assets, '--porta', $Porta, '--cache', $cache)
if ($Planilha) { $argumentos += @('--planilha', $Planilha) }
& $py.Source @argumentos
