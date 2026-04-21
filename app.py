import streamlit as st
import pandas as pd
import numpy as np
import pdfplumber
import re
from datetime import datetime
from fpdf import FPDF
import io

# ==========================================
# 1. IDENTIDADE VISUAL E UI (CSS)
# ==========================================
st.set_page_config(page_title="Focus ERP - Master 2026", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    /* Tema Premium */
    .stApp { background-color: #f1f3f5; }
    .header-box { 
        background-color: #444444; color: #ffffff; padding: 25px; border-radius: 10px; 
        font-size: 32px; font-weight: bold; text-align: center; margin-bottom: 25px; 
        border-bottom: 6px solid #1a73e8; 
    }
    .sub-header { 
        background-color: #666666; color: #ffffff; padding: 15px; border-radius: 6px; 
        font-size: 22px; font-weight: bold; margin-top: 20px; margin-bottom: 15px; 
    }
    .main-box { 
        background-color: #ffffff; border-radius: 12px; padding: 25px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 25px; 
    }
    
    /* Fontes Ampliadas */
    html, body, [class*="st-"] { font-size: 19px !important; }
    .stDataFrame div[data-testid="stTable"] { font-size: 21px !important; }

    /* Régua de Cores de Status */
    .status-box { padding: 30px; border-radius: 15px; text-align: center; font-weight: bold; font-size: 34px; color: white; }
    .bg-aprovado { background-color: #28a745; }
    .bg-ressalva { background-color: #007bff; }
    .bg-reprovado { background-color: #ff8c00; }
    .bg-critico { background-color: #dc3545; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. ESTADOS E MOTOR DE ENGENHARIA
# ==========================================
if 'logado' not in st.session_state: st.session_state.logado = False
if 'user_atual' not in st.session_state: st.session_state.user_atual = None
if 'carrinho' not in st.session_state: st.session_state.carrinho = []
if 'historico' not in st.session_state: st.session_state.historico = []

if 'mp_precos' not in st.session_state:
    st.session_state.mp_precos = {
        "Cobre (kg)": 88.00, "Alumínio (kg)": 18.50, "PVC Marfim (kg)": 9.50,
        "PVC HEPR (kg)": 18.60, "Capa PP (kg)": 11.99, "PVC Atox (kg)": 18.50,
        "Skin/Cores (kg)": 25.96, "Embalagem (un)": 16.70
    }

def calcular_custo_tecnico(row):
    mp = st.session_state.mp_precos
    # Cálculo de 8 Componentes
    soma_mp = (row.get('Cobre_kg', 0) * mp["Cobre (kg)"]) + \
              (row.get('Aluminio_kg', 0) * mp["Alumínio (kg)"]) + \
              (row.get('PVC_kg', 0) * mp["PVC Marfim (kg)"]) + \
              (row.get('HEPR_kg', 0) * mp["PVC HEPR (kg)"]) + \
              (row.get('Capa_PP_kg', 0) * mp["Capa PP (kg)"]) + \
              (row.get('PVC_atox_kg', 0) * mp["PVC Atox (kg)"]) + \
              (row.get('Skin_kg', 0) * mp["Skin/Cores (kg)"]) + \
              (row.get('Embalagem_un', 0) * mp["Embalagem (un)"])
    
    nome = str(row.get('Nome do produto', '')).upper()
    unidade = str(row.get('Unidade', '')).upper()
    is_roll = '100M' in nome or unidade == 'RL'
    return round(soma_mp if is_roll else soma_mp / 100.0, 4)

def styler_master(row):
    """Aplica Rosa (Império), Vermelho (Prejuízo) e Laranja (Custo Zero)"""
    nome = str(row.get('Nome do produto', row.get('Descrição', ''))).upper()
    styles = [''] * len(row)
    
    # 1. Destaque Rosa (Império)
    if 'IMPÉRIO' in nome or 'IMPERIUM' in nome:
        styles = ['background-color: #FFC0CB; color: black; font-weight: bold'] * len(row)
    
    # 2. Alerta Laranja (Custo Zero)
    if 'Custo_Un' in row and row['Custo_Un'] <= 0:
        styles = ['background-color: #ff9900; color: white'] * len(row)
    
    # 3. Trava Vermelha (Venda < Custo ou Preço Zero)
    if 'Preço_Un' in row and 'Custo_Un' in row:
        if row['Preço_Un'] < row['Custo_Un'] or row['Preço_Un'] <= 0:
            styles = ['background-color: #dc3545; color: white; font-weight: bold'] * len(row)
            
    return styles
# --- FUNÇÕES DE SUPORTE ---
def extrair_pdf(file):
    itens = []
    with pdfplumber.open(io.BytesIO(file.read())) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            matches = re.findall(r'(\d{4,5})\s+(.*?)\s+(\d+)\s+([\d,.]+)', text)
            for m in matches:
                itens.append({"Código": m[0], "Descrição": m[1], "Qtd": float(m[2]), "Preço_Un": float(m[3].replace('.','').replace(',','.'))})
    return itens

def carregar_dados():
    try:
        # Carrega o CSV
        df = pd.read_csv("base_dados_produtos_viabilidade.csv", sep=";")
        
        # LIMPEZA CRÍTICA: Remove espaços extras dos nomes das colunas (ex: " Família " vira "Família")
        df.columns = df.columns.str.strip()
        
        # GARANTIA DE COLUNAS: Se a coluna não existir, cria uma com valor "Geral"
        if 'Família' not in df.columns:
            df['Família'] = "Geral"
        if 'Grupo' not in df.columns:
            df['Grupo'] = "Geral"
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a base de dados: {e}")
        return pd.DataFrame()

# --- INTERFACE ---
df_base = carregar_dados()
tabs = st.tabs(["🛒 Orçamentos", "🏷️ Tabela Preços", "📑 Engenharia", "📜 Histórico", "⚙️ Admin"])

with tabs[0]:
    st.markdown('<div class="header-box">LANÇAMENTO DE PEDIDO</div>', unsafe_allow_html=True)
    
    # 1. UPLOAD PDF NO TOPO
    f_pdf = st.file_uploader("📂 Importar Orçamento em PDF", type=['pdf'])
    if f_pdf and st.button("Analisar PDF"):
        itens_pdf = extrair_pdf(f_pdf)
        for it in itens_pdf:
            match = df_base[df_base['Código'].astype(str) == str(it['Código'])]
            it['Custo_Un'] = calcular_custo_tecnico(match.iloc[0]) if not match.empty else 0.0
            it['Peso_Un'] = match.iloc[0].get('Peso_Total_kg', 0) if not match.empty else 0.0
            st.session_state.carrinho.append(it)
        st.success("PDF Importado!"); st.rerun()

    # 2. CABEÇALHO
    with st.container():
        st.markdown('<div class="main-box">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2,1.5,1])
        cli = c1.text_input("Cliente")
        cnpj = c2.text_input("CNPJ / CPF")
        orc_n = c3.text_input("Nº Orçamento")
        data_at = datetime.now().strftime("%d/%m/%Y")
        st.write(f"📅 **Data:** {data_at}")
        st.markdown('</div>', unsafe_allow_html=True)

    # 3. EDIÇÃO DINÂMICA
    if st.session_state.carrinho:
        st.markdown('<div class="sub-header">Grade de Itens (Rosa = Império | Vermelho = Erro)</div>', unsafe_allow_html=True)
        df_cart = pd.DataFrame(st.session_state.carrinho)
        df_edit = st.data_editor(df_cart.style.apply(styler_master, axis=1), num_rows="dynamic", use_container_width=True)
        st.session_state.carrinho = df_edit.to_dict('records')

        # 4. QUADRO DE DEDUÇÕES
        st.markdown('<div class="sub-header">Análise de Viabilidade Financeira</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="main-box">', unsafe_allow_html=True)
            f1, f2, f3, f4 = st.columns(4)
            c_ext = f1.number_input("Comissão Ext (%)", 0.0, 10.0, 3.0)
            c_int = f1.number_input("Comissão Int (%)", 0.0, 5.0, 0.65)
            t_op = f2.number_input("Taxa Operacional (%)", 0.0, 10.0, 3.5)
            f_cif = f2.number_input("Frete CIF (%)", 0.0, 15.0, 3.0)
            desc = f3.number_input("Desc. à Vista (%)", 0.0, 20.0, 0.0)
            acre = f3.number_input("Acréscimo Com. (%)", 0.0, 50.0, 0.0)
            imposto = f4.number_input("Impostos (%)", 0.0, 40.0, 12.0)
            st.markdown('</div>', unsafe_allow_html=True)

        # CÁLCULOS
        venda_bruta = sum([x['Qtd'] * x['Preço_Un'] for x in st.session_state.carrinho])
        venda_final = venda_bruta * (1 + (acre - desc)/100)
        custo_total = sum([x['Qtd'] * x['Custo_Un'] for x in st.session_state.carrinho])
        peso_total = sum([x['Qtd'] * (x.get('Peso_Un',0)/100) for x in st.session_state.carrinho])
        
        perc_deducoes = (c_ext + c_int + t_op + f_cif + imposto)
        lucro_liq = (venda_final * (1 - perc_deducoes/100)) - custo_total
        margem_real = (lucro_liq / venda_final * 100) if venda_final > 0 else 0

        st.write(f"### 📦 Venda Final (RB): R$ {venda_final:,.2f} | ⚖️ Peso Total: {peso_total:,.2f} kg")
        
        # 5. MARGEM OCULTA
        senha_admin = st.text_input("🔑 Senha Supervisor para ver Margem", type="password")
        if senha_admin == "maxfio123":
            status_classe = "bg-aprovado" if margem_real >= 11 else "bg-ressalva" if margem_real >= 9 else "bg-critico"
            st.markdown(f'<div class="status-box {status_classe}">Margem Real: {margem_real:.2f}% | Lucro: R$ {lucro_liq:,.2f}</div>', unsafe_allow_html=True)
            
            # BOTÃO PDF
            if st.button("🖨️ Gerar Relatório PDF"):
                pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 16)
                pdf.cell(190, 10, f"Analise Focus - {cli}", 0, 1, 'C')
                pdf.set_font("Arial", "", 12)
                pdf.cell(190, 10, f"Valor RB: R$ {venda_final:,.2f} | Margem: {margem_real:.2f}%", 0, 1)
                st.download_button("Baixar PDF", pdf.output(dest='S'), "analise.pdf")

        # TRAVA DE SALVAMENTO
        tem_erro = any([x['Preço_Un'] < x['Custo_Un'] or x['Preço_Un'] <= 0 for x in st.session_state.carrinho])
        if st.button("💾 Salvar Pedido no Histórico", disabled=tem_erro):
            st.session_state.historico.append({"Data": data_at, "Cliente": cli, "Total": venda_final, "User": st.session_state.user_atual, "Margem": f"{margem_real:.2f}%"})
            st.success("Gravado!")
            # --- ABA 2: TABELA DE PREÇOS ---
with tabs[1]:
    st.markdown('<div class="header-box">TABELA DE PREÇOS COMERCIAL</div>', unsafe_allow_html=True)
    f_fam = st.selectbox("Família", ["Todas"] + list(df_base['Família'].unique()) if not df_base.empty else ["Todas"])
    df_p = df_base if f_fam == "Todas" else df_base[df_base['Família'] == f_fam]
    st.dataframe(df_p.style.apply(styler_master, axis=1), use_container_width=True)

# --- ABA 3: ENGENHARIA ---
with tabs[2]:
    st.markdown('<div class="header-box">ENGENHARIA E MATÉRIA-PRIMA</div>', unsafe_allow_html=True)
    if not df_base.empty:
        df_e = df_base.copy()
        df_e['Custo_Un'] = df_e.apply(calcular_custo_tecnico, axis=1)
        st.dataframe(df_e.style.apply(styler_master, axis=1), use_container_width=True)

# --- ABA 4: HISTÓRICO ---
with tabs[3]:
    st.markdown('<div class="header-box">HISTÓRICO DE ANÁLISES</div>', unsafe_allow_html=True)
    if st.session_state.historico:
        st.table(pd.DataFrame(st.session_state.historico))

# --- ABA 5: ADMIN ---
with tabs[4]:
    st.title("⚙️ Administração de Custos")
    if st.session_state.user_atual == "admin":
        with st.form("admin_mp"):
            st.subheader("Ajuste de Preços MP (R$/kg)")
            novos_precos = {}
            cols = st.columns(3)
            for i, (k, v) in enumerate(st.session_state.mp_precos.items()):
                novos_precos[k] = cols[i % 3].number_input(k, value=v)
            if st.form_submit_button("💾 Atualizar Engenharia"):
                st.session_state.mp_precos.update(novos_precos)
                st.success("Toda a engenharia foi recalculada!")
    else: st.error("Acesso negado ao Administrador.")
    # --- ABA 2: TABELA DE PREÇOS ---
with tabs[1]:
    st.markdown('<div class="header-box">TABELA DE PREÇOS COMERCIAL</div>', unsafe_allow_html=True)
    
    if not df_base.empty:
        # Criamos os filtros em colunas para ficar elegante
        f1, f2 = st.columns(2)
        
        # Filtro de Família com proteção
        lista_familias = ["Todas"] + sorted(list(df_base['Família'].unique().astype(str)))
        f_fam = f1.selectbox("Filtrar por Família", lista_familias)
        
        # Filtro de Busca por Nome
        f_nome = f2.text_input("Buscar Produto por Nome")
        
        # Aplicando os filtros
        df_exibir = df_base.copy()
        if f_fam != "Todas":
            df_exibir = df_exibir[df_exibir['Família'] == f_fam]
        if f_nome:
            df_exibir = df_exibir[df_exibir['Nome do produto'].str.contains(f_nome, case=False, na=False)]
            
        # Exibição com o Styler Master (Destaque Rosa para Império)
        st.dataframe(df_exibir.style.apply(styler_master, axis=1), use_container_width=True)
    else:
        st.warning("Base de dados vazia ou não encontrada. Verifique o arquivo CSV.")