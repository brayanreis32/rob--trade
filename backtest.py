"""Fase 3: simula a estratégia no passado, com custos, e compara com comprar e segurar o SPY.

Uso:  python backtest.py            (8 anos de dados: ~7 de teste + 1 de aquecimento)
      python backtest.py --anos 12

Como a simulação funciona (dia a dia, para todos os ativos juntos):
  1. Durante o dia: se a mínima tocar o stop, vende no stop (ou na abertura, se abriu abaixo).
  2. No fechamento: vende o que deu sinal de saída e compra o que deu sinal de entrada,
     no preço de fechamento (o robô real opera ~15 min antes do fechamento).
  3. Depois do fechamento: sobe o stop móvel para o dia seguinte.
  Custo + slippage: 0,05% em cada compra e em cada venda.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from risk import RegrasRisco, kill_switch_disparou, tamanho_posicao, trava_diaria_ativa
from strategy import Estrategia

PASTA_RELATORIOS = Path(__file__).resolve().parent / "relatorios"
COLUNAS_OPERACOES = ["simbolo", "entrada", "preco_entrada", "saida", "preco_saida", "qtd", "motivo",
                     "resultado", "resultado_pct"]


@dataclass
class Resultado:
    curva: pd.Series  # patrimônio no fechamento de cada dia
    operacoes: pd.DataFrame
    kill_switch_em: pd.Timestamp | None = None
    metricas: dict = field(default_factory=dict)


def simular(
    dados: dict[str, pd.DataFrame],
    estrategia: Estrategia,
    regras: RegrasRisco,
    inicio=None,
    fim=None,
    capital: float = 100_000.0,
    custo: float = 0.0005,
) -> Resultado:
    prep = {s: estrategia.preparar(df) for s, df in dados.items()}
    todas = sorted(set().union(*[df.index for df in prep.values()]))
    datas = [d for d in todas if (inicio is None or d >= inicio) and (fim is None or d <= fim)]

    caixa = capital
    posicoes: dict[str, dict] = {}
    operacoes = []
    curva = {}
    ultimo_fechamento: dict[str, float] = {}
    patrimonio_ontem = pico = capital
    kill_switch_em = None

    def vender(simbolo, dia, preco, motivo):
        nonlocal caixa
        pos = posicoes.pop(simbolo)
        recebido = pos["qtd"] * preco * (1 - custo)
        caixa += recebido
        operacoes.append({
            "simbolo": simbolo, "entrada": pos["data"], "preco_entrada": pos["preco"],
            "saida": dia, "preco_saida": preco, "qtd": pos["qtd"], "motivo": motivo,
            "resultado": recebido - pos["custo_total"],
            "resultado_pct": recebido / pos["custo_total"] - 1,
        })

    for dia in datas:
        hoje = {s: df.loc[dia] for s, df in prep.items() if dia in df.index}
        for s, linha in hoje.items():
            ultimo_fechamento[s] = linha["close"]

        # 1. stops durante o dia
        for s in list(posicoes):
            if s in hoje and hoje[s]["low"] <= posicoes[s]["stop"]:
                vender(s, dia, min(hoje[s]["open"], posicoes[s]["stop"]), "stop")

        # 2a. saídas por sinal
        for s in list(posicoes):
            if s in hoje and hoje[s]["saida"]:
                vender(s, dia, hoje[s]["close"], "sinal de saída")

        patrimonio = caixa + sum(p["qtd"] * ultimo_fechamento[s] for s, p in posicoes.items())
        pico = max(pico, patrimonio)
        if kill_switch_em is None and kill_switch_disparou(patrimonio, pico, regras):
            kill_switch_em = dia

        # 2b. entradas (a trava diária bloqueia novas compras)
        if not trava_diaria_ativa(patrimonio, patrimonio_ontem, regras):
            for s in dados:  # ordem do config.yaml
                if len(posicoes) >= regras.max_posicoes:
                    break
                linha = hoje.get(s)
                if s in posicoes or linha is None or not linha["entrada"]:
                    continue
                preco = linha["close"]
                stop = estrategia.stop_inicial(preco, linha["atr"])
                qtd = tamanho_posicao(patrimonio, caixa / (1 + custo), preco, stop, regras)
                if qtd < 1:
                    continue
                custo_total = qtd * preco * (1 + custo)
                caixa -= custo_total
                posicoes[s] = {"qtd": qtd, "preco": preco, "data": dia, "stop": stop,
                               "stop_inicial": stop, "maior": preco, "custo_total": custo_total}

        # 3. stop móvel para amanhã (só sobe)
        for s, pos in posicoes.items():
            if s in hoje:
                pos["maior"] = max(pos["maior"], hoje[s]["close"])
                pos["stop"] = max(pos["stop"], estrategia.stop_movel(pos["maior"], hoje[s]["atr"]))

        patrimonio = caixa + sum(p["qtd"] * ultimo_fechamento[s] for s, p in posicoes.items())
        curva[dia] = patrimonio
        patrimonio_ontem = patrimonio

    # posições ainda abertas no fim entram no relatório pelo último preço
    for s in list(posicoes):
        vender(s, datas[-1], ultimo_fechamento[s], "fim do teste (ainda aberta)")
    curva[datas[-1]] = caixa

    resultado = Resultado(
        curva=pd.Series(curva, name="patrimonio"),
        operacoes=pd.DataFrame(operacoes, columns=COLUNAS_OPERACOES),
        kill_switch_em=kill_switch_em,
    )
    resultado.metricas = metricas(resultado.curva, resultado.operacoes)
    return resultado


def comprar_e_segurar(df: pd.DataFrame, inicio, fim, capital: float = 100_000.0, custo: float = 0.0005) -> pd.Series:
    fechamentos = df["close"][(df.index >= inicio) & (df.index <= fim)]
    qtd = capital * (1 - custo) / fechamentos.iloc[0]
    return (fechamentos * qtd).rename("patrimonio")


def maior_queda(curva: pd.Series) -> float:
    return float((1 - curva / curva.cummax()).max())


def metricas(curva: pd.Series, operacoes: pd.DataFrame | None = None) -> dict:
    anos = max((curva.index[-1] - curva.index[0]).days / 365.25, 1e-9)
    total = curva.iloc[-1] / curva.iloc[0] - 1
    m = {
        "retorno_total": total,
        "retorno_anual": (1 + total) ** (1 / anos) - 1 if total > -1 else -1.0,
        "max_drawdown": maior_queda(curva),
    }
    if operacoes is not None:
        n = len(operacoes)
        ganhos = operacoes[operacoes["resultado"] > 0]["resultado"] if n else pd.Series(dtype=float)
        perdas = operacoes[operacoes["resultado"] <= 0]["resultado"] if n else pd.Series(dtype=float)
        m.update({
            "operacoes": n,
            "taxa_acerto": len(ganhos) / n if n else 0.0,
            "ganho_medio": float(ganhos.mean()) if len(ganhos) else 0.0,
            "perda_media": float(perdas.mean()) if len(perdas) else 0.0,
        })
    return m


def texto_metricas(titulo: str, m: dict, spy: dict, kill_switch_em=None) -> str:
    def pct(x):
        return f"{x * 100:+.1f}%"

    linhas = [
        f"\n=== {titulo} ===",
        f"{'':28}{'Robô':>12}{'SPY (segurar)':>16}",
        f"{'Retorno total':28}{pct(m['retorno_total']):>12}{pct(spy['retorno_total']):>16}",
        f"{'Retorno por ano':28}{pct(m['retorno_anual']):>12}{pct(spy['retorno_anual']):>16}",
        f"{'Maior queda (drawdown)':28}{pct(-m['max_drawdown']):>12}{pct(-spy['max_drawdown']):>16}",
        f"{'Número de operações':28}{m['operacoes']:>12}",
        f"{'Taxa de acerto':28}{m['taxa_acerto'] * 100:>11.0f}%",
        f"{'Ganho médio / perda média':28}{'US$ {:,.0f} / {:,.0f}'.format(m['ganho_medio'], m['perda_media']):>28}",
    ]
    if m["perda_media"]:
        linhas.append(f"{'Ganho médio ÷ perda média':28}{abs(m['ganho_medio'] / m['perda_media']):>12.2f}")
    if kill_switch_em is not None:
        linhas.append(f"ATENÇÃO: o kill switch (queda de 10% desde o topo) teria parado o robô em {kill_switch_em.date()}.")
    return "\n".join(linhas)


def grafico(curvas: dict[str, pd.Series], corte, caminho: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for nome, curva in curvas.items():
        ax.plot(curva.index, curva.values, label=nome, linewidth=1.6)
    ax.axvline(corte, color="gray", linestyle="--", linewidth=1)
    ax.text(corte, ax.get_ylim()[1], "  início da validação", va="top", color="gray")
    ax.set_title("Curva de patrimônio (US$ 100 mil iniciais)")
    ax.set_ylabel("US$")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    caminho.parent.mkdir(exist_ok=True)
    fig.savefig(caminho, dpi=120)
    plt.close(fig)


def rodar(dados, estrategia, regras, referencia="SPY", fracao_ajuste=0.7, aquecimento_dias=260):
    """Roda ajuste, validação e período completo. Devolve o texto do relatório e os resultados."""
    if referencia not in dados:
        raise ValueError(f"Preciso dos dados de {referencia} para comparar.")
    datas = dados[referencia].index
    if len(datas) <= aquecimento_dias + 50:
        raise ValueError("Histórico curto demais para o backtest.")
    datas_teste = datas[aquecimento_dias:]  # os primeiros dias só servem para calcular as médias
    inicio, fim = datas_teste[0], datas_teste[-1]
    corte = datas_teste[int(len(datas_teste) * fracao_ajuste)]

    periodos = {
        f"Ajuste ({inicio.date()} a {corte.date()})": (inicio, corte),
        f"VALIDAÇÃO, dados nunca vistos ({corte.date()} a {fim.date()})": (corte, fim),
        f"Completo ({inicio.date()} a {fim.date()})": (inicio, fim),
    }
    textos, resultados = [], {}
    for titulo, (a, b) in periodos.items():
        r = simular(dados, estrategia, regras, inicio=a, fim=b)
        spy = metricas(comprar_e_segurar(dados[referencia], a, b))
        textos.append(texto_metricas(titulo, r.metricas, spy, r.kill_switch_em))
        resultados[titulo] = r
    completo = resultados[list(periodos)[-1]]
    curvas = {"Robô": completo.curva, f"{referencia} (comprar e segurar)": comprar_e_segurar(dados[referencia], inicio, fim)}
    return "\n".join(textos), completo, curvas, corte


EXPLICACAO_OVERFITTING = """
Sobre "overfitting" (ajuste demais ao passado):
  O período de AJUSTE é onde você pode testar variações dos parâmetros. O período de
  VALIDAÇÃO são dados que a estratégia "nunca viu". Se você mexer nos parâmetros até o
  ajuste ficar lindo e a validação piorar, a estratégia decorou o passado e
  provavelmente vai falhar no futuro. Confie mais no resultado da VALIDAÇÃO, e não
  mexa nos parâmetros olhando para ela.
