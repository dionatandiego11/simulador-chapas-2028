# -*- coding: utf-8 -*-
"""
🗳️ Simulador de Chapas — versão legada (v3 — histórico 2016–2024)
- Federações 2024 agrupáveis em chapas e cenários (fixas + detectadas no CSV)
- Mapa completo de equivalências partidárias 2016→2020→2024 (TSE)
- Modos de chapa: histórico por partido | bloco federativo | sugestão livre
- Histórico original preservado + equivalência 2024 e relatório de cadeiras observadas
- Chapa ideal global + pré-candidatos avulsos
Rodar:  pip install streamlit pandas   →   streamlit run app.py
"""
import io
from pathlib import Path
import re
import unicodedata

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Simulador de Chapas v3", page_icon="🗳️", layout="wide")

ANOS = [2016, 2020, 2024]

# ============================================================ PARTIDOS / BLOCOS
# Sigla histórica -> sigla vigente em 2024 (TSE). Institucional: não transfere
# automaticamente eleitorado — serve para alinhar o histórico partidário.
MAPA_PARTIDOS = {
    # mudança de nome/sigla
    "PTN": "PODE", "PTDOB": "AVANTE", "PMDB": "MDB", "PEN": "PRD",
    "PSDC": "DC", "SD": "SOLIDARIEDADE", "PR": "PL", "PRB": "REPUBLICANOS",
    "PPS": "CIDADANIA", "PTC": "AGIR", "PMN": "MOBILIZA",
    # fusões
    "PSL": "UNIAO", "DEM": "UNIAO", "PTB": "PRD", "PATRIOTA": "PRD",
    # incorporações
    "PRP": "PRD", "PPL": "PCDOB", "PHS": "PODE", "PSC": "PODE",
    "PROS": "SOLIDARIEDADE",
    # grafias
    "PC DO B": "PCDOB", "PCDO B": "PCDOB", "PCDO B ": "PCDOB",
}

FEDERACOES_2024 = {                       # bloco -> partidos membros
    "FE BRASIL": ["PT", "PCDOB", "PV"],
    "FED. PSDB CIDADANIA": ["PSDB", "CIDADANIA"],
    "FED. PSOL REDE": ["PSOL", "REDE"],
}
BLOCOS = {p: b for b, ps in FEDERACOES_2024.items() for p in ps}
COMP_BLOCOS = {b: list(ps) for b, ps in FEDERACOES_2024.items()}

def bloco_de(p: str) -> str:
    return BLOCOS.get(p, p)

def registrar_federacao(nome: str, partidos: list):
    for p in partidos:
        BLOCOS[p] = nome
    COMP_BLOCOS[nome] = partidos

def federacoes_do_csv(d: pd.DataFrame) -> dict:
    """Extrai federações de ds_composicao_coligacao:
    'Federação BRASIL DA ESPERANÇA - FE BRASIL (PT / PC do B / PV)'"""
    achadas = {}
    for comp in d["ds_composicao_coligacao"].fillna("").unique():
        c = norm(comp)
        m = re.match(r"^FEDERACAO\s+(.*?)\s*\(([^)]+)\)\s*$", c)
        if not m:
            continue
        g1, g2 = m.group(1), m.group(2)
        nome = g1.split(" - ")[-1].strip()
        if nome == g1:
            nome = f"FED. {g1.strip()}"
        ps = [MAPA_PARTIDOS.get(norm(x), norm(x)) for x in g2.split("/")]
        achadas.setdefault(nome, [])
        achadas[nome] = sorted(set(achadas[nome]) | set(ps))
    return achadas

# ============================================================ UTILIDADES
def norm(txt) -> str:
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return " ".join(t.upper().split())

