import numpy as np
import pandas as pd
from datetime import datetime

print("Preparando dados para Power BI...")

# =========================
# CARREGA DADOS BASE
# =========================
print("Carregando dados base...")
df_ads = pd.read_csv("../ads_data.csv", parse_dates=["date"])
df_sessions = pd.read_csv("../sessions_data.csv", parse_dates=["date"])
df_sales = pd.read_csv("../sales_data.csv", parse_dates=["date"])
df_customers = pd.read_csv("../customers_data.csv", parse_dates=["acquisition_date"])

print(f"Base carregada (ads={len(df_ads):,}, sessions={len(df_sessions):,}, sales={len(df_sales):,}, customers={len(df_customers):,})")

# =========================
# 1. TABELA FATO - PERFORMANCE DIÁRIA POR CAMPANHA
# =========================
print("Criando FATO_PERFORMANCE_DIARIA...")

# Agregação de ads por dia/canal/campanha
fato_ads = df_ads.groupby(['date', 'channel', 'campaign']).agg({
    'spend': 'sum',
    'impressions': 'sum',
    'clicks': 'sum',
    'conversions': 'sum'
}).reset_index()

# Agregação de vendas por dia/canal/campanha
fato_sales = df_sales.groupby(['date', 'channel', 'campaign']).agg({
    'order_id': 'count',
    'revenue': 'sum',
    'is_new_customer': 'sum'
}).reset_index()
fato_sales.columns = ['date', 'channel', 'campaign', 'Pedidos', 'Receita', 'Novos_Clientes']

# Merge completo (left join para manter todos os dias com gasto)
fato_performance = fato_ads.merge(
    fato_sales,
    on=['date', 'channel', 'campaign'],
    how='left'
)

# Preenche nulls (dias que tiveram gasto mas não venda)
fato_performance['Pedidos'] = fato_performance['Pedidos'].fillna(0)
fato_performance['Receita'] = fato_performance['Receita'].fillna(0)
fato_performance['Novos_Clientes'] = fato_performance['Novos_Clientes'].fillna(0)

# Trata infinitos e NaN
fato_performance = fato_performance.replace([np.inf, -np.inf], 0)
fato_performance = fato_performance.fillna(0)

# Renomeia colunas principais para português
fato_performance = fato_performance.rename(columns={
    'date': 'Data',
    'channel': 'Canal',
    'campaign': 'Campanha',
    'spend': 'Investimento',
    'impressions': 'Impressoes',
    'clicks': 'Cliques',
    'conversions': 'Conversoes'
})

print(f"OK FATO_PERFORMANCE_DIARIA: {len(fato_performance):,} linhas")

# =========================
# 2. TABELA FATO - VENDAS (granular)
# =========================
print("Criando FATO_VENDAS...")

fato_vendas = df_sales.copy()

# Adiciona informações do cliente
fato_vendas = fato_vendas.merge(
    df_customers[['customer_id', 'acquisition_date', 'status']],
    on='customer_id',
    how='left'
)

# Calcula dias desde aquisição até compra
fato_vendas['Dias_Desde_Aquisicao'] = (
    fato_vendas['date'] - fato_vendas['acquisition_date']
).dt.days

# Classifica tipo de venda
fato_vendas['Tipo_Venda'] = fato_vendas['is_new_customer'].apply(
    lambda x: 'Nova Venda' if x == 1 else 'Recompra'
)

# Renomeia colunas para português
fato_vendas = fato_vendas.rename(columns={
    'order_id': 'ID_Pedido',
    'date': 'Data',
    'customer_id': 'ID_Cliente',
    'is_new_customer': 'Cliente_Novo',
    'customer_segment': 'Segmento_Cliente',
    'customer_region': 'Regiao_Cliente',
    'product': 'Produto',
    'revenue': 'Receita',
    'acquisition_channel': 'Canal_Aquisicao',
    'acquisition_campaign': 'Campanha_Aquisicao',
    'channel': 'Canal',
    'campaign': 'Campanha',
    'acquisition_date': 'Data_Aquisicao',
    'status': 'Status_Cliente'
})

# Remove colunas redundantes (já estão em DIM_CALENDAR via relacionamento)
fato_vendas = fato_vendas.drop(columns=['Ano', 'Mes', 'Trimestre'], errors='ignore')

print(f"OK FATO_VENDAS: {len(fato_vendas):,} linhas")

# =========================
# 3. DIMENSÃO - CLIENTES
# =========================
print("Criando DIM_CLIENTES...")

dim_clientes = df_customers.copy()

