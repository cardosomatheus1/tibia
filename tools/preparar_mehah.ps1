<#
.SYNOPSIS
    Monta o client otclient (mehah) customizado deste servidor: AutoCaster,
    bandeirinha de idioma, sprites proprias e o servidor ja configurado.

.DESCRIPTION
    O artefato de CI do mehah contem SO o executavel (otclient.exe, otclient.ilk
    e otclient.pdb) -- nem modules/, nem data/, nem assets. E o repositorio do
    mehah nao distribui a arte da CipSoft. Por isso o client final e' a soma de
    tres origens:

      1. otclient.exe            <- artefato do GitHub Actions do mehah
      2. modules/ data/ mods/    <- codigo-fonte do mehah (git clone)
      3. assets/ e sounds/       <- client oficial 15.25 (dudantas)

    Em cima disso entram os modulos deste repositorio e as sprites proprias.

.PARAMETER ArtefatoZip
    windows-cmake-release.zip, baixado de
    https://github.com/cardosomatheus1/otclient/actions (secao Artifacts do run).

    E' o NOSSO FORK, nao o mehah. O fork existe por causa de uma correcao que
    nao da' para fazer de fora: o client cortava a aware range enviada pelo
    servidor -- min(awareRange, drawDimension/2 - 1) com drawDimension 18x14
    limitava a 8 e 6, os valores originais do Canary --, e a borda entre o que
    ele desenha e o que considera valido saia sem dado, mostrando a cor de
    limpeza do framebuffer. E' o quadrado azul que aparecia correndo rapido e a
    cada hit recebido. Ver docs/superpowers/specs/2026-08-06-quadrado-azul-diagnostico.md

    Pegar o artefato do mehah faz a correcao sumir sem aviso nenhum.

.PARAMETER ClientOficialZip
    tibia-client-15.25.*.zip, de
    https://github.com/dudantas/tibia-client/releases/latest
    Dele saem os assets da 15.25 e os sons.

.PARAMETER Destino
    Pasta do client montado. Padrao: C:\otclient-mehah
    ATENCAO: a pasta e' recriada do zero.

.PARAMETER LoginUrl
    Endereco do login-server. Uma unica entrada em Servers_init faz o client
    esconder os campos de host, porta e versao: o jogador so digita conta e senha.

.EXAMPLE
    .\tools\preparar_mehah.ps1 `
        -ArtefatoZip "$env:USERPROFILE\Downloads\windows-cmake-release.zip" `
        -ClientOficialZip "$env:USERPROFILE\Downloads\tibia-client-15.25.0a00a0.zip"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $ArtefatoZip,
    [Parameter(Mandatory = $true)] [string] $ClientOficialZip,
    [string] $Destino = "C:\otclient-mehah",
    [string] $LoginUrl = "http://rhapsodyyy.duckdns.org:8088/login",
    [int]    $Porta = 8088,
    [int]    $Protocolo = 1525,
    [string] $NomeApp = "Tibia rhapsodyyy",
    # O fork, nao o upstream: modules/ e data/ precisam vir do mesmo lugar que
    # o binario, senao o Lua nao casa com o C++ patchado.
    [string] $FonteMehah = "https://github.com/cardosomatheus1/otclient.git",
    [string] $CommitMehah,
    [switch] $PularSprites
)

$ErrorActionPreference = 'Stop'

function Write-Passo($t) { Write-Host "==> $t" -ForegroundColor Cyan }
function Write-Ok($t)    { Write-Host "    ok: $t" -ForegroundColor Green }
function Write-Aviso($t) { Write-Host "    ATENCAO: $t" -ForegroundColor Yellow }

$repoRaiz = Split-Path -Parent $PSScriptRoot
$origemModulos = Join-Path $repoRaiz 'client-modules'
if (-not (Test-Path $origemModulos)) {
    throw "Nao achei client-modules/ em '$repoRaiz'. Rode como tools\preparar_mehah.ps1, de dentro do repositorio."
}
foreach ($z in @($ArtefatoZip, $ClientOficialZip)) {
    if (-not (Test-Path $z)) { throw "Zip nao encontrado: $z" }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git nao encontrado no PATH -- e' necessario para baixar o codigo do mehah."
}

