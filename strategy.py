"""Indicadores e sinais de compra/venda.

Para criar outra estratégia: faça uma classe filha de `Estrategia` que preencha as
colunas `entrada`, `saida` e `atr` em `preparar()`, e registre-a em ESTRATEGIAS.
"""

import pandas as pd


# ---------------------------------------------------------------- indicadores

def media_movel(serie: pd.Series, periodo: int) -> pd.Series:
    """Média simples dos últimos `periodo` dias (vazio até ter dias suficientes)."""
    return serie.rolling(periodo, min_periods=periodo).mean()


def atr(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    """Average True Range (média de Wilder): quanto o preço costuma oscilar por dia."""
    fechamento_anterior = df["close"].shift(1)
    faixa = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - fechamento_anterior).abs(),
            (df["low"] - fechamento_anterior).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return faixa.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()


def cruzou_para_cima(a: pd.Series, b: pd.Series) -> pd.Series:
    """True no dia em que `a` passa de baixo (ou igual) para cima de `b`."""
    return (a > b) & (a.shift(1) <= b.shift(1))


# ----------------------------------------------------------------- estratégias

class Estrategia:
    """Base de toda estratégia. Cada linha do DataFrame é um dia."""

    nome = "base"

    def __init__(self, params: dict):
        self.params = params

    def preparar(self, df: pd.DataFrame) -> pd.DataFrame:
        """Devolve uma cópia do df com as colunas `atr`, `entrada` e `saida`."""
        raise NotImplementedError

    def stop_inicial(self, preco: float, atr_hoje: float) -> float:
        return preco - self.params["stop_atr"] * atr_hoje

    def stop_movel(self, maior_fechamento: float, atr_hoje: float) -> float:
        """Stop que sobe junto com o preço (nunca desce: quem chama usa o maior)."""
        return maior_fechamento - self.params["trailing_atr"] * atr_hoje


class CruzamentoMedias(Estrategia):
    """Compra quando a MM curta cruza a MM longa para cima, com preço acima da MM de tendência.
    Vende quando a MM curta cruza a longa para baixo (os stops ficam na corretora)."""

    nome = "cruzamento_medias"

    def preparar(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        out["mm_curta"] = media_movel(out["close"], p["media_curta"])
        out["mm_longa"] = media_movel(out["close"], p["media_longa"])
        out["mm_tendencia"] = media_movel(out["close"], p["media_tendencia"])
        out["atr"] = atr(out, p["atr_periodo"])

        acima_da_tendencia = out["close"] > out["mm_tendencia"]
        indicadores_prontos = out[["mm_curta", "mm_longa", "mm_tendencia", "atr"]].notna().all(axis=1)
        out["entrada"] = (
            cruzou_para_cima(out["mm_curta"], out["mm_longa"]) & acima_da_tendencia & indicadores_prontos
        )
        out["saida"] = cruzou_para_cima(out["mm_longa"], out["mm_curta"]) & indicadores_prontos
        return out


ESTRATEGIAS = {CruzamentoMedias.nome: CruzamentoMedias}


def criar_estrategia(config: dict) -> Estrategia:
    params = dict(config["estrategia"])
    nome = params.pop("nome", CruzamentoMedias.nome)
    if nome not in ESTRATEGIAS:
        raise ValueError(f"Estratégia desconhecida no config.yaml: {nome}")
    return ESTRATEGIAS[nome](params)
