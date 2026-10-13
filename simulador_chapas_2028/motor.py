"""Leitura, histórico e regras de composição; sem interface Streamlit."""

from __future__ import annotations
import io
import re
import unicodedata
import pandas as pd
from projecao import media_ponderada

ANOS = (2016, 2020, 2024)

# Fotografia histórica das 29 siglas registradas no TSE nas eleições de 2024.
# Não representa antecipação da composição do sistema partidário em 2028.
SIGLAS_2024 = (
    "AGIR",
    "AVANTE",
    "CIDADANIA",
    "DC",
    "MDB",
    "MOBILIZA",
    "NOVO",
    "PCB",
    "PCDOB",
    "PCO",
    "PDT",
    "PL",
    "PMB",
    "PODE",
    "PP",
    "PRD",
    "PRTB",
    "PSB",
    "PSD",
    "PSDB",
    "PSOL",
    "PSTU",
    "PT",
    "PV",
    "REDE",
    "REPUBLICANOS",
    "SOLIDARIEDADE",
    "UNIAO",
    "UP",
)

FEDERACOES_2024 = {
    "FE BRASIL": ("PT", "PCDOB", "PV"),
    "FED. PSDB CIDADANIA": ("PSDB", "CIDADANIA"),
    "FED. PSOL REDE": ("PSOL", "REDE"),
}
NOMES_FED = {
    "FE BRASIL": "Federação Brasil da Esperança (PT / PCdoB / PV)",
    "FED. PSDB CIDADANIA": "Federação PSDB Cidadania (PSDB / Cidadania)",
    "FED. PSOL REDE": "Federação PSOL REDE (PSOL / Rede)",
}
NOMES_SIGLAS = {
    p: "PCdoB" if p == "PCDOB" else "União Brasil" if p == "UNIAO" else p
    for p in SIGLAS_2024
}

# Equivalência institucional: NÃO representa migração, filiação atual,
# transferência de votos ou disponibilidade para uma chapa futura.
MAPA_PARTIDOS = {
    "PTN": "PODE",
    "PTDOB": "AVANTE",
    "PMDB": "MDB",
    "PEN": "PRD",
    "PSDC": "DC",
    "SD": "SOLIDARIEDADE",
    "PR": "PL",
    "PRB": "REPUBLICANOS",
    "PPS": "CIDADANIA",
    "PTC": "AGIR",
    "PMN": "MOBILIZA",
    "PSL": "UNIAO",
    "DEM": "UNIAO",
    "PTB": "PRD",
    "PATRIOTA": "PRD",
    "PRP": "PRD",
    "PPL": "PCDOB",
    "PHS": "PODE",
    "PSC": "PODE",
    "PROS": "SOLIDARIEDADE",
    "UB": "UNIAO",
    "PC DO B": "PCDOB",
    "PCDO B": "PCDOB",
    "PROGRESSISTAS": "PP",
}

MEMBRO_FED = {p: f for f, membros in FEDERACOES_2024.items() for p in membros}
OPCOES = {
    **{f"Partido: {NOMES_SIGLAS[p]}": p for p in SIGLAS_2024},
    **{f"Federação: {v}": k for k, v in NOMES_FED.items()},
}


def norm(texto: object) -> str:
    texto = unicodedata.normalize(
        "NFKD", str("" if texto is None or pd.isna(texto) else texto)
    )
    return " ".join(texto.encode("ascii", "ignore").decode().upper().split())


def padronizar_partido(sigla: object) -> str:
    original = norm(sigla)
    return MAPA_PARTIDOS.get(original, original)


def bloco_2024(partido: str) -> str:
    return MEMBRO_FED.get(partido, partido)


def nome_bloco(bloco: str) -> str:
    return NOMES_FED.get(bloco, NOMES_SIGLAS.get(bloco, bloco))


def agrupamento_selecao(item: str) -> str:
    """Uma sigla federada e sua federação são uma mesma chapa *na regra de 2024*."""
    return item if item in FEDERACOES_2024 else bloco_2024(item)


