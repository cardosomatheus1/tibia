<#
.SYNOPSIS
    Monta a pasta que o instalador do mapeador empacota.

.DESCRIPTION
    O mapeador e' Python, e quem vai usar (voce e seus amigos) nao deveria ter
    de instalar Python nem pacote nenhum. Entao o pacote leva o proprio
    interpretador: o "embeddable" oficial da python.org, que e' uma pasta
    solta de ~11 MB, sem instalacao, sem PATH e sem mexer no que a maquina ja
    tem. As bibliotecas (Pillow para desenhar, openpyxl para ler a planilha)
    entram ao lado, e o ._pth aponta para elas.

    O mapa NAO entra no pacote: sao 176 MB e ele vem de uma release publica
    do opentibiabr/canary, a mesma que o servidor baixa no boot. O abrir.ps1
    busca uma copia local e, se nao achar, baixa uma vez.

    Os sprites tambem nao entram: sao do client que a pessoa ja instalou, e
    redistribuir arte da CipSoft nao e' nossa. O abrir.ps1 procura a pasta
    assets do client instalado.

    Depois de rodar isto, compile tools\mapa\instalador_mapeador.iss.

.EXAMPLE
    .\tools\mapa\preparar_mapeador.ps1
    .\tools\mapa\preparar_mapeador.ps1 -Destino D:\pacote-mapeador
#>
[CmdletBinding()]
param(
    [string] $Destino = "C:\mapeador-hunts-pacote",
    [string] $VersaoPython = "3.11.9",
    [string] $Mapa,
    [string] $Assets,
    [string] $MapaUrl = "https://github.com/opentibiabr/canary/releases/download/v3.6.1/otservbr.otbm",
    [switch] $SemMapa,
    [switch] $SemAssets,
    [switch] $Limpar
)

$ErrorActionPreference = 'Stop'
function Passo($t) { Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t)    { Write-Host "    ok: $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "    ATENCAO: $t" -ForegroundColor Yellow }

$aqui = $PSScriptRoot
$raiz = Split-Path -Parent (Split-Path -Parent $aqui)

if ($Limpar -and (Test-Path $Destino)) {
    Remove-Item -Recurse -Force $Destino
    Ok "destino limpo"
}
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

# --- 1. interpretador embutido ----------------------------------------------
$pastaPy = Join-Path $Destino 'python'
if (-not (Test-Path (Join-Path $pastaPy 'python.exe'))) {
    Passo "Baixando o Python embeddable $VersaoPython"
    $zip = Join-Path $env:TEMP "python-embed-$VersaoPython.zip"
    if (-not (Test-Path $zip)) {
        $url = "https://www.python.org/ftp/python/$VersaoPython/python-$VersaoPython-embed-amd64.zip"
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    }
    New-Item -ItemType Directory -Force -Path $pastaPy | Out-Null
    Expand-Archive -Path $zip -DestinationPath $pastaPy -Force
    Ok "interpretador em $pastaPy"
} else {
    Ok "interpretador ja estava montado"
}

# O embeddable vem com o ._pth mandando NAO usar site-packages, o que e' o
# certo para embutir mas deixa qualquer biblioteca invisivel. Acrescentar as
# nossas duas pastas resolve sem ligar o site completo.
$pth = Get-ChildItem $pastaPy -Filter 'python*._pth' | Select-Object -First 1
if (-not $pth) { throw "._pth nao encontrado no embeddable" }
$linhas = @(Get-Content -LiteralPath $pth.FullName)
foreach ($extra in @('..\app', '..\pylibs')) {
    if ($linhas -notcontains $extra) { $linhas += $extra }
}
Set-Content -LiteralPath $pth.FullName -Value $linhas -Encoding ASCII
Ok "._pth aponta para app\ e pylibs\"

# --- 2. bibliotecas ----------------------------------------------------------
# Instaladas com o pip da maquina, mas COM --target e travadas na mesma versao
# e plataforma do embeddable -- senao um wheel de outra versao entraria e nao
# importaria na maquina do amigo.
$pylibs = Join-Path $Destino 'pylibs'
if (-not (Test-Path (Join-Path $pylibs 'PIL'))) {
    Passo "Baixando Pillow e openpyxl"
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $py) { throw "python nao encontrado no PATH (precisa so para montar o pacote)" }
    $curto = ($VersaoPython -split '\.')[0..1] -join '.'
    # O pip escreve avisos no stderr mesmo quando da tudo certo (a nota de
    # "nova versao disponivel"), e com ErrorActionPreference=Stop o PowerShell
    # trata isso como falha do comando. Quem decide aqui e' o codigo de saida.
    $antes = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $py.Source -m pip install --quiet --target $pylibs `
        --only-binary=:all: --python-version $curto --platform win_amd64 `
        --upgrade Pillow openpyxl
    $codigo = $LASTEXITCODE
    $ErrorActionPreference = $antes
    if ($codigo -ne 0) { throw "pip falhou (codigo $codigo)" }
    Ok "bibliotecas em $pylibs"
} else {
    Ok "bibliotecas ja estavam montadas"
}

# --- 3. codigo do mapeador ---------------------------------------------------
Passo "Copiando o mapeador"
$app = Join-Path $Destino 'app'
New-Item -ItemType Directory -Force -Path $app | Out-Null
# gerar_minimapa.py entrou na lista quando o servidor passou a precisar saber
# que tile da' para pisar (varinha). Sem ele o servidor nem inicia -- quebra no
# import, antes de qualquer tela. hunts_catalogo.json e' o id -> nome das 525
# hunts: a planilha fica na maquina de quem a montou, e sem essa copia o campo
# de id nao mostra nome nenhum para quem instala.
foreach ($f in @('servidor_mapeador.py', 'otbm.py', 'render.py', 'ver_item.py',
                 'monstros.py', 'gerar_minimapa.py', 'mapeador.html',
                 'hunts_catalogo.json')) {
    Copy-Item (Join-Path $aqui $f) $app -Force
}
Copy-Item (Join-Path $raiz 'tools\sprites\tibia_assets.py') $app -Force
Ok "9 arquivos"

