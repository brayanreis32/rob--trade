"""Testa o ciclo do dia com uma corretora FALSA (nenhuma ordem de verdade é enviada)."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pytest

import broker
import data
import estado as memoria
import robo
from conftest import PARAMS, barras
from strategy import CruzamentoMedias

NY = ZoneInfo("America/New_York")


def serie_com_compra_no_ultimo_dia():
    precos = np.concatenate([np.linspace(50, 150, 300), np.linspace(150, 130, 60), np.linspace(130, 170, 80)])
    df = barras(precos)
    prep = CruzamentoMedias(PARAMS).preparar(df)
    primeiro = prep.index[prep["entrada"]][0]
    return df.loc[:primeiro]


class Corretora:
    """Registra tudo que o robô tentaria fazer."""

    def __init__(self, monkeypatch, dados, *, aberto=True, patrimonio=100_000, ontem=100_000,
                 posicoes=None, stops=None, minutos_para_fechar=15):
        self.ordens = []
        self.stops = stops or {}
        self._posicoes = posicoes or {}
        hoje = max(df.index[-1] for df in dados.values()).date()
        agora = datetime(hoje.year, hoje.month, hoje.day, 15, 45, tzinfo=NY)
        self.conta = {"status": "ACTIVE", "patrimonio": patrimonio, "patrimonio_ontem": ontem,
                      "dinheiro": patrimonio, "poder_de_compra": patrimonio * 2, "bloqueada": False,
                      "mercado_aberto": aberto, "agora": agora,
                      "proxima_abertura": agora + timedelta(hours=18),
                      "proximo_fechamento": agora + timedelta(minutes=minutos_para_fechar)}
        mp = monkeypatch
        mp.setattr(broker, "resumo_da_conta", lambda c: dict(self.conta))
        mp.setattr(broker, "posicoes", lambda c: dict(self._posicoes))
        mp.setattr(broker, "ordens_stop_abertas", lambda c, s: self.stops.get(s, []))
        mp.setattr(broker, "comprar_com_stop", lambda c, s, q, st: self.ordens.append(("compra", s, q, st)))
        mp.setattr(broker, "criar_stop", lambda c, s, q, st: self.ordens.append(("stop", s, q, st)))
        mp.setattr(broker, "subir_stop", lambda c, i, st: self.ordens.append(("subir", i, st)))
        mp.setattr(broker, "zerar", lambda c, s: self.ordens.append(("zerar", s)))
        mp.setattr(data, "baixar_diario", lambda c, s, a, feed="sip": {k: v.copy() for k, v in dados.items() if k in s})
        mp.setattr(data, "completar_com_hoje", lambda c, d, h: None)


@pytest.fixture(autouse=True)
def estado_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(memoria, "ARQUIVO_ESTADO", tmp_path / "estado.json")
    monkeypatch.setattr(memoria, "ARQUIVO_OPERACOES", tmp_path / "operacoes.csv")
    real_salvar, real_carregar = memoria.salvar, memoria.carregar
    monkeypatch.setattr(memoria, "salvar", lambda e, caminho=None: real_salvar(e, tmp_path / "estado.json"))
    monkeypatch.setattr(memoria, "carregar", lambda caminho=None: real_carregar(tmp_path / "estado.json"))


def rodar(config, avisos=None, **kw):
    avisos = avisos if avisos is not None else []
    return robo.executar_ciclo(None, None, config, avisos.append, **kw), avisos


def test_compra_com_stop_quando_ha_sinal(monkeypatch, config):
    config["ativos"] = ["SPY"]
    corretora = Corretora(monkeypatch, {"SPY": serie_com_compra_no_ultimo_dia()})
    resumo, _ = rodar(config)
    assert len(corretora.ordens) == 1
    tipo, simbolo, qtd, stop = corretora.ordens[0]
    preco = serie_com_compra_no_ultimo_dia()["close"].iloc[-1]
    assert (tipo, simbolo) == ("compra", "SPY")
    assert 0 < stop < preco
    assert qtd * (preco - stop) <= 1_000 + 1e-6  # no máximo 1% de risco
    assert qtd * preco <= 20_000 + 1e-6  # no máximo 20% do patrimônio
    assert memoria.carregar().posicoes["SPY"]["stop_inicial"] == round(stop, 2)


def test_nao_roda_duas_vezes_no_mesmo_dia(monkeypatch, config):
    config["ativos"] = ["SPY"]
    corretora = Corretora(monkeypatch, {"SPY": serie_com_compra_no_ultimo_dia()})
    rodar(config)
    rodar(config)
    assert len(corretora.ordens) == 1


def test_mercado_fechado_nao_opera(monkeypatch, config):
    config["ativos"] = ["SPY"]
    corretora = Corretora(monkeypatch, {"SPY": serie_com_compra_no_ultimo_dia()}, aberto=False)
    rodar(config)
    assert corretora.ordens == []


def test_cedo_demais_nao_opera(monkeypatch, config):
    config["ativos"] = ["SPY"]
    corretora = Corretora(monkeypatch, {"SPY": serie_com_compra_no_ultimo_dia()}, minutos_para_fechar=300)
    rodar(config)
    assert corretora.ordens == []


def test_trava_diaria_bloqueia_compras(monkeypatch, config):
    config["ativos"] = ["SPY"]
    corretora = Corretora(monkeypatch, {"SPY": serie_com_compra_no_ultimo_dia()}, patrimonio=96_000, ontem=100_000)
    _, avisos = rodar(config)
    assert corretora.ordens == []
    assert any("Trava diária" in a for a in avisos)


def test_kill_switch_para_tudo_e_fica_ativo(monkeypatch, config):
    config["ativos"] = ["SPY"]
    e = memoria.Estado(pico_patrimonio=100_000)
    memoria.salvar(e)
    corretora = Corretora(monkeypatch, {"SPY": serie_com_compra_no_ultimo_dia()}, patrimonio=89_000, ontem=89_500)
    _, avisos = rodar(config)
    assert corretora.ordens == []
    assert memoria.carregar().kill_switch
    rodar(config, forcar=True)  # mesmo forçando, continua parado
    assert corretora.ordens == []


def test_dado_desatualizado_nao_opera(monkeypatch, config):
    config["ativos"] = ["SPY", "AAPL"]
    spy = serie_com_compra_no_ultimo_dia()
    corretora = Corretora(monkeypatch, {"SPY": spy, "AAPL": spy.iloc[:-1]})
    _, avisos = rodar(config)
    assert [o[1] for o in corretora.ordens] == ["SPY"]
    assert any("AAPL" in a and "não será operado" in a for a in avisos)


def test_posicao_sem_stop_ganha_um_stop(monkeypatch, config):
    config["ativos"] = ["SPY"]
    df = serie_com_compra_no_ultimo_dia().iloc[:-3]  # sem sinal hoje
    corretora = Corretora(monkeypatch, {"SPY": df}, posicoes={"SPY": {"qtd": 10, "preco_medio": 100, "valor": 1500}})
    rodar(config)
    assert len(corretora.ordens) == 1 and corretora.ordens[0][0] == "stop"
    assert corretora.ordens[0][3] < df["close"].iloc[-1]


def test_stop_movel_so_sobe(monkeypatch, config):
    config["ativos"] = ["SPY"]
    df = serie_com_compra_no_ultimo_dia().iloc[:-3]
    stop_alto = SimpleNamespace(id="a", stop_price=df["close"].iloc[-1] * 0.999)
    corretora = Corretora(monkeypatch, {"SPY": df}, posicoes={"SPY": {"qtd": 10, "preco_medio": 100, "valor": 1500}},
                          stops={"SPY": [stop_alto]})
    rodar(config)
    assert corretora.ordens == []  # o stop atual já é mais alto: não desce
    stop_baixo = SimpleNamespace(id="b", stop_price=1.0)
    corretora.stops = {"SPY": [stop_baixo]}
    rodar(config, forcar=True)
    assert corretora.ordens and corretora.ordens[0][:2] == ("subir", "b")
