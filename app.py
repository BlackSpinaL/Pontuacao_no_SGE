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

DISCIPLINAS_VALIDAS = list(MAPA_DISCIPLINAS.keys())

# ============================================================
# FUNÇÃO: EXTRAIR DADOS DO PDF
# ============================================================
@st.cache_data
def extrair_dados_pdf(pdf_bytes):
    dados = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for pagina in pdf.pages:
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
                
                linhas = texto.split('\n')
                for linha in linhas:
                    disciplina_encontrada = None
                    for disc in DISCIPLINAS_VALIDAS:
                        if linha.strip().startswith(disc):
                            disciplina_encontrada = disc
                            break
                    
                    if disciplina_encontrada:
                        linha_sem_nome = linha[len(disciplina_encontrada):].strip()
                        numeros = re.findall(r'\d+[\.,]?\d*', linha_sem_nome)
                        
                        nums_float = []
                        for n in numeros:
                            try:
                                nums_float.append(float(n.replace(',', '.')))
                            except ValueError:
                                pass
                        
                        n1 = nums_float[0] if len(nums_float) > 0 else 0
                        n2 = nums_float[2] if len(nums_float) > 2 else 0
                        n3 = nums_float[4] if len(nums_float) > 4 else 0
                        
                        nome_completo = MAPA_DISCIPLINAS.get(disciplina_encontrada, disciplina_encontrada)
                        
                        dados.append({
                            "Turma": turma,
                            "Matrícula": matricula,
                            "Aluno": nome,
                            "Disciplina": nome_completo,
                            "1ª Etapa": n1,
                            "2ª Etapa": n2,
                            "3ª Etapa": n3
                        })
    return pd.DataFrame(dados)

# ============================================================
# FUNÇÃO: PROCESSAR UMA ETAPA
# ============================================================
def processar_etapa(df, etapa):
    max_pontos = {"1ª Etapa": 30, "2ª Etapa": 35, "3ª Etapa": 35}[etapa]
    
    agrupado = df.groupby(['Turma', 'Aluno']).agg(
        Soma_Notas=(etapa, 'sum'),
        Num_Materias=(etapa, 'count')
    ).reset_index()
    
    # Média por matéria
    agrupado['Média das Notas'] = (agrupado['Soma_Notas'] / agrupado['Num_Materias']).round(2)
    
    # Porcentagem correta: média em relação ao máximo da etapa
    agrupado['Porcentagem'] = ((agrupado['Média das Notas'] / max_pontos) * 100).round(2)
    
    def calcular_pontos(porcentagem):
        if porcentagem < 80:
            return 0
        elif 80 <= porcentagem < 90:
            return 2
        else:
            return 3
    
    agrupado['Total de Pontos'] = agrupado['Porcentagem'].apply(calcular_pontos)
    
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
        df_notas = extrair_dados_pdf(uploaded_file)
    
    if not df_notas.empty:
        st.success(f"✅ Extração concluída! {len(df_notas)} registros encontrados.")
        
        st.subheader("✅ Prévia dos Dados Extraídos (por disciplina)")
        st.dataframe(df_notas.head(20))
        
        etapas = ["1ª Etapa", "2ª Etapa", "3ª Etapa"]
        
        # Exportar Excel com todas as turmas e 3 abas
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
