"""Memória do robô entre um dia e outro (fica em logs/estado.json)."""

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PASTA_LOGS = Path(__file__).resolve().parent / "logs"
ARQUIVO_ESTADO = PASTA_LOGS / "estado.json"
ARQUIVO_OPERACOES = PASTA_LOGS / "operacoes.csv"


@dataclass
class Estado:
    pico_patrimonio: float = 0.0
    kill_switch: bool = False
    kill_switch_motivo: str = ""
    ultima_execucao: str = ""  # data (AAAA-MM-DD) do último ciclo completo
    posicoes: dict = field(default_factory=dict)  # símbolo -> {"data_entrada", "stop_inicial"}


def carregar(caminho: Path | None = None) -> Estado:
    caminho = caminho or ARQUIVO_ESTADO
    if not caminho.exists():
        return Estado()
    return Estado(**json.loads(caminho.read_text(encoding="utf-8")))


def salvar(estado: Estado, caminho: Path | None = None) -> None:
    caminho = caminho or ARQUIVO_ESTADO
    caminho.parent.mkdir(exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(asdict(estado), indent=2, ensure_ascii=False), encoding="utf-8")
    temporario.replace(caminho)  # troca de uma vez só, para nunca deixar o arquivo pela metade


def registrar_operacao(linha: dict, caminho: Path | None = None) -> None:
    """Acrescenta uma linha em logs/operacoes.csv (data, símbolo, ação, quantidade, preço, motivo)."""
    caminho = caminho or ARQUIVO_OPERACOES
    caminho.parent.mkdir(exist_ok=True)
    novo = not caminho.exists()
    with open(caminho, "a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["data", "simbolo", "acao", "qtd", "preco", "stop", "motivo"])
        if novo:
            escritor.writeheader()
        escritor.writerow({k: linha.get(k, "") for k in escritor.fieldnames})