# --- 1. codigo-fonte do mehah ------------------------------------------------
# Vem antes do exe porque e' o clone que cria a arvore de pastas.
#
# O COMMIT IMPORTA. O otclient.exe vem de um artefato ja compilado do GitHub
# Actions, mas modules/ e data/ vinham do master do momento do empacotamento --
# sem nada amarrando os dois. O pacote entregue tinha binario de 30/jul e Lua
# de 4/ago: cinco dias de diferenca num projeto em desenvolvimento ativo. A
# interface entre o C++ e o Lua muda nesse intervalo, e o sintoma disso e'
# silencioso: nao ha erro no log, so coisa que deixa de ser desenhada.
#
# O SHA esta na pagina do run do Actions de onde o zip foi baixado -- do NOSSO
# fork (cardosomatheus1/otclient), nao do mehah.
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("mehah-src-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
if ($CommitMehah) {
    Write-Passo "Baixando o codigo-fonte do mehah no commit $CommitMehah"
    git init --quiet $temp
    git -C $temp remote add origin $FonteMehah
    git -C $temp fetch --depth 1 --quiet origin $CommitMehah
    if ($LASTEXITCODE -ne 0) { throw "fetch do commit $CommitMehah falhou" }
    git -C $temp checkout --quiet FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "checkout do commit $CommitMehah falhou" }
    Write-Ok "codigo no commit $CommitMehah"
} else {
    Write-Passo "Baixando o codigo-fonte do mehah (master, shallow clone)"
    git clone --depth 1 --quiet $FonteMehah $temp
    if ($LASTEXITCODE -ne 0) { throw "git clone falhou" }
    Write-Aviso @"
Sem -CommitMehah: o Lua vem do master de agora e o exe vem do artefato, que
pode ser de outro commit. Pegue o SHA na pagina do run do Actions de onde
voce baixou o zip e passe em -CommitMehah para os dois baterem.
"@
}

if (Test-Path $Destino) {
    Write-Aviso "$Destino ja existe - sera recriada"
    Remove-Item $Destino -Recurse -Force
}
New-Item -ItemType Directory -Path $Destino -Force | Out-Null

Write-Passo "Copiando a arvore do client (modules, data, mods, init.lua)"
foreach ($item in @('data', 'modules', 'mods', 'init.lua', 'otclientrc.lua', 'config.ini', 'cacert.pem')) {
    $de = Join-Path $temp $item
    if (Test-Path $de) { Copy-Item $de -Destination $Destino -Recurse -Force }
    else { Write-Aviso "'$item' nao existe no fonte do mehah - pulando" }
}
Write-Ok "arvore copiada"

# --- 2. executavel -----------------------------------------------------------
Write-Passo "Extraindo otclient.exe do artefato"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $ArtefatoZip))
try {
    $exe = $zip.Entries | Where-Object { $_.Name -eq 'otclient.exe' } | Select-Object -First 1
    if (-not $exe) { throw "otclient.exe nao esta no artefato -- confira se o zip e' o windows-cmake-release." }
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
        $exe, (Join-Path $Destino 'otclient.exe'), $true)
} finally { $zip.Dispose() }
Write-Ok ("otclient.exe ({0:N1} MB)" -f ((Get-Item (Join-Path $Destino 'otclient.exe')).Length / 1MB))

# O artefato do mehah e' compilado como aplicativo de CONSOLE, entao o Windows
# abre uma janela preta de terminal junto do jogo -- assusta o jogador. Troca o
# subsystem no cabecalho do PE de console (3) para GUI/janela (2), o mesmo que
# 'editbin /subsystem:windows' faria. O jogo passa a abrir so como janela.
Write-Passo "Removendo a janela de console do otclient.exe (subsystem GUI)"
$exePath = Join-Path $Destino 'otclient.exe'
$b = [System.IO.File]::ReadAllBytes($exePath)
$peOff = [BitConverter]::ToInt32($b, 0x3C)
if ($b[$peOff] -eq 0x50 -and $b[$peOff + 1] -eq 0x45) {   # "PE"
    $subOff = $peOff + 24 + 68
    if ($b[$subOff] -eq 3) {
        $b[$subOff] = 2
        [System.IO.File]::WriteAllBytes($exePath, $b)
        Write-Ok "subsystem -> GUI (sem console preto)"
    } else {
        Write-Ok "subsystem ja era $($b[$subOff]) (nao mexi)"
    }
} else {
    Write-Aviso "otclient.exe nao parece um PE valido - nao mexi no subsystem"
}

