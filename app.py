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
# MAPEAMENTO DE DISCIPLINAS (nomes cortados pelo PDF → completos)
# ============================================================
MAPA_DISCIPLINAS = {
    "LIN.PORTUGUESA 2": "LÍNGUA PORTUGUESA 2",
    "LIN.PORTUGUESA": "LÍNGUA PORTUGUESA",
    "GEOGRAFIA": "GEOGRAFIA",
    "HISTORIA": "HISTÓRIA",
    "EDUCACAO FISICA": "EDUCAÇÃO FÍSICA",
    "EDUCACAO": "EDUCAÇÃO FÍSICA",
    "MATEMATICA": "MATEMÁTICA",
    "CIENCIAS": "CIÊNCIAS",
    "ED.SOCIO.ENS.RELIG.": "ENS. RELIGIOSO",
    "ARTE": "ARTE",
    "LINGUA INGLESA": "LÍNGUA INGLESA",
    "LINGUA": "LÍNGUA INGLESA",
}

# Lista de disciplinas como aparecem no PDF (para busca na linha)
DISCIPLINAS_VALIDAS = [
    "LIN.PORTUGUESA 2", "LIN.PORTUGUESA", "GEOGRAFIA", "HISTORIA",
    "EDUCACAO FISICA", "EDUCACAO", "MATEMATICA", "CIENCIAS",
    "ED.SOCIO.ENS.RELIG.", "ARTE", "LINGUA INGLESA", "LINGUA"
]

# ============================================================
# FUNÇÃO: EXTRAIR DADOS DO PDF
# ============================================================
def extrair_dados_pdf(pdf_file):
    dados = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            
            # Captura cabeçalho: Matrícula, Aluno e Turma
            padrao_cabecalho = r"MATRÍCULA:\s*(\d+).*?ALUNO:\s*(.*?)\s*PERÍODO LETIVO:.*?TURMA:\s*(\d+)"
            match_cabecalho = re.search(padrao_cabecalho, texto, re.DOTALL | re.IGNORECASE)
            
            if match_cabecalho:
                matricula = match_cabecalho.group(1)
                nome = match_cabecalho.group(2).strip()
                turma = match_cabecalho.group(3).strip()
                
                linhas = texto.split('\n')
                for linha in linhas:
                    # Verifica qual disciplina a linha contém
                    disciplina_encontrada = None
                    for disc in DISCIPLINAS_VALIDAS:
                        if linha.strip().startswith(disc):
                            disciplina_encontrada = disc
                            break
                    
                    if disciplina_encontrada:
                        # Remove o nome da disciplina para pegar só os números
                        linha_sem_nome = linha[len(disciplina_encontrada):].strip()
                        
                        # Extrai todos os números da linha
                        numeros = re.findall(r'\d+[\.,]?\d*', linha_sem_nome)
                        
                        # Converte para float
                        nums_float = []
                        for n in numeros:
                            try:
                                nums_float.append(float(n.replace(',', '.')))
                            except ValueError:
                                pass
                        
                        # Estrutura: Nota1, Falta1, Nota2, Falta2, Nota3, Falta3, Total, FaltaTotal
                        # As notas estão nas posições pares: 0, 2, 4
                        n1 = nums_float[0] if len(nums_float) > 0 else 0
                        n2 = nums_float[2] if len(nums_float) > 2 else 0
                        n3 = nums_float[4] if len(nums_float) > 4 else 0
                        
                        # Usa o nome completo da disciplina
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
# FUNÇÃO: PROCESSAR UMA ETAPA (calcular média e pontos)
# ============================================================
def processar_etapa(df, etapa):
    """
    Recebe o DataFrame bruto e a etapa escolhida.
    Retorna um DataFrame agrupado por Turma + Aluno com soma, média e pontos.
    """
    # Total de pontos distribuídos em cada etapa
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
    
    # Função para calcular os pontos
    def calcular_pontos(porcentagem):
        if porcentagem < 80:
            return 0
        elif 80 <= porcentagem < 90:
            return 2
        else:
            return 3
    
    agrupado['Total de Pontos'] = agrupado['Porcentagem'].apply(calcular_pontos)
    
    # Renomeia as colunas
    agrupado = agrupado.rename(columns={
        'Soma_Notas': 'Soma das Notas',
        'Num_Materias': 'Nº de Matérias'
    })
    
    # Reorganiza a ordem das colunas
    agrupado = agrupado[[
        'Turma', 'Aluno', 'Soma das Notas',
        'Média das Notas', 'Nº de Matérias', 'Porcentagem', 'Total de Pontos'
    ]]
    
    return agrupado

