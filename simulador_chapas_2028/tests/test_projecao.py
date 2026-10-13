from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projecao import media_ponderada, resumir_votacao


class ProjecaoTest(unittest.TestCase):
    def test_anos_recentes_tem_maior_peso(self):
        self.assertEqual(
            media_ponderada(
                {2016: 100, 2020: 200, 2024: 400}, {2016: 2, 2020: 3, 2024: 5}
            ),
            280,
        )

    def test_ausencia_nao_e_zero_por_padrao(self):
        votos = {2016: 100, 2020: None, 2024: float("nan")}
        pesos = {2016: 2, 2020: 3, 2024: 5}
        self.assertEqual(media_ponderada(votos, pesos), 100)
        self.assertEqual(media_ponderada(votos, pesos, ausencia_zero=True), 20)

    def test_zero_votos_valido_e_pesos_sem_base(self):
        self.assertEqual(media_ponderada({2024: 0}, {2024: 5}), 0)
        self.assertIsNone(media_ponderada({2024: 100}, {2024: 0}))
        self.assertIsNone(media_ponderada({}, {2024: 5}))

    def test_legenda_contada_uma_vez_e_pendentes_explicitos(self):
        resultado = resumir_votacao([280, 100, None], 50)
        self.assertEqual(
            resultado, {"nominais": 380, "legenda": 50, "total": 430, "pendentes": 1}
        )


if __name__ == "__main__":
    unittest.main()