@st.cache_data(show_spinner=False)
def ler_csv(conteudo: bytes, ano: int) -> pd.DataFrame:
    # Aceita tanto os CSVs oficiais do TSE (ISO-8859-1) quanto arquivos
    # exportados em UTF-8 com BOM, sem corromper acentos no upload.
    ultimo_erro = None
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(conteudo), sep=";", encoding=codificacao,
                             dtype=str)
            break
        except UnicodeDecodeError as exc:
            ultimo_erro = exc
    else:
        raise ValueError(f"CSV {ano}: codificação não reconhecida") from ultimo_erro
    df.columns = [str(c).replace("ï»¿", "").strip() for c in df.columns]
    for col in ("nr_turno", "qt_votos_nom_validos", "qt_votos_concorrentes"):
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.strip().str.replace(",", ".", regex=False),
                errors="coerce").fillna(0)
        else:
            df[col] = 0
    df["ano"] = ano
    df["municipio"] = df["nm_municipio"].map(norm)
    df["cargo"] = df["ds_cargo"].map(norm)
    df["partido_original"] = df["sg_partido"].map(norm)
    df["partido"] = df["partido_original"].map(lambda p: MAPA_PARTIDOS.get(p, p))
    df["cand_key"] = df["nm_candidato"].map(norm)
    df["eleito"] = df["ds_sit_totalizacao"].map(norm).str.startswith("ELEITO")
    return df

def filtrar(df: pd.DataFrame, cidade: str) -> pd.DataFrame:
    return df[(df["municipio"] == cidade) & (df["cargo"] == "VEREADOR")
              & (df["nr_turno"] == 1)].copy()

def calcular_qe(votos_validos: int, vagas: int) -> int:
    """Código Eleitoral art. 106: frações até 0,5 são descartadas; acima, sobe 1."""
    if vagas <= 0:
        return 0
    q, resto = divmod(int(votos_validos), int(vagas))
    return q + int(2 * resto > vagas)


def resumo_ano(d: pd.DataFrame, vagas: int):
    validos = d["qt_votos_concorrentes"].max()
    if pd.isna(validos) or validos <= 0:
        validos = d["qt_votos_nom_validos"].sum()
    return float(validos), calcular_qe(int(validos), vagas)

def escalar_legenda(votos_partido: pd.Series, validos: float) -> pd.Series:
    nominais = votos_partido.sum()
    return votos_partido * (validos / nominais) if nominais > 0 else votos_partido

def distribuir_cadeiras(votos: dict, vagas: int):
    """Apenas indicador por maiores médias, NÃO apuração oficial TSE.

    Os CSVs de candidaturas não discriminam votos de legenda por agremiação,
    nem permitem reconstruir todas as condições de elegibilidade das sobras.
    """
    cadeiras = {g: 0 for g in votos}
    total = sum(max(0, float(v)) for v in votos.values())
    qe = calcular_qe(round(total), vagas)
    if vagas <= 0 or total <= 0:
        return cadeiras, qe
    for _ in range(vagas):
        elegiveis = [g for g in votos if float(votos[g]) > 0]
        if not elegiveis:
            break
        escolhido = max(elegiveis, key=lambda g: (float(votos[g]) / (cadeiras[g] + 1), float(votos[g]), str(g)))
        cadeiras[escolhido] += 1
    return cadeiras, qe

# ============================================================ HISTÓRICO
def montar_historico(dfs_f: dict, qes: dict, pesos: dict) -> pd.DataFrame:
    linhas = []
    for ano, d in dfs_f.items():
        if d.empty:
            continue
        for _, r in d.iterrows():
            linhas.append({"cand_key": r["cand_key"], "nome": str(r["nm_candidato"]).strip(),
                           "urna": str(r["nm_urna_candidato"]).strip(), "partido": r["partido"],
                           "votos": float(r["qt_votos_nom_validos"]), "eleito": bool(r["eleito"]),
                           "ano": ano})
    if not linhas:
        return pd.DataFrame()
    h = pd.DataFrame(linhas).sort_values("ano")
    hist = h.groupby("cand_key").agg(
        nome=("nome", "last"), urna=("urna", "last"),
        ultimo_partido=("partido", "last"),
        partidos=("partido", lambda s: sorted(set(s))),
        eleicoes=("ano", "nunique"), vezes_eleito=("eleito", "sum"))
    vp = h.pivot_table(index="cand_key", columns="ano", values="votos", aggfunc="max")
    for a in ANOS:
        hist[f"votos_{a}"] = vp[a] if a in vp.columns else 0.0
    hist[[f"votos_{a}" for a in ANOS]] = hist[[f"votos_{a}" for a in ANOS]].fillna(0.0)
    qe_seg = {a: max(qes.get(a, 0), 1) for a in ANOS}
    hist["score"] = sum(hist[f"votos_{a}"] / qe_seg[a] * pesos.get(a, 0.0) for a in ANOS)
    hist["ultimo_bloco"] = hist["ultimo_partido"].map(bloco_de)
    hist["blocos"] = hist["partidos"].apply(lambda L: sorted({bloco_de(p) for p in L}))
    hist["origem"] = "Histórico"
    return hist.sort_values("score", ascending=False)

