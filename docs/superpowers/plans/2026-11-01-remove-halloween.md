# remoção do halloween (cog + doces) — plano

> **For agentic workers:** required sub-skill tests first, suite green = done.

**goal:** tirar tudo de halloween do código: cog `halloween`, sistema de doces (farm, loja, comandos), pacote/conquista no `>daily` e display de conquistas no `>saldo`. dados no banco ficam intocados — sem DROP de tabela, sem reset de doces fora do `>resetuser`.

**decisão:** escolha do dono: "remoção total do código". conquistas/doces ficam no banco sem display; base genérica de conquistas em `data.py` (`dar_conquista`, `conquistas_de`, tabela) fica — não é halloween, é infra de dados.

**padrão de ordem (TDD invertido pra deleção):** teste ajustado/deletado primeiro → roda → cod deletado → suíte toda verde fecha cada task.

## cortes por arquivo

- `main.py`: fora `cogs.halloween` do COGS, `Halloween` de ORDEM_AJUDA e CATEGORIA_EMOJIS.
- `visual.py`: fora `Halloween` de CATEGORIAS.
- DELETE `cogs/halloween.py` (cog toda: countdown, farm de doces, >doces, >topdoces, >halloween, catalogo/linha_conquista).
- `cogs/economia.py`: fora bonus_hoje + constantes de halloween + pacote no _daily/daily/daily_slash (revert diário ao original 3-tuple), fora campo conquistas em saldo/saldo_slash, fora DOCES_LOJA + seção "Doces" da loja + _trocar_doces/_buy_doces + LOJA_EMOJIS["Doces"], fora 🍬 da linha de saldo da loja.
- `data.py`: fora funções de doces (buscar_doces, ganhar_doces, gastar_doces, top_doces), fora tabela doces do SCHEMA (dados de boa em dbs existentes), tentar_daily reverte (3-tuple, sem doces/conquista), fora doces do snapshot e do resumo do reset; reset_usuario mantém `("doces", "user_id")` nos alvos (try/except cobre tabela ausente); conquistas (schema + funcs) ficam.
- `tests/`: fora test_conquista.py; em test_dinheiro.py fora os 4 testes de halloween/doces e revert test_daily_1x_por_dia ao 3-tuple e test_gastar_doces; em test_reset.py fora linhas de doces (asserts de conquista ficam).
- `docs/ECONOMIA.md`: fora seção doces + menções (daily volta 100/2).
- `README.md`: fora linha "doces", >halloween em extras e o bônus do daily.

## não toca

- dados no banco (nenhum DROP, nenhum UPDATE).
- base genérica de conquistas em data.py + seu teste.
- reset_usuario limpando doces (proteção de dados).
- AGENTS.md (arquivo do dono — lembrete manual no fim).
- docs/superpowers (histórico dos planos de ontem, no git).

## pós-código (fora do repo, com consentimento)

- status da call permanece "faltam 364 dias" setado pela última rodada da cog — sem a cog nada limpa sozinho. proponho no fim: script one-shot local (busca o text channel? não — só o edit voice status) com o token do .env, OU limpeza manual no Discord.
