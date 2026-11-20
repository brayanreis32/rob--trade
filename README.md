# Robô de trade (bolsa dos EUA)

Robô em Python que opera ações e ETFs americanos pela API da **Alpaca**, sempre em
**conta simulada (paper trading)** por padrão.

> **Aviso:** projeto educativo, não é recomendação de investimento. Robôs de trade podem
> perder dinheiro. Rode em paper trading por meses antes de pensar em dinheiro real.

## Fases

| Fase | Situação |
|---|---|
| 1. Preparação: conectar na conta e mostrar o saldo | ✅ feita |
| 2. Dados e indicadores | ⏳ próxima |
| 3. Backtest | — |
| 4. Paper trading | — |
| 5. Alertas no Telegram | — |
| 6. Rodar sozinho na nuvem | — |

## Instalação

Precisa do Python 3.11 ou mais novo.

```bash
git clone https://github.com/brayanreis32/rob--trade.git
cd rob--trade
python3 -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Criando o arquivo `.env` (suas chaves)

1. Entre em [alpaca.markets](https://alpaca.markets), abra a conta **Paper** e clique em
   **Generate New Keys**.
2. Copie o modelo:
   ```bash
   cp .env.example .env          # no Windows: copy .env.example .env
   ```
3. Abra o `.env` num editor de texto e cole a **API Key** e a **Secret Key** no lugar de
   `cole_aqui_...`. Deixe `MODO=PAPER`.

O `.env` está no `.gitignore` e **nunca** vai para o GitHub. Não mande as chaves para
ninguém nem cole no chat.

## Rodando

```bash
python main.py
```

Se der certo, aparece algo assim:

```
Conectado à Alpaca - modo PAPER (dinheiro fictício)
  Status da conta:  AccountStatus.ACTIVE
  Patrimônio:       US$ 100,000.00
  ...
```

Testes automáticos:

```bash
pytest
```

## O que cada arquivo faz

- `settings.py`: lê as chaves do `.env`, o `config.yaml` e decide o modo (paper ou real).
- `broker.py`: conversa com a Alpaca (conta, relógio do mercado e, depois, ordens).
- `main.py`: o que você roda. Na Fase 1 só mostra o saldo.
- `config.yaml`: todos os parâmetros (ativos, médias, ATR, regras de risco).
- `logs/robo.log`: registro de tudo que o robô fez.
- `tests/`: testes automáticos.

## Segurança

- **Paper por padrão.** Dinheiro real só com `MODO=LIVE` no `.env` **e** digitando
  `EU ACEITO OPERAR COM DINHEIRO REAL` no terminal. Qualquer outro valor vira paper.
- Se faltar chave ou a conexão falhar, o robô para e não faz nada.
