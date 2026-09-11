import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(page_title="Boletim Escolar Online", layout="wide")
st.title("📊 Sistema de Cálculo de Médias e Pontos")
st.markdown("Faça o upload do boletim em PDF para calcular as médias e pontos por etapa.")

# ============================================================
# MAPEAMENTO DE DISCIPLINAS
# ============================================================
MAPA_DISCIPLINAS = {
    "ARTE": "Arte",
    "BIOLOGIA": "Biologia",
    "BIOLOGIA NA PRATICA": "Biologia na Prática",
    "C.DA NATUREZA P ENEM": "C. da Natureza P/ ENEM",
    "CIENCIAS": "Ciências",
    "DESENV. SUSTENTAVEL": "Desenv. Sustentável",
    "ED. PARA PROFISSOES": "Ed. para Profissões",
    "ED.FISICA NA PRATICA": "Ed. Física na Prática",
    "ED.SOCIO.ENS.RELIG.": "Ed. Socio. Ens. Relig.",
    "EDUCACAO FINANCEIRA": "Educação Financeira",
    "EDUCACAO FISICA": "Educação Física",
    "FILOSOFIA": "Filosofia",
    "FISICA": "Física",
    "GEOGRAFIA": "Geografia",
    "HISTORIA": "História",
    "L.INGLESA NA PRATICA": "L. Inglesa na Prática",
    "LIN.PORTUGUESA": "Lin. Portuguesa",
    "LIN.PORTUGUESA 2": "Lin. Portuguesa 2",
    "LINGUA INGLESA": "Língua Inglesa",
    "MAT.E ESTATISTICA": "Mat. e Estatística",
    "MATEMATICA": "Matemática",
    "OFICINA DE TEXTO": "Oficina de Texto",
    "PROJETO DE VIDA": "Projeto de Vida",
    "QUIMICA": "Química",
    "QUIMICA NA PRATICA": "Química na Prática",
    "SOCIOLOGIA": "Sociologia"
}

# Da mais longa para a mais curta (necessário para o caso de fallback abaixo)
DISCIPLINAS_VALIDAS = sorted(MAPA_DISCIPLINAS.keys(), key=len, reverse=True)

# ============================================================
# PARSER DE LINHA
# ------------------------------------------------------------
# Cada linha de disciplina no boletim tem o formato:
#   NOME  Notas1 Faltas1 Notas2 Faltas2 Notas3 Faltas3 TotalNotas TotalFaltas
# Onde Notas podem ser "-" (etapa ainda não lançada).
#
# PROBLEMA RESOLVIDO NESTA VERSÃO:
# Algumas disciplinas têm nomes parecidos, onde uma é prefixo da outra
# (ex: "LIN.PORTUGUESA" e "LIN.PORTUGUESA 2", "BIOLOGIA" e
# "BIOLOGIA NA PRATICA", "QUIMICA" e "QUIMICA NA PRATICA"). Isso causa
# ambiguidade: seria "LIN.PORTUGUESA 2" (a disciplina) ou "LIN.PORTUGUESA"
# com uma nota que começa em "2" (ex: 27,40)? Não dá pra saber só pelo
# texto. A solução é usar a coluna "Total" do próprio boletim (que é a
# soma das notas das 3 etapas) para VALIDAR qual interpretação está
# correta: só aceitamos a leitura em que Nota1+Nota2+Nota3 == Total.
# ============================================================
PADRAO_LINHA = re.compile(
    r'^(?P<nome>.+?)\s+(?P<n1>[\d,]+|-)\s+(?P<f1>\d+)\s+(?P<n2>[\d,]+|-)\s+(?P<f2>\d+)\s+'
    r'(?P<n3>[\d,]+|-)\s+(?P<f3>\d+)\s+(?P<tn>[\d,]+|-)\s+(?P<tf>\d+)$'
)
PADRAO_RESTO = re.compile(
    r'^([\d,]+|-)\s+(\d+)\s+([\d,]+|-)\s+(\d+)\s+([\d,]+|-)\s+(\d+)\s+([\d,]+|-)\s+(\d+)$'
)


def _num(s):
    return 0.0 if s == '-' else float(s.replace(',', '.'))


def extrair_linha(linha):
    """Retorna (nome_disciplina, n1, n2, n3) ou None se a linha não bater
    com o formato esperado / não passar na validação de consistência."""
    linha = linha.strip()
    m = PADRAO_LINHA.match(linha)
    if not m:
        return None

    nome_bruto = m.group('nome')
    n1, f1 = _num(m.group('n1')), int(m.group('f1'))
    n2, f2 = _num(m.group('n2')), int(m.group('f2'))
    n3, f3 = _num(m.group('n3')), int(m.group('f3'))
    tn, tf = _num(m.group('tn')), int(m.group('tf'))

    if abs((n1 + n2 + n3) - tn) <= 0.02 and (f1 + f2 + f3) == tf:
        # leitura padrão bateu com o total -> confirma o nome contra o mapa
        disc_final = nome_bruto if nome_bruto in MAPA_DISCIPLINAS else nome_bruto
        return disc_final, n1, n2, n3

    # Leitura padrão não validou (provável ambiguidade tipo "LIN.PORTUGUESA 2").
    # Tenta cada disciplina conhecida como prefixo literal e valida de novo.
    for disc in DISCIPLINAS_VALIDAS:
        if linha.startswith(disc):
            resto = linha[len(disc):].strip()
            m2 = PADRAO_RESTO.match(resto)
            if not m2:
                continue
            n1b, f1b = _num(m2.group(1)), int(m2.group(2))
            n2b, f2b = _num(m2.group(3)), int(m2.group(4))
            n3b, f3b = _num(m2.group(5)), int(m2.group(6))
            tnb, tfb = _num(m2.group(7)), int(m2.group(8))
            if abs((n1b + n2b + n3b) - tnb) <= 0.02 and (f1b + f2b + f3b) == tfb:
                return disc, n1b, n2b, n3b

    return None  # não foi possível validar nenhuma leitura


