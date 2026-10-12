# isso aq e o sistema de conquistas: lista fixa + avaliacao por snapshot.
# tudo on-demand: o >player monta o snapshot do banco e desbloqueia
# o que bateu. sem hook espalhado, nada passa batido.

# id -> {icone, nome, desc}. ordem = ordem de exibicao.
CONQUISTAS = {
    "primeiro_daily": {"icone": "🌅", "nome": "bom dia",           "desc": "resgata o daily 1x"},
    "nivel5":         {"icone": "🛡️", "nome": "veterano",          "desc": "chega no nível 5"},
    "nivel10":        {"icone": "👑", "nome": "lenda do lago",     "desc": "chega no nível 10"},
    "streak7":        {"icone": "📅", "nome": "em chamas",         "desc": "streak de 7 dias"},
    "primeiro_raro":  {"icone": "💠", "nome": "sangue raro",       "desc": "tem 1 axolotl raro ou mais"},
    "lendario1":      {"icone": "✨", "nome": "caçador de lendas",  "desc": "tem 1 axolotl lendário"},
    "colecao_full":   {"icone": "🪸", "nome": "lago completo",     "desc": "tem todas as espécies"},
    "maratona_ptp":   {"icone": "🎲", "nome": "maratonista",       "desc": "joga 100 ptp"},
    "vinculado":      {"icone": "🔗", "nome": "conexão steam",     "desc": "vincula o deadlock"},
    "mil_dima":       {"icone": "💰", "nome": "cofre cheio",       "desc": "junta 1000 diamantes"},
    "doce100":        {"icone": "🍬", "nome": "mão cheia",         "desc": "junta 100 doces"},
    "aposta10":       {"icone": "🎰", "nome": "freguês do bet",    "desc": "faz 10 apostas"},
    "pe_quente":      {"icone": "🔥", "nome": "pé quente",         "desc": "ganha 5 apostas"},
    "diaria_full":    {"icone": "✅", "nome": "dia perfeito",      "desc": "fecha as 3 diárias do dia"},
}


def avaliar(snap: dict) -> list[str]:
    """ids desbloqueados pelo snapshot. snap: nivel, vinculado, dima,
    doces, tem_raro, tem_lendario, full, apostas, vitorias, streak,
    feitas_hoje, ptp_total, daily_vez."""
    ids = []
    if snap.get("daily_vez"):
        ids.append("primeiro_daily")
    if snap.get("nivel", 1) >= 5:
        ids.append("nivel5")
    if snap.get("nivel", 1) >= 10:
        ids.append("nivel10")
    if snap.get("streak", 0) >= 7:
        ids.append("streak7")
    if snap.get("tem_raro"):
        ids.append("primeiro_raro")
    if snap.get("tem_lendario"):
        ids.append("lendario1")
    if snap.get("full"):
        ids.append("colecao_full")
    if snap.get("ptp_total", 0) >= 100:
        ids.append("maratona_ptp")
    if snap.get("vinculado"):
        ids.append("vinculado")
    if snap.get("dima", 0) >= 1000:
        ids.append("mil_dima")
    if snap.get("doces", 0) >= 100:
        ids.append("doce100")
    if snap.get("apostas", 0) >= 10:
        ids.append("aposta10")
    if snap.get("vitorias", 0) >= 5:
        ids.append("pe_quente")
    if snap.get("feitas_hoje", 0) >= 3:
        ids.append("diaria_full")
    return ids


def linha(cid: str) -> str:
    """icone + nome pra exibir."""
    info = CONQUISTAS.get(cid, {"icone": "🏅", "nome": cid, "desc": ""})
    return f"{info['icone']} **{info['nome']}**"
