"""Testes da regra de segurança nº 1: paper por padrão, LIVE só com confirmação."""

import pytest

from settings import FRASE_CONFIRMACAO, ErroConfiguracao, carregar_config, decidir_modo


def nao_deveria_perguntar(_):
    raise AssertionError("não deveria pedir confirmação no modo paper")


@pytest.mark.parametrize("valor", [None, "", "PAPER", "paper", "livee", "REAL"])
def test_qualquer_coisa_que_nao_seja_live_vira_paper(valor):
    assert decidir_modo(valor, nao_deveria_perguntar) is True


def test_live_com_frase_certa_libera_dinheiro_real():
    assert decidir_modo("LIVE", lambda _: FRASE_CONFIRMACAO) is False


@pytest.mark.parametrize("resposta", ["", "sim", FRASE_CONFIRMACAO.lower()])
def test_live_sem_frase_certa_para_o_robo(resposta):
    with pytest.raises(ErroConfiguracao):
        decidir_modo("LIVE", lambda _: resposta)


def test_config_tem_os_ativos_e_regras_de_risco():
    config = carregar_config()
    assert "SPY" in config["ativos"]
    assert config["risco"]["risco_por_operacao"] == 0.01
    assert config["risco"]["max_posicoes"] == 5