def ler_csv(bruto: bytes, ano: int) -> pd.DataFrame:
    # Os arquivos do TSE costumam vir em ISO-8859-1, mas uploads exportados
    # por planilhas frequentemente chegam em UTF-8 com BOM. Tentar UTF-8
    # primeiro evita mojibake sem deixar de aceitar os arquivos oficiais.
    ultimo_erro = None
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(
                io.BytesIO(bruto), sep=";", encoding=codificacao, dtype=str
            )
            break
        except UnicodeDecodeError as exc:
            ultimo_erro = exc
    else:
        raise ValueError(f"CSV {ano}: codificação não reconhecida") from ultimo_erro
    df.columns = [c.lstrip("\ufeff").replace("ï»¿", "").strip() for c in df.columns]
    obrigatorias = (
        "nm_municipio",
        "ds_cargo",
        "nr_turno",
        "nm_candidato",
        "nm_urna_candidato",
        "sg_partido",
        "ds_sit_totalizacao",
        "qt_votos_nom_validos",
        "qt_votos_concorrentes",
    )
    ausentes = [c for c in obrigatorias if c not in df.columns]
    if ausentes:
        raise ValueError(f"CSV {ano}: colunas ausentes: {', '.join(ausentes)}")
    for col in ("nr_turno", "qt_votos_nom_validos", "qt_votos_concorrentes"):
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce"
        ).fillna(0)
    df = df.drop_duplicates().reset_index(drop=True)
    df["ano"] = ano
    df["municipio"] = df["nm_municipio"].map(norm)
    df["cargo"] = df["ds_cargo"].map(norm)
    df["partido_original"] = df["sg_partido"].map(norm)
    df["partido"] = df["partido_original"].map(padronizar_partido)
    df["cand_key"] = df["nm_candidato"].map(norm)
    df["eleito"] = df["ds_sit_totalizacao"].map(norm).str.startswith("ELEITO")
    df["genero"] = df["ds_genero"].map(norm) if "ds_genero" in df.columns else ""
    return df


def isolar_municipio(df: pd.DataFrame, municipio: str, uf: str = "") -> pd.DataFrame:
    return df[
        (df["municipio"] == municipio)
        & (df["cargo"] == "VEREADOR")
        & (df["nr_turno"] == 1)
        & ((df["sg_uf"].fillna("").eq(uf)) if uf and "sg_uf" in df else True)
    ].copy()


def vagas_observadas(df: pd.DataFrame) -> int:
    """Infere vagas pelos nomes eleitos, se a exportação for completa."""
    if df.empty:
        return 0
    return int(df.loc[df["eleito"], "cand_key"].nunique())


def calcular_qe(validos: int, vagas: int) -> int:
    """Código Eleitoral, art. 106: eleva somente fração superior a 0,5."""
    if vagas <= 0:
        return 0
    parte, resto = divmod(int(validos), int(vagas))
    return parte + int(2 * resto > vagas)


def resumo_eleicoes(dados: dict[int, pd.DataFrame]) -> pd.DataFrame:
    linhas = []
    for ano, df in sorted(dados.items()):
        if df.empty:
            continue
        vagas = vagas_observadas(df)
        validos = int(df["qt_votos_concorrentes"].max())
        if validos <= 0:
            validos = int(df["qt_votos_nom_validos"].sum())
        linhas.append(
            {
                "Ano": ano,
                "Candidaturas": len(df),
                "Vagas observadas": vagas,
                "Limite de chapa (regra 2024)": vagas + 1 if vagas else None,
                "Votos válidos": validos,
                "QE": calcular_qe(validos, vagas) if vagas else None,
            }
        )
    return pd.DataFrame(linhas)


