import pandas as pd

from backtest import comprar_e_segurar, maior_queda, rodar, simular
from conftest import PARAMS, barras, onda
from risk import RegrasRisco
from strategy import CruzamentoMedias


def dados_falsos():
    return {"SPY": barras(onda(1200, seed=1)), "AAPL": barras(onda(1200, base=50, seed=2))}


def test_backtest_roda_e_respeita_regras():
    r = simular(dados_falsos(), CruzamentoMedias(PARAMS), RegrasRisco())
    assert r.metricas["operacoes"] > 0
    assert (r.curva > 0).all()
    ops = r.operacoes
    assert (ops["saida"] >= ops["entrada"]).all()
    # nunca compra mais de 20% do patrimônio (com folga para o custo)
    assert (ops["qtd"] * ops["preco_entrada"] <= 0.2 * r.curva.max() * 1.01).all()


def test_custos_reduzem_o_resultado():
    d = dados_falsos()
    sem = simular(d, CruzamentoMedias(PARAMS), RegrasRisco(), custo=0.0)
    com = simular(d, CruzamentoMedias(PARAMS), RegrasRisco(), custo=0.0005)
    assert com.curva.iloc[-1] < sem.curva.iloc[-1]


def test_stop_com_gap_vende_na_abertura_e_custo_entra_na_conta():
    import numpy as np

    precos = np.concatenate([np.linspace(50, 150, 300), np.linspace(150, 130, 60), np.linspace(130, 170, 80)])
    prep = CruzamentoMedias(PARAMS).preparar(barras(precos))
    dia_compra = prep.index.get_loc(prep.index[prep["entrada"]][0])
    precos = list(precos[: dia_compra + 1])
    df = barras(precos + [precos[-1] * 0.80, precos[-1] * 0.80])  # despenca 20% no dia seguinte
    df.iloc[-2, df.columns.get_loc("open")] = precos[-1] * 0.85  # abre já bem abaixo do stop
    r = simular({"SPY": df}, CruzamentoMedias(PARAMS), RegrasRisco())
    op = r.operacoes.iloc[0]
    assert op["motivo"] == "stop"
    assert op["saida"] == df.index[-2]
    assert abs(op["preco_saida"] - precos[-1] * 0.85) < 1e-9  # vendeu na abertura, não no stop
    assert op["resultado"] < 0
    # perdeu mais que 1% por causa do gap: o stop não garante o preço
    assert r.metricas["max_drawdown"] > 0.01


def test_maior_queda():
    assert abs(maior_queda(pd.Series([100, 120, 90, 130])) - 0.25) < 1e-9


def test_comprar_e_segurar():
    df = barras([100, 110, 121])
    c = comprar_e_segurar(df, df.index[0], df.index[-1], custo=0)
    assert abs(c.iloc[-1] - 121_000) < 1e-6


def test_relatorio_tem_ajuste_e_validacao():
    texto, completo, curvas, corte = rodar(dados_falsos(), CruzamentoMedias(PARAMS), RegrasRisco())
    assert "Ajuste" in texto and "VALIDAÇÃO" in texto
    assert completo.curva.index[0] < corte < completo.curva.index[-1]
