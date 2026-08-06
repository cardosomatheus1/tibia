# O quadrado azul: instrumentado, causa localizada

Investigado em 2026-08-06. **Este documento foi reescrito**: a primeira versão
apontava uma causa que o teste em jogo derrubou. O que segue está apoiado em log
de cliente instrumentado, não em leitura de código.

## O sintoma

Quadrado ou faixa azul no mapa. Acontece em mundo aberto e dentro de instância
-- nao tem relacao com hunt instanciada.

## O que o azul e'

A cor de limpeza do framebuffer do mapa (`uimap.cpp:62`), visível onde NADA foi
desenhado. E' azul quando a câmera está no `mapSeaFloor` (z=7) e preta abaixo
disso -- por isso o bug parece só existir na superfície: no subterrâneo o buraco
e' preto e se confunde com o fundo.

## A causa, medida

Duas instrumentações temporárias no cliente responderam o que a leitura de
código não deu:

- `[TILE-VAZIO]` em `setTileDescription`: registra tile que chega vazio.
  **Resultado: ruído.** Todos os vazios são andares ACIMA do jogador -- céu, e
  no subterrâneo rocha. O andar do jogador chega completo.
- `[SEM-TILE]` no laço de desenho: registra posição sem tile no andar da câmera,
  dizendo se está dentro da faixa que o cliente diz conhecer.

O log decisivo, na troca de andar (z 7 -> 6):

    [SEM-TILE] pos=36923,36904,6 camera=36934,36913,6 conhece=1
    [SEM-TILE] pos=36936,36904,6 camera=36934,36913,6 conhece=1
    [SEM-TILE] pos=36945,36908,6 camera=36934,36913,6 conhece=1

**`conhece=1` com tile ausente.** O cliente considera a posição dentro da faixa
recebida e não tem nada ali. Isso descarta geometria (não e' o cliente
desenhando além do que sabe) e aponta para dado que o servidor não enviou.

As posições são as quinas da faixa: `36923 = 36934-11` e `36904 = 36913-9`,
exatamente `x-X` e `y-Y` das constantes ampliadas.

## O suspeito

`ProtocolGame::MoveUpCreature`, em src/server/network/protocol/protocolgame.cpp:

    // west
    GetMapDescription(oldPos.x - MAP_MAX_CLIENT_VIEW_PORT_X,
                      oldPos.y - (MAP_MAX_CLIENT_VIEW_PORT_Y - 1), ...

A coluna oeste começa em `y - (Y-1)`, não em `y - Y`. Com o Y original (6) o
descompasso era de um tile numa janela pequena; com Y=9 ele acompanha a janela
ampliada. `MoveDownCreature` merece a mesma conferência.

NAO CONFIRMADO: a correção não foi testada. E' hipótese apoiada em evidência, o
que e' mais do que as anteriores tinham, mas ainda não e' prova. O caminho para
fechar: corrigir, subir, e olhar se `[SEM-TILE] ... conhece=1` some do log na
troca de andar.

## O que foi descartado, com evidência

- **Lentidão do servidor.** Os avisos de backlog são todos do `/testecarga`.
- **Buraco no mapa.** 0 de 441 tiles sem chão em Thais z7, 0 de 961 nos ciclopes.
- **`Tile::setFill`.** Ninguém chama, e o campo nasce em `Color::alpha`.
- **Barra de mana.** Tom de azul diferente, e e' fina.
- **`drawDimension = visibleDimension + 3`** cortando a aware range: parecia
  explicar tudo, foi compilado e testado em jogo, e **o bug continuou**. A
  alteração está na branch `janela-de-mapa-maior` do fork e deve ser revertida
  ou revalidada antes de qualquer distribuição.
- **Feature `GameEnvironmentEffect`** dessincronizando o pacote: o cliente a
  desliga a partir da versão 1281 e a nossa e' 1525.

## Capacidade nova

O fork `cardosomatheus1/otclient` existe e compila -- pela CI (quando o GitHub
não está em pane) e localmente em `C:\otc` (VS 2022 Build Tools, MSVC 14.44,
CMake 4.4, vcpkg com cache binário em `C:\otc\cache`, script `C:\otc\compilar.bat`).
Instrumentar o cliente deixou de ser impossível e passou a ser rotina de poucos
minutos.

`tools/preparar_mehah.ps1` já aponta para o fork.