def historico_candidaturas(
    dados: dict[int, pd.DataFrame], resumo: pd.DataFrame
) -> pd.DataFrame:
    colunas = [
        "nome",
        "urna",
        "ultimo_partido",
        "partidos",
        "eleicoes",
        "vezes_eleito",
        "participou_2024",
        "ultima_eleicao",
        "media_qe_pct",
        "min_qe_pct",
        "regularidade_pct",
        "genero_historico",
    ]
    if not dados:
        return pd.DataFrame(columns=colunas)
    partes = [d for d in dados.values() if not d.empty]
    if not partes:
        return pd.DataFrame(columns=colunas)
    concat = pd.concat(partes, ignore_index=True)
    if concat.empty:
        return pd.DataFrame(columns=colunas)
    concat = concat.sort_values("ano")
    qes = dict(zip(resumo["Ano"], resumo["QE"]))
    concat["participacao_qe"] = concat.apply(
        lambda r: (
            (float(r["qt_votos_nom_validos"]) / float(qes[r["ano"]]))
            if pd.notna(qes.get(r["ano"])) and qes[r["ano"]] > 0
            else float("nan")
        ),
        axis=1,
    )
    linhas = []
    for chave, grupo in concat.groupby("cand_key", sort=True):
        grupo = grupo.sort_values("ano")
        ultimo = grupo.iloc[-1]
        frac = grupo["participacao_qe"].dropna()
        regularidade = (
            100 * frac.min() / frac.max() if len(frac) >= 2 and frac.max() > 0 else None
        )
        generos = [g for g in grupo["genero"].tolist() if g]
        item = {
            "cand_key": chave,
            "nome": str(ultimo["nm_candidato"]).strip(),
            "urna": str(ultimo["nm_urna_candidato"]).strip(),
            "ultimo_partido": ultimo["partido"],
            "partidos": sorted(set(grupo["partido"])),
            "partidos_originais": sorted(set(grupo["partido_original"])),
            "eleicoes": int(grupo["ano"].nunique()),
            "vezes_eleito": int(grupo["eleito"].sum()),
            "participou_2024": bool((grupo["ano"] == 2024).any()),
            "ultima_eleicao": int(ultimo["ano"]),
            "media_qe_pct": round(100 * frac.mean(), 1) if not frac.empty else None,
            "min_qe_pct": round(100 * frac.min(), 1) if not frac.empty else None,
            "regularidade_pct": round(regularidade, 1)
            if regularidade is not None
            else None,
            "genero_historico": generos[-1] if generos else "",
        }
        for ano in ANOS:
            eleicao = grupo[grupo["ano"] == ano]
            item[f"votos_{ano}"] = (
                int(eleicao["qt_votos_nom_validos"].max())
                if not eleicao.empty
                else None
            )
            item[f"status_{ano}"] = (
                str(eleicao.iloc[0]["ds_sit_totalizacao"])
                if not eleicao.empty
                else "Não concorreu"
            )
            item[f"sigla_{ano}"] = (
                str(eleicao.iloc[0]["sg_partido"]) if not eleicao.empty else "—"
            )
        linhas.append(item)
    return pd.DataFrame(linhas).set_index("cand_key").sort_values("urna")


def explorar_historico(
    hist: pd.DataFrame,
    minimo_eleicoes: int,
    piso_qe_pct: float,
    regularidade_pct: float,
    exclui_eleitos: bool,
    participou_2024: bool,
) -> pd.DataFrame:
    """Filtro descritivo; não calcula probabilidade nem recomenda candidaturas."""
    filtrado = hist[hist["eleicoes"] >= minimo_eleicoes]
    filtrado = filtrado[filtrado["min_qe_pct"].fillna(-1) >= piso_qe_pct]
    if minimo_eleicoes >= 2:
        filtrado = filtrado[filtrado["regularidade_pct"].fillna(-1) >= regularidade_pct]
    if exclui_eleitos:
        filtrado = filtrado[filtrado["vezes_eleito"] == 0]
    if participou_2024:
        filtrado = filtrado[filtrado["participou_2024"]]
    return filtrado.sort_values("urna")


def tem_vinculo(r: pd.Series, grupo: str) -> bool:
    membros = set(FEDERACOES_2024.get(grupo, (grupo,)))
    return bool(membros.intersection(r["partidos"]))


def normalizar_genero(valor: object) -> str:
    valor = norm(valor)
    if valor in {"F", "FEMININO", "MULHER"}:
        return "Feminino"
    if valor in {"M", "MASCULINO", "HOMEM"}:
        return "Masculino"
    return "Não informado"


def calcular_base_votacao(
    hist: pd.DataFrame,
    resumo: pd.DataFrame,
    generos_informados: dict[str, str],
    pesos: dict[int, float],
    ausencia_zero: bool = False,
) -> pd.DataFrame:
    """Ordena pelo histórico relativo ao QE, usando os mesmos pesos da projeção."""
    t = hist.copy()
    qes = dict(zip(resumo["Ano"], resumo["QE"]))

    def pontuar(r):
        percentuais = {
            a: 100 * r[f"votos_{a}"] / qes[a]
            if a in qes
            and pd.notna(qes[a])
            and qes[a] > 0
            and pd.notna(r[f"votos_{a}"])
            else None
            for a in ANOS
        }
        return media_ponderada(percentuais, pesos, ausencia_zero) or 0.0

    t["base_votacao"] = (
        t.apply(pontuar, axis=1) if not t.empty else pd.Series(dtype=float)
    )
    t["genero_planejamento"] = [
        generos_informados.get(
            chave, normalizar_genero(t.at[chave, "genero_historico"])
        )
        for chave in t.index
    ]
    return t


