# Robô de trade (bolsa dos EUA)

Robô em Python que opera ações e ETFs americanos pela API da **Alpaca**, com gráfico
diário (swing trade). Por padrão roda **sempre em conta simulada (paper trading)**.

> **Aviso:** projeto educativo, não é recomendação de investimento. Robôs de trade podem
> perder dinheiro. Rode em paper trading por pelo menos 2 a 3 meses antes de pensar em
> dinheiro real, e só use um valor que você aceite perder.

## Fases

| Fase | Comando | Só avance quando... |
|---|---|---|
| 1. Preparação | `python main.py` | aparecer o saldo de US$ 100 mil fictícios |
| 2. Dados e indicadores | `python main.py sinais` | você entender média móvel e ATR (glossário abaixo) |
| 3. Backtest | `python backtest.py` | a VALIDAÇÃO for aceitável e a maior queda for algo que você aguentaria |
| 4. Paper trading | `python main.py rodar` | rodar 2 a 3 meses sem erros e parecido com o backtest |
| 5. Alertas | `python main.py telegram-teste` | os avisos chegarem, inclusive os de erro |
| 6. Nuvem | ver "Fase 6" | você conferir os logs diariamente por algumas semanas |

---

## Fase 1: instalação e conexão

Precisa do **Python 3.11 ou mais novo**.

```bash
git clone https://github.com/brayanreis32/rob--trade.git
cd rob--trade
python3 -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Criando o arquivo `.env` (suas chaves)

1. Entre em [alpaca.markets](https://alpaca.markets), abra a conta **Paper**, role a página
   inicial até a caixa **API Keys** (lado direito) e clique em **Generate New Keys**.
2. Rode `python configurar.py` e cole a **Key** e a **Secret** quando ele pedir (nada aparece
   na tela enquanto você cola; é de propósito). Ele cria o `.env` no formato certo, com `MODO=PAPER`.

O `.env` está no `.gitignore` e **nunca** vai para o GitHub. Não mande as chaves para
ninguém nem cole no chat.

```bash
python main.py
```

**O que pode dar errado:** chave da conta real em vez da Paper (erro de autorização);
espaço ou aspas sobrando no `.env`; Python antigo.

## Fase 2: dados e indicadores

```bash
python main.py sinais          # baixa 5 anos e mostra os sinais de hoje (não opera)
python main.py sinais --csv    # também salva os indicadores em relatorios/
```

Para cada ativo aparecem: fechamento, médias de 20, 50 e 200 dias, ATR, tendência e o
sinal do dia (`COMPRA`, `VENDA` ou `-`). Na maioria dos dias o sinal é `-`: cruzamentos
são raros, e isso é normal.

## Fase 3: backtest

```bash
python backtest.py             # 8 anos de dados (o primeiro ano só "aquece" as médias)
python backtest.py --anos 12
```

- Custos + slippage de **0,05% em cada compra e venda**.
- Usa as mesmas regras de risco do robô: 1% por operação, até 5 posições, até 20% por
  ativo, trava diária e stops (stop com "gap" vende na abertura, que pode ser pior que o stop).
- Separa os dados em **ajuste** (70% iniciais) e **validação** (30% finais, que a
  estratégia "nunca viu").
- Compara com simplesmente comprar e segurar o SPY.
- Gera `relatorios/backtest.png` (curva de patrimônio), `backtest_operacoes.csv` e `backtest.txt`.

**Overfitting:** se você mexer nos parâmetros do `config.yaml` até o passado ficar
perfeito, a estratégia "decora" o passado e quase sempre falha no futuro. Teste
variações olhando só o período de ajuste, e confie mais no resultado da validação.

## Fase 4: paper trading

```bash
python main.py rodar           # ciclo do dia
python main.py rodar --agora   # para testar fora da última hora do pregão
```

O ciclo só envia ordens se o mercado estiver aberto e faltar **no máximo 1 hora** para o
fechamento (o ideal é ~15 min antes). Ele roda no máximo **uma vez por dia**. Passo a passo:

1. Atualiza o topo do patrimônio e checa o **kill switch** (queda de 10% desde o topo).
2. Baixa e confere os dados. Ativo com dado estranho ou desatualizado não é operado.
3. Posições abertas: vende no sinal de saída, **sobe o stop móvel** (3 x ATR abaixo do
   maior fechamento desde a compra; nunca desce) e cria um stop se alguma estiver sem.
4. Se a **trava diária** (-3% no dia) não estiver ativa, compra os sinais de entrada.
   Cada compra já sai com o **stop na corretora** (ordem OTO).

Tudo fica registrado em `logs/robo.log`, `logs/operacoes.csv` e `logs/estado.json`.

Se o kill switch disparar, o robô para até você analisar e rodar:

```bash
python main.py reativar
```

## Fase 5: alertas no Telegram

1. No Telegram, fale com **@BotFather**, mande `/newbot` e siga as instruções. Ele te dá
   um **token** (algo como `123456:ABC...`).
2. Abra uma conversa com o seu bot novo e mande qualquer mensagem (ex.: "oi").
3. No navegador, abra `https://api.telegram.org/botSEU_TOKEN/getUpdates` (troque
   `SEU_TOKEN`). Procure `"chat":{"id":` e copie o número: esse é o **chat id**.
