import numpy as np
import pandas as pd

from conftest import PARAMS, barras, onda
from strategy import CruzamentoMedias, atr, criar_estrategia, cruzou_para_cima, media_movel


def test_media_movel():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    m = media_movel(s, 3)
    assert m.isna().sum() == 2
    assert list(m.dropna()) == [2.0, 3.0, 4.0]


def test_atr_de_preco_que_oscila_sempre_igual():
    df = pd.DataFrame({"high": [11.0] * 30, "low": [9.0] * 30, "close": [10.0] * 30})
    assert abs(atr(df, 14).iloc[-1] - 2.0) < 1e-9


def test_cruzamento_so_no_dia_em_que_acontece():
    a = pd.Series([1, 2, 3, 4], dtype=float)
    b = pd.Series([2.5] * 4)
    assert list(cruzou_para_cima(a, b)) == [False, False, True, False]


def test_compra_exige_tendencia_de_alta():
    # sobe muito (acima da MM200), corrige e volta a subir -> cruzamento 20/50 para cima
    sobe = np.linspace(50, 150, 300)
    corrige = np.linspace(150, 130, 60)
    volta = np.linspace(130, 170, 80)
    df = CruzamentoMedias(PARAMS).preparar(barras(np.concatenate([sobe, corrige, volta])))
    entradas = df[df["entrada"]]
    assert len(entradas) >= 1
    assert (entradas["close"] > entradas["mm_tendencia"]).all()


def test_sem_compra_em_tendencia_de_baixa():
    desce = np.linspace(200, 80, 300)
    repique = np.linspace(80, 100, 80)
    df = CruzamentoMedias(PARAMS).preparar(barras(np.concatenate([desce, repique])))
    assert not df["entrada"].any()


def test_sem_sinal_antes_dos_indicadores_ficarem_prontos():
    df = CruzamentoMedias(PARAMS).preparar(barras(onda(400)))
    assert not df["entrada"].iloc[:199].any()
    assert not df["saida"].iloc[:49].any()


def test_stops():
    e = criar_estrategia({"estrategia": PARAMS})
    assert e.stop_inicial(100, 2) == 96
    assert e.stop_movel(110, 2) == 104
