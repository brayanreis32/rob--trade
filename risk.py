"""Tamanho de posição e travas de segurança. Nenhuma função aqui fala com a corretora."""

import math
from dataclasses import dataclass


@dataclass
class RegrasRisco:
    risco_por_operacao: float = 0.01  # fração do patrimônio arriscada até o stop
    max_posicoes: int = 5
    max_por_ativo: float = 0.20  # fração máxima do patrimônio em um ativo
    trava_diaria: float = 0.03  # queda no dia que bloqueia novas compras
    kill_switch: float = 0.10  # queda desde o topo que para o robô

    @classmethod
    def do_config(cls, config: dict) -> "RegrasRisco":
        return cls(**config["risco"])


def tamanho_posicao(patrimonio: float, caixa: float, preco: float, stop: float, regras: RegrasRisco) -> int:
    """Quantas ações comprar (número inteiro, pode ser 0).

    Usa o MENOR de três limites:
      1. perder no máximo `risco_por_operacao` do patrimônio se o stop for atingido;
      2. no máximo `max_por_ativo` do patrimônio neste ativo;
      3. só o dinheiro disponível (sem alavancagem).
    """
    if min(patrimonio, preco, stop) <= 0 or stop >= preco or caixa <= 0:
        return 0
    por_risco = regras.risco_por_operacao * patrimonio / (preco - stop)
    por_limite = regras.max_por_ativo * patrimonio / preco
    por_caixa = caixa / preco
    return max(0, math.floor(min(por_risco, por_limite, por_caixa)))


def queda(atual: float, referencia: float) -> float:
    """Quanto caiu de `referencia` até `atual` (0.05 = caiu 5%; negativo = subiu)."""
    if referencia <= 0:
        return 0.0
    return 1 - atual / referencia


def trava_diaria_ativa(patrimonio: float, patrimonio_ontem: float, regras: RegrasRisco) -> bool:
    """True se a conta já perdeu `trava_diaria` ou mais hoje."""
    return queda(patrimonio, patrimonio_ontem) >= regras.trava_diaria - 1e-12


def kill_switch_disparou(patrimonio: float, pico: float, regras: RegrasRisco) -> bool:
    """True se a conta caiu `kill_switch` ou mais desde o maior valor já atingido."""
    return queda(patrimonio, pico) >= regras.kill_switch - 1e-12


def pode_abrir_nova(posicoes_abertas: int, regras: RegrasRisco) -> bool:
    return posicoes_abertas < regras.max_posicoes
