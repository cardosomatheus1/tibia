# Traduzir as conversas com NPC

Sistema de idioma **por jogador** para os diálogos de NPC. Dois jogadores
lado a lado leem cada um no seu idioma, e os dois podem digitar em
qualquer um dos dois.

## Como funciona

Traduzir os 1036 arquivos de NPC à mão seria insustentável — qualquer
atualização do datapack desfaria o trabalho. Em vez disso a tradução entra
em dois pontos por onde **tudo** passa:

| Ponto | Onde | O que faz |
|---|---|---|
| saída | `Npc:say` | todo NPC fala por aqui, inclusive o caminho com atraso (`SayEvent`) e o `sendMessage`. O texto sai no idioma **daquele** jogador |
| entrada | `NpcHandler:onSay` | normaliza o que o jogador digitou para inglês **antes** de qualquer comparação |

A normalização de entrada é o que faz `oi`, `depositar tudo` e `sim` caírem
nas mesmas regras que `hi`, `deposit all` e `yes`. Ela só **acrescenta**: o
inglês continua funcionando igual, e nenhuma regra de NPC precisa saber que
existe outro idioma.

```
oi                   -> hi
depositar tudo       -> deposit all
trocar ouro          -> change gold
cura suprema         -> ultimate healing
hi                   -> hi          (inglês passa direto)
```

Ela casa o **maior trecho** primeiro, para "depositar tudo" não virar
"depositar" + "tudo".

O que está entre chaves é o que o client deixa clicável, então também sai
traduzido — e é exatamente por isso que a volta precisa existir: sem ela o
jogador clicaria em `{negociar}` e o NPC não entenderia.

Frase sem tradução sai em inglês, nunca vazia. E mesmo aí as chaves são
traduzidas, então a parte clicável já fica em português antes da frase
inteira estar pronta.

## Trocar de idioma

A escolha fica no KV do personagem — acompanha o char e não depende de
client nenhum.

```
!idioma          mostra o atual e os disponíveis
!idioma br       português
!idioma us       inglês
```

O [`client-modules/idioma/`](../../client-modules/idioma/) é só uma
bandeirinha que manda esse mesmo comando (Ctrl+Shift+I).

## Nome próprio não se traduz

O dicionário tem duas listas, e a diferença importa:

| Lista | Vale em | Para quê |
|---|---|---|
| `palavras` | entrada **e** saída | palavra funcional: `hi`, `trade`, `deposit all`, `yes` |
| `apelidos` | **só** entrada | nome de magia, cidade e bênção |

Nome de magia fica no original na saída de propósito. Se o NPC dissesse
`{cura suprema}` mas a spellbook, a hotkey e a encantação seguem
`Ultimate Healing` / `exura vita`, o jogador ficaria procurando um nome que
não existe em nenhum outro lugar do jogo. Como apelido, ele **pode** dizer
"cura suprema" e o NPC entende — só não inventa nome novo na resposta.

## A estratégia

Traduzir por frequência foi um erro, e o `progresso.py` mostra o preço:
**373 NPCs ficaram pela metade**. Metade é a pior leitura possível — o
jogador vê a saudação em português, a resposta em inglês, e conclui que o
servidor está quebrado. Em inglês inteiro pelo menos é coerente.

Três regras, e as três são cobradas por ferramenta, não por boa intenção:

**1. A unidade de trabalho é o NPC inteiro.** Nunca se entrega um NPC pela
metade. `por_npc.py` mostra o roteiro completo de um personagem na ordem
do arquivo, que é o que preserva a voz — e é impossível dar voz a um
personagem traduzindo suas frases separadas por semanas.

**2. A ordem é por cidade, uma de cada vez.** Com Rookgaard 100%, quem
começa o jogo tem a experiência completa mesmo que Thais não tenha
começado. `progresso.py` mede por cidade, não o percentual global, que
engana.

Ordem: **Rookgaard e Dawnport** (todo jogador passa), depois **Thais**,
depois as demais na ordem em que o jogador tende a conhecê-las.

**3. Nada entra sem passar nos portões.** `verificar.py` reprova se:

