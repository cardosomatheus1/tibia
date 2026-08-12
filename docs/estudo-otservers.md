# Estudo: o que os principais OTServers fazem de diferente

Levantamento de agosto de 2026, a partir das listas públicas de servidores,
do wiki do RubinOT e das discussões do OTLand. O objetivo não é copiar
funcionalidade — é entender **onde nos posicionamos** e o que vale construir.

---

## 1. O mercado não é um só

A primeira coisa que os números mostram é que "OTServer" descreve três
mercados quase sem contato entre si.

| Escola | Protocolo | Rate | Exemplos | Como ganha jogador |
|---|---|---|---|---|
| **High-rate PvP** | 8.6 | 400×–999× | Dinera, SimsonOTS, Axera, Holiday | Corrida por level, guerra de guild |
| **Global moderno** | 13–15 | 1×–25× | RubinOT, Taleon | Conteúdo oficial + sistemas próprios |
| **Retrô** | 7.4–7.7 | baixa | Tibiantis, Nostalrius, ClassicOT | Fidelidade ao Tibia antigo |

No dia da consulta, o topo da `ots-list.org` era **inteiramente** 8.6 com
400× — Dinera com 382 jogadores, SimsonOTS com 306, Axera com 190. O maior
servidor de protocolo moderno na mesma lista, o Taleon SA, aparecia com 82.

Isso não significa que 8.6 é "melhor". Significa que aquela lista mede um
mercado que **não é o nosso**. Um servidor 15.25 não compete por aqueles
jogadores; competir com eles em rate seria abandonar a razão de existir do
projeto.

O RubinOT — que é a referência declarada deste servidor — nem aparece nessas
listas, e tem **mais de 200 mil contas registradas**. Servidores grandes não
dependem de agregador.

---

## 2. Os diferenciais catalogados

### RubinOT — o mais próximo do que fazemos

Do wiki deles, os sistemas que o Tibia oficial não tem:

**Conforto (quality of life)**
- **Autoloot / Loot Pouch** — coleta automática de loot
- **Equipment Preset** — salvar e trocar conjuntos de equipamento
- **Huntfinder** — encontrar e organizar hunts
- **Interactive Map** — mapa melhor que o do client
- **Skill Calculator** — planejar progressão

**Progressão paralela ao level**
- **Battle Pass** — temporadas com recompensas (estavam na 4ª)
- **Obelisk System** — progressão/buff
- **Prestige Arena** — ranking de PvP
- **Castle System** — posse e disputa de castelo
- **Boosted Exercise** — treino de skill acelerado

**Sorte e economia**
- **Drop / Roulette System** — recompensa aleatória

**Conteúdo**
- **Linked Tasks** — tasks encadeadas, não avulsas
- Bosses, hunts e quests próprios, além do conteúdo oficial

**Cosmético**
- **Cosmetic Card System**, outfits, montarias e auras próprias
- Sprites customizadas, e sprites antigas para magias

### Taleon — a escola oposta dentro do mesmo protocolo

Protocolo moderno, mas **rate baixa** e não-PvP. Os diferenciais dele são de
outra natureza: **sistema anti-bot com GMs e denúncia**, Cast (assistir
jogador ao vivo), Rookgaard próprio com quest e casas, rates separadas para
skill e magic, autoloot. É um servidor que vende *controle e permanência*,
não velocidade.

Vale notar o contraste: RubinOT **libera** semi-bot de assistência; Taleon
**caça** bot. São teses opostas, e as duas funcionam — o que não funciona é
não ter tese.

### Retrô — vender ausência

Tibiantis, Nostalrius e ClassicOT competem por *não* ter coisas. O ClassicOT
chega a rodar sobre o código-fonte 7.7 decompilado, sem OTServ nem TFS, para
preservar o comportamento original. O diferencial é autenticidade, e a
detecção de bot é parte central da proposta.

---

## 3. O achado incômodo: o problema não é funcionalidade

As discussões do OTLand sobre por que servidores morrem apontam para outro
lugar, e isso é mais útil do que qualquer lista de sistemas:

- **Não entram jogadores novos no Tibia.** A base é a mesma envelhecendo.
- **Os jogadores pulam de servidor.** Abre tanto servidor que ninguém fixa —
  sempre tem um lançamento novo na esquina.
- **A corrida inicial é o produto.** Muita gente entra pela disputa do topo;
  quando ela acaba, saem em bloco.
- **O GM destrói o esforço acumulado.** Raid de exp e evento que facilita
  demais transformam em nada o que o veterano levou meses para conquistar.
  É a reclamação mais recorrente.

