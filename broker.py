"""Conversa com a corretora (Alpaca): conta, relógio do mercado e, nas próximas fases, ordens."""

from alpaca.trading.client import TradingClient

from settings import Credenciais


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
        "status": str(conta.status),
        "patrimonio": float(conta.equity),
        "dinheiro": float(conta.cash),
        "poder_de_compra": float(conta.buying_power),
        "bloqueada": bool(conta.trading_blocked or conta.account_blocked),
        "mercado_aberto": bool(relogio.is_open),
        "proxima_abertura": relogio.next_open,
        "proximo_fechamento": relogio.next_close,
    }