def acrescentar_precandidatos(hist: pd.DataFrame, texto: str, qe_base: float):
    """Linhas 'Nome;PARTIDO' ou 'Nome;PARTIDO;votos_estimados'."""
    novos, erros = [], []
    for i, ln in enumerate(texto.splitlines(), 1):
        ln = ln.strip()
        if not ln:
            continue
        partes = [x.strip() for x in ln.split(";")]
        if len(partes) < 2 or not partes[0] or not partes[1]:
            erros.append(f"linha {i}: '{ln}'")
            continue
        nome, p = partes[0], MAPA_PARTIDOS.get(norm(partes[1]), norm(partes[1]))
        ve = 0.0
        if len(partes) >= 3:
            try:
                ve = float(partes[2].replace(",", "."))
            except ValueError:
                erros.append(f"linha {i}: votos inválidos")
        novos.append({"cand_key": norm(nome), "nome": nome, "urna": nome,
                      "ultimo_partido": p, "ultimo_bloco": bloco_de(p),
                      "partidos": [p], "blocos": [bloco_de(p)],
                      "eleicoes": 0, "vezes_eleito": 0,
                      "votos_2016": 0.0, "votos_2020": 0.0, "votos_2024": 0.0,
                      "score": ve / max(qe_base, 1), "origem": "Pré-candidato"})
    if not novos:
        return hist, erros
    pc = pd.DataFrame(novos).drop_duplicates("cand_key")
    pc = pc[~pc["cand_key"].isin(hist.index)]          # histórico tem prioridade
    return pd.concat([hist, pc.set_index("cand_key")]).sort_values("score", ascending=False), erros

# ============================================================ CHAPAS
def montar_chapas_vinculo(hist, alvos, limite, por_bloco: bool):
    """Modos 1 e 2: 1º passe = último vínculo; 2º = vínculo em qualquer eleição."""
    col_ult = "ultimo_bloco" if por_bloco else "ultimo_partido"
    col_grp = "blocos" if por_bloco else "partidos"
    chapas = {a: hist.iloc[0:0].copy() for a in alvos}
    usados = set()
    for a in alvos:
        pool = hist[(hist[col_ult] == a) & (~hist.index.isin(usados))]
        chapas[a] = pool.sort_values("score", ascending=False).head(limite).copy()
        usados.update(chapas[a].index)
    for a in alvos:
        faltam = limite - len(chapas[a])
        if faltam > 0:
            extra = hist[hist[col_grp].apply(lambda L: a in L)
                         & (~hist.index.isin(usados))]
            extra = extra.sort_values("score", ascending=False).head(faltam)
            chapas[a] = pd.concat([chapas[a], extra])
            usados.update(extra.index)
    return chapas, usados

def marca_vinculo(r, b):
    if r["origem"] == "Pré-candidato":
        return "✚ Pré-candidato"
    vinc = r["ultimo_bloco"] == b or any(bloco_de(p) == b for p in r["partidos"])
    return "✔ Vínculo histórico" if vinc else "↔ Campo aberto"

