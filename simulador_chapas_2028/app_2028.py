"""Simulador de chapas municipais: cenário, composição e votação."""

from __future__ import annotations
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from motor import (
    ANOS,
    FEDERACOES_2024,
    NOMES_SIGLAS,
    OPCOES,
    SIGLAS_2024,
    agrupamento_selecao,
    bloco_2024,
    calcular_base_votacao,
    chave_chapa,
    diagnosticar_cota_genero,
    editar_lista,
    explorar_historico,
    formatar_numero,
    historico_candidaturas,
    isolar_municipio,
    ler_csv,
    montar_generos,
    montar_novos_nomes,
    nome_bloco,
    norm,
    planilha,
    preselecionar_por_grupo,
    resumo_eleicoes,
)
from projecao import media_ponderada, resumir_votacao

st.set_page_config(
    page_title="Chapas 2028", page_icon=":material/ballot:", layout="wide"
)
ler_csv = st.cache_data(show_spinner=False, max_entries=12)(ler_csv)
st.title("Simulador de chapas 2028")
st.caption("Configure o cenário, monte as listas e confira a votação projetada.")

# Dados e filtros ficam na lateral; a composição ocupa o conteúdo principal.
pasta = Path(__file__).resolve().parent
with st.sidebar.expander("Dados eleitorais", expanded=True):
    bytes_anos = {}
    for ano in ANOS:
        envio = st.file_uploader(f"CSV {ano}", type="csv", key=f"csv_{ano}")
        if envio is not None:
            bytes_anos[ano] = envio.getvalue()
        elif (pasta / f"{ano}.csv").is_file():
            bytes_anos[ano] = (pasta / f"{ano}.csv").read_bytes()
    st.caption("Arquivos locais são usados quando não há upload.")
if not bytes_anos:
    st.info("Envie pelo menos um CSV eleitoral para começar.")
    st.stop()
try:
    dados_brutos = {a: ler_csv(b, a) for a, b in bytes_anos.items()}
except (ValueError, pd.errors.ParserError) as exc:
    st.error(f"Não foi possível ler os dados: {exc}")
    st.stop()

localidades = sorted(
    {
        (r["municipio"], norm(r.get("sg_uf", "")))
        for df in dados_brutos.values()
        for _, r in df.iterrows()
        if r["municipio"]
    }
)
if not localidades:
    st.error("Os arquivos não contêm municípios válidos.")
    st.stop()
if len(localidades) == 1:
    municipio, uf = localidades[0]
else:
    municipio, uf = st.sidebar.selectbox(
        "Município",
        localidades,
        format_func=lambda v: f"{v[0].title()} ({v[1]})",
        key="municipio",
    )
dados = {a: isolar_municipio(df, municipio, uf) for a, df in dados_brutos.items()}
resumo = resumo_eleicoes(dados)
if resumo.empty:
    st.error("Não há candidaturas a vereador em primeiro turno neste município.")
    st.stop()
ult_ano = int(resumo["Ano"].max())
vagas = int(resumo.loc[resumo["Ano"] == ult_ano, "Vagas observadas"].iloc[0])
if vagas <= 0:
    st.error(
        "O arquivo mais recente não permite identificar as vagas. Envie a totalização completa."
    )
    st.stop()
limite = vagas + 1

st.sidebar.header("Chapas do cenário")
selecoes = st.sidebar.multiselect("Partidos / federações", list(OPCOES), key="selecoes")
alvos = list(dict.fromkeys(agrupamento_selecao(OPCOES[s]) for s in selecoes))
if len(alvos) < len(selecoes):
    st.sidebar.caption("Membros da mesma federação compõem uma única chapa.")

with st.sidebar.expander("Filtros do histórico"):
    minimo_eleicoes = st.select_slider(
        "Participação em pelo menos", [1, 2, 3], value=2, key="minimo_eleicoes"
    )
    piso_qe_pct = st.slider("Menor votação (% do QE)", 0, 60, 8, key="piso_qe")
    regularidade = st.slider(
        "Regularidade mínima (%)", 0, 100, 50, 5, key="regularidade"
    )
    sem_eleitos = st.checkbox(
        "Ocultar quem já foi eleito", value=True, key="sem_eleitos"
    )
    apenas_2024 = st.checkbox("Somente participantes de 2024", key="apenas_2024")