# Cohort (Ano-Mês de aquisição)
dim_clientes['Cohort'] = dim_clientes['acquisition_date'].dt.to_period('M').astype(str)

# Renomeia colunas para português
dim_clientes = dim_clientes.rename(columns={
    'customer_id': 'ID_Cliente',
    'acquisition_date': 'Data_Aquisicao',
    'acquisition_channel': 'Canal_Aquisicao',
    'acquisition_campaign': 'Campanha_Aquisicao',
    'segment': 'Segmento',
    'region': 'Regiao',
    'total_orders': 'Total_Pedidos',
    'total_revenue': 'LTV',
    'status': 'Status'
})

# Remove colunas redundantes (já estão em DIM_CALENDAR via relacionamento)
dim_clientes = dim_clientes.drop(columns=['Ano_Aquisicao', 'Mes_Aquisicao', 'Trimestre_Aquisicao'], errors='ignore')

print(f"OK DIM_CLIENTES: {len(dim_clientes):,} linhas")

# =========================
# 4. TABELA CALENDAR (Dimensão Tempo)
# =========================
# NOTA: DIM_CALENDAR é criada dinamicamente no Power Query (CarregarDados.pq)
# Não é necessário gerar CSV - economiza espaço e garante sincronização

# =========================
# 4. TABELA DE METAS (granularidade diária)
# =========================
print("Criando DIM_METAS...")

# Gera metas diárias baseadas nas médias do fato_performance
date_range = pd.date_range(start='2022-01-01', end='2024-12-31', freq='D')
metas_data = []

for date in date_range:
    year = date.year
    month = date.month
    
    # Crescimento anual
    year_mult = 1 + 0.12 * (year - 2022)
    
    # Sazonalidade
    if month == 11:
        season_mult = 1.5  # Black Friday
    elif month == 12:
        season_mult = 1.3  # Natal
    elif month in [5, 10]:
        season_mult = 1.1  # Dias das Mães e Dia das Crianças
    else:
        season_mult = 1.0
    
    # Fim de semana tem meta menor
    weekday_mult = 0.7 if date.weekday() >= 5 else 1.0
    
    # METAS DIÁRIAS (baseadas em média diária realista)
    base_receita_dia = 24500  # ~750k/mês
    base_pedidos_dia = 60
    base_novos_clientes_dia = 40
    base_roas = 2.8
    
    metas_data.append({
        'Data': date,
        'Meta_Receita': round(base_receita_dia * year_mult * season_mult * weekday_mult, 2),
        'Meta_Pedidos': int(base_pedidos_dia * year_mult * season_mult * weekday_mult),
        'Meta_Novos_Clientes': int(base_novos_clientes_dia * year_mult * season_mult * weekday_mult),
        'Meta_ROAS': round(base_roas * (1 + 0.08 * (year - 2022)), 2)  # Meta ROAS cresce com maturidade
    })

dim_metas = pd.DataFrame(metas_data)

print(f"OK DIM_METAS: {len(dim_metas):,} linhas (diária)")

# =========================
# SALVA TODOS OS ARQUIVOS
# =========================
print("Salvando arquivos em powerbi_data/...")

# Cria pasta de output
import os
os.makedirs('powerbi_data', exist_ok=True)

# Salva arquivos
fato_performance.to_csv('powerbi_data/FATO_PERFORMANCE_DIARIA.csv', index=False)
print("OK FATO_PERFORMANCE_DIARIA.csv")

fato_vendas.to_csv('powerbi_data/FATO_VENDAS.csv', index=False)
print("OK FATO_VENDAS.csv")

dim_clientes.to_csv('powerbi_data/DIM_CLIENTES.csv', index=False)
print("OK DIM_CLIENTES.csv")

print("DIM_CALENDAR gerado no Power Query (não cria CSV)")

dim_metas.to_csv('powerbi_data/DIM_METAS.csv', index=False)
print("OK DIM_METAS.csv")

# =========================
# DOCUMENTAÇÃO DAS TABELAS
# =========================
print("Gerando DOCUMENTACAO.txt...")