def cota_minima_genero(total: int) -> int:
    """Mínimo de 30%, com toda fração elevada (Res. TSE 23.609, art. 17, § 3º)."""
    return (3 * max(0, total) + 9) // 10


def preselecionar_por_grupo(
    base: pd.DataFrame,
    grupos: list[str],
    limite: int,
    limites: dict[str, int] | None = None,
) -> tuple[dict[str, list[str]], dict[str, dict[str, int | bool]]]:
    """Monta listas sem repetição, por votação histórica e com controle de gênero."""
    resultado = {grupo: [] for grupo in grupos}
    if base.empty or not grupos:
        return resultado, {}
    todos = list(
        base.sort_values(["base_votacao", "urna"], ascending=[False, True]).index
    )
    capacidades = {
        grupo: min(limite, max(0, (limites or {}).get(grupo, limite)))
        for grupo in grupos
    }
    total_alocavel = min(len(todos), sum(capacidades.values()))
    metas = {grupo: 0 for grupo in grupos}
    for _ in range(total_alocavel):
        grupo = min(
            (g for g in grupos if metas[g] < capacidades[g]), key=lambda g: metas[g]
        )
        metas[grupo] += 1
    minimo = {grupo: cota_minima_genero(metas[grupo]) for grupo in grupos}
    usados: set[str] = set()

    def ordem(grupo: str, genero: str | None = None) -> list[str]:
        filtrados = [
            p
            for p in todos
            if genero is None or base.at[p, "genero_planejamento"] == genero
        ]
        vinculados = [p for p in filtrados if tem_vinculo(base.loc[p], grupo)]
        demais = [p for p in filtrados if p not in vinculados]
        return vinculados + demais

    # Reserva o mínimo de candidaturas Femininas e Masculinas em cada grupo.
    for genero in ("Feminino", "Masculino"):
        for grupo in grupos:
            for pessoa in ordem(grupo, genero):
                if (
                    pessoa not in usados
                    and len(resultado[grupo]) < metas[grupo]
                    and len(
                        [
                            p
                            for p in resultado[grupo]
                            if base.at[p, "genero_planejamento"] == genero
                        ]
                    )
                    < minimo[grupo]
                ):
                    resultado[grupo].append(pessoa)
                    usados.add(pessoa)

    # Completa a cota de cada grupo sem ocupar vagas necessárias ao outro gênero.
    for grupo in grupos:
        for pessoa in ordem(grupo):
            if pessoa in usados or len(resultado[grupo]) >= metas[grupo]:
                continue
            genero = base.at[pessoa, "genero_planejamento"]
            atual_f = sum(
                base.at[p, "genero_planejamento"] == "Feminino"
                for p in resultado[grupo]
            )
            atual_m = sum(
                base.at[p, "genero_planejamento"] == "Masculino"
                for p in resultado[grupo]
            )
            maximo_por_genero = metas[grupo] - minimo[grupo]
            if genero == "Feminino" and atual_f >= maximo_por_genero:
                continue
            if genero == "Masculino" and atual_m >= maximo_por_genero:
                continue
            resultado[grupo].append(pessoa)
            usados.add(pessoa)

    diagnosticos = {}
    for grupo, pessoas in resultado.items():
        femininos = sum(
            base.at[p, "genero_planejamento"] == "Feminino" for p in pessoas
        )
        masculinos = sum(
            base.at[p, "genero_planejamento"] == "Masculino" for p in pessoas
        )
        nao_informados = len(pessoas) - femininos - masculinos
        minimo_real = cota_minima_genero(len(pessoas))
        atende = (
            len(pessoas) >= 2
            and nao_informados == 0
            and femininos >= minimo_real
            and masculinos >= minimo_real
        )
        diagnosticos[grupo] = {
            "meta": metas[grupo],
            "minimo": minimo_real,
            "femininos": femininos,
            "masculinos": masculinos,
            "nao_informados": nao_informados,
            "atende": atende,
        }
    return resultado, diagnosticos


def diagnosticar_cota_genero(
    pessoas: list[str], base: pd.DataFrame
) -> dict[str, int | bool]:
    """Resume a cota sobre os nomes efetivamente selecionados no cartão."""
    total = len(pessoas)
    minimo = cota_minima_genero(total)
    femininos = sum(
        p in base.index and base.at[p, "genero_planejamento"] == "Feminino"
        for p in pessoas
    )
    masculinos = sum(
        p in base.index and base.at[p, "genero_planejamento"] == "Masculino"
        for p in pessoas
    )
    nao_informados = total - femininos - masculinos
    atende = (
        total >= 2
        and nao_informados == 0
        and femininos >= minimo
        and masculinos >= minimo
    )
    return {
        "total": total,
        "minimo": minimo,
        "femininos": femininos,
        "masculinos": masculinos,
        "nao_informados": nao_informados,
        "atende": atende,
    }