4. Coloque os dois no `.env`:
   ```
   TELEGRAM_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=987654321
   ```
5. Teste: `python main.py telegram-teste`

O robô avisa: resumo de cada ciclo, compras e vendas, dados com problema, trava diária,
kill switch e qualquer erro. Relatório de desempenho:

```bash
python main.py relatorio              # na tela
python main.py relatorio --telegram   # também no Telegram
```

## Fase 6: rodar sozinho na nuvem

Qualquer VPS Linux barato serve (1 GB de RAM basta): Hetzner, DigitalOcean, Vultr,
Oracle Cloud (tem plano grátis) etc. Escolha **Ubuntu 24.04**.

1. **Entre no servidor** (o provedor mostra o IP): `ssh root@IP_DO_SERVIDOR`
2. **Crie um usuário só para o robô** e instale o Python:
   ```bash
   adduser robo
   apt update && apt install -y python3 python3-venv git
   su - robo
   ```
3. **Instale o robô** (como usuário `robo`):
   ```bash
   git clone https://github.com/brayanreis32/rob--trade.git
   cd rob--trade
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python configurar.py   # cola as chaves (e o Telegram) e cria o .env
   chmod 600 .env     # só o usuário robo consegue ler as chaves
   .venv/bin/python main.py                 # tem que mostrar o saldo
   .venv/bin/python main.py telegram-teste  # tem que chegar no Telegram
   exit
   ```
4. **Agende** (de volta como root):
   ```bash
   cp /home/robo/rob--trade/deploy/robo-trade* /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable --now robo-trade.timer robo-trade-relatorio.timer
   systemctl list-timers 'robo-trade*'      # mostra quando vai rodar
   ```
   O agendamento roda de segunda a sexta às **15:45 de Nova York** (e às 12:45 para os dias
   de pregão curto), com o horário de verão ajustado sozinho. Como está "enabled", **volta
   sozinho se o servidor reiniciar**. Feriados: o robô vê que o mercado está fechado e não faz nada.
5. **Acompanhe:**
   ```bash
   journalctl -u robo-trade --since today            # saída do último ciclo
   tail -f /home/robo/rob--trade/logs/robo.log        # log completo
   systemctl start robo-trade.service                 # rodar um ciclo agora
   ```
6. **Atualizar o código:** `su - robo -c "cd rob--trade && git pull && .venv/bin/pip install -r requirements.txt"`

