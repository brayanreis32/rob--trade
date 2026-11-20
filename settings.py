"""Carrega as configurações do robô: chaves (.env), modo de operação e config.yaml.

Regra de segurança nº 1: o robô roda SEMPRE em paper trading, a não ser que
MODO=LIVE esteja no .env E a pessoa digite a frase de confirmação no terminal.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PASTA_PROJETO = Path(__file__).resolve().parent
FRASE_CONFIRMACAO = "EU ACEITO OPERAR COM DINHEIRO REAL"


class ErroConfiguracao(Exception):
    """Algo está faltando ou errado na configuração. O robô não deve operar."""


@dataclass
class Credenciais:
    api_key: str
    secret_key: str
    paper: bool  # True = conta simulada, False = dinheiro real


def carregar_config(caminho: Path = PASTA_PROJETO / "config.yaml") -> dict:
    """Lê o config.yaml e devolve um dicionário com os parâmetros."""
    with open(caminho, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def decidir_modo(modo_env: str | None, perguntar=input) -> bool:
    """Decide se o robô roda em paper. Devolve True para paper, False para real.

    Qualquer valor diferente de "LIVE" (inclusive vazio ou errado) vira PAPER.
    Para LIVE, a pessoa precisa digitar exatamente a frase de confirmação.
    """
    modo = (modo_env or "PAPER").strip().upper()
    if modo != "LIVE":
        return True

    print("\n*** ATENÇÃO: MODO=LIVE está ativo no .env. O robô usaria DINHEIRO REAL. ***")
    print(f'Para continuar, digite exatamente: {FRASE_CONFIRMACAO}')
    resposta = perguntar("> ").strip()
    if resposta != FRASE_CONFIRMACAO:
        raise ErroConfiguracao("Confirmação não recebida. Nada foi feito; o robô não vai operar.")
    return False


def carregar_credenciais(perguntar=input) -> Credenciais:
    """Lê as chaves do .env. Se faltar alguma, para com uma mensagem clara."""
    load_dotenv(PASTA_PROJETO / ".env")
    api_key = os.getenv("ALPACA_API_KEY", "").strip()
    secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()

    if not api_key or not secret_key or api_key.startswith("cole_aqui"):
        raise ErroConfiguracao(
            "Chaves da Alpaca não encontradas. Copie .env.example para .env "
            "e preencha ALPACA_API_KEY e ALPACA_SECRET_KEY (veja o README)."
        )

    paper = decidir_modo(os.getenv("MODO"), perguntar)
    return Credenciais(api_key=api_key, secret_key=secret_key, paper=paper)