with st.sidebar.expander("Cadastro em lote e gêneros"):
    texto_avulsos = st.text_area(
        "Novos nomes: Nome;Observação", key=f"lote_{municipio}_{uf}"
    )
    registros_lote, erros_avulsos = montar_novos_nomes(texto_avulsos)
    texto_generos = st.text_area(
        "Gêneros: Nome completo;Feminino ou Masculino", key=f"generos_{municipio}_{uf}"
    )
    generos_informados, erros_generos = montar_generos(texto_generos)
    if erros_avulsos or erros_generos:
        st.warning(" | ".join(erros_avulsos + erros_generos))
with st.sidebar.expander("Pesos da votação", expanded=True):
    pesos_votacao = {
        a: st.slider(f"Peso {a}", 0, 10, p, key=f"peso_votacao_{a}")
        if a in resumo["Ano"].values
        else 0
        for a, p in ((2016, 2), (2020, 3), (2024, 5))
    }
    ausencia_zero = st.checkbox("Tratar ausência como zero voto", key="ausencia_zero")
    st.caption(
        "Pesos aplicam-se às eleições carregadas. Por padrão, a média considera apenas as disputadas."
    )
    if not sum(pesos_votacao.values()):
        st.warning("Sem peso positivo, as médias históricas ficam pendentes.")

hist = historico_candidaturas(dados, resumo)
painel = explorar_historico(
    hist, minimo_eleicoes, piso_qe_pct, regularidade, sem_eleitos, apenas_2024
)

st.header(f"{municipio.title()} ({uf})")
c1, c2, c3 = st.columns(3)
c1.metric("Vagas observadas", vagas)
c2.metric("Limite por chapa", limite)
c3.metric("Pessoas no histórico", len(hist))
with st.expander("Consultar histórico eleitoral"):
    st.dataframe(resumo, hide_index=True, width="stretch")
    usar_filtros_consulta = st.checkbox(
        "Aplicar filtros à consulta", value=True, key="filtrar_consulta"
    )
    consulta = painel if usar_filtros_consulta else hist
    busca = norm(st.text_input("Buscar nome no histórico", key="busca_historico"))
    if busca:
        consulta = consulta[
            consulta["nome"].map(norm).str.contains(busca, regex=False)
            | consulta["urna"].map(norm).str.contains(busca, regex=False)
        ]
    st.caption(f"{len(consulta)} de {len(hist)} pessoas. Ordem alfabética.")
    st.dataframe(planilha(consulta), hide_index=True, width="stretch")
    st.download_button(
        "Exportar histórico consultado",
        planilha(consulta).to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"historico_{municipio.lower()}.csv",
        mime="text/csv",
    )
    st.caption(
        "Regularidade = menor / maior participação no QE nas eleições disputadas."
    )

st.header("1. Configurar o cenário")
st.caption(
    "Limites usam os dados e a referência eleitoral de 2024. O partido de destino é uma escolha do cenário."
)
reservas = {}
for grupo in alvos:
    membros = FEDERACOES_2024.get(grupo, (grupo,))
    if grupo not in FEDERACOES_2024:
        reservas[grupo] = {grupo: limite}
        continue
    with st.expander(f"Reservas locais — {nome_bloco(grupo)}"):
        if (municipio, uf, grupo) == ("ITAGUARA", "MG", "FE BRASIL"):
            padrao = {
                "PT": min(5, limite),
                "PV": min(5, max(0, limite - 5)),
                "PCDOB": 0,
            }
            st.caption(
                "Cenário local informado: PT 5, PV 5, PCdoB sem participação. Ajuste se necessário."
            )
        else:
            padrao = {
                p: limite // len(membros) + int(i < limite % len(membros))
                for i, p in enumerate(membros)
            }
        reservas[grupo] = {
            p: int(
                st.number_input(
                    f"Máximo — {NOMES_SIGLAS[p]}",
                    0,
                    limite,
                    padrao[p],
                    key=f"reserva_{municipio}_{uf}_{grupo}_{p}",
                )
            )
            for p in membros
        }
        if sum(reservas[grupo].values()) > limite:
            st.error(
                f"As reservas somam {sum(reservas[grupo].values())}; o limite conjunto é {limite}."
            )
config_valida = all(sum(r.values()) <= limite for r in reservas.values())
base_preselecao_opcao = st.radio(
    "Base da pré-seleção",
    ["Histórico completo (2016–2024)", "Aplicar somente os filtros atuais"],
    key="base_preselecao",
    horizontal=True,
)
incluir_eleitos_pre = st.checkbox(
    "Incluir pessoas eleitas na pré-seleção", value=True, key="incluir_eleitos_pre"
)
st.caption(
    "Sugestões usam os mesmos pesos da votação, com os resultados relativos ao QE para comparar eleições."
)

