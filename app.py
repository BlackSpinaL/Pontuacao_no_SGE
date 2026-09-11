import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# Configuração da página
st.set_page_config(page_title="Boletim Escolar Online", layout="wide")
st.title("📊 Sistema de Cálculo de Médias e Pontos")
st.markdown("Faça o upload do boletim em PDF para calcular as médias e pontos por etapa.")

# Função para extrair dados do PDF
def extrair_dados_pdf(pdf_file):
    dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            
            padrao_cabecalho = r"MATRÍCULA:\s*(\d+).*?ALUNO:\s*(.*?)\s*PERÍODO LETIVO:.*?TURMA:\s*(\d+)"
            match_cabecalho = re.search(padrao_cabecalho, texto, re.DOTALL | re.IGNORECASE)
            
            if match_cabecalho:
                matricula = match_cabecalho.group(1)
                nome = match_cabecalho.group(2).strip()
                turma = match_cabecalho.group(3).strip()
                
                linhas = texto.split('\n')
                for linha in linhas:
                    if any(disciplina in linha for disciplina in ["LIN.PORTUGUESA", "GEOGRAFIA", "HISTORIA", "EDUCACAO FISICA", "MATEMATICA", "CIENCIAS", "ED.SOCIO.ENS.RELIG.", "ARTE", "LINGUA INGLESA"]):
                        partes = linha.split()
                        disciplina_nome = partes[0]
                        if disciplina_nome == "LIN.PORTUGUESA" and len(partes) > 1 and partes[1] == "2":
                            disciplina_nome = "LIN.PORTUGUESA 2"
                        
                        numeros = re.findall(r'\d+[\.,]?\d*', linha)
                        
                        if len(numeros) >= 5:
                            try:
                                n1 = float(numeros[0].replace(',', '.'))
                                n2 = float(numeros[2].replace(',', '.'))
                                n3 = float(numeros[4].replace(',', '.'))
                                
                                dados.append({
                                    "Turma": turma,
                                    "Matrícula": matricula,
                                    "Aluno": nome,
                                    "Disciplina": disciplina_nome,
                                    "1ª Etapa": n1,
                                    "2ª Etapa": n2,
                                    "3ª Etapa": n3
                                })
                            except ValueError:
                                pass
    return pd.DataFrame(dados)

# Função para processar uma etapa específica
def processar_etapa(df, etapa):
    max_pontos = {"1ª Etapa": 30, "2ª Etapa": 35, "3ª Etapa": 35}[etapa]
    
    # Agrupa por Turma e Aluno
    agrupado = df.groupby(['Turma', 'Aluno']).agg(
        Soma_Notas=(etapa, 'sum'),
        Num_Materias=(etapa, 'count')
    ).reset_index()
    
    # Calcula a média das notas (soma / número de matérias)
    agrupado['Média das Notas'] = (agrupado['Soma_Notas'] / agrupado['Num_Materias']).round(2)
    
    # Calcula a porcentagem em relação ao máximo da etapa
    agrupado['Porcentagem'] = ((agrupado['Média das Notas'] / max_pontos) * 100).round(2)
    
    # Calcula os pontos
    def calcular_pontos(porcentagem):
        if porcentagem < 80:
            return 0
        elif 80 <= porcentagem < 90:
            return 2
        else:
            return 3
    
    agrupado['Total de Pontos'] = agrupado['Porcentagem'].apply(calcular_pontos)
    
    # Renomeia as colunas para ficar bonito
    agrupado = agrupado.rename(columns={
        'Soma_Notas': 'Soma das Notas',
        'Num_Materias': 'Nº de Matérias'
    })
    
    # Reorganiza a ordem das colunas
    agrupado = agrupado[['Turma', 'Aluno', 'Soma das Notas', 'Média das Notas', 'Nº de Matérias', 'Porcentagem', 'Total de Pontos']]
    
    return agrupado

# --- Interface Principal ---
uploaded_file = st.sidebar.file_uploader("📂 Faça o upload do Boletim (PDF)", type="pdf")

if uploaded_file is not None:
    st.success("PDF carregado com sucesso!")
    
    with st.spinner("Extraindo dados do PDF..."):
        df_notas = extrair_dados_pdf(uploaded_file)
    
    if not df_notas.empty:
        st.subheader("✅ Prévia dos Dados Extraídos (por disciplina)")
        st.dataframe(df_notas.head())
        
        # Filtros
        st.sidebar.header("⚙️ Filtros")
        turmas = sorted(df_notas['Turma'].unique())
        turma_selecionada = st.sidebar.selectbox("Selecione a Turma", turmas)
        
        etapas = ["1ª Etapa", "2ª Etapa", "3ª Etapa"]
        etapa_selecionada = st.sidebar.selectbox("Selecione a Etapa", etapas)
        
        # Filtra os dados pela turma selecionada
        df_filtrado = df_notas[df_notas['Turma'] == turma_selecionada].copy()
        
        # Processa a etapa selecionada
        df_resultado = processar_etapa(df_filtrado, etapa_selecionada)
        
        st.subheader(f"📋 Resultados: Turma {turma_selecionada} - {etapa_selecionada}")
        
        # Colorir a porcentagem
        def colorir_porcentagem(val):
            if val < 80:
                return 'color: red; font-weight: bold'
            elif 80 <= val < 90:
                return 'color: blue; font-weight: bold'
            else:
                return 'color: green; font-weight: bold'
        
        st.dataframe(df_resultado.style.map(colorir_porcentagem, subset=['Porcentagem']))
        
        # --- Exportar para Excel com 3 abas ---
        st.subheader("📥 Exportar Dados para Excel")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for etapa in etapas:
                df_etapa = processar_etapa(df_filtrado, etapa)
                df_etapa.to_excel(writer, sheet_name=etapa, index=False)
        
        st.download_button(
            label="Baixar Planilha Excel (3 abas - 1ª, 2ª e 3ª etapas)",
            data=output.getvalue(),
            file_name=f"resultados_turma_{turma_selecionada}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    else:
        st.warning("Nenhum dado foi extraído. Verifique se o PDF está no formato correto.")
else:
    st.info("👈 Por favor, faça o upload do arquivo PDF do boletim na barra lateral esquerda.")
