# 🐉 Tibia OT Server — Global

Servidor de Tibia completo (estilo **Global**), baseado no [Canary](https://github.com/opentibiabr/canary) **v3.6.1** da OpenTibiaBR — o emulador de servidor mais atualizado da comunidade, compatível com o protocolo do Tibia 15.x. Inclui o datapack global completo (mapa do Tibia real, monstros, NPCs, quests, bosses, hunts).

> 📄 O README original do projeto Canary foi preservado em [`CANARY.md`](CANARY.md).

## ✅ Testado e funcionando

Este repositório foi validado de ponta a ponta em Ubuntu 24.04 (binário oficial v3.6.1 + MariaDB):

- Banco de dados criado a partir do `schema.sql` — 48 tabelas, conta `god` presente;
- Datapack **global completo** carregado (mapa `otservbr.otbm` de 177 MB, badges, títulos, todos os módulos Lua) em ~30 segundos, **zero erros no log**;
- Log final: `OTServBR-Global server online!`;
- Portas **7171** (login) e **7172** (game) abertas e aceitando conexões TCP;
- Consumo: ~1,3 GB de RAM com o mapa global carregado.

---

## 🚀 Rodando o servidor em minutos (Docker — sem compilar nada)

O jeito mais fácil: o Docker baixa o servidor pronto, o banco de dados, o site e o mapa automaticamente.

### 1. Instale o Docker

- **Windows/Mac:** [Docker Desktop](https://docs.docker.com/get-started/get-docker/)
- **Linux:** Docker Engine + Docker Compose v2

### 2. Clone este repositório

```bash
git clone https://github.com/cardosomatheus1/tibia.git
cd tibia/docker
```

### 3. Suba tudo

**Windows (PowerShell):**
```powershell
.\up.ps1
```

**Linux/macOS:**
```bash
sh ./up.sh
```

A primeira vez demora alguns minutos (baixa as imagens, monta o site e baixa o mapa global ~ centenas de MB). Acompanhe com `docker compose logs -f server`.

### 4. O que fica no ar

| Serviço | Endereço |
|---|---|
| Site + painel admin (MyAAC) | http://localhost:8080 |
| Login do client | http://localhost:8088/login |
| Porta do jogo | 7172 (login 7171, status 7173) |
| Banco MariaDB | interno (volume Docker) |

### 5. Contas padrão (⚠️ apenas para teste local!)

| Conta | Login | Senha |
|---|---|---|
| God (acesso total in-game) | `god` | `god` |
| Conta de teste | `@test1` | `test` |
| Admin do site MyAAC | `myaacadmin` | `admin123` |

---

## 🎮 Client (para jogar)

Você precisa de um client compatível com Tibia 13+/15. As duas opções recomendadas pelo próprio projeto:

1. **[Game Client (dudantas)](https://github.com/dudantas/tibia-client/releases/latest)** — client oficial adaptado para OT, já vem com os assets/sprites. **Mais fácil para começar.** Configure o endereço de login para `http://localhost:8088/login`.
2. **[OTClient Redemption (mehah)](https://github.com/mehah/otclient)** — client open source, altamente customizável, suporta protocolos 7.72 a 15.x.

### Jogando de outro PC da rede local

Suba com detecção de IP da LAN:

```powershell
.\up.ps1 -Lan          # Windows
```
```bash
LAN=true sh ./up.sh    # Linux/macOS
```

No outro PC, use `http://IP_DA_MAQUINA:8088/login` no client e `http://IP_DA_MAQUINA:8080` para o site.

---

## ⚙️ Configurando o seu servidor

- **`docker/.env`** — nome do servidor, IP anunciado, portas, senhas do banco e do site. Criado automaticamente a partir de [`docker/.env.dist`](docker/.env.dist) na primeira execução.
- **`config.lua.dist`** — todas as configurações do jogo (rates de XP/skill/loot, PvP, housing, etc.) para quem roda o servidor fora do Docker ou builda a própria imagem.
- **`data-otservbr-global/`** — o coração do jogo: scripts Lua de quests, monstros, NPCs, raids, eventos. É aqui que você customiza o conteúdo.
- **`schema.sql`** — estrutura do banco de dados (importada automaticamente no Docker).

---

## 🌍 Colocando online (VPS)

1. Contrate um VPS Linux (Ubuntu 24.04, mínimo 2 vCPU / 4 GB RAM; recomendado 4 vCPU / 8 GB).
2. Instale Docker e clone este repositório.
3. Edite `docker/.env`:
   - `CANARY_SERVER_IP` = IP público do VPS
   - `CANARY_TEST_ACCOUNTS=false`
   - Troque **todas** as senhas (`CANARY_DB_PASSWORD`, `CANARY_DB_ROOT_PASSWORD`, `MYAAC_ADMIN_PASSWORD`)
4. Libere as portas TCP no firewall: `7171`, `7172`, `8080`, `8088`.
5. `sh ./up.sh` e pronto.

> ⚠️ O quickstart Docker foi pensado para testes/LAN. Para produção séria, leia [`docker/DOCKER.md`](docker/DOCKER.md) e a [documentação oficial](https://docs.opentibiabr.com/).

---

## 🔨 Compilando do código-fonte (avançado, opcional)

Só é necessário se você quiser modificar o C++ do servidor:

- **Windows:** Visual Studio 2022 + vcpkg — [guia oficial](https://docs.opentibiabr.com/opentibiabr/projects/canary/getting-started)
- **Linux:** CMake + vcpkg (`./recompile.sh` como atalho)

---

## 🧰 Ferramentas úteis

| Ferramenta | Para quê |
|---|---|
| [Assets Editor](https://github.com/Arch-Mina/Assets-Editor) | Editar sprites/assets do client (Tibia 12+) |
| [Remere's Map Editor](https://github.com/opentibiabr/remeres-map-editor/) | Editar o mapa |
| [ClientConverter](https://github.com/Arch-Mina/ClientConverter) | Converter sprite sheets ↔ .spr/.dat |
| [OpenTibia Sprite Pack](https://github.com/peonso/opentibia_sprite_pack) | Sprites **livres** (CC-BY 4.0) para projetos próprios |
| [OTLand](https://otland.net/) | Maior fórum da comunidade OT |

---

## 📁 Estrutura do repositório

```
├── docker/                  # Quickstart Docker (server + banco + site + login)
├── data-otservbr-global/    # Datapack global (quests, monstros, NPCs, scripts)
├── data-canary/             # Datapack mínimo de testes
├── data/                    # Bibliotecas Lua compartilhadas (core)
├── src/                     # Código-fonte C++ do servidor
├── schema.sql               # Estrutura do banco de dados
├── config.lua.dist          # Modelo de configuração do servidor
└── CANARY.md                # README original do projeto Canary
```

---

## 📜 Créditos e licença

- Baseado no [Canary](https://github.com/opentibiabr/canary) v3.6.1, da comunidade [OpenTibiaBR](https://github.com/opentibiabr) — licença **GPL-2.0** (mantida em [`LICENSE`](LICENSE)).
- Tibia é marca registrada da CipSoft GmbH. Os assets/sprites originais do Tibia pertencem à CipSoft — este repositório contém apenas o emulador open source e dados da comunidade.
