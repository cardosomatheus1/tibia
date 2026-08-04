<#
.SYNOPSIS
    Launcher/atualizador do client rhapsodyyy. Verifica atualizacoes, baixa so o
    que mudou e abre o otclient.exe.

.DESCRIPTION
    E' o "executor" que o jogador clica -- o atalho aponta para ca, nao para o
    otclient.exe direto. Fluxo:

      1. baixa o manifest (arquivo -> CRC32) do servidor de update
      2. calcula o CRC32 dos arquivos locais e compara
      3. baixa os que faltam ou mudaram (e o otclient.exe, se mudou)
      4. abre o otclient.exe

    Regra de ouro: o jogo SEMPRE abre. Se a atualizacao falhar (servidor fora do
    ar, sem internet, erro qualquer), o launcher registra em launcher.log e abre
    o jogo com o que ja esta instalado -- nunca deixa o jogador na mao. So mostra
    uma janela de aviso se o proprio otclient.exe nao abrir.

.PARAMETER Raiz
    Pasta do client (onde esta o otclient.exe). Padrao: a pasta do proprio script.

.PARAMETER ManifestUrl
    Endpoint que devolve o manifest JSON.

.PARAMETER SemAbrir
    So atualiza, nao abre o client (para testar).

.PARAMETER Visivel
    Mostra o progresso numa janela (para diagnostico). Sem isto, roda silencioso.
#>

[CmdletBinding()]
param(
    [string] $Raiz = $PSScriptRoot,
    [string] $ManifestUrl = "http://rhapsodyyy.duckdns.org:8090/updater",
    [switch] $SemAbrir,
    [switch] $Visivel
)

# NAO usar ErrorActionPreference=Stop global: um unico erro nao-tratado mataria
# o launcher sem abrir o jogo. Aqui os erros sao contidos por try/catch e o
# finally garante a abertura.
$ErrorActionPreference = 'Continue'
if (-not $Raiz) { $Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path }
$exe = Join-Path $Raiz 'otclient.exe'
$logFile = Join-Path $Raiz 'launcher.log'
$versionFile = Join-Path $Raiz '.versao_instalada'

function Log($msg) {
    $linha = "{0} {1}" -f (Get-Date).ToString('HH:mm:ss'), $msg
    try { Add-Content -LiteralPath $logFile -Value $linha -Encoding UTF8 } catch {}
    if ($Visivel) { Write-Host $linha }
}

function Mostrar-Aviso($msg) {
    Log "AVISO: $msg"
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [System.Windows.Forms.MessageBox]::Show(
            $msg, "Tibia rhapsodyyy", 'OK', 'Warning') | Out-Null
    } catch { }
}

