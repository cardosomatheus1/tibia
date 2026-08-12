# Regras deste repositório

## Validar o que foi implementado — sempre

Nada é entregue como "pronto" sem ter sido executado. Revisar o código não
conta como teste. Se algo não puder ser testado, isso tem que ser **dito
explicitamente** ao usuário, não omitido.

Cada camada tem um jeito de validar. Use o que couber:

### Lua de servidor (datapack, migrations, NPCs, spells, quests)

Suba o servidor de verdade e leia o log:

```bash
service mariadb start                    # o container reseta; o banco não sobe sozinho
./canary-bin > /tmp/boot.log 2>&1 &
# esperar por "OTServBR-Global server online!" — leva 1–3 min
```

O teste só passa se aparecer `OTServBR-Global server online!` **e** não houver
`[error]`, `Lua Script Error` nem `nil value` no log. Migrations imprimem o
que fizeram — confira linha a linha, não só o "online".

Depois conferir o efeito no banco (`mysql -N -B canary -e "..."`), porque log
de sucesso não prova que gravou: uma coluna que não existe faz o save falhar
em silêncio.

Mate o processo ao terminar (`pkill -x canary-bin`).

### Lua de client (client-modules/)

**O otclient não roda aqui** — precisa de janela, OpenGL e 170+ MB de assets.
Então a lógica é exercitada num banco de prova que simula as APIs do client
(`g_keyboard`, `g_settings`, `g_game`, `modules`...), carrega o módulo real e
verifica o comportamento:

```bash
lua5.4 client-modules/autocaster/teste_teclas.lua
```

Use `client-modules/autocaster/teste_teclas.lua` como modelo — ele pesca os
locais do módulo pelos upvalues das funções globais (`debug.getupvalue`), o
que permite testar função interna sem exportar nada só para o teste.

Sintaxe, no mínimo, sempre: `luac -p arquivo.lua`.

### O que NÃO dá para validar aqui

Diga ao usuário quando cair nestes casos, em vez de deixar passar como testado:

- **Desenho de interface** (`.otui`): posição, tamanho, sobreposição.
- **Toque real de tecla** no client.
- **Qualquer coisa na VPS**: não há SSH nem rota de rede até ela daqui.
- **LibreOffice está quebrado** neste ambiente (não converte nem `.txt`), então
  não dá para renderizar `.docx`. Para PDF, use o Chromium headless em
  `/opt/pw-browsers/chromium-1194/chrome-linux/chrome --headless --print-to-pdf`,
  e confira as páginas com `gs -sDEVICE=png16m`.

## Fatos do ambiente que economizam tempo

- **Não compile o Canary.** O CI já produz o binário: workflow
  `build-manual.yml` → artefato `canary-linux-release`. O `ci.yml` não serve
  (o portão de formatação do stylua está vermelho e pula os builds).
- **`config.lua` é gitignored** — mudanças nele não vão em commit e precisam
  ser aplicadas à mão na VPS.
- **O protocolo do Tibia usa CP1252**, não UTF-8. Texto com acento que vai
  para o client precisa estar nessa codificação.
- **Deploy é manual**: commit e push aqui; o usuário atualiza a VPS.

## Ao mexer em conteúdo do Canary

Antes de chamar algo de bug nosso, veja se o arquivo é nosso:
`git log --oneline -- <arquivo>`. Se o único commit for o inicial
(`Adiciona servidor Tibia Global completo`), é conteúdo do upstream — a
correção certa pode ser atualizar a base, não remendar.