def planilha(h: pd.DataFrame) -> pd.DataFrame:
    if h.empty:
        return pd.DataFrame(
            columns=[
                "Nome de urna",
                "Nome completo",
                "Eleições",
                "Eleito no recorte",
                "Votos 2016",
                "Votos 2020",
                "Votos 2024",
            ]
        )
    t = h.copy()
    t["Siglas históricas"] = t["partidos_originais"].map(lambda v: ", ".join(v))
    t["Siglas equivalentes 2024"] = t["partidos"].map(lambda v: ", ".join(v))
    t["Participou em 2024"] = t["participou_2024"].map({True: "Sim", False: "Não"})
    cols = {
        "urna": "Nome de urna",
        "nome": "Nome completo",
        "eleicoes": "Eleições",
        "vezes_eleito": "Eleito no recorte",
        "votos_2016": "Votos 2016",
        "votos_2020": "Votos 2020",
        "votos_2024": "Votos 2024",
        "media_qe_pct": "Média (% do QE)",
        "min_qe_pct": "Mínimo (% do QE)",
        "regularidade_pct": "Regularidade (%)",
        "ultima_eleicao": "Última eleição",
    }
    campos = [
        "urna",
        "nome",
        "eleicoes",
        "vezes_eleito",
        "votos_2016",
        "votos_2020",
        "votos_2024",
        "media_qe_pct",
        "min_qe_pct",
        "regularidade_pct",
        "ultima_eleicao",
        "Participou em 2024",
        "Siglas históricas",
        "Siglas equivalentes 2024",
    ]
    return t[campos].rename(columns=cols).reset_index(drop=True)


def montar_novos_nomes(texto: str) -> tuple[dict[str, dict], list[str]]:
    """Entrada opcional de pessoas sem votos passados; nomes nunca são pré-classificados."""
    novos, erros = {}, []
    for i, linha in enumerate(texto.splitlines(), 1):
        partes = [p.strip() for p in linha.split(";")]
        if not linha.strip():
            continue
        if len(partes) > 2 or not partes[0]:
            erros.append(f"linha {i}: use Nome;Observação")
            continue
        chave = f"AVULSO|{norm(partes[0])}"
        novos[chave] = {
            "nome": partes[0],
            "observacao": partes[1] if len(partes) == 2 else "",
            "genero": "Não informado",
            "estimativa": None,
        }
    return novos, erros


def montar_generos(texto: str) -> tuple[dict[str, str], list[str]]:
    """Lê Nome completo;Feminino ou Nome completo;Masculino sem inferir pelo nome."""
    generos, erros = {}, []
    for i, linha in enumerate(texto.splitlines(), 1):
        if not linha.strip():
            continue
        partes = [p.strip() for p in linha.split(";")]
        if len(partes) != 2 or not partes[0]:
            erros.append(
                f"linha {i}: use Nome completo;Feminino ou Nome completo;Masculino"
            )
            continue
        genero = normalizar_genero(partes[1])
        if genero == "Não informado":
            erros.append(f"linha {i}: informe Feminino ou Masculino")
            continue
        generos[norm(partes[0])] = genero
    return generos, erros


def chave_chapa(grupo: str, partido: str) -> str:
    sufixo = grupo if grupo == partido else f"{grupo}_{partido}"
    return "chapa_" + re.sub(r"[^A-Z0-9]+", "_", norm(sufixo))


def formatar_numero(valor: float, casas: int = 0) -> str:
    return f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def editar_lista(
    atuais: list[str],
    retirar: str | None,
    adicionar: str | None,
    capacidade: int,
    ocupados: set[str],
) -> list[str]:
    if retirar is None and adicionar is None:
        raise ValueError("Escolha um nome para retirar ou incluir.")
    if retirar is not None and retirar not in atuais:
        raise ValueError("O nome a retirar não está nesta lista.")
    if adicionar in ocupados:
        raise ValueError("Este nome já está em outra lista. Retire-o de lá primeiro.")
    resultado = [p for p in atuais if p != retirar]
    if adicionar is not None and adicionar not in resultado:
        resultado.append(adicionar)
    if len(resultado) > capacidade:
        raise ValueError("Lista cheia: escolha também quem será substituído.")
    return resultado
