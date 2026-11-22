import pytest

from risk import RegrasRisco, kill_switch_disparou, pode_abrir_nova, tamanho_posicao, trava_diaria_ativa

R = RegrasRisco()


def test_risco_de_1_porcento():
    # patrimônio 100 mil, risco 1% = US$ 1.000; distância até o stop US$ 10 -> 100 ações
    assert tamanho_posicao(100_000, 100_000, 100, 90, R) == 100


def test_limite_de_20_porcento_por_ativo():
    # pelo risco daria 1000 ações (US$ 100 mil), mas 20% do patrimônio = 200 ações
    assert tamanho_posicao(100_000, 100_000, 100, 99, R) == 200


def test_sem_alavancagem_usa_so_o_dinheiro_disponivel():
    assert tamanho_posicao(100_000, 5_000, 100, 99, R) == 50


@pytest.mark.parametrize("preco,stop,caixa", [(100, 100, 1e5), (100, 110, 1e5), (100, 0, 1e5), (100, 90, 0)])
def test_casos_invalidos_dao_zero(preco, stop, caixa):
    assert tamanho_posicao(100_000, caixa, preco, stop, R) == 0


def test_trava_diaria():
    assert not trava_diaria_ativa(97_500, 100_000, R)
    assert trava_diaria_ativa(97_000, 100_000, R)
    assert trava_diaria_ativa(90_000, 100_000, R)


def test_kill_switch():
    assert not kill_switch_disparou(91_000, 100_000, R)
    assert kill_switch_disparou(90_000, 100_000, R)


def test_maximo_de_5_posicoes():
    assert pode_abrir_nova(4, R)
    assert not pode_abrir_nova(5, R)
