import numpy as np
import pandas as pd
import pytest

import estado as memoria

PARAMS = {"media_curta": 20, "media_longa": 50, "media_tendencia": 200,
          "atr_periodo": 14, "stop_atr": 2.0, "trailing_atr": 3.0}


def barras(fechamentos, inicio="2020-01-01", amplitude=0.01):
    """DataFrame diário falso a partir de uma lista de fechamentos."""
    c = pd.Series(np.asarray(fechamentos, dtype=float))
    idx = pd.bdate_range(inicio, periods=len(c), name="data")
    df = pd.DataFrame({"open": c.shift(1).fillna(c.iloc[0]).values, "close": c.values}, index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + amplitude)
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - amplitude)
    df["volume"] = 1_000_000.0
    return df[["open", "high", "low", "close", "volume"]]


def onda(n=900, base=100, seed=0):
    """Preço com tendência de alta e ondas, para gerar cruzamentos de médias."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return base * (1 + 0.001 * t) * (1 + 0.08 * np.sin(t / 30)) * np.exp(rng.normal(0, 0.004, n).cumsum() * 0.2)


@pytest.fixture
def config():
    return {
        "ativos": ["SPY", "AAPL"],
        "estrategia": dict(PARAMS),
        "risco": {"risco_por_operacao": 0.01, "max_posicoes": 5, "max_por_ativo": 0.20,
                  "trava_diaria": 0.03, "kill_switch": 0.10},
    }


@pytest.fixture(autouse=True)
def logs_temporarios(tmp_path, monkeypatch):
    """Nenhum teste pode escrever nos arquivos reais de logs/ (estado e operações)."""
    reais = (memoria.ARQUIVO_ESTADO, memoria.ARQUIVO_OPERACOES)
    antes = [p.read_bytes() if p.exists() else None for p in reais]
    monkeypatch.setattr(memoria, "ARQUIVO_ESTADO", tmp_path / "estado.json")
    monkeypatch.setattr(memoria, "ARQUIVO_OPERACOES", tmp_path / "operacoes.csv")
    yield
    depois = [p.read_bytes() if p.exists() else None for p in reais]
    assert antes == depois, "um teste mexeu nos arquivos reais de logs/"