**O que pode dar errado:** relógio do servidor errado (o robô usa o relógio da Alpaca
para decidir, então não opera fora de hora); `.env` faltando no servidor (aparece no
`journalctl`); provedor desligando o servidor (o Telegram para de mandar o resumo diário,
e é por isso que vale olhar se ele chegou).

> `MODO=LIVE` **não funciona agendado** de propósito: a confirmação precisa ser digitada no
> terminal, e o agendamento não tem terminal. Isso só deve mudar depois do checklist abaixo.

---

## Regras de segurança

1. **Paper por padrão.** Dinheiro real só com `MODO=LIVE` no `.env` **e** digitando
   `EU ACEITO OPERAR COM DINHEIRO REAL` no terminal.
2. Chaves só no `.env` (fora do GitHub).
3. Risco máximo de **1%** do patrimônio por operação (pela distância até o stop).
4. Toda posição tem **stop na corretora**, então fica protegida mesmo se o robô cair.
5. No máximo **5 posições** e **20%** do patrimônio por ativo.
6. **Trava diária:** -3% no dia = sem novas compras até amanhã.
7. **Kill switch:** -10% desde o topo = robô para até `python main.py reativar`.
8. Sem alavancagem, sem venda a descoberto, sem opções.
9. Erro ou dado estranho = não opera, registra e avisa.
10. Só envia ordens com o mercado aberto (relógio da Alpaca).

## Checklist antes de pensar em dinheiro real

- [ ] Rodou em paper por pelo menos 2 a 3 meses sem erros
- [ ] O resultado do paper ficou parecido com o do backtest
- [ ] Você desligou o robô e viu que as posições continuaram protegidas pelo stop na corretora
- [ ] A trava diária e o kill switch foram testados e funcionaram
- [ ] Você sabe ler o log e explicar por que o robô fez cada operação
- [ ] A conta real aceita residentes do Brasil e você entende como enviar e sacar dólares
- [ ] Você entende a tributação de ganhos no exterior (vale consultar um contador)
- [ ] O valor inicial é pequeno e você aceita perdê-lo

## Arquivos

| Arquivo | O que faz |
|---|---|
| `config.yaml` | todos os parâmetros (ativos, médias, ATR, risco) |
| `settings.py` | lê o `.env` e o `config.yaml`, decide paper ou real |
| `data.py` | baixa os dados da Alpaca e confere se fazem sentido |
| `strategy.py` | indicadores e sinais; para criar outra estratégia, faça uma classe filha de `Estrategia` |
| `risk.py` | tamanho da posição, trava diária e kill switch |
| `broker.py` | conversa com a Alpaca: conta, ordens e stops |
| `robo.py` | o ciclo do dia (Fase 4) |
| `estado.py` | memória do robô entre um dia e outro |
| `notify.py` | avisos pelo Telegram |
| `backtest.py` | simulação no passado (Fase 3) |
| `main.py` | os comandos que você roda |
| `configurar.py` | cria o `.env` com as suas chaves |
| `deploy/` | agendamento no servidor (Fase 6) |
| `tests/` | testes automáticos: `pytest` |

## Glossário

- **Paper trading:** operar com dinheiro fictício, em tempo real, para testar.
- **Backtest:** simular a estratégia em dados do passado.
- **Média móvel (MM):** média dos preços dos últimos N dias; mostra a tendência.
- **ATR:** quanto o preço costuma oscilar por dia; usado para posicionar o stop.
- **Stop loss:** ordem que vende automaticamente para limitar a perda.
- **Trailing stop (stop móvel):** stop que sobe junto com o preço para proteger o lucro.
- **Drawdown:** maior queda da conta desde um topo.
- **Slippage:** diferença entre o preço esperado e o preço executado.
- **Overfitting:** estratégia ajustada demais ao passado, que não funciona no futuro.
- **VPS:** computador alugado na nuvem, ligado 24 horas.
- **ETF:** fundo negociado como uma ação (o SPY acompanha as 500 maiores empresas americanas).
