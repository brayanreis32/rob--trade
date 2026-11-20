"""Ponto de entrada do robô.

Fase 1: só conecta na conta e mostra o saldo. Nenhuma ordem é enviada.
Uso:  python main.py
"""

import logging
import sys

import broker
from settings import PASTA_PROJETO, ErroConfiguracao, carregar_credenciais

PASTA_LOGS = PASTA_PROJETO / "logs"
PASTA_LOGS.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(PASTA_LOGS / "robo.log", encoding="utf-8")],
)
log = logging.getLogger("robo")


def dolar(valor: float) -> str:
    return f"US$ {valor:,.2f}"


def main() -> int:
    try:
        credenciais = carregar_credenciais()
        cliente = broker.conectar(credenciais)
        resumo = broker.resumo_da_conta(cliente)
    except ErroConfiguracao as erro:
        log.error("Configuração: %s", erro)
        print(f"ERRO: {erro}")
        return 1
    except Exception as erro:  # sem internet, chave inválida, API fora do ar...
        log.exception("Falha ao falar com a Alpaca")
        print(f"ERRO ao conectar na Alpaca: {erro}")
        print("Confira as chaves no .env e sua internet. Nada foi feito.")
        return 1

    modo = "PAPER (dinheiro fictício)" if credenciais.paper else "LIVE (DINHEIRO REAL)"
    print(f"\nConectado à Alpaca - modo {modo}")
    print(f"  Status da conta:  {resumo['status']}")
    print(f"  Patrimônio:       {dolar(resumo['patrimonio'])}")
    print(f"  Dinheiro:         {dolar(resumo['dinheiro'])}")
    print(f"  Poder de compra:  {dolar(resumo['poder_de_compra'])}")
    if resumo["bloqueada"]:
        print("  ATENÇÃO: a conta está bloqueada para operar.")
    if resumo["mercado_aberto"]:
        print(f"  Mercado: ABERTO (fecha em {resumo['proximo_fechamento']})")
    else:
        print(f"  Mercado: FECHADO (abre em {resumo['proxima_abertura']})")

    log.info("Conectado (%s). Patrimônio %s", modo, dolar(resumo["patrimonio"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
