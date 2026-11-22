"""Ponto de entrada do robô.

Comandos:
  python main.py                 mostra saldo da conta e situação do mercado (Fase 1)
  python main.py sinais          indicadores e sinais de hoje, sem operar (Fase 2)
  python main.py rodar           ciclo do dia: aplica travas e envia ordens (Fase 4)
       --agora                   permite rodar fora da última hora do pregão (para testes)
       --forcar                  roda mesmo que o ciclo de hoje já tenha rodado
  python main.py relatorio       desempenho da conta (Fase 5)
  python main.py telegram-teste  manda uma mensagem de teste para o seu Telegram (Fase 5)
  python main.py reativar        desliga o kill switch depois que você analisou o que houve
O backtest (Fase 3) fica em: python backtest.py
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

import broker
import data
import estado as memoria
import notify
from settings import PASTA_PROJETO, ErroConfiguracao, carregar_config, carregar_credenciais
from strategy import criar_estrategia

PASTA_LOGS = PASTA_PROJETO / "logs"
PASTA_LOGS.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[RotatingFileHandler(PASTA_LOGS / "robo.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")],
)
log = logging.getLogger("robo")


def dolar(valor: float) -> str:
    return f"US$ {valor:,.2f}"


# ------------------------------------------------------------------ comandos

def cmd_saldo(credenciais, config, args):
    resumo = broker.resumo_da_conta(broker.conectar(credenciais))
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
    log.info("Saldo consultado (%s). Patrimônio %s", modo, dolar(resumo["patrimonio"]))


def cmd_sinais(credenciais, config, args):
    estrategia = criar_estrategia(config)
    p = config["estrategia"]
    print(f"Baixando {args.anos:g} anos de dados diários...")
    dados = data.baixar_diario(data.conectar(credenciais), config["ativos"], args.anos,
                               feed=config.get("dados", {}).get("feed", "sip"))
    print(f"\n{'Ativo':6} {'Data':10} {'Fech.':>9} {'MM' + str(p['media_curta']):>9} {'MM' + str(p['media_longa']):>9} "
          f"{'MM' + str(p['media_tendencia']):>9} {'ATR':>7}  {'Tendência':10} Sinal")
    for s in config["ativos"]:
        problemas = data.validar(dados.get(s), p["media_tendencia"] + 5)
        if problemas:
            print(f"{s:6} problema nos dados: {'; '.join(problemas)}")
            continue
        df = estrategia.preparar(dados[s])
        h = df.iloc[-1]
        sinal = "COMPRA" if h["entrada"] else "VENDA" if h["saida"] else "-"
        tendencia = "alta" if h["close"] > h["mm_tendencia"] else "baixa"
        print(f"{s:6} {str(df.index[-1].date()):10} {h['close']:9.2f} {h['mm_curta']:9.2f} {h['mm_longa']:9.2f} "
              f"{h['mm_tendencia']:9.2f} {h['atr']:7.2f}  {tendencia:10} {sinal}")
        if args.csv:
            (PASTA_PROJETO / "relatorios").mkdir(exist_ok=True)
            df.to_csv(PASTA_PROJETO / "relatorios" / f"indicadores_{s}.csv")
    print("\nCOMPRA = MM curta cruzou acima da longa hoje, com preço acima da MM de tendência.")
    print("VENDA  = MM curta cruzou abaixo da longa hoje. Nada foi enviado à corretora.")


def cmd_rodar(credenciais, config, args):
    import robo

    resumo = robo.executar_ciclo(
        broker.conectar(credenciais), data.conectar(credenciais), config, notify.enviar,
        agora_mesmo=args.agora, forcar=args.forcar,
    )
    print("\n".join(resumo))


def cmd_relatorio(credenciais, config, args):
    from alpaca.trading.requests import GetPortfolioHistoryRequest

    from backtest import maior_queda

    cliente = broker.conectar(credenciais)
    historico = cliente.get_portfolio_history(GetPortfolioHistoryRequest(period="1A", timeframe="1D"))
    pares = [(t, e) for t, e in zip(historico.timestamp, historico.equity) if e]
    linhas = ["📈 Relatório do robô"]
    if len(pares) >= 2:
        import pandas as pd

        curva = pd.Series([e for _, e in pares], index=[datetime.fromtimestamp(t, timezone.utc).date() for t, _ in pares])
        linhas += [
            f"Período: {curva.index[0]} a {curva.index[-1]}",
            f"Patrimônio: {dolar(curva.iloc[0])} -> {dolar(curva.iloc[-1])} ({(curva.iloc[-1] / curva.iloc[0] - 1) * 100:+.1f}%)",
            f"Maior queda (drawdown): {maior_queda(curva) * 100:.1f}%",
        ]
    posicoes = broker.posicoes(cliente)
    linhas.append(f"Posições abertas: {len(posicoes)}")
    for s, p in posicoes.items():
        linhas.append(f"  {s}: {p['qtd']:g} ações, valor {dolar(p['valor'])} (preço médio {dolar(p['preco_medio'])})")
    if memoria.ARQUIVO_OPERACOES.exists():
        import pandas as pd

        ops = pd.read_csv(memoria.ARQUIVO_OPERACOES)
        linhas.append(f"Operações registradas: {len(ops)} ({(ops['acao'] == 'COMPRA').sum()} compras, {(ops['acao'] == 'VENDA').sum()} vendas)")
    estado = memoria.carregar()
    linhas.append(f"Topo do patrimônio: {dolar(estado.pico_patrimonio)} | kill switch: {'ATIVO' if estado.kill_switch else 'desligado'}")
    texto = "\n".join(linhas)
    print(texto)
    if args.telegram:
        notify.enviar(texto)


def cmd_telegram_teste(credenciais, config, args):
    if notify.enviar("✅ Teste do robô de trade: o Telegram está funcionando!"):
        print("Mensagem enviada. Confira o seu Telegram.")
    else:
        print("Não foi possível enviar. Confira TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no .env (veja o README).")
        return 1


def cmd_reativar(credenciais, config, args):
    estado = memoria.carregar()
    if not estado.kill_switch:
        print("O kill switch não está ativo. Nada a fazer.")
        return
    print(f"Kill switch ativo: {estado.kill_switch_motivo}")
    if input('Digite "REATIVAR" para o robô voltar a operar: ').strip() != "REATIVAR":
        print("Nada foi alterado.")
        return
    resumo = broker.resumo_da_conta(broker.conectar(credenciais))
    estado.kill_switch = False
    estado.kill_switch_motivo = ""
    estado.pico_patrimonio = resumo["patrimonio"]  # o novo topo passa a ser o valor de agora
    memoria.salvar(estado)
    log.info("Kill switch reativado manualmente. Novo topo: %s", dolar(resumo["patrimonio"]))
    print(f"Robô reativado. Novo topo de referência: {dolar(resumo['patrimonio'])}")


COMANDOS = {
    "saldo": cmd_saldo,
    "sinais": cmd_sinais,
    "rodar": cmd_rodar,
    "relatorio": cmd_relatorio,
    "telegram-teste": cmd_telegram_teste,
    "reativar": cmd_reativar,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Robô de trade (Alpaca)")
    sub = parser.add_subparsers(dest="comando")
    for nome in COMANDOS:
        sp = sub.add_parser(nome)
        if nome == "sinais":
            sp.add_argument("--anos", type=float, default=5)
            sp.add_argument("--csv", action="store_true", help="salva os indicadores em relatorios/")
        if nome == "rodar":
            sp.add_argument("--agora", action="store_true")
            sp.add_argument("--forcar", action="store_true")
        if nome == "relatorio":
            sp.add_argument("--telegram", action="store_true", help="manda o relatório para o Telegram")
    args = parser.parse_args(argv)
    comando = args.comando or "saldo"

    try:
        config = carregar_config()
        credenciais = carregar_credenciais()
        return COMANDOS[comando](credenciais, config, args) or 0
    except ErroConfiguracao as erro:
        log.error("Configuração: %s", erro)
        print(f"ERRO: {erro}")
        return 1
    except Exception as erro:  # sem internet, API fora do ar, dado inesperado...
        log.exception("Erro no comando %s", comando)
        print(f"ERRO: {erro}")
        if comando == "rodar":
            notify.enviar(f"🚨 Erro no robô ({comando}): {erro}. O ciclo foi interrompido; confira o log.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