def montar_chapas_livre(hist, alvos, limite, priorizar_vinculo=True):
    """Modo 3: round-robin — em cada rodada cada bloco recebe seu melhor candidato
    ainda não usado (ordenado por vínculo+score). Usa TODO o campo."""
    ordens, chapas = {}, {b: [] for b in alvos}
    for b in alvos:
        h = hist.copy()
        h["_vinc"] = h.apply(lambda r: r["ultimo_bloco"] == b
                             or any(bloco_de(p) == b for p in r["partidos"]), axis=1)
        if priorizar_vinculo:
            h = h.sort_values(["_vinc", "score"], ascending=[False, False])
        else:
            h = h.sort_values("score", ascending=False)
        ordens[b] = h
    pont, usados = {b: 0 for b in alvos}, set()
    while True:
        progrediu = False
        for b in alvos:
            if len(chapas[b]) >= limite:
                continue
            lst = ordens[b]
            while pont[b] < len(lst):
                idx = lst.index[pont[b]]
                pont[b] += 1
                if idx not in usados:
                    chapas[b].append(idx)
                    usados.add(idx)
                    progrediu = True
                    break
        if not progrediu:
            break
    out = {}
    for b in alvos:
        df = hist.loc[chapas[b]].copy() if chapas[b] else hist.iloc[0:0].copy()
        df["Vínculo"] = [marca_vinculo(hist.loc[i], b) for i in chapas[b]]
        out[b] = df
    return out, usados

# ============================================================ SIDEBAR
st.sidebar.title("🗳️ Simulador de Chapas v3")
uploads = {a: st.sidebar.file_uploader(f"CSV {a}", type="csv", key=f"up{a}") for a in ANOS}
cidade = st.sidebar.text_input("Cidade (ex.: Itaguara)", value="Itaguara")
vagas = st.sidebar.number_input("Vagas de vereador", 1, 100, 9)
n_partidos = st.sidebar.number_input("Nº de partidos/blocos", 1, 30, 5)
partidos_raw = [st.sidebar.text_input(f"Partido {i+1}", key=f"part{i}").strip()
                for i in range(int(n_partidos))]
partidos_sel = []
for p in partidos_raw:
    if not p:
        continue
    pn = MAPA_PARTIDOS.get(norm(p), norm(p))
    if pn != norm(p):
        st.sidebar.caption(f"↪ `{p}` → **{pn}** (equivalência TSE)")
    partidos_sel.append(pn)
partidos_sel = list(dict.fromkeys(partidos_sel))
limite = st.sidebar.number_input(
    "Candidatos por chapa", min_value=1, max_value=int(vagas) + 1, value=int(vagas) + 1,
    help="Regra aplicada em 2024 (Lei 9.504/97, art. 10): até 100% das vagas + 1. "
         "Federação concorre como uma única chapa. Conferir legislação do próximo pleito.")
agg = st.sidebar.radio("Agregação (força e cadeiras)",
                       ["Por partido", "Por bloco federativo (2024)"])
por_bloco = agg.startswith("Por bloco")
st.sidebar.markdown("---")
st.sidebar.subheader("Pesos do histórico")
pesos = {2016: st.sidebar.slider("Peso 2016", 0.0, 1.0, 0.2, 0.05),
         2020: st.sidebar.slider("Peso 2020", 0.0, 1.0, 0.3, 0.05),
         2024: st.sidebar.slider("Peso 2024", 0.0, 1.0, 0.5, 0.05)}
st.sidebar.markdown("---")
st.sidebar.subheader("Pré-candidatos avulsos (opcional)")
txt_precand = st.sidebar.text_area("Um por linha: `Nome;PARTIDO` ou `Nome;PARTIDO;votos_estimados`",
                                   height=100, placeholder="JOAO NOVO;PSD\nMARIA NOVA;AVANTE;300")

# ============================================================ CARGA
base_dir = Path(__file__).resolve().parent
arquivos = {}
for ano, enviado in uploads.items():
    if enviado is not None:
        arquivos[ano] = enviado.getvalue()
    elif (base_dir / f"{ano}.csv").is_file():
        arquivos[ano] = (base_dir / f"{ano}.csv").read_bytes()
        st.sidebar.caption(f"✅ CSV {ano}: carregado da pasta do app")
if not arquivos:
    st.info("👈 Envie pelo menos um CSV ou coloque 2016.csv, 2020.csv e 2024.csv na pasta do app.")
    st.stop()