# --- 4. dados do datapack ----------------------------------------------------
# Sao os dois arquivos que dizem ONDE cada monstro nasce e COM QUE cara: o xml
# de spawn e os .lua de onde sai o lookType. Juntos dao ~15 MB.
Passo "Copiando spawns e monstros do datapack"
$dados = Join-Path $Destino 'dados'
New-Item -ItemType Directory -Force -Path $dados | Out-Null
Copy-Item (Join-Path $raiz 'data-otservbr-global\world\otservbr-monster.xml') `
    $dados -Force
$destMon = Join-Path $dados 'monster'
if (Test-Path $destMon) { Remove-Item -Recurse -Force $destMon }
Copy-Item (Join-Path $raiz 'data-otservbr-global\monster') $destMon -Recurse -Force
$nLua = (Get-ChildItem $destMon -Recurse -Filter *.lua).Count
Ok "otservbr-monster.xml + $nLua arquivos de monstro"

# --- 5. launcher e icone -----------------------------------------------------
Passo "Gerando o launcher"
Copy-Item (Join-Path $aqui 'abrir_mapeador_instalado.ps1') `
    (Join-Path $Destino 'abrir.ps1') -Force

$ico = Join-Path $Destino 'mapeador.ico'
if (-not (Test-Path $ico)) {
    $origem = Join-Path $raiz 'tools\installer\tibia.ico'
    if (Test-Path $origem) { Copy-Item $origem $ico -Force; Ok "icone reaproveitado do client" }
    else { Aviso "sem icone; o instalador usara o padrao" }
}

# --- 6. mapa -----------------------------------------------------------------
# Vai DENTRO do pacote: instalar tem de bastar. O arquivo tem 185 MB mas cai
# para ~30 MB no instalador, porque OTBM e' muito repetitivo.
if (-not $SemMapa) {
    $destMapa = Join-Path $dados 'otservbr.otbm'
    if (-not $Mapa) {
        $cand = @((Join-Path $raiz 'data-otservbr-global\world\otservbr.otbm'),
                  (Join-Path $env:TEMP 'otservbr.otbm'))
        $achado = Get-ChildItem $env:TEMP -Recurse -Filter 'otservbr.otbm' `
            -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($achado) { $cand += $achado.FullName }
        $Mapa = $cand | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $Mapa -or -not (Test-Path $Mapa)) {
        Passo "Baixando o mapa (185 MB, uma vez)"
        $Mapa = Join-Path $env:TEMP 'otservbr.otbm'
        $antesP = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $MapaUrl -OutFile $Mapa -UseBasicParsing
        $ProgressPreference = $antesP
    }
    Passo "Copiando o mapa"
    Copy-Item $Mapa $destMapa -Force
    Ok ("mapa: {0} MB" -f [math]::Round((Get-Item $destMapa).Length / 1MB))
}

# --- 7. sprites do client ----------------------------------------------------
# Tambem vao juntos, senao "instalou, abriu" nao seria verdade para quem ainda
# nao tem o client. Sao 135 MB e quase nao comprimem: as folhas ja sao LZMA.
if (-not $SemAssets) {
    if (-not $Assets) {
        foreach ($b in @("$env:USERPROFILE\Desktop", "$env:USERPROFILE\Downloads",
                         "$env:LOCALAPPDATA\Tibia rhapsodyyy",
                         "$env:LOCALAPPDATA\Tibia\packages\Tibia")) {
            $c = Get-ChildItem $b -Recurse -Filter 'catalog-content.json' `
                -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($c) { $Assets = $c.DirectoryName; break }
        }
    }
    if (-not $Assets -or -not (Test-Path (Join-Path $Assets 'catalog-content.json'))) {
        throw "pasta de assets do client nao encontrada; passe -Assets <caminho> ou -SemAssets"
    }
    Passo "Copiando os sprites do client"
    $destAssets = Join-Path $Destino 'assets'
    if (Test-Path $destAssets) { Remove-Item -Recurse -Force $destAssets }
    Copy-Item $Assets $destAssets -Recurse -Force
    Ok ("sprites: {0} arquivos, {1} MB" -f `
        (Get-ChildItem $destAssets -File).Count,
        [math]::Round(((Get-ChildItem $destAssets -Recurse -File |
            Measure-Object Length -Sum).Sum) / 1MB))
}

# --- 8. tirar o que nasce em uso --------------------------------------------
# O Excludes do Inno casa nome de arquivo, nao caminho: "cache_tiles\*" nao
# pegou e 10 tiles renderizados foram parar dentro do instalador. Apagar aqui
# e' o que de fato garante que o pacote so leve o que deve.
Passo "Tirando o que e' gerado em uso"
foreach ($lixo in @('cache_tiles', 'dados\otservbr.otbm.parcial')) {
    $p = Join-Path $Destino $lixo
    if (Test-Path $p) { Remove-Item -Recurse -Force $p; Ok "removido: $lixo" }
}

# --- fim ---------------------------------------------------------------------
$mb = [math]::Round(((Get-ChildItem $Destino -Recurse -File |
    Measure-Object Length -Sum).Sum) / 1MB)
Write-Host ""
Write-Host "Pacote montado em $Destino ($mb MB)" -ForegroundColor Green
Write-Host "Agora compile: tools\mapa\instalador_mapeador.iss"
