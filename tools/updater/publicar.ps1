<#
.SYNOPSIS
    Publica uma atualizacao do client: regenera o manifest a partir do client
    montado, envia ao VPS e reinicia o servico. Depois disso, os jogadores
    recebem a atualizacao no proximo clique no launcher.

.DESCRIPTION
    Fluxo de uma atualizacao, do inicio ao fim:

      1. voce muda o que precisa no client (um modulo, um patch, o binario)
      2. roda este script
      3. pronto -- o launcher de cada jogador baixa so o que mudou

    O script gera o manifest (arquivo -> CRC32), compacta a pasta publicada,
    envia por scp, extrai no VPS e reinicia o rhapsodyyy-updater.

.PARAMETER Client
    Pasta do client montado. Padrao: C:\otclient-mehah

.PARAMETER Vps
    usuario@host do VPS. Padrao: root@209.126.8.53

.PARAMETER Chave
    Caminho da chave SSH. Padrao: ~\.ssh\id_ed25519_vps

.PARAMETER Url
    URL base de download (sem barra final). Padrao aponta para o VPS na 8090.

.PARAMETER SemBinario
    Nao inclui o otclient.exe no manifest (updates so de codigo/assets leves).
#>
[CmdletBinding()]
param(
    [string] $Client = "C:\otclient-mehah",
    [string] $Vps = "root@209.126.8.53",
    [string] $Chave = "$env:USERPROFILE\.ssh\id_ed25519_vps",
    [string] $Url = "http://rhapsodyyy.duckdns.org:8090/files",
    [switch] $SemBinario
)

$ErrorActionPreference = 'Stop'
$aqui = $PSScriptRoot
$repoRaiz = Split-Path -Parent (Split-Path -Parent $aqui)
$publicado = Join-Path $aqui 'publicado'
$tar = Join-Path $aqui 'publicado.tar.gz'

function Passo($t) { Write-Host "==> $t" -ForegroundColor Cyan }

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { throw "python nao encontrado no PATH" }

# 1. manifest + pasta files/
Passo "Gerando o manifest a partir de $Client"
$argsGer = @("$aqui\gerar_manifest.py", '--client', $Client, '--url', $Url, '--saida', $publicado)
if ($SemBinario) { $argsGer += '--sem-binario' }
& $python @argsGer
if ($LASTEXITCODE -ne 0) { throw "gerar_manifest.py falhou" }

# 2. compacta (scp de milhares de arquivos soltos e' lento; um .tar.gz vai rapido)
Passo "Compactando"
if (Test-Path $tar) { Remove-Item $tar -Force }
tar czf $tar -C $aqui publicado
if ($LASTEXITCODE -ne 0) { throw "tar falhou" }
Write-Host ("    {0:N1} MB" -f ((Get-Item $tar).Length / 1MB))

# 3. envia e aplica no VPS
Passo "Enviando ao VPS"
& scp -i $Chave -o BatchMode=yes $tar "${Vps}:/root/publicado.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "scp falhou" }

Passo "Aplicando no VPS e reiniciando o servico"
$remoto = @'
set -e
rm -rf /tmp/pub && mkdir -p /tmp/pub
tar xzf /root/publicado.tar.gz -C /tmp/pub
rm -rf /root/client-update/files /root/client-update/manifest.json
mv /tmp/pub/publicado/files /tmp/pub/publicado/manifest.json /root/client-update/
rm -f /root/publicado.tar.gz
systemctl restart rhapsodyyy-updater
sleep 2
systemctl is-active rhapsodyyy-updater
'@
& ssh -i $Chave -o BatchMode=yes $Vps $remoto
if ($LASTEXITCODE -ne 0) { throw "aplicacao no VPS falhou" }

Remove-Item $tar -Force -ErrorAction SilentlyContinue

# Grava a versao publicada dentro do client, para o instalador empacotar. Assim
# a PRIMEIRA abertura do jogador ja bate com o servidor e abre na hora, em vez
# de conferir os ~3000 arquivos (que leva ~1 min so na primeira vez).
try {
    $manifestLocal = Join-Path $publicado 'manifest.json'
    $versao = (Get-Content -LiteralPath $manifestLocal -Raw | ConvertFrom-Json).version
    if ($versao) {
        Set-Content -LiteralPath (Join-Path $Client '.versao_instalada') -Value $versao -Encoding ASCII
        Write-Host ("  versao gravada no client: {0}" -f $versao)
    }
} catch { Write-Host "  aviso: nao gravei a versao no client ($($_.Exception.Message))" }

Write-Host ""
Write-Host "Atualizacao publicada." -ForegroundColor Green
Write-Host "  Os jogadores recebem no proximo clique no launcher."
Write-Host "  Recompile o instalador (Inno) se for distribuir para gente nova."
