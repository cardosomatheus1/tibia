/**
 * Canary - A free and open-source MMORPG server emulator
 * Copyright (©) 2019–present OpenTibiaBR <opentibiabr@outlook.com>
 * Repository: https://github.com/opentibiabr/canary
 * License: https://github.com/opentibiabr/canary/blob/main/LICENSE
 * Contributors: https://github.com/opentibiabr/canary/graphs/contributors
 * Website: https://docs.opentibiabr.com/
 */

#pragma once

// Janela de mapa que o servidor mantem para o client. O padrao do Tibia e' 8/6
// (18x14 tiles), e a tela desenha 15x11 -- ou seja, so 1,5 tile de folga de
// cada lado.
//
// POR QUE FOI AUMENTADO. A folga e' o que o client tem para desenhar enquanto
// espera a proxima fatia de mapa. O servidor manda UMA coluna por passo, e o
// passo mais rapido do engine e' o SERVER_BEAT: 50 ms, ou 20 tiles por
// segundo. Com 124 ms de ida-e-volta ate o servidor, o jogador percorre 2,5
// tiles antes de a fatia chegar -- mais que os 1,5 de folga, e a borda da tela
// fica sem desenhar. Um jogador comum anda 0,2 tile por RTT e nunca ve isso;
// quem tem setmaxspeed (GOD, 65535) ve o tempo todo.
//
// 11/9 da 24x20, ou 4,5 tiles de folga de cada lado.
//
// O CLIENT PRECISA CONCORDAR. Ele dimensiona TODA leitura de mapa pelo proprio
// aware range (protocolgameparse.cpp: setMapDescription com range.horizontal()
// e range.vertical()), entao um valor diferente aqui desalinha o fluxo de
// bytes e derruba a conexao. Quem alinha e' o sendMapAwareRange, enviado no
// login ANTES da primeira descricao de mapa. Client sem suporte a esse opcode
// (o oficial da CipSoft) nao funciona com estes valores.
//
// Efeito colateral consciente: o servidor tem de enxergar pelo menos o que o
// client enxerga, entao alcance de perseguicao de monstro, de experiencia
// compartilhada e de espectadores de magia crescem junto.
static constexpr int32_t MAP_MAX_CLIENT_VIEW_PORT_X = 11;
static constexpr int32_t MAP_MAX_CLIENT_VIEW_PORT_Y = 9;
static constexpr int32_t MAP_MAX_VIEW_PORT_X = MAP_MAX_CLIENT_VIEW_PORT_X + 3; // min value: maxClientViewportX + 1
static constexpr int32_t MAP_MAX_VIEW_PORT_Y = MAP_MAX_CLIENT_VIEW_PORT_Y + 5; // min value: maxClientViewportY + 1

static constexpr int8_t MAP_MAX_LAYERS = 16;
static constexpr int8_t MAP_INIT_SURFACE_LAYER = 7; // (MAP_MAX_LAYERS / 2) -1
static constexpr int8_t MAP_LAYER_VIEW_LIMIT = 2;

// SECTOR_SIZE must be power of 2 value
// The bigger the SECTOR_SIZE is the less hash map collision there should be but it'll consume more memory
static constexpr int32_t SECTOR_SIZE = 16;
static constexpr int32_t SECTOR_MASK = SECTOR_SIZE - 1;
