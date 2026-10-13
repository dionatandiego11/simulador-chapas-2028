"""Regressões dos cenários locais; executar com unittest discover -s tests."""

from pathlib import Path
import unittest
import sys

from streamlit.testing.v1 import AppTest


PASTA = Path(__file__).resolve().parents[1]
if str(PASTA) not in sys.path:
    sys.path.insert(0, str(PASTA))


class ComposicaoTest(unittest.TestCase):
    def test_migracao_da_versao_anterior_preserva_lista(self):
        app = self.abrir()
        nome = app.multiselect(key="chapa_PDT").value[0]
        contexto = app.session_state["_contexto_chapas"]
        app.session_state["_assinatura_preselecoes"] = ("v5", *contexto)
        app.session_state["_contexto_chapas"] = None
        app.session_state["_composicoes"] = {}
        app.multiselect(key="chapa_PDT").set_value([nome]).run()
        self.sem_erros(app)
        self.assertEqual(app.multiselect(key="chapa_PDT").value, [nome])

    def abrir(self):
        # Instrumentação apenas na cópia em memória para conferir o conteúdo
        # exportado, sem introduzir dados de teste na interface do aplicativo.
        fonte = (PASTA / "app_2028.py").read_text(encoding="utf-8")
        fonte = fonte.replace(
            "pasta = Path(__file__).resolve().parent", f"pasta = Path({str(PASTA)!r})"
        )
        fonte += '\nst.session_state["_teste_export"] = linhas_export\n'
        fonte += 'st.session_state["_teste_historico"] = hist[["ultimo_partido", "nome"]].to_dict("index")\n'
        fonte += 'st.session_state["_teste_projecoes"] = resumos_votacao\n'
        app = AppTest.from_string(fonte, default_timeout=30).run()
        self.sem_erros(app)
        app.sidebar.multiselect[0].set_value(
            ["Partido: PDT", "Partido: PV", "Partido: PODE"]
        ).run()
        self.sem_erros(app)
        return app

    def sem_erros(self, app):
        self.assertFalse(app.exception, [e.value for e in app.exception])

    def test_itaguara_divide_pt_pv_sem_repeticao(self):
        app = self.abrir()
        self.assertEqual(len(app.multiselect(key="chapa_FE_BRASIL_PT").value), 5)
        self.assertEqual(len(app.multiselect(key="chapa_FE_BRASIL_PV").value), 5)
        self.assertEqual(
            app.number_input(key="reserva_ITAGUARA_MG_FE BRASIL_PCDOB").value, 0
        )
        linhas = app.session_state["_teste_export"]
        self.assertEqual(len(linhas), 30)
        self.assertEqual(len({r["Nome"] for r in linhas}), 30)
        self.assertEqual(
            sum(r["Partido de destino no cenário"] == "PV" for r in linhas), 5
        )
        app.number_input(key="reserva_ITAGUARA_MG_FE BRASIL_PT").set_value(6).run()
        self.sem_erros(app)
        self.assertTrue(any("reservas somam 11" in e.value for e in app.error))

    def test_puxar_nome_preserva_partido_original(self):
        app = self.abrir()
        ocupados = {
            p
            for widget in app.multiselect
            if widget.key and widget.key.startswith("chapa_")
            for p in widget.value
        }
        historico = app.session_state["_teste_historico"]
        pessoa = next(
            p
            for p, r in historico.items()
            if p not in ocupados and r["ultimo_partido"] == "PSD"
        )
        app.checkbox(key="puxar_chapa_PDT").set_value(False).run()
        self.sem_erros(app)
        app.checkbox(key="puxar_chapa_PDT").set_value(True).run()
        app.multiselect(key="origens_chapa_PDT").set_value(["PSD"]).run()
        app.multiselect(key="chapa_PDT").set_value([pessoa]).run()
        self.sem_erros(app)
        registro = next(
            r
            for r in app.session_state["_teste_export"]
            if r["Nome"] == historico[pessoa]["nome"]
        )
        self.assertEqual(registro["Partido de destino no cenário"], "PDT")
        self.assertEqual(registro["Sigla original mais recente"], "PSD")
        app.multiselect(key="origens_chapa_PDT").set_value(["PL"]).run()
        self.sem_erros(app)
        self.assertEqual(app.multiselect(key="chapa_PDT").value, [pessoa])

    def test_estreante_genero_observacao_e_remocao(self):
        app = self.abrir()
        app.text_input(key="novo_nome").set_value("Pessoa Estreante")
        app.selectbox(key="novo_genero").set_value("Feminino")
        app.text_input(key="novo_observacao").set_value("Nunca concorreu")
        app.button(key="cadastrar_nome").click().run()
        self.sem_erros(app)
        app.multiselect(key="chapa_FE_BRASIL_PV").set_value(
            ["AVULSO|PESSOA ESTREANTE"]
        ).run()
        self.sem_erros(app)
        registro = next(
            r
            for r in app.session_state["_teste_export"]
            if r["Nome"] == "Pessoa Estreante"
        )
        self.assertEqual(registro["Partido de destino no cenário"], "PV")
        self.assertEqual(registro["Gênero informado"], "Feminino")
        self.assertEqual(registro["Observação"], "Nunca concorreu")
        self.assertEqual(registro["Eleições observadas"], 0)
        app.sidebar.text_area[1].set_value("Pessoa Estreante;Masculino").run()
        self.sem_erros(app)
        self.assertEqual(
            app.multiselect(key="chapa_FE_BRASIL_PV").value, ["AVULSO|PESSOA ESTREANTE"]
        )
        app.multiselect(key="remover_novos").set_value(
            ["AVULSO|PESSOA ESTREANTE"]
        ).run()
        app.button(key="remover_cadastro").click().run()
        self.sem_erros(app)
        self.assertFalse(
            any(
                r["Nome"] == "Pessoa Estreante"
                for r in app.session_state["_teste_export"]
            )
        )

    def test_cota_por_membro_mesmo_se_conjunto_atende(self):
        app = self.abrir()
        pt = app.multiselect(key="chapa_FE_BRASIL_PT").value
        pv = app.multiselect(key="chapa_FE_BRASIL_PV").value
        texto = [
            f"{p};{'Feminino' if i == 0 else 'Masculino'}" for i, p in enumerate(pt)
        ]
        texto += [
            f"{p};{'Feminino' if i < 3 else 'Masculino'}" for i, p in enumerate(pv)
        ]
        app.sidebar.text_area[1].set_value("\n".join(texto)).run()
        self.sem_erros(app)
        self.assertEqual(app.multiselect(key="chapa_FE_BRASIL_PT").value, pt)
        self.assertEqual(app.multiselect(key="chapa_FE_BRASIL_PV").value, pv)
        self.assertTrue(
            any(
                "PT: 5/5 nomes; 1 Feminino, 4 Masculino" in w.value for w in app.warning
            )
        )
        self.assertTrue(any("4 Feminino, 6 Masculino" in w.value for w in app.warning))

    def test_recorte_vazio_ainda_permite_estreante(self):
        app = self.abrir()
        app.radio(key="base_preselecao").set_value(
            "Aplicar somente os filtros atuais"
        ).run()
        app.sidebar.slider[0].set_value(60).run()
        self.sem_erros(app)
        self.assertFalse(app.session_state["_teste_export"])
        app.sidebar.text_area[0].set_value("Pessoa sem histórico;contato").run()
        app.checkbox(key="puxar_chapa_FE_BRASIL_PV").set_value(False).run()
        app.multiselect(key="chapa_FE_BRASIL_PV").set_value(
            ["AVULSO|PESSOA SEM HISTORICO"]
        ).run()
        self.sem_erros(app)
        self.assertEqual(
            app.session_state["_teste_export"][0]["Partido de destino no cenário"], "PV"
        )

    def test_trocar_lista_cheia_por_estreante_e_projetar(self):
        app = self.abrir()
        original = app.multiselect(key="chapa_PDT").value
        self.assertEqual(len(original), 10)
        app.text_input(key="novo_nome").set_value("Estreante com estimativa")
        app.selectbox(key="novo_genero").set_value("Feminino")
        app.number_input(key="novo_estimativa").set_value(150)
        app.button(key="cadastrar_nome").click().run()
        self.sem_erros(app)
        novo = "AVULSO|ESTREANTE COM ESTIMATIVA"
        app.selectbox(key="retirar_chapa_PDT").set_value(original[0])
        app.selectbox(key="adicionar_chapa_PDT").set_value(novo)
        app.button(key="aplicar_chapa_PDT").click().run()
        self.sem_erros(app)
        atuais = app.multiselect(key="chapa_PDT").value
        self.assertEqual(len(atuais), 10)
        self.assertIn(novo, atuais)
        self.assertNotIn(original[0], atuais)
        app.number_input(key="legenda_ITAGUARA_MG_PDT").set_value(75).run()
        self.sem_erros(app)
        linhas = [
            r
            for r in app.session_state["_teste_export"]
            if r["Partido de destino no cenário"] == "PDT"
        ]
        self.assertEqual(
            next(
                r["Votos projetados"]
                for r in linhas
                if r["Nome"] == "Estreante com estimativa"
            ),
            150,
        )
        resumo = next(
            r for r in app.session_state["_teste_projecoes"] if r["Chapa"] == "PDT"
        )
        self.assertAlmostEqual(
            resumo["Total projetado"],
            sum(r["Votos projetados"] for r in linhas) + 75,
            places=2,
        )
        app.number_input(
            key="estimativa_ITAGUARA_MG_AVULSO|ESTREANTE COM ESTIMATIVA"
        ).set_value(250).run()
        self.sem_erros(app)
        atualizado = next(
            r for r in app.session_state["_teste_projecoes"] if r["Chapa"] == "PDT"
        )
        self.assertAlmostEqual(
            atualizado["Total projetado"], resumo["Total projetado"] + 100, places=2
        )
        self.assertEqual(app.multiselect(key="chapa_PDT").value, atuais)
        app.button(key="esvaziar_chapa_PDT").click().run()
        self.sem_erros(app)
        self.assertEqual(app.multiselect(key="chapa_PDT").value, [])

    def test_filtros_preservam_edicao_manual(self):
        app = self.abrir()
        nome = app.multiselect(key="chapa_PDT").value[0]
        app.multiselect(key="chapa_PDT").set_value([nome]).run()
        app.radio(key="base_preselecao").set_value(
            "Aplicar somente os filtros atuais"
        ).run()
        app.sidebar.slider(key="piso_qe").set_value(60).run()
        self.sem_erros(app)
        self.assertEqual(app.multiselect(key="chapa_PDT").value, [nome])
        self.assertEqual(len([w for w in app.warning if w.value.startswith("PDT:")]), 1)

    def test_desmarcar_e_remarcar_chapa_preserva_edicao(self):
        app = self.abrir()
        nome = app.multiselect(key="chapa_PDT").value[0]
        app.multiselect(key="chapa_PDT").set_value([nome]).run()
        app.sidebar.multiselect(key="selecoes").set_value(
            ["Partido: PV", "Partido: PODE"]
        ).run()
        app.sidebar.multiselect(key="selecoes").set_value(
            ["Partido: PDT", "Partido: PV", "Partido: PODE"]
        ).run()
        self.sem_erros(app)
        self.assertEqual(app.multiselect(key="chapa_PDT").value, [nome])

    def test_arquivo_ausente_nao_recebe_peso_nem_zero_ficticio(self):
        fonte = (PASTA / "app_2028.py").read_text(encoding="utf-8")
        fonte = fonte.replace(
            "pasta = Path(__file__).resolve().parent", f"pasta = Path({str(PASTA)!r})"
        )
        fonte = fonte.replace(
            "try:\n    dados_brutos",
            "bytes_anos = {2024: bytes_anos[2024]}\ntry:\n    dados_brutos",
            1,
        )
        fonte += '\nst.session_state["_teste_pesos"] = pesos_votacao\nst.session_state["_teste_votos"] = votos_projetados\n'
        app = AppTest.from_string(fonte, default_timeout=30).run()
        self.sem_erros(app)
        self.assertEqual(app.session_state["_teste_pesos"], {2016: 0, 2020: 0, 2024: 5})
        original = app.session_state["_teste_votos"].copy()
        app.sidebar.checkbox(key="ausencia_zero").set_value(True).run()
        self.sem_erros(app)
        self.assertEqual(app.session_state["_teste_votos"], original)
        app.sidebar.slider(key="peso_votacao_2024").set_value(0).run()
        self.sem_erros(app)
        self.assertTrue(app.button(key="reaplicar").disabled)


if __name__ == "__main__":
    unittest.main()
