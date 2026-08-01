# Ferramentas de protocolo 15.25

Duas ferramentas usadas para validar que o servidor fala mesmo o protocolo do
client Tibia **15.25** (`CLIENT_VERSION = 1525`, perfil `current`).

## `login_webservice.py` — serviço de login HTTP

Os clients Tibia 12+/15 não fazem login pela porta 7171: eles chamam um
webservice HTTP que devolve a *session key*, a lista de mundos e os
personagens. Este script implementa esse endpoint.

Com `authType = "password"` no `config.lua`, a session key é simplesmente
`email\nsenha` — por isso não é preciso banco de sessão.

```bash
sudo python3 tools/protocol/login_webservice.py 80
```

Depois aponte o client para ele em `conf/config.ini`:

```ini
loginWebService=http://127.0.0.1/login.php
clientWebService=http://127.0.0.1/login.php
```

Ajuste `IP`/`GAME_PORT` e a lista `CHARS` no topo do arquivo conforme o seu
servidor.

## `login_1525.py` — client de protocolo (sem gráficos)

Faz o handshake completo do protocolo 15.25 direto na porta do jogo, útil para
diagnosticar o servidor sem depender de client gráfico:

1. recebe o *challenge* do servidor (`timestamp` + `random`);
2. cifra a chave XTEA com a chave RSA do servidor (`key.pem`);
3. monta o pacote de login com a session key e o personagem;
4. decifra as respostas.

```bash
python3 tools/protocol/login_1525.py
```

Um login bem-sucedido aparece no log do servidor como:

```
Claude has logged in. (Protocol: 1525, Profile: current)
```

### Detalhes do contrato de rede (perfil `current`)

Descobertos na prática e úteis para quem for depurar o protocolo:

- **Enquadramento do pedido:** `[u16 blocos][u32 adler32][corpo]`, onde o corpo
  precisa ser múltiplo de 8 bytes — o servidor calcula o tamanho como
  `blocos * 8 + 4`.
- **Porta do jogo:** o servidor manda o challenge assim que a conexão abre, ou
  seja, **não** existe byte identificador de protocolo no primeiro pacote do
  client (diferente da porta de login).
- **Challenge do perfil moderno:** `[u32 checksum][0x01][0x1F][u32 timestamp][u8 random][0x71]`.
- **Bloco RSA (128 bytes):** `[0x00][chave XTEA 16B][flag gamemaster][session key][personagem][timestamp][random][probe OTCv8]`.
- O `clientVersion` enviado precisa bater exatamente com `CLIENT_VERSION` do
  servidor, senão a conexão é recusada.
