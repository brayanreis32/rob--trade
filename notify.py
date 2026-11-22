"""Avisos pelo Telegram. Se o Telegram não estiver configurado, o aviso só vai para o log.

Um aviso que falha NUNCA derruba o robô.
"""

import logging
import os

import requests
from dotenv import load_dotenv

from settings import PASTA_PROJETO

log = logging.getLogger("robo")


def _configuracao() -> tuple[str, str]:
    load_dotenv(PASTA_PROJETO / ".env")
    return os.getenv("TELEGRAM_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def enviar(texto: str) -> bool:
    """Manda `texto` para o seu Telegram. Devolve True se chegou."""
    log.info("AVISO: %s", texto.replace("\n", " | "))
    token, chat_id = _configuracao()
    if not token or not chat_id:
        return False
    try:
        resposta = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": texto[:4000]},
            timeout=15,
        )
        resposta.raise_for_status()
        return True
    except Exception as erro:  # o aviso falhou, mas o robô segue
        log.error("Falha ao enviar aviso pelo Telegram: %s", str(erro).replace(token, "***"))
        return False
