"""Fase 4: o ciclo do dia. Roda uma vez por dia, ~15 minutos antes do fechamento.

Ordem do ciclo:
  1. Confere se já rodou hoje, se o kill switch está ativo e se o mercado está aberto.
  2. Lê a conta, atualiza o topo do patrimônio e checa o kill switch (-10% do topo).
  3. Baixa e valida os dados. Ativo com dado estranho não é operado.
  4. Cuida das posições abertas: vende no sinal de saída, sobe o stop móvel e garante
     que toda posição tem um stop na corretora.
  5. Se a trava diária (-3% no dia) não estiver ativa, abre novas posições.
  6. Manda o resumo do dia.
Qualquer erro inesperado interrompe o ciclo (main.py avisa você).
"""

import logging
from zoneinfo import ZoneInfo

import pandas as pd

import broker
import data
import estado as memoria
from risk import RegrasRisco, kill_switch_disparou, pode_abrir_nova, tamanho_posicao, trava_diaria_ativa
from strategy import criar_estrategia

log = logging.getLogger("robo")
FUSO = ZoneInfo("America/New_York")
JANELA_MINUTOS = 60  # só opera se faltar no máximo 1 hora para o fechamento
ANOS_DE_DADOS = 2  # suficiente para a média de 200 dias


def _dolar(v: float) -> str:
    return f"US$ {v:,.2f}"