# --- 3. assets e sons do client oficial --------------------------------------
# O mehah le assets de data/things/<versao>/ (ver data/things/README.md dele).
# O assets.json.sha256 nao e' opcional: sem ele o modulo client_assets conclui
# que os arquivos faltam e abre a tela de "Downloading Assets", que baixaria os
# assets originais por cima das sprites proprias.
$pastaAssets = Join-Path $Destino "data\things\$Protocolo"
$pastaSons   = Join-Path $Destino "data\sounds\$Protocolo"
New-Item -ItemType Directory -Path $pastaAssets, $pastaSons -Force | Out-Null

Write-Passo "Extraindo assets e sons da 15.25 (algumas milhares de entradas)"
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $ClientOficialZip))
try {
    $mapa = @{ 'assets/' = $pastaAssets; 'sounds/' = $pastaSons }
    $contagem = @{ 'assets/' = 0; 'sounds/' = 0 }

    foreach ($entrada in $zip.Entries) {
        if ([string]::IsNullOrEmpty($entrada.Name)) { continue }   # diretorio
        foreach ($prefixo in $mapa.Keys) {
            if (-not $entrada.FullName.StartsWith($prefixo)) { continue }
            $rel = $entrada.FullName.Substring($prefixo.Length).Replace('/', '\')
            $saida = Join-Path $mapa[$prefixo] $rel
            $pai = Split-Path -Parent $saida
            if (-not (Test-Path $pai)) { New-Item -ItemType Directory -Path $pai -Force | Out-Null }
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entrada, $saida, $true)
            $contagem[$prefixo]++
            break
        }
    }

    # assets.json e assets.json.sha256 ficam na RAIZ do zip oficial, nao em assets/
    foreach ($nome in @('assets.json', 'assets.json.sha256')) {
        $e = $zip.Entries | Where-Object { $_.FullName -eq $nome } | Select-Object -First 1
        if ($e) {
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, (Join-Path $pastaAssets $nome), $true)
        } else {
            Write-Aviso "$nome nao encontrado na raiz do zip oficial"
        }
    }
} finally { $zip.Dispose() }

Write-Ok "$($contagem['assets/']) arquivos de asset, $($contagem['sounds/']) de som"
if (-not (Test-Path (Join-Path $pastaAssets 'catalog-content.json'))) {
    throw "catalog-content.json nao chegou em $pastaAssets -- o zip oficial esta correto?"
}

# --- 4. modulos deste repositorio -------------------------------------------
$modulos = @('autocaster', 'idioma')
foreach ($m in $modulos) {
    $de = Join-Path $origemModulos $m
    if (-not (Test-Path $de)) { Write-Aviso "modulo '$m' nao existe em client-modules - pulando"; continue }
    Write-Passo "Instalando modulo '$m'"
    Copy-Item $de -Destination (Join-Path $Destino 'modules') -Recurse -Force
    Write-Ok "$m instalado"
}

# --- 4b. minimapa da hunt instanciada ----------------------------------------
# Dentro de uma instancia o jogador esta em x >= 36864 e o minimapa fica preto:
# ele e client-side e indexado por coordenada absoluta. A traducao tem de valer
# nos DOIS sentidos -- exibicao (camera e cruz) e clique (distancia e autoWalk).
# So o primeiro deixa o mapa bonito e o clique quebrado, com "out of range".
#
# E patch em arquivos da arvore do mehah, entao PRECISA rodar a cada rebuild,
# senao se perde.
Write-Passo "Patch do minimapa para hunt instanciada"
$patcher = Join-Path $repoRaiz 'tools\patch_client_minimapa.py'
if (Test-Path $patcher) {
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue) }
    if ($py) {
        & $py.Source $patcher $Destino
        if ($LASTEXITCODE -eq 0) { Write-Ok "minimapa patchado" }
        else { Write-Aviso "patch do minimapa falhou (codigo $LASTEXITCODE)" }
    } else {
        Write-Aviso "python nao encontrado - minimapa NAO patchado"
    }
} else {
    Write-Aviso "tools/patch_client_minimapa.py ausente - minimapa NAO patchado"
}

