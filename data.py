"""Baixa dados diários da Alpaca e confere se eles fazem sentido."""

from datetime import date, datetime, timedelta, timezone

import pandas as pd
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame

from settings import Credenciais

COLUNAS = ["open", "high", "low", "close", "volume"]
FUSO_BOLSA = "America/New_York"


def conectar(credenciais: Credenciais) -> StockHistoricalDataClient:
    return StockHistoricalDataClient(credenciais.api_key, credenciais.secret_key)


def _para_datas_da_bolsa(indice: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Converte horários UTC da Alpaca para a data do pregão em Nova York."""
    return pd.DatetimeIndex(indice.tz_convert(FUSO_BOLSA).date, name="data")


def baixar_diario(cliente, simbolos: list[str], anos: float, feed: str = "sip") -> dict[str, pd.DataFrame]:
    """Baixa `anos` de barras diárias (ajustadas por splits e dividendos) para cada símbolo.

    No plano grátis da Alpaca, o feed "sip" (todas as bolsas) tem atraso de 15 minutos,
    por isso o pedido termina 16 minutos atrás.
    """
    fim = datetime.now(timezone.utc) - timedelta(minutes=16)
    inicio = fim - timedelta(days=int(365.25 * anos) + 10)
    pedido = StockBarsRequest(
        symbol_or_symbols=list(simbolos),
        timeframe=TimeFrame.Day,
        start=inicio,
        end=fim,
        adjustment=Adjustment.ALL,
        feed=DataFeed(feed),
    )
    barras = cliente.get_stock_bars(pedido).df
    resultado = {}
    if barras.empty:
        return resultado
    presentes = set(barras.index.get_level_values(0))
    for simbolo in simbolos:
        if simbolo not in presentes:
            continue
        df = barras.xs(simbolo, level=0)[COLUNAS].astype(float)
        df.index = _para_datas_da_bolsa(df.index)
        resultado[simbolo] = df[~df.index.duplicated(keep="last")].sort_index()
    return resultado


def completar_com_hoje(cliente, dados: dict[str, pd.DataFrame], hoje: date) -> None:
    """Se a barra de hoje não veio no histórico, usa o "snapshot" em tempo real (feed IEX, grátis)."""
    faltando = [s for s, df in dados.items() if df.empty or df.index[-1].date() != hoje]
    if not faltando:
        return
    fotos = cliente.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=faltando, feed=DataFeed.IEX))
    for simbolo in faltando:
        barra = getattr(fotos.get(simbolo), "daily_bar", None)
        if barra is None:
            continue
        dia = pd.Timestamp(barra.timestamp).tz_convert(FUSO_BOLSA).date()
        if dia != hoje:
            continue
        linha = pd.DataFrame(
            [[barra.open, barra.high, barra.low, barra.close, barra.volume]],
            columns=COLUNAS,
            index=pd.DatetimeIndex([pd.Timestamp(dia)], name="data"),
        ).astype(float)
        dados[simbolo] = pd.concat([dados[simbolo], linha])


def validar(df: pd.DataFrame | None, minimo_barras: int, hoje: date | None = None) -> list[str]:
    """Lista de problemas nos dados (lista vazia = dados ok). Dado estranho = não operar."""
    if df is None or df.empty:
        return ["sem dados"]
    problemas = []
    if len(df) < minimo_barras:
        problemas.append(f"só {len(df)} dias de histórico (precisa de {minimo_barras})")
    recentes = df.tail(minimo_barras)
    if recentes[COLUNAS[:4]].isna().any().any():
        problemas.append("há preços vazios")
    if (recentes[COLUNAS[:4]] <= 0).any().any():
        problemas.append("há preços zerados ou negativos")
    if (recentes["high"] < recentes["low"]).any():
        problemas.append("máxima menor que a mínima")
    variacao = recentes["close"].pct_change().abs().max()
    if variacao > 0.5:
        problemas.append(f"variação de {variacao:.0%} em um dia (dado suspeito)")
    if hoje is not None and df.index[-1].date() != hoje:
        problemas.append(f"último dado é de {df.index[-1].date()}, não de hoje ({hoje})")
    return problemas
