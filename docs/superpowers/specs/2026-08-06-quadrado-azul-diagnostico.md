# O quadrado azul: diagnóstico fechado, correção pendente

Investigado em 2026-08-06. A causa está identificada com precisão; o que falta
é a capacidade de compilar o cliente.

## O sintoma

Quadrado ou faixa azul no mapa. Aparece correndo rápido (faixa inteira no lado
do movimento) e parado, a cada hit recebido (quadrado isolado). Acontece em
mundo aberto e dentro de instância — não tem relação com hunt instanciada.

## A causa

O cliente **descarta** a janela de mapa ampliada que o servidor envia.

Em `src/client/mapview.cpp:524`:

```cpp
const uint8_t left = std::min(g_map.getAwareRange().left, (m_drawDimension.width()/2) - 1);
const uint8_t top  = std::min(g_map.getAwareRange().top,  (m_drawDimension.height()/2) - 1);
```

E `m_drawDimension = visibleDimension + 3` (linha 498). O cliente usa
`visibleDimension = 15x11` em todos os caminhos do `game_interface`, então:

    drawDimension = 18x14
    limite        = (18/2)-1 = 8   e   (14/2)-1 = 6

**8 e 6 são exatamente os valores originais do Canary.** O servidor manda 11 e
9 pelo opcode 0x33 (`sendMapAwareRange`), e o `min()` corta de volta. A janela
ampliada nunca chegou a valer.

O buraco aparece porque o cliente DESENHA `visibleDimension + 3` tiles mas só
considera válidos os de dentro da faixa cortada. A borda entre os dois sai sem
dado, e o que se vê ali é a cor de limpeza do framebuffer do mapa
(`uimap.cpp:62`) — não é algo pintado por cima, é o fundo aparecendo.

## O que foi descartado, com evidência

- **Lentidão do servidor.** Os avisos de `player-visible backlog` são todos do
  `/testecarga`, nenhum durante o jogo.
- **Tamanho escrito na mão no servidor.** Todas as chamadas de
  `GetMapDescription` usam as constantes; nenhuma literal sobrou.
- **`Tile::setFill`** (pinta o tile inteiro de uma cor): ninguém chama, nem no
  C++ nem nos módulos, e o campo nasce em `Color::alpha`.
- **Barra de mana.** É fina, só do jogador local, e o tom de azul é outro — o
  do bug é o mesmo da faixa que aparece correndo.
- **Textura faltando.** Quando falta, o cliente não desenha nada; não pinta cor.

## A correção

`m_drawDimension = visibleDimension + 3` → **`+ 9`**:

    18x14 → 24x20        limite: 11 e 9        = exatamente o que o servidor manda

O jogador continua vendo os mesmos 15x11 tiles; muda só a margem que o cliente
mantém pronta em volta. Custo: renderizar 24x20 em vez de 18x14, ~1,8x mais
tiles, quase todos fora da tela. Vale medir FPS antes e depois em máquina
fraca.

Alternativa descartada: subir `visibleDimension` para 21x17 resolve igual, mas
muda o campo de visão do jogo — mexer na cara do jogo para consertar um bug
interno.

## Por que não foi feito ainda

O `otclient.exe` não é compilado aqui: vem pronto de um artefato do GitHub
Actions do mehah (`tools/preparar_mehah.ps1:76`). Aplicar um patch em C++ exige
fork do mehah/otclient, o patch, e a CI deles produzindo o artefato de Windows.

É uma capacidade nova para este projeto, e o passo seguinte.