dados = {a: ler_csv(raw, a) for a, raw in arquivos.items()}
if not cidade.strip():
    st.info("👈 Informe o nome da cidade.")
    st.stop()
cidade_n = norm(cidade)

dfs_f = {}
for a, df in dados.items():
    d = filtrar(df, cidade_n)
    if d.empty:
        st.warning(f"CSV {a}: nenhum registro para **{cidade.strip()}**.")
    dfs_f[a] = d
if all(d.empty for d in dfs_f.values()):
    st.error("Nada encontrado — confira a grafia da cidade.")
    st.stop()

# registra federações encontradas no CSV 2024
feds_csv = federacoes_do_csv(dfs_f[2024]) if 2024 in dfs_f and not dfs_f[2024].empty else {}
for nome, ps in feds_csv.items():
    registrar_federacao(nome, ps)

resumo = []
for a, d in dfs_f.items():
    if d.empty:
        continue
    validos, qe = resumo_ano(d, int(vagas))
    resumo.append({"Eleição": a, "Votos válidos": int(validos),
                   "Vagas": int(vagas), "QE": qe})
qes = {r["Eleição"]: r["QE"] for r in resumo}
validos_ano = {r["Eleição"]: r["Votos válidos"] for r in resumo}

# ============================================================ 1. QE
st.header("1️⃣ Quociente eleitoral")
st.dataframe(pd.DataFrame(resumo), hide_index=True, width="stretch")
if qes:
    st.success(f"QE médio histórico: **{round(sum(qes.values())/len(qes))}** votos/vaga. "
               f"Ano mais recente ({max(qes)}): QE {qes[max(qes)]}.")

# ============================================================ 2. FORÇA
st.header("2️⃣ Força partidária")
linhas = []
for a, d in dfs_f.items():
    if d.empty:
        continue
    g = d.groupby("partido")["qt_votos_nom_validos"].sum()
    for p, v in g.items():
        linhas.append({"Eleição": a, "Chave": bloco_de(p) if por_bloco else p,
                       "Votos nominais": int(v),
                       "% dos válidos": round(100 * v / validos_ano[a], 1)})
tb = pd.DataFrame(linhas)
if por_bloco:
    tb = tb.groupby(["Eleição", "Chave"], as_index=False).sum()
st.dataframe(tb.sort_values(["Eleição", "Votos nominais"], ascending=[True, False]),
             hide_index=True, width="stretch")
st.caption("Os votos desta tabela são nominais (dos candidatos). Ao selecionar blocos, "
           "as votações de 2016 e 2020 são somadas retrospectivamente pelas federações de 2024; "
           "elas não existiam naqueles pleitos. Não há distribuição oficial de votos de legenda.")

with st.expander("🔎 Siglas originais presentes nos CSVs e equivalências de 2024"):
    origem = []
    for a, d in dfs_f.items():
        if d.empty:
            continue
        for (orig, atual), sub in d.groupby(["partido_original", "partido"]):
            origem.append({"Ano": a, "Sigla na eleição": orig, "Equivalência institucional 2024": atual,
                           "Bloco federalizado 2024": bloco_de(atual),
                           "Candidaturas": len(sub), "Votos nominais": int(sub["qt_votos_nom_validos"].sum()),
                           "Cadeiras observadas": int(sub["eleito"].sum())})
    tabela_origem = pd.DataFrame(origem).sort_values(["Ano", "Sigla na eleição"])
    st.dataframe(tabela_origem, hide_index=True, width="stretch")
    st.download_button("⬇️ Baixar equivalências do município (CSV)",
        tabela_origem.to_csv(sep=";", index=False).encode("utf-8-sig"),
        "equivalencias_partidos_2016_2024.csv", "text/csv")

with st.expander("🤝 Federações em vigor (2024)"):
    fd = pd.DataFrame([{"Federação": b, "Partidos": " / ".join(ps),
                        "Detectada no CSV": "✅" if b in feds_csv else "tabela oficial"}
                       for b, ps in COMP_BLOCOS.items()])
    st.dataframe(fd, hide_index=True, width="stretch")
    st.caption("Na federação, os partidos lançam candidatos em conjunto — a chapa do bloco "
               "tem limite próprio, como um partido único.")

