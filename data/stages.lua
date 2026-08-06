-- Rates por faixa, copiadas do RubinOT (rubinot.com.br/serverinfo, lidas em
-- 2026-08-06) a pedido. Sao os numeros deles, nao estimativa nem arredondamento.
--
-- E' curva de high rate: 50x nos oito primeiros levels, 80x na faixa 9-50 e
-- caindo ate' 1.2x no fim. O pico NAO e' no level 1 -- comeca em 50x e so'
-- depois sobe para 80x.
--
-- Minlevel e multiplier sao OBRIGATORIOS. Maxlevel e' OPCIONAL e vale infinito
-- por padrao, por isso a ultima faixa de cada tabela nao tem.
--
-- So' vale com `rateUseStages = true` no config.lua; com false o servidor usa
-- rateExp/rateSkill/rateMagic como numero unico.

experienceStages = {
	{ minlevel = 1, maxlevel = 8, multiplier = 50 },
	{ minlevel = 9, maxlevel = 50, multiplier = 80 },
	{ minlevel = 51, maxlevel = 100, multiplier = 60 },
	{ minlevel = 101, maxlevel = 150, multiplier = 40 },
	{ minlevel = 151, maxlevel = 200, multiplier = 30 },
	{ minlevel = 201, maxlevel = 300, multiplier = 15 },
	{ minlevel = 301, maxlevel = 400, multiplier = 12 },
	{ minlevel = 401, maxlevel = 500, multiplier = 10 },
	{ minlevel = 501, maxlevel = 600, multiplier = 7 },
	{ minlevel = 601, maxlevel = 700, multiplier = 6 },
	{ minlevel = 701, maxlevel = 800, multiplier = 5 },
	{ minlevel = 801, maxlevel = 900, multiplier = 4 },
	{ minlevel = 901, maxlevel = 1000, multiplier = 3 },
	{ minlevel = 1001, maxlevel = 1200, multiplier = 2 },
	{ minlevel = 1201, maxlevel = 1400, multiplier = 1.5 },
	{ minlevel = 1401, multiplier = 1.2 },
}

-- Skill abre em 1 e magic em 0. E' assim na fonte: magic level de fato comeca
-- em 0, e a faixa de skill abre antes do 10 para nao deixar buraco.
skillsStages = {
	{ minlevel = 1, maxlevel = 80, multiplier = 10 },
	{ minlevel = 81, maxlevel = 100, multiplier = 7 },
	{ minlevel = 101, maxlevel = 120, multiplier = 4 },
	{ minlevel = 121, multiplier = 2 },
}

magicLevelStages = {
	{ minlevel = 0, maxlevel = 80, multiplier = 10 },
	{ minlevel = 81, maxlevel = 100, multiplier = 7 },
	{ minlevel = 101, maxlevel = 120, multiplier = 4 },
	{ minlevel = 121, maxlevel = 130, multiplier = 3 },
	{ minlevel = 131, multiplier = 2 },
}