Ou seja: **o gargalo é retenção, não catálogo de sistemas.** Um servidor com
20 sistemas próprios e sem resposta para "por que eu continuo jogando no mês
3?" morre igual.

---

## 4. Onde estamos

| Diferencial | Nós | RubinOT | Observação |
|---|---|---|---|
| Hunt instanciada | ✅ 9 hunts | ❌ | **Ninguém grande tem isso** |
| Tradução PT-BR completa | ✅ 748 NPCs | ❌ | Nenhum concorrente oferece |
| Autoloot / Loot Pouch | ✅ | ✅ | Paridade |
| Semi-bot de assistência | ✅ AutoCaster | ✅ RTCaster | Paridade, mesma tese |
| Client próprio + updater | ✅ | ✅ | Paridade |
| Rates escalonadas | ✅ | ✅ | Paridade |
| Sprites/outfits próprios | ✅ parcial | ✅ | Eles têm muito mais |
| Task system | ❌ | ✅ linked | Lacuna |
| Battle pass / temporada | ❌ | ✅ | Lacuna |
| Equipment preset | ❌ | ✅ | Lacuna barata |
| Huntfinder | ❌ | ✅ | Temos as ferramentas de mapa |
| Roulette / drop | ❌ | ✅ | Lacuna |
| Cosméticos, montarias | ❌ | ✅ | Lacuna cara |
| Arena / castelo / ranking | ❌ | ✅ | Lacuna |

**Dois diferenciais reais, e são nossos sozinhos:**

**A hunt instanciada** ataca de frente um dos problemas de retenção mais
concretos do Tibia: disputa de spot. Não achei nenhum servidor grande com
isso. É o ativo mais valioso do projeto, e o mais difícil de copiar — foram
~6.250 linhas de Lua e um sistema de carga de mapa sob demanda.

**A tradução PT-BR completa** — 748 NPCs, 12.428 falas. O público brasileiro
é a maior fatia do mercado de OT e joga em inglês por falta de opção. Nenhum
concorrente oferece isso.

---

## 5. O que vale construir

Ordenado por retorno sobre esforço, considerando o que já existe aqui:

**1. Task system.** É a lacuna mais sentida. Task dá objetivo diário e
motivo para voltar — exatamente o que falta quando a corrida inicial acaba.
O RubinOT investiu em tasks *encadeadas*, não avulsas, o que sugere que a
versão simples não segura sozinha. O servidor já tem bestiário, que é meio
caminho.

**2. Equipment preset.** Barato e muito visível. É Lua puro, mexe só no
client e num par de comandos.

**3. Huntfinder.** Aqui há uma vantagem injusta: as ferramentas de
`tools/mapa` já sabem achar e contornar hunts pelo bestiário. Boa parte do
trabalho pesado está feita, só não está exposta ao jogador.

**4. Progressão de temporada (battle pass).** Responde diretamente ao "por
que eu continuo no mês 3?". É o mais caro dos quatro, e o que mais mexe em
economia — não faria antes dos outros três.

**O que eu não faria agora:** cosméticos, montarias e arena/castelo. São
caros, competem com o RubinOT no terreno *dele*, e não resolvem retenção —
resolvem monetização, que não é o problema aqui.

**E uma regra tirada do estudo, não um sistema:** não aplicar raid de exp
nem evento que desvalorize o esforço acumulado. É a queixa mais repetida em
servidor que esvaziou. Custa zero e é fácil de violar sem perceber.

---

## Fontes

- [ots-list.org](https://ots-list.org/) — listagem e contagem de jogadores
- [wiki.rubinot.com](https://wiki.rubinot.com/en) — catálogo de sistemas
- [OTLand: You guys do not understand why OTs are dying](https://otland.net/threads/you-guys-do-not-understand-why-ots-are-dying.267669/page-5)
- [OTLand: Why do oldschool servers not last?](https://otland.net/threads/why-do-oldschool-servers-not-last.297821/)
- [OTH Host: melhores OTServers](https://othhost.com.br/melhores-otservers-para-jogar-atualmente-lista-de-servidores-ot-populares/)
- [Taleon](https://taleon.online/) e [OT Archive: Taleon SA](https://otarchive.com/server/62cde2f41770eac22ec6ad0d)
- [OTLand: ClassicOT sobre o 7.7 decompilado](https://otland.net/threads/classicot-authentic-tibia-7-10-built-on-the-decompiled-7-7-by-fusion32.301670/)