def executar_ciclo(cliente, cliente_dados, config: dict, avisar, agora_mesmo=False, forcar=False, estado=None) -> list[str]:
    """Roda o ciclo do dia e devolve as linhas do resumo."""
    estado = estado or memoria.carregar()
    regras = RegrasRisco.do_config(config)
    estrategia = criar_estrategia(config)
    resumo: list[str] = []

    conta = broker.resumo_da_conta(cliente)
    hoje = conta["agora"].astimezone(FUSO).date()

    if estado.ultima_execucao == hoje.isoformat() and not forcar:
        log.info("Ciclo já rodou hoje (%s). Nada a fazer.", hoje)
        return ["O ciclo já rodou hoje. Nada foi feito."]
    if estado.kill_switch:
        avisar(f"🛑 Kill switch ATIVO ({estado.kill_switch_motivo}). O robô não opera até você rodar: python main.py reativar")
        return ["Kill switch ativo. Nada foi feito."]
    if not conta["mercado_aberto"]:
        log.info("Mercado fechado. Próxima abertura: %s", conta["proxima_abertura"])
        return [f"Mercado fechado (abre {conta['proxima_abertura']}). Nada foi feito."]
    minutos = (conta["proximo_fechamento"] - conta["agora"]).total_seconds() / 60
    if minutos > JANELA_MINUTOS and not agora_mesmo:
        log.info("Faltam %.0f min para o fechamento; o robô só opera na última hora.", minutos)
        return [f"Ainda faltam {minutos:.0f} minutos para o fechamento. Nada foi feito (use --agora para testar)."]
    if conta["bloqueada"]:
        avisar("⚠️ A conta está bloqueada para operar na Alpaca. Nada foi feito.")
        return ["Conta bloqueada. Nada foi feito."]

    patrimonio, caixa = conta["patrimonio"], max(conta["dinheiro"], 0.0)
    estado.pico_patrimonio = max(estado.pico_patrimonio, patrimonio)
    if kill_switch_disparou(patrimonio, estado.pico_patrimonio, regras):
        estado.kill_switch = True
        estado.kill_switch_motivo = (
            f"patrimônio {_dolar(patrimonio)} caiu {regras.kill_switch:.0%} ou mais do topo "
            f"{_dolar(estado.pico_patrimonio)} em {hoje}"
        )
        memoria.salvar(estado)
        avisar(f"🛑 KILL SWITCH DISPAROU: {estado.kill_switch_motivo}. O robô parou. "
               "As posições abertas seguem protegidas pelos stops na corretora. "
               "Para voltar: python main.py reativar")
        return ["Kill switch disparou. Robô parado."]
    memoria.salvar(estado)

    # ---- dados
    abertas = broker.posicoes(cliente)
    simbolos = list(dict.fromkeys(config["ativos"] + list(abertas)))
    dados = data.baixar_diario(cliente_dados, simbolos, ANOS_DE_DADOS, feed=config.get("dados", {}).get("feed", "sip"))
    for s in simbolos:
        dados.setdefault(s, pd.DataFrame(columns=data.COLUNAS))
    data.completar_com_hoje(cliente_dados, dados, hoje)
    minimo = config["estrategia"]["media_tendencia"] + 5
    prontos = {}
    for s in simbolos:
        problemas = data.validar(dados.get(s), minimo, hoje)
        if problemas:
            avisar(f"⚠️ {s}: dados com problema ({'; '.join(problemas)}). {s} não será operado hoje.")
        else:
            prontos[s] = estrategia.preparar(dados[s]).iloc[-1]

    # ---- posições que sumiram (o stop foi executado pela corretora)
    for s in list(estado.posicoes):
        if s not in abertas:
            resumo.append(f"{s}: posição encerrada pela corretora (stop executado).")
            memoria.registrar_operacao({"data": hoje, "simbolo": s, "acao": "VENDA", "motivo": "stop executado na corretora"})
            estado.posicoes.pop(s)

    # ---- gerenciar posições abertas
    for s, pos in abertas.items():
        linha = prontos.get(s)
        stops = broker.ordens_stop_abertas(cliente, s)
        if linha is None:
            if not stops:
                avisar(f"🚨 {s}: posição SEM stop e sem dados confiáveis. Confira na Alpaca agora!")
            continue
        preco, atr_hoje = float(linha["close"]), float(linha["atr"])
        if linha["saida"]:
            broker.zerar(cliente, s)
            resumo.append(f"VENDA {s}: {pos['qtd']:g} ações (~{_dolar(preco)}), sinal de saída.")
            memoria.registrar_operacao({"data": hoje, "simbolo": s, "acao": "VENDA", "qtd": pos["qtd"], "preco": preco, "motivo": "sinal de saída"})
            estado.posicoes.pop(s, None)
            continue

        info = estado.posicoes.get(s)
        if info:
            # stop móvel: maior fechamento desde a compra - 3 x ATR (nunca abaixo do stop inicial)
            fechamentos = dados[s]["close"]
            fechamentos = fechamentos[fechamentos.index >= info["data_entrada"]]
            novo_stop = max(estrategia.stop_movel(float(fechamentos.max()), atr_hoje), float(info["stop_inicial"]))
        else:
            # posição que o robô não abriu (ou memória perdida): sem data de compra, então
            # só garante um stop inicial a partir do preço de hoje
            novo_stop = estrategia.stop_inicial(preco, atr_hoje)

        if novo_stop >= preco:
            broker.zerar(cliente, s)
            resumo.append(f"VENDA {s}: preço {_dolar(preco)} abaixo do stop móvel {_dolar(novo_stop)}.")
            memoria.registrar_operacao({"data": hoje, "simbolo": s, "acao": "VENDA", "qtd": pos["qtd"], "preco": preco, "stop": novo_stop, "motivo": "stop móvel"})
            estado.posicoes.pop(s, None)
        elif not stops:
            broker.criar_stop(cliente, s, pos["qtd"], novo_stop)
            avisar(f"⚠️ {s} estava sem stop na corretora. Stop criado em {_dolar(novo_stop)}.")
        else:
            atual = max(float(o.stop_price) for o in stops)
            if novo_stop > atual + 0.01:
                for o in stops:
                    broker.subir_stop(cliente, o.id, novo_stop)
                resumo.append(f"{s}: stop subiu de {_dolar(atual)} para {_dolar(novo_stop)}.")

    # ---- novas compras
    if trava_diaria_ativa(patrimonio, conta["patrimonio_ontem"], regras):
        avisar(f"⏸️ Trava diária: a conta caiu {regras.trava_diaria:.0%} ou mais hoje. Sem novas compras até amanhã.")
    else:
        n_abertas = len(broker.posicoes(cliente))
        for s in config["ativos"]:
            linha = prontos.get(s)
            if s in abertas or linha is None or not linha["entrada"]:
                continue
            if not pode_abrir_nova(n_abertas, regras):
                resumo.append(f"{s}: sinal de compra ignorado (já há {regras.max_posicoes} posições).")
                continue
            preco = float(linha["close"])
            stop = estrategia.stop_inicial(preco, float(linha["atr"]))
            qtd = tamanho_posicao(patrimonio, caixa, preco, stop, regras)
            if qtd < 1:
                resumo.append(f"{s}: sinal de compra, mas o tamanho calculado deu 0 ações.")
                continue
            broker.comprar_com_stop(cliente, s, qtd, stop)
            caixa -= qtd * preco
            n_abertas += 1
            estado.posicoes[s] = {"data_entrada": hoje.isoformat(), "stop_inicial": round(stop, 2)}
            resumo.append(f"COMPRA {s}: {qtd} ações (~{_dolar(preco)}), stop {_dolar(stop)}, risco ~{_dolar(qtd * (preco - stop))}.")
            memoria.registrar_operacao({"data": hoje, "simbolo": s, "acao": "COMPRA", "qtd": qtd, "preco": preco, "stop": round(stop, 2), "motivo": "cruzamento de médias"})

    estado.ultima_execucao = hoje.isoformat()
    memoria.salvar(estado)

    cabecalho = [f"📊 Robô de trade - {hoje}", f"Patrimônio: {_dolar(patrimonio)} (ontem {_dolar(conta['patrimonio_ontem'])})"]
    resumo = cabecalho + (resumo or ["Nenhuma operação hoje."])
    avisar("\n".join(resumo))
    return resumo