st.header("2. Cadastrar novos nomes")
cadastro_key = f"novos_{municipio}_{uf}"
st.session_state.setdefault(cadastro_key, {})
with st.expander("Cadastrar ou gerenciar estreantes"):
    with st.form(f"cadastro_{municipio}_{uf}", clear_on_submit=True):
        nome_novo = st.text_input("Nome completo", key="novo_nome")
        genero_novo = st.selectbox(
            "Gênero informado",
            ["Não informado", "Feminino", "Masculino"],
            key="novo_genero",
        )
        estimativa_novo = st.number_input(
            "Estimativa de votos",
            min_value=0,
            value=None,
            step=1,
            key="novo_estimativa",
        )
        observacao_novo = st.text_input("Observação", key="novo_observacao")
        cadastrar = st.form_submit_button("Cadastrar nome", key="cadastrar_nome")
    if cadastrar:
        nome_novo = nome_novo.strip()
        chave_novo = f"AVULSO|{norm(nome_novo)}"
        if not norm(nome_novo):
            st.error("Informe o nome completo.")
        elif (
            norm(nome_novo) in hist.index
            or chave_novo in registros_lote
            or chave_novo in st.session_state[cadastro_key]
        ):
            st.error("Esse nome já existe. Use o registro existente.")
        else:
            st.session_state[cadastro_key][chave_novo] = {
                "nome": nome_novo,
                "genero": genero_novo,
                "estimativa": estimativa_novo,
                "observacao": observacao_novo.strip(),
            }
            st.success("Nome cadastrado e disponível nas listas.")
    novos_cadastrados = st.session_state[cadastro_key]
    if novos_cadastrados:
        remover_novos = st.multiselect(
            "Remover cadastros",
            list(novos_cadastrados),
            format_func=lambda k: novos_cadastrados[k]["nome"],
            key="remover_novos",
        )
        if st.button(
            "Remover do cadastro", key="remover_cadastro", disabled=not remover_novos
        ):
            for pessoa in remover_novos:
                novos_cadastrados.pop(pessoa, None)
            st.rerun()
    st.caption(
        "Cadastros ficam nesta sessão e neste município. Exporte antes de encerrar."
    )
registros_novos = {**registros_lote, **novos_cadastrados}
repetidos = [k for k, r in registros_novos.items() if norm(r["nome"]) in hist.index]
for k in repetidos:
    registros_novos.pop(k)
if repetidos:
    st.warning(
        "Alguns nomes do cadastro já têm histórico. Use o registro eleitoral para evitar duplicação."
    )
avulsos = {k: r["nome"] for k, r in registros_novos.items()}
estimativas_novos = {}
if avulsos:
    with st.expander("Estimativas dos novos nomes"):
        for pessoa, r in registros_novos.items():
            estimativas_novos[pessoa] = st.number_input(
                f"Estimativa de votos — {r['nome']}",
                min_value=0,
                value=r.get("estimativa"),
                step=1,
                key=f"estimativa_{municipio}_{uf}_{pessoa}",
            )
            generos_informados.setdefault(
                norm(r["nome"]), r.get("genero", "Não informado")
            )

base_todos = calcular_base_votacao(
    hist, resumo, generos_informados, pesos_votacao, ausencia_zero
)
base_preselecao = (
    base_todos
    if base_preselecao_opcao.startswith("Histórico")
    else base_todos.loc[painel.index]
)
if not incluir_eleitos_pre:
    base_preselecao = base_preselecao[base_preselecao["vezes_eleito"] == 0]
base_conferencia = base_todos[["genero_planejamento"]].copy()
for pessoa, nome in avulsos.items():
    base_conferencia.loc[pessoa, "genero_planejamento"] = generos_informados.get(
        norm(nome), "Não informado"
    )