doc = """
╔══════════════════════════════════════════════════════════════════════╗
║                    MODELO DE DADOS - POWER BI                        ║
║                    (Star Schema Otimizado)                           ║
╚══════════════════════════════════════════════════════════════════════╝

🔷 TABELAS FATO (Fact Tables)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. FATO_PERFORMANCE_DIARIA
   ├─ Granularidade: Dia + Canal + Campanha
   ├─ Métricas: Investimento, Impressoes, Cliques, Conversoes, Pedidos, Receita, Novos_Clientes
   ├─ Calculadas no Power BI: ROAS, CAC, CPC, CPM, CTR, CVR
   └─ Uso: Análise diária de performance de campanhas

2. FATO_VENDAS
   ├─ Granularidade: Cada venda individual
   ├─ Métricas: Receita, Cliente_Novo
   ├─ Dimensões: ID_Cliente, Produto, Segmento_Cliente, Regiao_Cliente
   └─ Uso: Análise detalhada de vendas e comportamento do cliente

🔶 TABELAS DIMENSÃO (Dimension Tables)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3. DIM_CLIENTES
   ├─ Chave: ID_Cliente
   ├─ Atributos: Segmento, Regiao, Status, Cohort
   ├─ Métricas: Total_Pedidos, LTV
   ├─ Classificações: Calculadas em DAX (Tier_Cliente, Frequencia_Compra)
   └─ Uso: Segmentação e análise de clientes

4. DIM_CALENDAR
   ├─ Chave: Data
   ├─ Gerada: Dinamicamente no Power Query (2023-2024)
   ├─ Atributos: Ano, Mes_Numero, Mes_Nome, Trimestre, Semana, Dia_Semana, Dia_Mes
   ├─ Flags: Fim_Semana, Black_Friday, Natal
   └─ Uso: Time intelligence e análise temporal

5. DIM_METAS
   ├─ Chave: Data (granularidade DIÁRIA)
   ├─ Métricas: Meta_Receita, Meta_Pedidos, Meta_Novos_Clientes, Meta_ROAS
   ├─ Sazonalidade: Black Friday (+50%), Natal (+30%), Fim de Semana (-30%)
   ├─ Crescimento: +12% ao ano, ROAS +8% ao ano
   └─ Uso: Comparação real vs meta com granularidade diária

╔══════════════════════════════════════════════════════════════════════╗
║                    MEDIDAS DAX (Copiar no Power BI)                  ║
╚══════════════════════════════════════════════════════════════════════╝

// ========== MÉTRICAS BÁSICAS ==========

Total Investimento = SUM(FATO_PERFORMANCE_DIARIA[Investimento])

Total Impressoes = SUM(FATO_PERFORMANCE_DIARIA[Impressoes])

Total Cliques = SUM(FATO_PERFORMANCE_DIARIA[Cliques])

Total Conversoes = SUM(FATO_PERFORMANCE_DIARIA[Conversoes])

Total Pedidos = SUM(FATO_PERFORMANCE_DIARIA[Pedidos])

Total Receita = SUM(FATO_PERFORMANCE_DIARIA[Receita])

Total Novos Clientes = SUM(FATO_PERFORMANCE_DIARIA[Novos_Clientes])

// ========== MÉTRICAS CALCULADAS ==========

ROAS = 
DIVIDE(
    [Total Receita],
    [Total Investimento],
    0
)

CAC = 
DIVIDE(
    [Total Investimento],
    [Total Novos Clientes],
    0
)

CPC = 
DIVIDE(
    [Total Investimento],
    [Total Cliques],
    0
)

CPM = 
DIVIDE(
    [Total Investimento],
    [Total Impressoes] / 1000,
    0
)

CTR = 
DIVIDE(
    [Total Cliques],
    [Total Impressoes],
    0
)

CVR = 
DIVIDE(
    [Total Conversoes],
    [Total Cliques],
    0
)

Ticket Medio = 
DIVIDE(
    [Total Receita],
    [Total Pedidos],
    0
)

// ========== MÉTRICAS DE CLIENTES ==========

LTV Medio = 
AVERAGE(DIM_CLIENTES[LTV])

LTV Total = 
SUM(DIM_CLIENTES[LTV])

Relacao LTV CAC = 
DIVIDE(
    [LTV Medio],
    [CAC],
    0
)

Total Clientes = 
DISTINCTCOUNT(FATO_VENDAS[ID_Cliente])

Taxa Churn = 
DIVIDE(
    CALCULATE(
// ========== COMPARAÇÃO COM METAS (GRANULARIDADE DIÁRIA) ==========

Meta ROAS = 
AVERAGE(DIM_METAS[Meta_ROAS])

Meta Receita = 
SUM(DIM_METAS[Meta_Receita])

Meta Pedidos = 
SUM(DIM_METAS[Meta_Pedidos])

Meta Novos Clientes = 
SUM(DIM_METAS[Meta_Novos_Clientes])

// ROAS vs Meta
ROAS vs Meta = 
[ROAS] - [Meta ROAS]

ROAS vs Meta % = 
DIVIDE(
    [ROAS vs Meta],
    [Meta ROAS],
    0
)

// Receita vs Meta
Receita vs Meta = 
[Total Receita] - [Meta Receita]

Receita vs Meta % = 
DIVIDE(
    [Receita vs Meta],
    [Meta Receita],
    0
)

// Pedidos vs Meta
Pedidos vs Meta = 
[Total Pedidos] - [Meta Pedidos]

Pedidos vs Meta % = 
DIVIDE(
    [Pedidos vs Meta],
    [Meta Pedidos],
    0
)

// Novos Clientes vs Meta
Novos Clientes vs Meta = 
[Total Novos Clientes] - [Meta Novos Clientes]

Novos Clientes vs Meta % = 
DIVIDE(
    [Novos Clientes vs Meta],
    [Meta Novos Clientes],
    0
)
Receita vs Meta = 
[Total Receita] - [Meta Receita]

Receita vs Meta % = 
DIVIDE(
    [Receita vs Meta],
    [Meta Receita],
    0
)

// ========== ANÁLISE TEMPORAL ==========

Receita Mes Anterior = 
CALCULATE(
    [Total Receita],
    DATEADD(DIM_CALENDAR[Data], -1, MONTH)
)

Receita YoY = 
CALCULATE(
    [Total Receita],
    DATEADD(DIM_CALENDAR[Data], -1, YEAR)
)

Crescimento MoM = 
DIVIDE(
    [Total Receita] - [Receita Mes Anterior],
    [Receita Mes Anterior],
    0
)

Crescimento YoY =
DIVIDE(
    [Total Receita] - [Receita YoY],
    [Receita YoY],
    0
)

// ========== CLASSIFICAÇÃO DE PERFORMANCE ==========

Classificacao Campanha =
VAR _ROAS = [ROAS]
RETURN
    SWITCH(
        TRUE(),
        _ROAS >= 4, "🏆 Excelente",
        _ROAS >= 3, "✅ Boa",
        _ROAS >= 2, "⚠️ Média",
        _ROAS >= 1, "❌ Ruim",
        "💀 Crítica"
    )
// ========== CLASSIFICAÇÃO DE CLIENTES (DINÂMICA) ==========

// Tier baseado em LTV
Tier Cliente =
VAR _LTV = SELECTEDVALUE(DIM_CLIENTES[LTV])
RETURN
    SWITCH(
        TRUE(),
        _LTV >= 2000, "🥇 Ouro",
        _LTV >= 500, "🥈 Prata",
        "🥉 Bronze"
    )

// Frequência de compra
Frequencia Compra =
VAR _Pedidos = SELECTEDVALUE(DIM_CLIENTES[Total_Pedidos])
RETURN
    SWITCH(
        TRUE(),
        _Pedidos >= 3, "🔥 Frequente",
        _Pedidos >= 2, "⏰ Ocasional",
        "⭐ Única"
    )

// Classificação dinâmica por percentil
Tier Cliente Dinamico =
VAR _LTV = SELECTEDVALUE(DIM_CLIENTES[LTV])
VAR P75 = PERCENTILE.INC(ALL(DIM_CLIENTES[LTV]), 0.75)
VAR P25 = PERCENTILE.INC(ALL(DIM_CLIENTES[LTV]), 0.25)
RETURN
    SWITCH(
        TRUE(),
        _LTV >= P75, "🥇 Top 25%",
        _LTV >= P25, "🥈 Médio 50%",
        "🥉 Bottom 25%"
    )

// ========== ANÁLISE GEOGRÁFICA (FATO_VENDAS) ==========

// Receita por Região
Receita Regional =
CALCULATE(
    SUM(FATO_VENDAS[Receita]),
    ALLEXCEPT(FATO_VENDAS, FATO_VENDAS[Regiao_Cliente])
)

// Participação da Região
Share Regional % =
DIVIDE(
    SUM(FATO_VENDAS[Receita]),
    CALCULATE(SUM(FATO_VENDAS[Receita]), ALL(FATO_VENDAS[Regiao_Cliente])),
    0
)

// Ticket Médio Regional
Ticket Medio Regional =
DIVIDE(
    SUM(FATO_VENDAS[Receita]),
    COUNTROWS(FATO_VENDAS),
    0
)

"""

with open('powerbi_data/DOCUMENTACAO.txt', 'w', encoding='utf-8') as f:
     f.write(doc)

print("OK DOCUMENTACAO.txt salva")
print("Concluído.")