# --- 5. limitVisibleDimension ------------------------------------------------
# O mehah permite zoom-out ate 513 tiles de altura (uimap.cpp: m_maxZoomOut),
# mas o protocolo so entrega uma janela de 18x14 tiles em volta do jogador.
# Quando a viewport passa desse alcance, o MapView faz:
#
#     if (m_limitVisibleDimension) return;   // recusa
#     m_drawViewportEdge = true;             // aceita e desenha a borda vazia
#
# O padrao do C++ e' seguro (m_limitVisibleDimension = true), mas o Lua do
# mehah sobrescreve com false em data_options.lua. Resultado: rolar a roda do
# mouse sobre o mapa afasta a camera para fora dos dados e aparece uma faixa
# sem mapa na borda -- o client oficial nao faz isso porque nao tem zoom-out.
Write-Passo "Ativando limitVisibleDimension (evita desenhar mapa que o servidor nao enviou)"
$opcoes = Join-Path $Destino 'modules\client_options\data_options.lua'
if (Test-Path $opcoes) {
    $txt = Get-Content $opcoes -Raw
    $novo = [regex]::Replace($txt,
        '(limitVisibleDimension\s+=\s*\{\s*\r?\n\s*value\s*=\s*)false',
        '${1}true')
    if ($novo -ne $txt) {
        Set-Content -Path $opcoes -Value $novo -Encoding UTF8 -NoNewline
        Write-Ok "limitVisibleDimension = true"
    } else {
        Write-Aviso "nao achei 'limitVisibleDimension = false' - confira data_options.lua"
    }
} else {
    Write-Aviso "data_options.lua nao encontrado - pulando"
}

# --- 5b. smartWalk -----------------------------------------------------------
# Andar na diagonal segurando duas direcoes (W+D, seta cima + seta direita).
# O mehah tem a opcao, mas entrega desligada -- e quem vem do client oficial,
# onde a diagonal e' o padrao, acha que o personagem "travou". Ligar aqui evita
# que cada jogador tenha de descobrir sozinho em Options > Controls.
#
# A forma no arquivo e' plana ("smartWalk = false,"), diferente do
# limitVisibleDimension acima, que e' uma tabela com 'value ='. Por isso o
# regex e' outro -- reaproveitar o de cima nao pegaria nada.
Write-Passo "Ativando smartWalk (andar na diagonal com duas teclas)"
if (Test-Path $opcoes) {
    $txt = Get-Content $opcoes -Raw
    $novo = [regex]::Replace($txt, '(smartWalk\s*=\s*)false', '${1}true')
    if ($novo -ne $txt) {
        Set-Content -Path $opcoes -Value $novo -Encoding UTF8 -NoNewline
        Write-Ok "smartWalk = true"
    } else {
        Write-Aviso "nao achei 'smartWalk = false' - confira data_options.lua"
    }
} else {
    Write-Aviso "data_options.lua nao encontrado - pulando smartWalk"
}

# No modo de visao cheio (setupViewMode 2), o mehah desliga o limite de range
# para GM -- "limitedZoom and not isGM()". Como os personagens deste servidor
# sao GM, a viewport estica pela largura da janela widescreen, passa dos 18
# tiles que o servidor manda e desenha faixa azul nas laterais. Forcando o
# limite, a janela enche por ZOOM (tiles maiores) em vez de por mais tiles.
Write-Passo "Corrigindo a faixa azul no modo de visao cheio (limitVisibleRange)"
$interface = Join-Path $Destino 'modules\game_interface\gameinterface.lua'
if (Test-Path $interface) {
    $txt = Get-Content $interface -Raw
    $alvo = "local limit = limitedZoom and not g_game.isGM()`n        gameMapPanel:setLimitVisibleRange(limit)"
    if ($txt.Contains($alvo)) {
        $txt = $txt.Replace($alvo, "gameMapPanel:setLimitVisibleRange(true)")
        Set-Content -Path $interface -Value $txt -Encoding UTF8 -NoNewline
        Write-Ok "modo cheio agora limita o range (sem faixa azul)"
    } else {
        Write-Aviso "trecho de limitVisibleRange nao encontrado - confira gameinterface.lua"
    }
} else {
    Write-Aviso "gameinterface.lua nao encontrado - pulando"
}