votos_projetados = {
    pessoa: media_ponderada(
        {a: r[f"votos_{a}"] for a in ANOS}, pesos_votacao, ausencia_zero
    )
    for pessoa, r in hist.iterrows()
}
votos_projetados.update(estimativas_novos)
ids_hist = sorted(hist.index, key=lambda k: norm(hist.at[k, "urna"]))
rotulos = {
    k: f"{hist.at[k, 'urna']} — {hist.at[k, 'nome']} ({hist.at[k, 'ultimo_partido']})"
    for k in ids_hist
}
rotulos.update({k: f"{nome} — estreante" for k, nome in avulsos.items()})
destinos = [
    p for r in reservas.values() for p, capacidade in r.items() if capacidade > 0
]
limites_destinos = {p: n for r in reservas.values() for p, n in r.items() if n > 0}
sugestoes, _ = preselecionar_por_grupo(
    base_preselecao, destinos, limite, limites_destinos
)
assinatura_dados = tuple(
    (a, hashlib.sha256(b).hexdigest()) for a, b in sorted(bytes_anos.items())
)
contexto = (municipio, uf, assinatura_dados)
mudou_contexto = st.session_state.get("_contexto_chapas") != contexto
if mudou_contexto:
    assinatura_anterior = st.session_state.get("_assinatura_preselecoes", ())
    migrar = (
        st.session_state.get("_contexto_chapas") is None
        and assinatura_anterior[1:4] == contexto
    )
    listas_anteriores = {
        chave_chapa(g, p): list(st.session_state[chave_chapa(g, p)])
        for g in alvos
        for p in reservas[g]
        if migrar and chave_chapa(g, p) in st.session_state
    }
    st.session_state["_contexto_chapas"] = contexto
    st.session_state["_composicoes"] = listas_anteriores
    st.session_state["_automaticas"] = {}
    st.session_state["_recorte_chapas"] = None
memoria = st.session_state["_composicoes"]
automaticas = st.session_state["_automaticas"]
recorte = (base_preselecao_opcao, incluir_eleitos_pre, tuple(base_preselecao.index))
mudou_recorte = st.session_state.get("_recorte_chapas") != recorte

st.header("3. Montar e editar")
st.caption(
    "As listas abaixo são a composição atual. Filtros orientam sugestões; escolhas manuais são preservadas."
)
b1, b2 = st.columns(2)
sugestoes_habilitadas = config_valida and bool(sum(pesos_votacao.values()))
gerar = b1.button(
    "Aplicar pré-seleção",
    key="reaplicar",
    disabled=not alvos or not sugestoes_habilitadas,
    help="Substitui a composição ativa pelas sugestões calculadas agora.",
)
limpar = b2.button(
    "Começar com todas as listas vazias", key="esvaziar_todas", disabled=not alvos
)
validos = set(ids_hist) | set(avulsos)
for grupo in alvos:
    for partido, capacidade in reservas[grupo].items():
        chave = chave_chapa(grupo, partido)
        atual = (
            list(memoria.get(chave, []))
            if mudou_contexto
            else list(st.session_state.get(chave, memoria.get(chave, [])))
        )
        inicial = chave not in memoria
        pristine = atual == automaticas.get(chave)
        if sugestoes_habilitadas and (gerar or inicial or (mudou_recorte and pristine)):
            atual = list(sugestoes.get(partido, []))
            automaticas[chave] = atual.copy()
        if limpar:
            atual = []
            automaticas[chave] = None
        atual = list(dict.fromkeys(p for p in atual if p in validos))
        if len(atual) > capacidade:
            st.warning(
                f"{NOMES_SIGLAS[partido]}: a reserva foi reduzida; {len(atual) - capacidade} nome(s) foram retirados do fim da lista."
            )
            atual = atual[:capacidade]
        memoria[chave] = atual
        st.session_state[chave] = atual
st.session_state["_recorte_chapas"] = recorte

selecionados, partidos_destino, resumos_votacao, linhas_export = {}, {}, [], []
if not alvos:
    st.info("Selecione partidos ou federações na lateral para montar as chapas.")
