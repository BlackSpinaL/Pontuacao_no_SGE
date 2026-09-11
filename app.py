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
            
            # Regex para capturar Matrícula, Aluno e Turma
            padrao_cabecalho = r"MATRÍCULA:\s*(\d+).*?ALUNO:\s*(.*?)\s*PERÍODO LETIVO:.*?TURMA:\s*(\d+)"
            match_cabecalho = re.search(padrao_cabecalho, texto, re.DOTALL | re.IGNORECASE)
            
            if match_cabecalho:
                matricula = match_cabecalho.group(1)
                nome = match_cabecalho.group(2).strip()
                turma = match_cabecalho.group(3).strip()
                
                linhas = texto.split('\n')
                for linha in linhas:
                    # Verifica se a linha é de uma disciplina
                    if any(disciplina in linha for disciplina in ["LIN.PORTUGUESA", "GEOGRAFIA", "HISTORIA", "EDUCACAO FISICA", "MATEMATICA", "CIENCIAS", "ED.SOCIO.ENS.RELIG.", "ARTE", "LINGUA INGLESA"]):
                        partes = linha.split()
                        disciplina_nome = partes[0]
                        if disciplina_nome == "LIN.PORTUGUESA" and len(partes) > 1 and partes[1] == "2":
                            disciplina_nome = "LIN.PORTUGUESA 2"
                        
                        # Extrai os números da linha (notas e faltas)
                        numeros = re.findall(r'\d+[\.,]?\d*', linha)
                        
                        # O formato do PDF geralmente é: Disciplina, N1, F1, N2, F2, N3, F3, Total, Faltas
                        # Precisamos das notas das etapas (N1, N2, N3)
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

# Função para calcular média e pontos
def calcular_media_pontos(nota, etapa):
    if etapa == "1ª Etapa":
        max_pontos = 30
    elif etapa == "2ª Etapa":
        max_pontos = 35
    else: # 3ª Etapa
        max_pontos = 35
    
    # Calcula a média percentual
    media = (nota / max_pontos) * 100
    
    # Define os pontos conforme a regra
    if media < 80:
        pontos = 0
    elif 80 <= media < 90:
        pontos = 2
    else:
        pontos = 3
        
    return round(media, 2), pontos

# --- Interface Principal ---
uploaded_file = st.sidebar.file_uploader("📂 Faça o upload do Boletim (PDF)", type="pdf")

if uploaded_file is not None:
    st.success("PDF carregado com sucesso!")
    
    with st.spinner("Extraindo dados do PDF..."):
        df_notas = extrair_dados_pdf(uploaded_file)
    
    if not df_notas.empty:
        st.subheader("✅ Prévia dos Dados Extraídos")
        st.dataframe(df_notas.head())
        
        # Filtros na barra lateral
        st.sidebar.header("⚙️ Filtros")
        turmas = sorted(df_notas['Turma'].unique())
        turma_selecionada = st.sidebar.selectbox("Selecione a Turma", turmas)
        
        etapas = ["1ª Etapa", "2ª Etapa", "3ª Etapa"]
        etapa_selecionada = st.sidebar.selectbox("Selecione a Etapa", etapas)
        
        # Filtrar dados
        df_filtrado = df_notas[df_notas['Turma'] == turma_selecionada].copy()
        
        # Aplicar cálculo
        df_filtrado[['Média', 'Pontos']] = df_filtrado.apply(
            lambda row: calcular_media_pontos(row[etapa_selecionada], etapa_selecionada), 
            axis=1, result_type='expand'
        )
        
        # Organizar tabela final
        df_final = df_filtrado[['Turma', 'Aluno', 'Disciplina', etapa_selecionada, 'Média', 'Pontos']].copy()
        df_final = df_final.rename(columns={etapa_selecionada: f'Nota {etapa_selecionada}'})
        
        st.subheader(f"📋 Resultados: Turma {turma_selecionada} - {etapa_selecionada}")
        
        # Colorir as médias (Vermelho para < 80, Azul para 80-90, Verde para >= 90)
        def colorir_media(val):
            if val < 80:
                return 'color: red; font-weight: bold'
            elif 80 <= val < 90:
                return 'color: blue; font-weight: bold'
            else:
                return 'color: green; font-weight: bold'
        
        st.dataframe(df_final.style.map(colorir_media, subset=['Média']))
        
        # Exportar para Excel
        st.subheader("📥 Exportar Dados")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Notas')
        
        st.download_button(
            label="Baixar Tabela em Excel",
            data=output.getvalue(),
            file_name=f"notas_{turma_selecionada}_{etapa_selecionada}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    else:
        st.warning("Nenhum dado foi extraído. Verifique se o PDF está no formato correto ou se é um arquivo escaneado (imagem).")
else:
    st.info("👈 Por favor, faça o upload do arquivo PDF do boletim na barra lateral esquerda.")