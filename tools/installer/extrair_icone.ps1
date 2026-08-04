<#
.SYNOPSIS
    Extrai o icone do Tibia do client oficial e salva como tibia.ico na pasta do
    client mehah, para o instalador usar.

.DESCRIPTION
    O otclient.exe do mehah tem um icone generico. O client oficial (dudantas)
    traz o icone real do Tibia embutido. Este script pega o client.exe de dentro
    do zip oficial e extrai o icone completo (todas as resolucoes, ate 256x256)
    com gerar_icone.py.

.PARAMETER ClientOficialZip
    tibia-client-15.25.*.zip (o mesmo do preparar_mehah.ps1).

.PARAMETER Raiz
    Pasta do client mehah. Padrao: C:\otclient-mehah
#>
param(
    [Parameter(Mandatory = $true)] [string] $ClientOficialZip,
    [string] $Raiz = "C:\otclient-mehah"
)

$ErrorActionPreference = 'Stop'
$aqui = $PSScriptRoot

if (-not (Test-Path $ClientOficialZip)) { throw "Zip nao encontrado: $ClientOficialZip" }
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { throw "python nao encontrado no PATH" }

# extrai o client.exe oficial para um temp
$tmpExe = Join-Path ([System.IO.Path]::GetTempPath()) "tibia_client_oficial.exe"
Write-Host "Extraindo o client oficial do zip..."
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $ClientOficialZip))
try {
    $e = $zip.Entries | Where-Object { $_.FullName -eq 'bin/client.exe' } | Select-Object -First 1
    if (-not $e) { throw "bin/client.exe nao esta no zip -- o zip e' o do dudantas?" }
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, $tmpExe, $true)
} finally { $zip.Dispose() }

$ico = Join-Path $Raiz 'tibia.ico'
& $python (Join-Path $aqui 'gerar_icone.py') $tmpExe $ico
Remove-Item $tmpExe -Force -ErrorAction SilentlyContinue

if (Test-Path $ico) { Write-Host "Icone do Tibia salvo em: $ico" }
else { throw "gerar_icone.py nao produziu o tibia.ico" }