for grupo in alvos:
    titulo = nome_bloco(grupo)
    selecionados[grupo], partidos_destino[grupo] = [], {}
    membros_ok = []
    with st.container(border=True):
        st.subheader(titulo)
        if grupo in FEDERACOES_2024:
            st.caption(
                "Reservas: "
                + " · ".join(
                    f"{NOMES_SIGLAS[p]} {n}" for p, n in reservas[grupo].items() if n
                )
            )
        for partido, capacidade in reservas[grupo].items():
            if not capacidade:
                continue
            chave = chave_chapa(grupo, partido)
            atuais = st.session_state[chave]
            ocupados = {
                pessoa
                for g in alvos
                for p in reservas[g]
                if chave_chapa(g, p) != chave
                for pessoa in st.session_state.get(chave_chapa(g, p), [])
            }
            with st.expander(f"Buscar e trocar nomes — {NOMES_SIGLAS[partido]}"):
                puxar = st.checkbox(
                    "Puxar nomes de outros partidos / fora do recorte",
                    value=True,
                    key=f"puxar_{chave}",
                )
                origens = st.multiselect(
                    "Último partido observado",
                    sorted(hist["ultimo_partido"].unique()),
                    key=f"origens_{chave}",
                    disabled=not puxar,
                )
                pool = (
                    hist
                    if puxar
                    else base_preselecao.loc[
                        base_preselecao["partidos"]
                        .map(lambda ps: partido in ps)
                        .astype(bool)
                    ]
                )
                if puxar and origens:
                    pool = pool[pool["ultimo_partido"].isin(origens)]
                opcoes = sorted(
                    (set(pool.index) | set(avulsos)) - ocupados,
                    key=lambda k: norm(rotulos[k]),
                )
                opcoes = list(dict.fromkeys(atuais + opcoes))
                with st.form(f"editar_{chave}", clear_on_submit=True):
                    retirar = st.selectbox(
                        "Nome a retirar ou substituir",
                        [None] + atuais,
                        format_func=lambda k: (
                            rotulos[k] if k else "Nenhum — só adicionar"
                        ),
                        key=f"retirar_{chave}",
                    )
                    adicionar = st.selectbox(
                        "Nome a incluir",
                        [None] + [p for p in opcoes if p not in atuais],
                        format_func=lambda k: (
                            rotulos[k] if k else "Nenhum — só retirar"
                        ),
                        key=f"adicionar_{chave}",
                    )
                    aplicar = st.form_submit_button(
                        "Aplicar edição",
                        key=f"aplicar_{chave}",
                        disabled=not config_valida,
                    )
                if aplicar:
                    try:
                        st.session_state[chave] = editar_lista(
                            atuais, retirar, adicionar, capacidade, ocupados
                        )
                        st.success("Lista atualizada.")
                    except ValueError as exc:
                        st.warning(str(exc))
                if st.button(
                    "Esvaziar esta lista",
                    key=f"esvaziar_{chave}",
                    disabled=not config_valida,
                ):
                    st.session_state[chave] = []
                st.caption(
                    "Para mover alguém entre listas, retire-o da origem antes de incluir no destino."
                )
            nomes = st.multiselect(
                f"Nomes para {NOMES_SIGLAS[partido]} (máximo {capacidade})",
                opcoes,
                format_func=lambda k: rotulos[k],
                key=chave,
                max_selections=capacidade,
                disabled=not config_valida,
            )
            memoria[chave] = nomes.copy()
            selecionados[grupo].extend(nomes)
            partidos_destino[grupo].update({pessoa: partido for pessoa in nomes})
            conferencia = diagnosticar_cota_genero(nomes, base_conferencia)
            membros_ok.append(conferencia["atende"] if nomes else True)
            if nomes:
                texto = (
                    f"{NOMES_SIGLAS[partido]}: {len(nomes)}/{capacidade} nomes; "
                    f"{conferencia['femininos']} Feminino, {conferencia['masculinos']} Masculino, "
                    f"{conferencia['nao_informados']} sem informação. Mínimo de cada gênero: {conferencia['minimo']}."
                )
                if conferencia["atende"]:
                    st.caption(texto + " Cota conferida.")
                else:
                    st.warning(texto)
        if grupo in FEDERACOES_2024 and selecionados[grupo]:
            total_cota = diagnosticar_cota_genero(selecionados[grupo], base_conferencia)
            texto = (
                f"Federação: {total_cota['femininos']} Feminino, {total_cota['masculinos']} Masculino, "
                f"{total_cota['nao_informados']} sem informação."
            )
            if not (total_cota["atende"] and all(membros_ok)):
                st.warning(texto + " Conferência pendente no conjunto ou em um membro.")
            else:
                st.caption(texto + " Cotas dos membros e do conjunto conferidas.")
        for pessoa in selecionados[grupo]:
            r = hist.loc[pessoa] if pessoa in hist.index else None
            historico = r is not None
            linhas_export.append(
                {
                    "Município": municipio,
                    "UF": uf,
                    "Cenário": 2028,
                    "Partido/Federação base 2024": titulo,
                    "Partido de destino no cenário": partidos_destino[grupo][pessoa],
                    "Nome": r["nome"] if historico else avulsos[pessoa],
                    "Nome de urna histórico": r["urna"] if historico else "",
                    "Sigla original mais recente": str(
                        r[f"sigla_{r['ultima_eleicao']}"]
                    )
                    if historico
                    else "",
                    "Eleições observadas": int(r["eleicoes"]) if historico else 0,
                    **{
                        f"Votos {a}": r[f"votos_{a}"] if historico else None
                        for a in ANOS
                    },
                    "Gênero informado": base_conferencia.at[
                        pessoa, "genero_planejamento"
                    ],
                    "Votos projetados": votos_projetados.get(pessoa),
                    "Método de projeção": "Média ponderada histórica"
                    if historico
                    else "Estimativa informada",
                    **{f"Peso {a}": peso for a, peso in pesos_votacao.items()},
                    "Ausência como zero": ausencia_zero,
                    "Observação": registros_novos.get(pessoa, {}).get("observacao", ""),
                }
            )
        linhas_grupo = [
            r for r in linhas_export if r["Partido/Federação base 2024"] == titulo
        ]
        if linhas_grupo:
            campos = [
                "Nome",
                "Partido de destino no cenário",
                "Sigla original mais recente",
                "Gênero informado",
                "Votos 2016",
                "Votos 2020",
                "Votos 2024",
                "Votos projetados",
            ]
            st.dataframe(
                pd.DataFrame(linhas_grupo)[campos], hide_index=True, width="stretch"
            )
        else:
            st.caption("Lista vazia. Adicione nomes ou aplique a pré-seleção.")
        votos_legenda = st.number_input(
            "Votos exclusivamente de legenda",
            min_value=0,
            value=0,
            step=1,
            key=f"legenda_{municipio}_{uf}_{grupo}",
        )
        resumo_votos = resumir_votacao(
            [votos_projetados.get(p) for p in selecionados[grupo]], votos_legenda
        )
        a, b, c = st.columns(3)
        a.metric("Nominais projetados", formatar_numero(resumo_votos["nominais"], 2))
        b.metric("Legenda estimada", formatar_numero(votos_legenda))
        c.metric("Total da chapa", formatar_numero(resumo_votos["total"], 2))
        if resumo_votos["pendentes"]:
            st.warning(
                f"Projeção parcial: {resumo_votos['pendentes']} nome(s) sem média ou estimativa."
            )
        resumos_votacao.append(
            {
                "Município": municipio,
                "UF": uf,
                "Cenário": 2028,
                "Chapa": titulo,
                "Nomes": len(selecionados[grupo]),
                "Nominais projetados": resumo_votos["nominais"],
                "Votos de legenda estimados": votos_legenda,
                "Total projetado": resumo_votos["total"],
                "Nomes com projeção pendente": resumo_votos["pendentes"],
                **{f"Peso {a}": peso for a, peso in pesos_votacao.items()},
                "Ausência como zero": ausencia_zero,
            }
        )