# O mehah traz um bot nativo (mods/game_bot) que abre uma janela "Bot/cavebot"
# sozinho. Este servidor usa o AutoCaster proprio, entao o bot nativo e'
# redundante e so confunde. autoload: false impede ele de carregar -- e' um
# arquivo modificado (nao removido), entao o updater consegue distribuir a
# mudanca para quem ja instalou.
Write-Passo "Desligando o bot nativo do mehah (game_bot)"
$botOtmod = Join-Path $Destino 'mods\game_bot\bot.otmod'
if (Test-Path $botOtmod) {
    $txt = Get-Content $botOtmod -Raw
    if ($txt -notmatch 'autoload:\s*false') {
        $txt = $txt -replace '(\r?\n)(\s*description:)', "`n  autoload: false`$1`$2"
        Set-Content -Path $botOtmod -Value $txt -Encoding UTF8 -NoNewline
        Write-Ok "game_bot desligado (autoload: false)"
    } else {
        Write-Ok "game_bot ja estava desligado"
    }
} else {
    Write-Aviso "mods\game_bot\bot.otmod nao encontrado - pulando"
}

# --- 6. init.lua: servidor, nome e downloader --------------------------------
Write-Passo "Configurando init.lua"
$initPath = Join-Path $Destino 'init.lua'
$init = Get-Content $initPath -Raw

# clientAssets = false: este client ja vem com os assets embutidos. Se ficar
# ligado, ele baixa os originais do dudantas e apaga as sprites customizadas.
$init = [regex]::Replace(
    $init,
    'clientAssets\s*=\s*\{.*?\},\s*--\s*\./client_assets',
    "clientAssets = false, -- ./client_assets (desligado: assets vao embutidos)",
    [System.Text.RegularExpressions.RegexOptions]::Singleline)

# Uma unica entrada em Servers_init aciona setUniqueServer: host, porta e versao
# ficam escondidos e o jogador so preenche conta e senha.
$blocoServidores = @"
    Servers_init = {
        ["$LoginUrl"] = {
            port = $Porta,
            protocol = $Protocolo,
            httpLogin = true,
            useAuthenticator = false
        }
    }
"@
# MatchEvaluator em vez de string de substituicao: assim o texto entra literal,
# sem o regex interpretar $ nem \ (a URL e o bloco tem os dois).
$avaliador = [System.Text.RegularExpressions.MatchEvaluator] { param($m) $blocoServidores }
$init = [regex]::Replace($init, '(?s)    Servers_init = \{.*?\n    \}', $avaliador)