# ============================================================
# FUNÇÃO: COLORIR A PORCENTAGEM NA TABELA
# ============================================================
def colorir_porcentagem(val):
    if val < 80:
        return 'color: red; font-weight: bold'
    elif 80 <= val < 90:
        return 'color: blue; font-weight: bold'
    else:
        return 'color: green; font-weight: bold'

# ============================================================
# INTERFACE PRINCIPAL
# ============================================================
uploaded_file = st.sidebar.file_uploader("📂 Faça o upload do Boletim (PDF)", type="pdf")

if uploaded_file is not None:
    st.success("PDF carregado com sucesso!")
    
    # Extrai os dados do PDF
    with st.spinner("Extraindo dados do PDF..."):
        df_notas = extrair_dados_pdf(uploaded_file)
    
    if not df_notas.empty:
        # Mostra a prévia dos dados brutos
        st.subheader("✅ Prévia dos Dados Extraídos (por disciplina)")
        st.dataframe(df_notas.head(20))
        
        # Filtros na barra lateral
        st.sidebar.header("⚙️ Filtros")
        turmas = sorted(df_notas['Turma'].unique())
        turma_selecionada = st.sidebar.selectbox("Selecione a Turma", turmas)
        
        etapas = ["1ª Etapa", "2ª Etapa", "3ª Etapa"]
        etapa_selecionada = st.sidebar.selectbox("Selecione a Etapa", etapas)
        
        # Filtra os dados pela turma selecionada
        df_filtrado = df_notas[df_notas['Turma'] == turma_selecionada].copy()
        
        # Processa a etapa selecionada
        df_resultado = processar_etapa(df_filtrado, etapa_selecionada)
        
        # Exibe o resultado
        st.subheader(f"📋 Resultados: Turma {turma_selecionada} - {etapa_selecionada}")
        st.dataframe(df_resultado.style.map(colorir_porcentagem, subset=['Porcentagem']))
        
        # ============================================================
        # EXPORTAR PARA EXCEL COM 3 ABAS
        # ============================================================
        st.subheader("📥 Exportar Dados para Excel")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for etapa in etapas:
                df_etapa = processar_etapa(df_filtrado, etapa)
                # Nome da aba (Excel não aceita "ª" em alguns casos, mas aceita)
                nome_aba = etapa.replace("ª", "a")
                df_etapa.to_excel(writer, sheet_name=nome_aba, index=False)
        
        st.download_button(
            label="📥 Baixar Planilha Excel (3 abas - 1ª, 2ª e 3ª etapas)",
            data=output.getvalue(),
            file_name=f"resultados_turma_{turma_selecionada}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # ============================================================
        # EXPORTAR PARA CSV (opcional)
        # ============================================================
        st.subheader("📥 Exportar para CSV (etapa selecionada)")
        csv = df_resultado.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label=f"📥 Baixar CSV - {etapa_selecionada}",
            data=csv,
            file_name=f"resultados_{turma_selecionada}_{etapa_selecionada}.csv",
            mime="text/csv"
        )
        
    else:
        st.warning("Nenhum dado foi extraído. Verifique se o PDF está no formato correto.")
else:
    st.info("👈 Por favor, faça o upload do arquivo PDF do boletim na barra lateral esquerda.")