duplos = {}
for grupo, nomes in selecionados.items():
    for pessoa in nomes:
        duplos.setdefault(pessoa, []).append(grupo)
duplicados = {p: gs for p, gs in duplos.items() if len(gs) > 1}
if duplicados:
    st.error("Há nomes repetidos entre listas. Corrija antes de exportar.")
exportacao_valida = config_valida and not duplicados
st.header("4. Exportar o cenário")
if linhas_export:
    st.download_button(
        "Composição e votos por pessoa (CSV)",
        pd.DataFrame(linhas_export).to_csv(sep=";", index=False).encode("utf-8-sig"),
        file_name="composicoes_2028.csv",
        mime="text/csv",
        disabled=not exportacao_valida,
    )
if resumos_votacao:
    st.download_button(
        "Totais por chapa (CSV)",
        pd.DataFrame(resumos_votacao).to_csv(sep=";", index=False).encode("utf-8-sig"),
        file_name="projecoes_votacao_2028.csv",
        mime="text/csv",
        disabled=not exportacao_valida,
    )

with st.expander("Como interpretar e conferir os dados"):
    st.markdown("""
- A votação projetada é uma média ponderada do histórico, acrescida das estimativas dos estreantes.
- Total da chapa = votos nominais projetados + votos exclusivamente de legenda, contados uma única vez.
- Filiação, participação dos partidos e disponibilidade dos nomes precisam ser conferidas para o cenário.
- A identificação usa nomes normalizados; homônimos e mudanças de nome exigem conferência.
- Vagas, limites e federações têm referência nos dados e nas regras de 2024.
- Gênero é informado pelo usuário ou pelo CSV; não é deduzido do nome.
""")
    catalogo = [
        {
            "Partido": NOMES_SIGLAS[p],
            "Bloco de referência 2024": nome_bloco(bloco_2024(p)),
        }
        for p in SIGLAS_2024
    ]
    st.dataframe(pd.DataFrame(catalogo), hide_index=True, width="stretch")
