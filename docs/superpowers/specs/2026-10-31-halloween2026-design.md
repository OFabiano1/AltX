# especificação — conquista halloween 2026 + daily do dia 31

combinado no chat em 31/10/2026. vale uma única rodada.

## intent

dar uma marca do halloween de 2026: quem resgatar o `>daily`/`/daily` no dia 31/10/2026 leva um pacote de festa e desbloqueia a conquista "halloween 2026", visível pra sempre no `>saldo`.

## decisões (escolhidas pelo dono no brainstorm)

- janela da conquista e do bônus: **só o dia 31/10/2026**, fuso UTC-3 (mesmo do countdown da cog halloween). 22h de br de 31/10 ainda vale; 00h de br de 01/11 fecha.
- pacote do dia 31 (em cima do daily normal de 100 💎 + 2 🟣): **+50 💎, +1 🟣, +20 🍬** e a conquista.
- doces caem na **mesma transação** do daily (`tentar_daily`), sem janela de perda.
- display da conquista: campo "🏅 conquistas" no `>saldo`/`/saldo`. o card png do `>player` não entra.
- base de conquistas mínima (tabela + `dar_conquista` + `conquistas_de` em `data.py`); as 14 conquistas antigas não voltam — catálogo de exibição fica em `cogs/halloween.py`.

## não-metas

- reintroduzir o sistema geral de conquistas (ripado em `fix conquistas`).
- mexer no farm de doces por mensagem, no countdown ou na loja.
- mudar card do `>player`.
- nada de mensagem diferenciada no daily nos outros dias do mês.