$init = $init -replace 'g_app\.setName\("[^"]*"\)', "g_app.setName(`"$NomeApp`")"

Set-Content -Path $initPath -Value $init -Encoding UTF8 -NoNewline

foreach ($esperado in @($LoginUrl, $NomeApp, 'clientAssets = false')) {
    if ((Get-Content $initPath -Raw) -notmatch [regex]::Escape($esperado)) {
        Write-Aviso "nao confirmei '$esperado' no init.lua - revise o arquivo a mao"
    }
}
Write-Ok "init.lua configurado ($LoginUrl)"

# --- 7. sprites proprias ----------------------------------------------------
# A arte fica versionada em tools/sprites/arte/; os assets do client nao. Por
# isso a injecao e' refeita a cada client montado.
#
# NAO passa --dat-servidor: o data/items/appearances.dat do repositorio JA tem
# essas aparencias commitadas, e as ferramentas nao checam duplicata -- injetar
# de novo acrescentaria entradas repetidas num binario de 4,8 MB versionado.
if (-not $PularSprites) {
    $python = $null
    foreach ($c in @('python', 'python3', 'py')) {
        $achado = Get-Command $c -ErrorAction SilentlyContinue
        if ($achado) { $python = $achado.Source; break }
    }
    $sprites = Join-Path $repoRaiz 'tools\sprites'

    if (-not $python) {
        Write-Aviso "Python nao encontrado no PATH - sprites proprias NAO injetadas"
    } elseif (-not (Test-Path $sprites)) {
        Write-Aviso "tools\sprites nao existe - pulando sprites"
    } else {
        # a ordem dos quadros do efeito e' proposital (01,03,04,06,05)
        $quadros = @('efeito_01.png', 'efeito_03.png', 'efeito_04.png', 'efeito_06.png', 'efeito_05.png') |
                   ForEach-Object { Join-Path $sprites "arte\fogo\$_" }

        $injecoes = @(
            @{ Nome = 'magic effect 350 (exori chama)'
               Args = @("$sprites\novo_efeito.py", 'efeito', '--assets', $pastaAssets,
                        '--id', '350', '--duracao', '110') + $quadros },
            @{ Nome = 'missile 70'
               Args = @("$sprites\novo_efeito.py", 'missile', '--assets', $pastaAssets,
                        '--id', '70', "$sprites\arte\fogo\missile_base.png") },
            @{ Nome = 'outfit 1950 (Mago de Fogo)'
               Args = @("$sprites\novo_outfit.py", "$sprites\arte\mago", '--assets', $pastaAssets,
                        '--id', '1950', '--colorizavel') }
        )

        foreach ($inj in $injecoes) {
            Write-Passo "Injetando $($inj.Nome)"
            & $python @($inj.Args) | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Aviso "falhou (exit $LASTEXITCODE) - veja tools/sprites/README.md"
            } else { Write-Ok $inj.Nome }
        }
    }
}

# --- 8. minimapa completo ----------------------------------------------------
# No Tibia o minimapa e' revelado andando. Este .otmm e' gerado do proprio OTBM
# por tools/mapa/gerar_minimapa.py, entao o jogador ja instala com o mapa todo
# aberto. O modulo game_minimap procura /minimap.otmm na raiz dos recursos e
# carrega sozinho no login -- nao precisa de botao nem de download.
$minimapa = Join-Path $repoRaiz 'tools\mapa\saida\minimap.otmm'
if (Test-Path $minimapa) {
    Write-Passo "Instalando o minimapa completo"
    Copy-Item $minimapa -Destination (Join-Path $Destino 'minimap.otmm') -Force
    Write-Ok ("minimap.otmm ({0:N1} MB)" -f ((Get-Item $minimapa).Length / 1MB))
} else {
    Write-Aviso "tools\mapa\saida\minimap.otmm nao existe - o client comeca com o mapa por explorar"
    Write-Aviso "para gerar: python tools/mapa/gerar_minimapa.py (precisa do otservbr.otbm, que nao vai no git)"
}

# --- 9. launcher (o "executor" que atualiza e abre o jogo) -------------------
# O atalho do instalador aponta para o launcher, nao para o otclient.exe: ele
# verifica atualizacoes no servidor, baixa so o que mudou e abre o jogo.
$launcher = Join-Path $repoRaiz 'tools\updater\launcher.ps1'
$launcherVbs = Join-Path $repoRaiz 'tools\updater\launcher.vbs'
if ((Test-Path $launcher) -and (Test-Path $launcherVbs)) {
    Write-Passo "Instalando o launcher (atualizador)"
    Copy-Item $launcher -Destination (Join-Path $Destino 'launcher.ps1') -Force
    Copy-Item $launcherVbs -Destination (Join-Path $Destino 'launcher.vbs') -Force
    Write-Ok "launcher.ps1 + launcher.vbs"
} else {
    Write-Aviso "tools\updater\launcher.* nao existe - o instalador abrira o otclient.exe direto, sem auto-update"
}

# --- limpeza e resumo -------------------------------------------------------
Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Client montado." -ForegroundColor Green
Write-Host "  Pasta:      $Destino"
Write-Host "  Executavel: $(Join-Path $Destino 'otclient.exe')"
Write-Host "  Servidor:   $LoginUrl"
Write-Host ""
Write-Host "Proximos passos:"
Write-Host "  1. Abra o otclient.exe e entre com conta e senha (host ja vem fixo)."
Write-Host "  2. AutoCaster: Ctrl+Shift+A. Idioma dos NPCs: Ctrl+Shift+I."
Write-Host "  3. Para distribuir, empacote a pasta com o Inno Setup:"
Write-Host "     MainExeName = otclient.exe   (nao bin\client.exe, que era do client oficial)"
Write-Host ""
Write-Host "Log do client, se algo nao carregar: $Destino\otclient.log"