# O ícone dos atalhos é gravado no .lnk pelo instalador, e o updater não mexe em
# atalho -- ele só distribui arquivos do client. Quem instalou com uma versão
# antiga ficou com o atalho apontando para o ícone genérico do otclient.exe.
# Como o launcher roda a cada abertura, ele mesmo conserta: é barato (só toca no
# .lnk quando está errado) e alcança quem já tinha instalado.
function Corrigir-Icone {
    $ico = Join-Path $Raiz 'tibia.ico'
    if (-not (Test-Path -LiteralPath $ico)) { return }

    $atalhos = @(
        (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Tibia rhapsodyyy.lnk'),
        (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Tibia rhapsodyyy\Tibia rhapsodyyy.lnk')
    )
    $desejado = "$ico,0"
    try {
        $ws = New-Object -ComObject WScript.Shell
        foreach ($lnk in $atalhos) {
            if (-not (Test-Path -LiteralPath $lnk)) { continue }
            $s = $ws.CreateShortcut($lnk)
            if ($s.IconLocation -ne $desejado) {
                $s.IconLocation = $desejado
                $s.Save()
                Log "icone do atalho corrigido: $lnk"
            }
        }
    } catch {
        Log "nao consegui corrigir o icone do atalho: $($_.Exception.Message)"
    }
}

function Abrir-Client {
    if ($SemAbrir) { return }
    if (-not (Test-Path -LiteralPath $exe)) {
        Mostrar-Aviso ("Nao encontrei o jogo (otclient.exe) em:`n$Raiz`n`n" +
                       "A instalacao pode estar incompleta -- reinstale o jogo.")
        return
    }
    try {
        Start-Process -FilePath $exe -WorkingDirectory $Raiz
        Log "jogo aberto"
    } catch {
        Mostrar-Aviso ("Nao consegui abrir o jogo.`n`n" +
                       "Erro: $($_.Exception.Message)`n`n" +
                       "Se for a primeira vez, instale o 'Microsoft Visual C++ " +
                       "Redistributable x64' e tente de novo.")
    }
}

# CRC32 no formato do client: hex minusculo, sem zero a esquerda (dec_to_hex).
#
# Compilado em C# de proposito. A primeira versao era um laco byte a byte em
# PowerShell puro, e conferir os ~3700 arquivos (87 MB) levava de 30 s a 1 min
# a cada atualizacao -- o jogador ficava olhando para o nada. Em C# o mesmo
# trabalho leva poucos segundos. O Add-Type compila uma vez por execucao.
if (-not ('Crc32Util' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;

public static class Crc32Util
{
    static readonly uint[] Tabela = Criar();

    static uint[] Criar()
    {
        var t = new uint[256];
        for (uint i = 0; i < 256; i++)
        {
            uint c = i;
            for (int k = 0; k < 8; k++)
                c = (c & 1) != 0 ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
            t[i] = c;
        }
        return t;
    }

    public static string DoArquivo(string caminho)
    {
        uint crc = 0xFFFFFFFFu;
        using (var s = new FileStream(caminho, FileMode.Open, FileAccess.Read,
                                      FileShare.ReadWrite, 1 << 16))
        {
            var buf = new byte[1 << 16];
            int n;
            while ((n = s.Read(buf, 0, buf.Length)) > 0)
                for (int i = 0; i < n; i++)
                    crc = Tabela[(crc ^ buf[i]) & 0xFF] ^ (crc >> 8);
        }
        crc ^= 0xFFFFFFFFu;
        // mesmo formato do stdext::dec_to_hex: minusculo, sem zero a esquerda
        return crc.ToString("x");
    }
}
'@ -ErrorAction SilentlyContinue
}

function Get-Crc32([string] $arquivo) {
    return [Crc32Util]::DoArquivo($arquivo)
}

# URL preservando barras mas escapando cada segmento (nomes com [ ] da loja).
function Montar-Url([string] $base, [string] $chave) {
    $partes = $chave.Split('/') | ForEach-Object { [Uri]::EscapeDataString($_) }
    return $base + ($partes -join '/')
}

function Baixar([string] $url, [string] $destino) {
    $wc = New-Object System.Net.WebClient
    try { $wc.DownloadFile($url, $destino) } finally { $wc.Dispose() }
}

# Janela simples de "Atualizando...", so usada quando ha download. No caso comum
# (nada mudou) o launcher nem chega aqui -- abre o jogo direto e invisivel.
$script:formProgresso = $null
$script:barra = $null
$script:rotulo = $null
function Abrir-Progresso($totalPassos) {
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        Add-Type -AssemblyName System.Drawing -ErrorAction Stop
        $f = New-Object System.Windows.Forms.Form
        $f.Text = "Tibia rhapsodyyy"
        $f.Size = New-Object System.Drawing.Size(420, 130)
        $f.StartPosition = 'CenterScreen'
        $f.FormBorderStyle = 'FixedDialog'
        $f.MaximizeBox = $false; $f.MinimizeBox = $false
        $f.TopMost = $true
        $l = New-Object System.Windows.Forms.Label
        $l.Text = "Atualizando o jogo..."
        $l.AutoSize = $true
        $l.Location = New-Object System.Drawing.Point(15, 15)
        $f.Controls.Add($l)
        $b = New-Object System.Windows.Forms.ProgressBar
        $b.Location = New-Object System.Drawing.Point(15, 45)
        $b.Size = New-Object System.Drawing.Size(375, 25)
        $b.Minimum = 0; $b.Maximum = [Math]::Max(1, $totalPassos)
        $f.Controls.Add($b)
        $f.Show(); $f.Refresh()
        $script:formProgresso = $f; $script:barra = $b; $script:rotulo = $l
    } catch { Log "sem UI de progresso: $($_.Exception.Message)" }
}
function Passo-Progresso($texto) {
    if (-not $script:formProgresso) { return }
    try {
        $script:barra.Value = [Math]::Min($script:barra.Maximum, $script:barra.Value + 1)
        if ($texto) { $script:rotulo.Text = $texto }
        [System.Windows.Forms.Application]::DoEvents()
    } catch {}
}
function Fechar-Progresso {
    if ($script:formProgresso) { try { $script:formProgresso.Close() } catch {} }
}

# ---------------------------------------------------------------- principal
# reinicia o log a cada execucao
try { Set-Content -LiteralPath $logFile -Value "" -Encoding UTF8 } catch {}
Log "=== launcher iniciado ==="
Log "raiz=$Raiz"
Log ("PowerShell {0}" -f $PSVersionTable.PSVersion)

try {
    # 1. manifest
    Log "consultando $ManifestUrl"
    $manifest = Invoke-RestMethod -Uri $ManifestUrl -Method Post -Body '{}' `
        -ContentType 'application/json' -TimeoutSec 20
    $baseUrl = $manifest.url.TrimEnd('/')
    Log ("manifest ok: {0} arquivos, versao {1}" -f `
        @($manifest.files.PSObject.Properties).Count, $manifest.version)

    # Atalho rapido: se a versao instalada bate com a do servidor, nada mudou --
    # abre o jogo na hora, sem conferir os ~3000 arquivos (que levava ~1 min).
    # So cai na verificacao completa quando ha atualizacao de verdade.
    if ($manifest.version) {
        $versaoLocal = ""
        if (Test-Path -LiteralPath $versionFile) {
            $versaoLocal = (Get-Content -LiteralPath $versionFile -Raw).Trim()
        }
        if ($versaoLocal -eq $manifest.version) {
            Log "versao local igual a do servidor -- nada a atualizar"
            Abrir-Client
            Log "=== fim ==="
            return
        }
        Log "versao mudou ($versaoLocal -> $($manifest.version)); verificando arquivos"
    }

    # 2. compara
    $aBaixar = New-Object System.Collections.Generic.List[object]
    foreach ($prop in $manifest.files.PSObject.Properties) {
        $rel = $prop.Name.TrimStart('/')
        $local = Join-Path $Raiz $rel
        $precisa = $true
        if (Test-Path -LiteralPath $local) {
            try { if ((Get-Crc32 $local) -eq $prop.Value) { $precisa = $false } }
            catch { Log "crc falhou em $rel : $($_.Exception.Message)" }
        }
        if ($precisa) { $aBaixar.Add(@{ Rel = $rel; Chave = $prop.Name }) }
    }

    $binPrecisa = $false
    if ($manifest.binary -and $manifest.binary.file) {
        if (-not (Test-Path -LiteralPath $exe) -or (Get-Crc32 $exe) -ne $manifest.binary.checksum) {
            $binPrecisa = $true
        }
    }

    $total = $aBaixar.Count + [int]$binPrecisa
    Log "a atualizar: $total"

    if ($total -gt 0) {
        Abrir-Progresso $total
        foreach ($item in $aBaixar) {
            $destino = Join-Path $Raiz $item.Rel
            $pasta = Split-Path -Parent $destino
            if (-not (Test-Path -LiteralPath $pasta)) {
                New-Item -ItemType Directory -Path $pasta -Force | Out-Null
            }
            Baixar (Montar-Url $baseUrl $item.Chave) $destino
            Passo-Progresso "Atualizando o jogo..."
        }
        if ($binPrecisa) {
            Passo-Progresso "Atualizando o jogo (executavel)..."
            Baixar (Montar-Url $baseUrl $manifest.binary.file) $exe
        }
        Fechar-Progresso
        Log "download concluido"
    } else {
        Log "nada a atualizar"
    }

    # grava a versao instalada, para o proximo arranque ser instantaneo
    if ($manifest.version) {
        try { Set-Content -LiteralPath $versionFile -Value $manifest.version -Encoding ASCII }
        catch { Log "nao consegui gravar a versao: $($_.Exception.Message)" }
    }
} catch {
    # atualizacao falhou -- nao trava; o finally abre o jogo assim mesmo
    Log "atualizacao falhou (segue e abre o jogo): $($_.Exception.Message)"
} finally {
    Fechar-Progresso
    Corrigir-Icone
    Abrir-Client
    Log "=== fim ==="
}
