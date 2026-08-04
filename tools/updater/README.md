# Distribuição e atualização do client

O jogador instala **uma vez** (Inno Setup) e, a cada vez que abre, um
**launcher** verifica atualizações e baixa só o que mudou — sem reinstalar.

![Client em jogo no protocolo 15.25](../../docs/images/sprites-em-jogo.png)

## As peças

| Arquivo | Papel | Onde roda |
|---|---|---|
| [`gerar_manifest.py`](gerar_manifest.py) | Lista arquivo→CRC32 e monta a pasta a publicar | sua máquina |
| [`updater_server.py`](updater_server.py) | Serve o manifest e os arquivos | VPS (serviço systemd) |
| [`launcher.ps1`](launcher.ps1) | Verifica, baixa o que mudou, abre o jogo | PC do jogador |
| [`publicar.ps1`](publicar.ps1) | Faz tudo de uma vez: gera, envia, reinicia | sua máquina |
| [`../installer/instalador.iss`](../installer/instalador.iss) | Empacota o client num instalador | sua máquina (Inno) |

O checksum é **CRC32 em hex minúsculo sem zero à esquerda** — o mesmo que o
client usa (`stdext::dec_to_hex`). As chaves do manifest levam barra inicial
(`/modules/x.lua`), como o `g_resources.filesChecksums()` gera. Errar qualquer
um dos dois faz o launcher rebaixar tudo a cada abertura.

## Por que um launcher próprio, e não o updater do mehah

O mehah tem um updater embutido, mas ele espera o client empacotado em
`data.zip`. O nosso roda com arquivos soltos, então o updater embutido não
dispara. O launcher faz o mesmo papel, com controle total, e é o modelo que o
RubinOT usa.

## Primeira instalação (montar o instalador)

```powershell
# 1. monta o client (exe + assets + modulos + minimapa + launcher)
.\tools\preparar_mehah.ps1 `
    -ArtefatoZip "$env:USERPROFILE\Downloads\windows-cmake-release.zip" `
    -ClientOficialZip "$env:USERPROFILE\Downloads\tibia-client-15.25.0a00a0.zip"

# 2. extrai o icone do jogo
.\tools\installer\extrair_icone.ps1

# 3. abre tools\installer\instalador.iss no Inno Setup e aperta Compile (Ctrl+F9)
#    -> gera TibiaInstaller-rhapsodyyy.exe
```

O atalho criado pelo instalador **não** abre o `otclient.exe` direto: abre o
`launcher.ps1`, que atualiza antes de entrar no jogo.

## Publicar uma atualização

Depois de mudar o que precisar no client montado (`C:\otclient-mehah`):

```powershell
.\tools\updater\publicar.ps1
```

Isso regenera o manifest, envia ao VPS e reinicia o serviço. Os jogadores
recebem no próximo clique no launcher. Para atualizar só código/assets leves
sem reenviar o `otclient.exe` (40 MB), use `-SemBinario`.

## O servidor no VPS

Roda como serviço systemd `rhapsodyyy-updater` na porta **8090**, servindo
`/root/client-update/` (manifest.json + files/). Comandos úteis:

```bash
systemctl status rhapsodyyy-updater      # estado
journalctl -u rhapsodyyy-updater -n 50   # log
curl http://127.0.0.1:8090/health        # ping
```

## O que o updater NÃO distribui, de propósito

- **`data/things/` e `data/sounds/`** — os assets da 15.25 (170+ MB). Vêm no
  instalador uma vez; não faz sentido reenviar a cada correção de código.
- **`minimap.otmm`** — o client sobrescreve esse arquivo conforme o jogador
  explora, então o checksum de cada um diverge. Incluí-lo faria todo mundo
  rebaixar o mapa base a cada login. Vai só no instalador.
