# economia do alt — de onde vem, pra onde vai

moedas: diamante (base), ametista (escassa), doces (evento) e xp.
buffs 2x (xp2, dima2, 30min) dobram o farm/xp por mensagem.

## diamante

entra:
- farm por msg: 2–6 (cooldown 60s, x2 com buff)
- daily: 100
- ptp: vitória 20, empate 5
- doces: 50 por 30🍬 (`dima50`)
- caixa comum: bônus 40–80 (30%)
- bet: slots até 10x, coin 2x, mines

sai:
- `>box`: 150
- bet: 1–1000 por aposta
- `>pay` (só gira entre players)

conta de bar: daily (100) + ~1 mês de farm ativo cobre 1 box (150) com folga.
bet rtp: slots 0.575, coin 0.5 — a banca segura ~45% no longo prazo.

## ametista

entra:
- daily: 2
- doces: 1 por 20🍬 (`ametista1`)
- caixa rara: bônus 2–4 (30%)

sai:
- `>roll`: 5 (1 axolotl)
- `>caixarara`: 15 (3 do pool raro)
- `>buy`: auras 10–200
- bet: 1–1000 por aposta

conta de bar: 1 daily = 40% de 1 roll. ametista é a moeda do gacha;
se sobrar demais, subir preço do roll/caixarara. se faltar, evento de doces.

## doces

entra: msg 1–3 (cooldown 60s, sem buff).

sai (loja, direto, sem sorteio):
- 20 = 1 ametista · 30 = 50 diamantes · 300 = bruxinho · 666 = demônio

## xp

entra: msg 10–25 (cooldown 60s, x2 com buff), quests 15+10+20,
streak +5/dia (teto 50). nível N pede N*100 xp.

## axolotls (18 espécies)

- giro normal: pesos somam 100 (roxo 0.1, o mais raro)
- rara: sem comum (roxo 1%, demônio 1%)
- exclusivos fora do giro (peso 0): bruxinho e demônio (doces ou rara)

## regras

- saldo nunca negativo (tudo checa antes de debitar).
- aposta/buy falhou = nada muda (sem meio-termo).
- mines persiste no banco: restart e timeout reembolsam.
- backup diário 04:00, retém 7, com integrity_check.
