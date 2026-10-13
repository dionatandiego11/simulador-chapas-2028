from pathlib import Path
import sys
import unittest
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from motor import (
    calcular_base_votacao,
    cota_minima_genero,
    editar_lista,
    historico_candidaturas,
    ler_csv,
    montar_novos_nomes,
    norm,
)


class MotorTest(unittest.TestCase):
    def test_nomes_ausentes_nao_viram_nan(self):
        self.assertEqual(norm(float("nan")), "")
        self.assertEqual(norm(None), "")
        self.assertEqual(norm("Itaguara"), "ITAGUARA")

    def test_observacao_preservada_no_cadastro_em_lote(self):
        registros, erros = montar_novos_nomes("Pessoa Nova;contato confirmado")
        self.assertFalse(erros)
        self.assertEqual(
            registros["AVULSO|PESSOA NOVA"]["observacao"], "contato confirmado"
        )

    def test_base_relativa_usa_mesmos_pesos_e_ignora_ausencias(self):
        hist = pd.DataFrame(
            {
                "votos_2016": [100],
                "votos_2020": [None],
                "votos_2024": [400],
                "genero_historico": [""],
            },
            index=["PESSOA"],
        )
        resumo = pd.DataFrame({"Ano": [2016, 2020, 2024], "QE": [1000, 1000, 1000]})
        base = calcular_base_votacao(hist, resumo, {}, {2016: 2, 2020: 3, 2024: 5})
        self.assertAlmostEqual(base.at["PESSOA", "base_votacao"], 31.43)

    def test_historico_sem_linhas_utilizaveis(self):
        self.assertTrue(
            historico_candidaturas({2024: pd.DataFrame()}, pd.DataFrame()).empty
        )

    def test_duplicacao_exata_do_csv_nao_dobra_candidaturas(self):
        caminho = Path(__file__).resolve().parents[1] / "2024.csv"
        linhas = caminho.read_bytes().splitlines()
        bruto = b"\n".join([linhas[0], linhas[1], linhas[1]])
        self.assertEqual(len(ler_csv(bruto, 2024)), 1)

    def test_troca_lista_cheia_e_impede_duplicacao(self):
        self.assertEqual(editar_lista(["A", "B"], "A", "C", 2, set()), ["B", "C"])
        with self.assertRaises(ValueError):
            editar_lista(["A", "B"], None, "C", 2, set())
        with self.assertRaises(ValueError):
            editar_lista(["A", "B"], "A", "C", 2, {"C"})

    def test_minimo_genero_arredonda_para_cima(self):
        self.assertEqual(cota_minima_genero(5), 2)
        self.assertEqual(cota_minima_genero(8), 3)


if __name__ == "__main__":
    unittest.main()
