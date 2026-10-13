"""Cálculos descritivos de votação para composições exploratórias."""

from math import isfinite
from collections.abc import Mapping


def media_ponderada(
    votos: Mapping[int, float | None],
    pesos: Mapping[int, float],
    ausencia_zero: bool = False,
) -> float | None:
    """Usa apenas resultados observados, salvo opção explícita de ausência zero."""
    soma = denominador = 0.0
    for ano, peso in pesos.items():
        if peso <= 0 or not isfinite(peso):
            continue
        valor = votos.get(ano)
        if valor is None or not isfinite(float(valor)):
            if not ausencia_zero:
                continue
            valor = 0.0
        soma += max(0.0, float(valor)) * peso
        denominador += peso
    return round(soma / denominador, 2) if denominador else None


def resumir_votacao(votos: list[float | None], legenda: float) -> dict:
    """Separa os nominais dos votos exclusivamente de legenda, sem duplicação."""
    informados = [v for v in votos if v is not None]
    nominais = round(sum(informados), 2)
    return {
        "nominais": nominais,
        "legenda": legenda,
        "total": round(nominais + legenda, 2),
        "pendentes": len(votos) - len(informados),
    }
