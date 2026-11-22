"""Conversa com a corretora (Alpaca): conta, relógio do mercado, posições e ordens.

Regra: toda compra já sai com um stop loss na corretora (ordem OTO), para a posição
ficar protegida mesmo que o robô, a internet ou o servidor caiam.
"""

import time

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, OrderType, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    MarketOrderRequest,
    ReplaceOrderRequest,
    StopLossRequest,
    StopOrderRequest,
)

from settings import Credenciais

STATUS_ENCERRADOS = {"filled", "canceled", "expired", "rejected", "replaced", "done_for_day"}


def _valor(x):
    return getattr(x, "value", x)


def conectar(credenciais: Credenciais) -> TradingClient:
    """Cria a conexão com a Alpaca. paper=True usa a conta simulada."""
    return TradingClient(
        api_key=credenciais.api_key,
        secret_key=credenciais.secret_key,
        paper=credenciais.paper,
    )


def resumo_da_conta(cliente: TradingClient) -> dict:
    """Busca saldo e situação da conta e do mercado."""
    conta = cliente.get_account()
    relogio = cliente.get_clock()
    return {
        "status": str(_valor(conta.status)),
        "patrimonio": float(conta.equity),
        "patrimonio_ontem": float(conta.last_equity),
        "dinheiro": float(conta.cash),
        "poder_de_compra": float(conta.buying_power),
        "bloqueada": bool(conta.trading_blocked or conta.account_blocked),
        "mercado_aberto": bool(relogio.is_open),
        "agora": relogio.timestamp,
        "proxima_abertura": relogio.next_open,
        "proximo_fechamento": relogio.next_close,
    }


def posicoes(cliente: TradingClient) -> dict[str, dict]:
    return {
        p.symbol: {
            "qtd": float(p.qty),
            "preco_medio": float(p.avg_entry_price),
            "valor": float(p.market_value or 0),
        }
        for p in cliente.get_all_positions()
    }


def comprar_com_stop(cliente: TradingClient, simbolo: str, qtd: int, stop: float):
    """Compra a mercado e, assim que executar, a corretora já deixa um stop de venda ativo."""
    pedido = MarketOrderRequest(
        symbol=simbolo,
        qty=int(qtd),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.GTC,
        order_class=OrderClass.OTO,
        stop_loss=StopLossRequest(stop_price=round(stop, 2)),
    )
    return cliente.submit_order(pedido)


def ordens_stop_abertas(cliente: TradingClient, simbolo: str) -> list:
    """Ordens de stop de venda ainda ativas para o símbolo (inclusive as "pernas" de ordens OTO)."""
    ordens = cliente.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[simbolo], nested=True))
    encontradas = []
    for ordem in ordens:
        for o in [ordem, *(ordem.legs or [])]:
            if (
                o.symbol == simbolo
                and _valor(o.side) == OrderSide.SELL.value
                and _valor(o.type) in (OrderType.STOP.value, OrderType.STOP_LIMIT.value)
                and _valor(o.status) not in STATUS_ENCERRADOS
            ):
                encontradas.append(o)
    return encontradas


def criar_stop(cliente: TradingClient, simbolo: str, qtd: float, stop: float):
    pedido = StopOrderRequest(
        symbol=simbolo,
        qty=int(qtd),
        side=OrderSide.SELL,
        time_in_force=TimeInForce.GTC,
        stop_price=round(stop, 2),
    )
    return cliente.submit_order(pedido)


def subir_stop(cliente: TradingClient, ordem_id, novo_stop: float):
    return cliente.replace_order_by_id(ordem_id, ReplaceOrderRequest(stop_price=round(novo_stop, 2)))


def zerar(cliente: TradingClient, simbolo: str, espera_max: float = 15.0):
    """Vende a posição inteira: primeiro cancela os stops (senão as ações ficam "presas") e depois vende."""
    for ordem in ordens_stop_abertas(cliente, simbolo):
        cliente.cancel_order_by_id(ordem.id)
    limite = time.monotonic() + espera_max
    while ordens_stop_abertas(cliente, simbolo):
        if time.monotonic() > limite:
            raise RuntimeError(f"{simbolo}: os stops não foram cancelados a tempo; posição não foi vendida.")
        time.sleep(1)
    return cliente.close_position(simbolo)