with st.expander("📋 Equivalência de partidos 2016 → 2020 → 2024 (TSE)"):
    TABELA_EQUIV = [
        ("DEM", "DEM", "UNIÃO", "Fusão DEM+PSL (2022)"), ("PSL", "PSL", "UNIÃO", "Fusão (2022)"),
        ("PTB", "PTB", "PRD", "Fusão PTB+PATRIOTA (2023)"), ("PEN", "PATRIOTA", "PRD", "PEN→PATRIOTA; fusão"),
        ("PRP", "—", "PRD", "Incorporado ao PATRIOTA (2019)"), ("PTN", "PODE", "PODE", "Nome novo (2017)"),
        ("PHS", "—", "PODE", "Incorporado (2019)"), ("PSC", "PSC", "PODE", "Incorporado (2023)"),
        ("PTdoB", "AVANTE", "AVANTE", "Nome novo (2017)"), ("PMDB", "MDB", "MDB", "Nome novo (2018)"),
        ("PSDC", "DC", "DC", "Nome novo (2018)"), ("PR", "PL", "PL", "Nome novo (2019)"),
        ("PRB", "REPUBLICANOS", "REPUBLICANOS", "Nome novo (2019)"), ("PPS", "CIDADANIA", "CIDADANIA", "Nome novo (2019)"),
        ("PTC", "PTC", "AGIR", "Nome novo (2022)"), ("PMN", "PMN", "MOBILIZA", "Nome novo (2023)"),
         ("PROS", "PROS", "SOLIDARIEDADE", "Incorporado (2023)"), ("PPL", "—", "PCdoB", "Incorporado (2019)"),
         ("SD", "SOLIDARIEDADE", "SOLIDARIEDADE", "Mudança da sigla de exibição"),
         ("PP", "PP", "PP", "Progressista → Progressistas; sigla mantida")]
    st.dataframe(pd.DataFrame(TABELA_EQUIV, columns=["2016", "2020", "2024", "Observação"]),
                 hide_index=True, width="stretch")
    st.caption("Equivalência institucional — não implica transferência automática de eleitorado.")

# ============================================================ 3. CHAPAS
st.header("3️⃣ Chapas")
modo = st.radio("Como montar?", ["🏛️ Por partido (histórico)", "🤝 Por bloco federativo",
                                 "✨ Sugestão livre — todo o campo"], horizontal=True)
if not partidos_sel:
    st.info("Informe ao menos um partido na barra lateral.")
    st.stop()

hist = montar_historico(dfs_f, qes, pesos)
if hist.empty:
    st.error("Sem candidatos no histórico desta cidade.")
    st.stop()
if txt_precand.strip():
    hist, erros = acrescentar_precandidatos(hist, txt_precand,
                                            qes.get(max(qes), 1) if qes else 1)
    st.caption(f"✚ {len(hist[hist['origem']=='Pré-candidato'])} pré-candidato(s) incluído(s)."
               + (f" ⚠️ Ignorado: {', '.join(erros)}" if erros else ""))

disponiveis = set().union(*hist["partidos"].tolist())
for p in partidos_sel:
    if p not in disponiveis:
        st.warning(f"**{p}** não aparece no histórico — confira a grafia.")

modo_partido = modo.startswith("🏛️")
alvos = list(dict.fromkeys(partidos_sel if modo_partido else (bloco_de(p) for p in partidos_sel)))
if modo_partido and any(bloco_de(p) != p for p in partidos_sel):
    st.warning("Modo por partido: separação para ANÁLISE HISTÓRICA. "
               "Na eleição de 2024, partidos federados concorrem em chapa conjunta.")
if not modo_partido:
    for bloco in alvos:
        if bloco in COMP_BLOCOS:
            st.info(f"🤝 Chapa federativa **{bloco}**: {' / '.join(COMP_BLOCOS[bloco])}")

if modo.startswith("🏛️"):
    chapas, _ = montar_chapas_vinculo(hist, alvos, int(limite), por_bloco=False)
elif modo.startswith("🤝"):
    chapas, _ = montar_chapas_vinculo(hist, alvos, int(limite), por_bloco=True)
