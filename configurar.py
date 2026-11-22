"""Cria o arquivo .env com as suas chaves da Alpaca, no formato certo.

Uso:  python configurar.py
As chaves não aparecem na tela enquanto você cola (é de propósito).
"""

import getpass

from settings import PASTA_PROJETO

print("Cole cada chave e aperte Enter. Nada aparece enquanto você cola: é normal.")
key = getpass.getpass("API KEY da Alpaca: ").strip()
secret = getpass.getpass("SECRET KEY da Alpaca: ").strip()
telegram_token = getpass.getpass("Token do Telegram (Enter para pular): ").strip()
telegram_chat = input("Chat id do Telegram (Enter para pular): ").strip()

if not key or not secret:
    raise SystemExit("Uma das chaves ficou vazia. Nada foi salvo; rode de novo.")

(PASTA_PROJETO / ".env").write_text(
    f"ALPACA_API_KEY={key}\nALPACA_SECRET_KEY={secret}\nMODO=PAPER\n"
    f"TELEGRAM_TOKEN={telegram_token}\nTELEGRAM_CHAT_ID={telegram_chat}\n",
    encoding="utf-8",
)
print(f"Arquivo .env salvo (tamanhos: {len(key)} e {len(secret)}). Agora rode: python main.py")