# ============================================================
# FUNÇÃO: EXTRAIR DADOS DO PDF
# ============================================================
@st.cache_data
def extrair_dados_pdf(pdf_bytes):
    dados = []
    linhas_nao_lidas = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for num_pagina, pagina in enumerate(pdf.pages, start=1):
            try:
                texto = pagina.extract_text()
            except Exception:
                continue

            if not texto or len(texto.strip()) < 10:
                continue

            padrao_cabecalho = r"MATRÍCULA:\s*(\d+).*?ALUNO:\s*(.*?)\s*PERÍODO LETIVO:.*?TURMA:\s*(\d+)"
            match_cabecalho = re.search(padrao_cabecalho, texto, re.DOTALL | re.IGNORECASE)

            if match_cabecalho:
                matricula = match_cabecalho.group(1)
                nome = match_cabecalho.group(2).strip()
                turma = match_cabecalho.group(3).strip()

                for linha in texto.split('\n'):
                    # só tenta processar linhas que começam com uma disciplina conhecida
                    if not any(linha.strip().startswith(d) for d in DISCIPLINAS_VALIDAS):
                        continue

                    resultado = extrair_linha(linha)
                    if resultado is None:
                        linhas_nao_lidas.append((num_pagina, nome, linha))
                        continue

                    disc, n1, n2, n3 = resultado
                    nome_completo = MAPA_DISCIPLINAS.get(disc, disc)

                    dados.append({
                        "Turma": turma,
                        "Matrícula": matricula,
                        "Aluno": nome,
                        "Disciplina": nome_completo,
                        "1ª Etapa": n1,
                        "2ª Etapa": n2,
                        "3ª Etapa": n3
                    })

    return pd.DataFrame(dados), linhas_nao_lidas

# ============================================================
# FUNÇÃO: PROCESSAR UMA ETAPA
# ============================================================
def processar_etapa(df, etapa):
    max_pontos = {"1ª Etapa": 30, "2ª Etapa": 35, "3ª Etapa": 35}[etapa]

    agrupado = df.groupby(['Turma', 'Aluno']).agg(
        Soma_Notas=(etapa, 'sum'),
        Num_Materias=(etapa, 'count')
    ).reset_index()

    # Calcula média e porcentagem a partir dos valores EXATOS (sem
    # arredondar a média antes de dividir pelo máximo), e só arredonda
    # para exibição no final. Arredondar a média antes causava pequenas
    # diferenças na porcentagem (ex: 86,47% em vez de 86,45%).
    media_exata = agrupado['Soma_Notas'] / agrupado['Num_Materias']
    pct_exata = (media_exata / max_pontos) * 100
    agrupado['Média das Notas'] = media_exata.round(2)
    agrupado['Porcentagem'] = pct_exata.round(2)

    def calcular_pontos(porcentagem):
        if porcentagem < 80:
            return 0
        elif 80 <= porcentagem < 90:
            return 2
        else:
            return 3

    # Usa a porcentagem EXATA (não a arredondada) para decidir a faixa de
    # pontos, evitando que um arredondamento na casa decimal empurre o
    # aluno pra faixa de pontos errada perto de um limite (80% ou 90%).
    agrupado['Total de Pontos'] = pct_exata.apply(calcular_pontos)

    agrupado = agrupado.rename(columns={
        'Soma_Notas': 'Soma das Notas',
        'Num_Materias': 'Nº de Matérias'
    })

    return agrupado[['Turma', 'Aluno', 'Soma das Notas', 'Média das Notas', 'Nº de Matérias', 'Porcentagem', 'Total de Pontos']]

# ============================================================
# INTERFACE PRINCIPAL
# ============================================================
uploaded_file = st.sidebar.file_uploader("📂 Faça o upload do Boletim (PDF)", type="pdf")

if uploaded_file is not None:
    st.success("PDF carregado com sucesso!")

    with st.spinner("Extraindo dados do PDF..."):
        df_notas, linhas_nao_lidas = extrair_dados_pdf(uploaded_file)

    if not df_notas.empty:
        st.success(f"✅ Extração concluída! {len(df_notas)} registros encontrados.")

        if linhas_nao_lidas:
            with st.expander(f"⚠️ {len(linhas_nao_lidas)} linha(s) não puderam ser lidas com confiança (clique para ver)"):
                for pag, aluno, linha in linhas_nao_lidas:
                    st.text(f"Página {pag} | {aluno} | {linha}")

        st.subheader("✅ Prévia dos Dados Extraídos (por disciplina)")
        st.dataframe(df_notas.head(20))

        etapas = ["1ª Etapa", "2ª Etapa", "3ª Etapa"]

        st.subheader("📥 Exportar Dados para Excel")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for etapa in etapas:
                df_etapa = processar_etapa(df_notas, etapa)
                nome_aba = etapa.replace("ª", "a")
                df_etapa.to_excel(writer, sheet_name=nome_aba, index=False)

        st.download_button(
            label="📥 Baixar Planilha Excel (todas as turmas - 1ª, 2ª e 3ª etapas)",
            data=output.getvalue(),
            file_name="resultados_todas_turmas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.warning("Nenhum dado foi extraído. Verifique se o PDF está no formato correto.")
else:
    st.info("👈 Por favor, faça o upload do arquivo PDF do boletim na barra lateral esquerda.")