else:
    priorizar = st.checkbox("Priorizar vínculo histórico do bloco", True,
                            help="Desligado = puramente por score, misturando partidos livremente.")
    chapas, _ = montar_chapas_livre(hist, alvos, int(limite), priorizar)

COLS = ["nome", "urna", "origem", "ultimo_partido", "votos_2016", "votos_2020",
        "votos_2024", "eleicoes", "vezes_eleito", "score"]
ROT = {"nome": "Candidato", "urna": "Nome de urna", "origem": "Origem",
       "ultimo_partido": "Última sigla observada (equivalência 2024)", "votos_2016": "Votos 2016",
       "votos_2020": "Votos 2020", "votos_2024": "Votos 2024", "eleicoes": "Eleições",
       "vezes_eleito": "Vezes eleito", "score": "Score"}
saida_download = []
for b, chapa in chapas.items():
    st.subheader(f"Chapa {b} — {len(chapa)}/{int(limite)} nomes")
    if len(chapa) < int(limite):
        st.caption(f"⚠️ Faltam {int(limite)-len(chapa)} nomes — complete pelo banco/ pré-candidatos.")
    if not chapa.empty:
        comp = chapa["ultimo_partido"].value_counts()
        st.caption("Composição: " + " | ".join(f"{p}: {n}" for p, n in comp.items()))
        if "Vínculo" in chapa.columns:
            st.dataframe(chapa[["Vínculo"] + COLS].rename(columns=ROT),
                         hide_index=True, width="stretch")
            saida_download.append(chapa[["Vínculo"] + COLS].assign(chapa=b))
        else:
            st.dataframe(chapa[COLS].rename(columns=ROT), hide_index=True, width="stretch")
            saida_download.append(chapa[COLS].assign(chapa=b))

if saida_download:
    st.download_button("⬇️ Baixar chapas (CSV ;)",
                       pd.concat(saida_download).rename(columns=ROT)
                       .to_csv(sep=";", index=False).encode("utf-8-sig"),
                       "chapas.csv", "text/csv")
else:
    st.info("Não há candidaturas para as chapas selecionadas.")

with st.expander(f"⭐ Chapa ideal — top {int(vagas)} de todo o campo (qualquer partido)"):
    ideal = hist.sort_values("score", ascending=False).head(int(vagas))
    st.dataframe(ideal[COLS].rename(columns=ROT), hide_index=True, width="stretch")
    st.caption("Se fosse possível escolher livremente em todo o campo eleitoral histórico.")

# ============================================================ BANCO
st.header("📋 Banco de candidatos")
st.caption("Score = Σ peso_ano × (votos_ano ÷ QE_ano). Pré-candidatos com votos estimados "
           "recebem score = estimativa ÷ QE do último ano.")
hist_v = hist.copy()
hist_v["Bloco 2024"] = hist_v["ultimo_bloco"]
st.dataframe(hist_v[COLS + ["Bloco 2024"]].rename(columns=ROT),
             hide_index=True, width="stretch")

# ============================================================ 4. CADEIRAS
st.header(f"4️⃣ Cadeiras observadas e cenários ilustrativos ({agg.lower()})")
chave = (lambda p: bloco_de(p)) if por_bloco else (lambda p: p)

def agrupar(vp: pd.Series) -> dict:
    g = {}
    for p, v in vp.items():
        g[chave(p)] = g.get(chave(p), 0) + v
    return g