"""


def main():
    from data import baixar_diario, conectar
    from settings import carregar_config, carregar_credenciais
    from strategy import criar_estrategia

    parser = argparse.ArgumentParser(description="Backtest da estratégia")
    parser.add_argument("--anos", type=float, default=8, help="anos de dados a baixar (padrão 8)")
    args = parser.parse_args()

    config = carregar_config()
    credenciais = carregar_credenciais()
    ativos = list(dict.fromkeys(config["ativos"] + ["SPY"]))
    print(f"Baixando {args.anos:g} anos de dados de {len(ativos)} ativos...")
    dados = baixar_diario(conectar(credenciais), ativos, args.anos, feed=config.get("dados", {}).get("feed", "sip"))
    faltando = [s for s in ativos if s not in dados]
    if faltando:
        print(f"Sem dados para: {', '.join(faltando)} (ficam de fora)")

    texto, completo, curvas, corte = rodar(dados, criar_estrategia(config), RegrasRisco.do_config(config))
    print(texto)
    print(EXPLICACAO_OVERFITTING)

    PASTA_RELATORIOS.mkdir(exist_ok=True)
    grafico(curvas, corte, PASTA_RELATORIOS / "backtest.png")
    completo.operacoes.to_csv(PASTA_RELATORIOS / "backtest_operacoes.csv", index=False)
    (PASTA_RELATORIOS / "backtest.txt").write_text(texto + "\n" + EXPLICACAO_OVERFITTING, encoding="utf-8")
    print(f"Gráfico: {PASTA_RELATORIOS / 'backtest.png'}")
    print(f"Operações: {PASTA_RELATORIOS / 'backtest_operacoes.csv'}")


if __name__ == "__main__":
    main()