| Portão | Por quê |
|---|---|
| glossário violado | nome próprio traduzido manda o jogador procurar o que não existe |
| palavra clicável sem volta | jogador clica em `{dicas}`, o NPC não entende, a conversa trava |
| chave desatualizada | o upstream editou a frase e a tradução se soltou |
| órfã com par parecido | provavelmente é a mesma frase editada |

Os três portões já pegaram erros meus: `Global Bank` e `Ice Islands`
traduzidos, e `{templo}`/`{aventureiro}` sem caminho de volta.

## Traduzir mais

```bash
python3 tools/traducao/extrair.py            # recolhe o que falta
# preencher os campos "pt" em tools/traducao/catalogo.json
python3 tools/traducao/gerar_dicionario.py   # gera o dicionário Lua
```

Cada frase no catálogo traz **quem a diz** (campo `npc`) e quantas vezes
aparece. O falante é o que permite traduzir com contexto: a mesma frase
muda de tom conforme quem fala, e sem saber quem é fica fácil escolher a
palavra errada.

O `extrair.py` **preserva o que já foi traduzido** — rodar de novo depois
de atualizar o datapack só acrescenta as chaves novas, e marca como
`obsoleto` o que sumiu, em vez de apagar. Ele também conta quantas vezes
cada frase é dita, o que permite atacar por impacto.

## Proteger o trabalho

A tradução é a parte cara e a parte frágil. Quatro coisas garantem que ela
não se perca:

**Mora fora dos NPCs.** Tudo vive em `tools/traducao/catalogo.json`, um
arquivo só, que não depende de nenhum dos 1036 scripts. Atualizar o
datapack — ou trocá-lo inteiro — não encosta nele.

**Nada feito à mão é descartado.** O `extrair.py` preserva os campos `pt`
ao rodar de novo, e o gerador inclui **até** a tradução de frase que sumiu
do datapack. Guardar custa uma linha; se a frase voltar, já funciona.
Descartar custa o trabalho de uma pessoa.

**Mudança pequena não quebra.** O dicionário também é indexado por chave
tolerante (minúscula, espaço colapsado, pontuação de borda fora), então
uma vírgula corrigida lá em cima não derruba a linha para o inglês.

**Mudança grande fica visível.** É o `verificar.py`:

```bash
python3 tools/traducao/verificar.py
```

```
chave desatualizada (a frase mudou de pontuacao/espaco):
  - Good bye.
  + Good bye!

traducao orfa com frase parecida no lugar (1):
  - There is not enought room.
  + There is not enough room.
```

Ele sai com código 1 quando tem algo para decidir, então serve direto num
hook de commit ou na CI. A troca automática **não** é feita de propósito:
frase parecida pode ser outra frase, e mostrar a fala errada é pior do que
mostrar em inglês. A ferramenta aponta; quem decide é uma pessoa.

## O tamanho real disso

Vale saber antes de começar:

| | |
|---|---|
| arquivos de NPC | 1036 |
| falas distintas | 7503 (~636 mil caracteres, ~160 mil palavras) |
| palavras-chave distintas | 1606 |

E a cauda é longa — não é um caso onde traduzir 20% resolve:

| Para cobrir | Precisa traduzir |
|---|---|
| 25% das falas ditas | 171 frases (2% do catálogo) |
| 50% | 989 frases (13%) |
| 80% | 4735 frases (64%) |
| 100% | 7503 frases (100%) |

**Estado atual: 38 palavras funcionais, 78 apelidos e 23 frases** — 3,6% das
falas ditas. Parece pouco, e é, mas cobre a interação inteira: saudação,
despedida, sim/não, banco, cura, compra e venda, nomes de magia. É onde o
jogador digita.

O resto do catálogo é diálogo de ambientação. Isso é trabalho de volume e
**deve ser feito à mão, frase a frase** — tradução automática de diálogo de
NPC erra tom e contexto com frequência, e o campo `npc` de cada frase está
lá justamente para permitir traduzir sabendo quem fala. A infraestrutura já
roteia 100% das falas; o que falta é o texto.