if 2024 in dfs_f and not dfs_f[2024].empty:
    d24 = dfs_f[2024]
    eleitos24 = d24[d24["eleito"]].groupby("partido").size()
    eleitos_real = agrupar(eleitos24)
    st.subheader("Cadeiras observadas em 2024 (registradas no CSV)")
    st.dataframe(pd.DataFrame({"Grupo": list(eleitos_real),
                               "Cadeiras observadas": list(eleitos_real.values())})
                 .sort_values(["Cadeiras observadas", "Grupo"], ascending=[False, True]),
                 hide_index=True, width="stretch")
    if not por_bloco:
        st.caption("A repartição por sigla interna à federação é descritiva; "
                   "as vagas são conquistadas pelo conjunto federativo.")

    vp24 = escalar_legenda(d24.groupby("partido")["qt_votos_nom_validos"].sum(),
                           validos_ano[2024])
    cadeiras, qe24 = distribuir_cadeiras(agrupar(vp24), int(vagas))
    st.subheader(f"Estimativa ilustrativa por maiores médias, 2024 — QE = {qes[2024]}")
    st.caption("NÃO é reconstituição oficial: votos de legenda por partido indisponíveis; "
               "foram distribuídos proporcionalmente aos votos nominais. "
               "O método simplificado não reproduz elegibilidade individual nem regras de sobras.")
    gg = agrupar(vp24)
    st.dataframe(pd.DataFrame({"Grupo": list(gg), "Votos": [int(gg[g]) for g in gg],
                               "Cadeiras": [cadeiras[g] for g in gg]}
                    ).sort_values(["Cadeiras", "Votos"], ascending=False),
                    hide_index=True, width="stretch")

todos = sorted({p for d in dfs_f.values() if not d.empty for p in d["partido"].unique()})
shares = {p: sum(pesos[a] * d.loc[d["partido"] == p, "qt_votos_nom_validos"].sum()
                 / validos_ano[a] for a, d in dfs_f.items() if not d.empty) for p in todos}
soma = sum(shares.values())
if soma and validos_ano:
    ano_base = max(validos_ano)
    votos_proj = {p: s / soma * validos_ano[ano_base] for p, s in shares.items()}
    cadeiras_p, qe_proj = distribuir_cadeiras(agrupar(pd.Series(votos_proj)), int(vagas))
    gg = agrupar(pd.Series(votos_proj))
    st.subheader(f"Cenário ilustrativo ponderado — QE aproximado = {qe_proj}")
    st.caption("Exercício de médias ponderadas 2016/2020/2024, não previsão eleitoral "
               "nem apuração TSE; histórico de fusões/federações não equivale a soma de eleitorados.")
    st.dataframe(pd.DataFrame({"Grupo": list(gg),
        "É bloco escolhido?": ["✅" if g in alvos else "" for g in gg],
        "Votos projetados": [int(gg[g]) for g in gg],
        "Cadeiras": [cadeiras_p[g] for g in gg]}
        ).sort_values(["Cadeiras", "Votos projetados"], ascending=False),
        hide_index=True, width="stretch")

with st.expander("⚠️ Notas e limitações"):
    st.markdown("""- **Federação**: partidos federados lançam chapas em conjunto; aqui o bloco
herda o limite de partido único. Use a composição exibida para ratear os nomes (ex.: PT 5 + PV 5).
- **Equivalência TSE** é institucional — não transfere eleitorado automaticamente.
- Modo **sugestão livre** usa round-robin: cada rodada, cada bloco recebe seu melhor
candidato disponível (vínculo+score). Ninguém entra em duas chapas.
- Candidatos casados por **nome normalizado** — homônimos exigem conferência manual.
- **Cadeiras observadas** vêm de `ds_sit_totalizacao` do CSV; as demais distribuições são ILUSTRATIVAS.
- Votos de legenda imputados proporcionalmente apenas para os cenários indicativos; o CSV não traz legenda por partido.
- Cadeiras simuladas por maiores médias simplificadas, sem reproduzir as etapas legais de sobras,
  as exigências nominais ou eventual desdobramento por federação.
- **Limite de registro de chapa (regra 2024)**: número de vagas + 1 (Lei 9.504/1997, art. 10).
- **QE**: arredondar somente quando parte fracionária for superior a 0,5 (CE, art. 106).""")

# Fontes normativas (situação das eleições de 2024):
# https://www.tse.jus.br/legislacao/codigo-eleitoral/lei-das-eleicoes/lei-das-eleicoes-lei-nb0-9.504-de-30-de-setembro-de-1997
# https://www.tse.jus.br/legislacao/compilada/res/2021/resolucao-no-23-677-de-16-de-dezembro-de-2021
# https://www.tse.jus.br/partidos/partidos-politicos/partidos-registrados-no-tse
