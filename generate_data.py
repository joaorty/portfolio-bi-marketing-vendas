import numpy as np
import pandas as pd
import uuid
from datetime import timedelta, datetime

np.random.seed(42)

# =========================
# CONFIGURAÇÕES REALISTAS (REDUZIDAS PARA PERFORMANCE)
# =========================
segments = ["SMB", "Mid-Market", "Enterprise"]
segment_probs = [0.6, 0.3, 0.1]

# Distribuição realista por estado (baseado em PIB e população)
state_weights = {
    "SP": 0.30, "RJ": 0.12, "MG": 0.10, "ES": 0.03,
    "PR": 0.08, "SC": 0.07, "RS": 0.07,
    "BA": 0.06, "PE": 0.05, "CE": 0.05,
    "DF": 0.03, "GO": 0.04
}

states = list(state_weights.keys())
weights = np.array(list(state_weights.values()))
state_probs = weights / weights.sum()

products = {
    "Plano Básico": (79, 149),
    "Plano Pro": (199, 399),
    "Plano Enterprise": (599, 1499)
}

segment_product_bias = {
    "SMB": ["Plano Básico", "Plano Pro"],
    "Mid-Market": ["Plano Pro", "Plano Enterprise"],
    "Enterprise": ["Plano Enterprise"]
}

# =========================
# 1. GERA DADOS DE ADS (Google Ads, Meta, TikTok)
# =========================
print("Gerando dados de anúncios...")

# REDUZIDO: apenas 2023-2024 (2 anos ao invés de 3)
dates = pd.date_range("2023-01-01", "2024-12-31")

channels = {
    "Google Ads": {"cpc": 2.5, "ctr": 0.35, "cvr": 0.20},
    "Meta Ads": {"cpc": 1.8, "ctr": 0.32, "cvr": 0.18},
    "TikTok Ads": {"cpc": 1.2, "ctr": 0.38, "cvr": 0.22}
}

campaigns = [
    "Performance_Search", 
    "Performance_Shopping", 
    "Remarketing_Display",
    "Lead_Generation",
    # Campanhas RUINS (para identificar e pausar)
    "Display_Generico",
    "Video_Awareness_Amplo"
]


# Multiplicadores realistas de performance (ajustados para CVR ~20%)
campaign_multipliers = {
    "Performance_Search": 1.10,     # CVR ~22%
    "Performance_Shopping": 0.95,   # CVR ~19%
    "Remarketing_Display": 1.25,    # CVR ~25% (melhor conversão)
    "Lead_Generation": 0.85,        # CVR ~17%
    # Campanhas RUINS (devem ser pausadas)
    "Display_Generico": 0.15,       # CVR ~3% (terrível)
    "Video_Awareness_Amplo": 0.20   # CVR ~4% (muito ruim)
} 
monthly_seasonality = {
    1: 0.85,  # Janeiro (férias)
    2: 0.90,  # Fevereiro
    3: 1.00,  # Março
    4: 1.05,  # Abril
    5: 1.10,  # Maio (Dia das Mães)
    6: 1.05,  # Junho
    7: 0.95,  # Julho (férias)
    8: 1.00,  # Agosto
    9: 1.05,  # Setembro
    10: 1.10, # Outubro
    11: 1.50, # Novembro (Black Friday)
    12: 1.30  # Dezembro (Natal)
}

ads_data = []

for date in dates:
    year_growth = 1 + 0.15 * (date.year - 2022)  # Crescimento ano a ano
    month_factor = monthly_seasonality[date.month]
    weekday_factor = 0.65 if date.weekday() >= 5 else 1.0  # Fim de semana
    
    for channel, cfg in channels.items():
        for campaign in campaigns:
            # Budget diário varia por campanha (REDUZIDO para menos dados)
            if "Display_Generico" in campaign or "Video_Awareness_Amplo" in campaign:
                # Campanhas ruins com budget ALTO (desperdício)
                base_budget = np.random.uniform(800, 1500)
            elif "Remarketing" in campaign:
                base_budget = np.random.uniform(200, 400)
            else:
                base_budget = np.random.uniform(400, 1000)
            
            spend = base_budget * year_growth * month_factor * weekday_factor
            
            # IMPRESSIONS e CLICKS
            cpc = cfg["cpc"] * np.random.uniform(0.9, 1.1)  # Variação do CPC
            clicks = int(spend / cpc)  # Clicks baseado em spend e CPC
            
            # CTR varia por tipo de campanha (AJUSTADO para ~30-35% geral)
            if "Display" in campaign or "Video" in campaign:
                # Campanhas ruins têm CTR baixo mas não impossível
                ctr = cfg["ctr"] * 0.25 * np.random.uniform(0.8, 1.2)  # ~8% CTR
            else:
                # Campanhas de performance têm CTR alto
                ctr = cfg["ctr"] * np.random.uniform(0.9, 1.1)  # ~35% CTR
            
            impressions = int(clicks / ctr) if ctr > 0 else 0  # Impressions baseado em clicks e CTR
            
            # CONVERSIONS (evento configurado no pixel/tag)
            campaign_mult = campaign_multipliers[campaign]
            cvr = cfg["cvr"] * campaign_mult * np.random.uniform(0.90, 1.10)
            conversions = int(clicks * cvr)
            
            ads_data.append({
                "date": date,
                "channel": channel,
                "campaign": campaign,
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "cpc": round(cpc, 2),
                "ctr": round(ctr, 4),
                "cvr": round(cvr, 4)
            })

df_ads = pd.DataFrame(ads_data)
print(f"✓ Dados de anúncios gerados: {len(df_ads):,} linhas")
print(f"  Total de conversões: {df_ads['conversions'].sum():,}")

# =========================
# 2. GERA DADOS DE SESSÕES (Google Analytics) - OTIMIZADO
# =========================
print("\nGerando dados de sessões web...")

# Agrupa por data/canal/campanha para processar em lote
sessions_agg = []

for _, ad_row in df_ads.iterrows():
    # Nem todo click vira sessão (bots, duplicatas, etc)
    num_sessions = int(ad_row["clicks"] * np.random.uniform(0.85, 0.95))
    
    if num_sessions == 0:
        continue
    
    # Gera distribuição de devices para todas as sessões de uma vez
    devices = np.random.choice(
        ["mobile", "desktop", "tablet"],
        size=num_sessions,
        p=[0.65, 0.30, 0.05]
    )
    
    # Calcula bounce agregado
    mobile_count = (devices == "mobile").sum()
    desktop_count = (devices == "desktop").sum()
    tablet_count = (devices == "tablet").sum()
    
    bounce_mobile = 0.65 if "Remarketing" not in ad_row["campaign"] else 0.45
    bounce_other = 0.50 if "Remarketing" not in ad_row["campaign"] else 0.35
    
    bounced_sessions = int(mobile_count * bounce_mobile + (desktop_count + tablet_count) * bounce_other)
    non_bounced_sessions = num_sessions - bounced_sessions
    
    # Métricas agregadas simplificadas
    avg_pages = 1.0 * bounced_sessions + 3.5 * non_bounced_sessions
    avg_duration = 20 * bounced_sessions + 150 * non_bounced_sessions
    
    sessions_agg.append({
        "date": ad_row["date"],
        "channel": ad_row["channel"],
        "campaign": ad_row["campaign"],
        "total_sessions": num_sessions,
        "bounced_sessions": bounced_sessions,
        "mobile_sessions": mobile_count,
        "desktop_sessions": desktop_count,
        "tablet_sessions": tablet_count,
        "total_pages": int(avg_pages),
        "total_duration_seconds": int(avg_duration)
    })

df_sessions = pd.DataFrame(sessions_agg)
print(f"✓ Dados de sessões gerados: {len(df_sessions):,} linhas (agregadas)")

# =========================
# 3. GERA DADOS DE VENDAS (CRM/Sistema de Vendas) - OTIMIZADO
# =========================
print("\nGerando dados de vendas...")

customers = {}
customer_counter = 1
sales_data = []

# Agrupa conversões por data/canal/campanha para processar em lote
conversions_by_campaign = df_ads.groupby(['date', 'channel', 'campaign'])['conversions'].sum().reset_index()

print(f"Processando {len(conversions_by_campaign)} grupos de conversões...")

for idx, row in conversions_by_campaign.iterrows():
    if idx % 1000 == 0:
        print(f"  Progresso: {idx}/{len(conversions_by_campaign)} grupos ({len(sales_data):,} vendas geradas)")
    
    date = row["date"]
    channel = row["channel"]
    campaign = row["campaign"]
    total_conversions = int(row["conversions"])
    
    if total_conversions == 0:
        continue
    
    # Taxa de conversão de lead para venda: 22%
    # (nem toda conversão de ads vira venda fechada)
    num_sales = int(total_conversions * 0.22)
    
    if num_sales == 0:
        continue
    
    year = date.year
    
    # Evolução natural do mix de produtos ao longo dos anos
    basic_weight = max(0.30, 0.50 - 0.04 * (year - 2022))
    enterprise_weight = min(0.25, 0.15 + 0.03 * (year - 2022))
    pro_weight = 1 - basic_weight - enterprise_weight
    
    # Gera vendas em lote para este grupo
    for _ in range(num_sales):
        # Cliente novo vs recorrente (recompra)
        is_new_customer = 1
        
        # 35% são recompras de clientes existentes
        if customers and np.random.rand() < 0.35:
            customer_id = np.random.choice(list(customers.keys()))
            is_new_customer = 0
            customer = customers[customer_id]
        else:
            customer_id = customer_counter
            customer_counter += 1
            
            # Dados do cliente (coletados no CRM)
            segment = np.random.choice(segments, p=segment_probs)
            region = np.random.choice(states, p=state_probs)
            
            customer = {
                "segment": segment,
                "region": region,
                "acquisition_date": date,
                "acquisition_channel": channel,
                "acquisition_campaign": campaign,
                "total_orders": 0,
                "total_revenue": 0,
                "status": "active"
            }
            customers[customer_id] = customer
        
        segment = customer["segment"]
        
        # Produto baseado no segmento do cliente
        possible_products = segment_product_bias[segment]
        if segment == "SMB":
            prod_probs = [basic_weight / (basic_weight + pro_weight), pro_weight / (basic_weight + pro_weight)]
        elif segment == "Mid-Market":
            prod_probs = [pro_weight / (pro_weight + enterprise_weight), enterprise_weight / (pro_weight + enterprise_weight)]
        else:  # Enterprise
            prod_probs = [1.0]
        
        product = np.random.choice(possible_products, p=prod_probs)
        
        # Revenue com variação realista
        min_price, max_price = products[product]
        revenue = round(np.random.uniform(min_price, max_price), 2)
        
        # Data da venda (0-5 dias após conversão)
        sale_date = date + timedelta(days=int(np.random.randint(0, 6)))
        
        # Atualiza dados do cliente
        customer["total_orders"] += 1
        customer["total_revenue"] += revenue
        
        sales_data.append({
            "order_id": str(uuid.uuid4()),
            "date": sale_date,
            "customer_id": customer_id,
            "is_new_customer": is_new_customer,
            "customer_segment": segment,
            "customer_region": customer["region"],
            "product": product,
            "revenue": revenue,
            "acquisition_channel": customer["acquisition_channel"],
            "acquisition_campaign": customer["acquisition_campaign"],
            "channel": channel,
            "campaign": campaign
        })

df_sales = pd.DataFrame(sales_data)
print(f"✓ Dados de vendas gerados: {len(df_sales):,} linhas")
print(f"  Total de clientes: {len(customers):,}")
if len(df_sales) > 0:
    print(f"  Revenue total: R$ {df_sales['revenue'].sum():,.2f}")
else:
    print(f"  Revenue total: R$ 0.00")

# =========================
# 4. GERA DADOS DE CLIENTES (CRM)
# =========================
print("\nGerando dados de clientes...")

customers_data = []
for customer_id, customer_info in customers.items():
    # Simula churn realista (clientes que cancelaram)
    months_since_acquisition = max(0, (
        pd.Timestamp("2024-12-31") - customer_info["acquisition_date"]
    ).days / 30)
    
    # Probabilidade de churn aumenta com tempo
    churn_prob = min(0.35, 0.05 + 0.02 * months_since_acquisition)
    
    if customer_info["total_orders"] == 0:
        status = "lead"  # Nunca comprou (não deveria acontecer aqui, mas por segurança)
    elif np.random.rand() < churn_prob:
        status = "churned"
    else:
        status = "active"
    
    customers_data.append({
        "customer_id": customer_id,
        "acquisition_date": customer_info["acquisition_date"],
        "acquisition_channel": customer_info["acquisition_channel"],
        "acquisition_campaign": customer_info["acquisition_campaign"],
        "segment": customer_info["segment"],
        "region": customer_info["region"],
        "total_orders": customer_info["total_orders"],
        "total_revenue": round(customer_info["total_revenue"], 2),
        "status": status
    })

df_customers = pd.DataFrame(customers_data)
print(f"✓ Dados de clientes gerados: {len(df_customers):,} linhas")

# =========================
# SALVA ARQUIVOS
# =========================
print("\n" + "="*60)
print("SALVANDO ARQUIVOS...")
print("="*60)

df_ads.to_csv("ads_data.csv", index=False)
print(f"✓ ads_data.csv: {len(df_ads):,} linhas")

df_sessions.to_csv("sessions_data.csv", index=False)
print(f"✓ sessions_data.csv: {len(df_sessions):,} linhas")

df_sales.to_csv("sales_data.csv", index=False)
print(f"✓ sales_data.csv: {len(df_sales):,} linhas")

df_customers.to_csv("customers_data.csv", index=False)
print(f"✓ customers_data.csv: {len(df_customers):,} linhas")

# =========================
# PREVIEW DOS DADOS
# =========================
print("\n" + "="*60)
print("\n📊 ADS DATA (primeiras 3 linhas):")
print(df_ads.head(3))

print("\n🌐 SESSIONS DATA (primeiras 3 linhas):")
print(df_sessions.head(3))

print("\n💰 SALES DATA (primeiras 3 linhas):")
if len(df_sales) > 0:
    print(df_sales.head(3))
else:
    print("Nenhuma venda gerada")

print("\n👥 CUSTOMERS DATA (primeiras 3 linhas):")
if len(df_customers) > 0:
    print(df_customers.head(3))
else:
    print("Nenhum cliente gerado")

# =========================
# ESTATÍSTICAS RESUMIDAS
# =========================
print("\n" + "="*60)
print("ESTATÍSTICAS RESUMIDAS")
print("="*60)

print(f"\n📊 FUNIL DE CONVERSÃO:")
print(f"   Impressions:  {df_ads['impressions'].sum():,}")
print(f"   Clicks:       {df_ads['clicks'].sum():,}")
print(f"   Conversions:  {df_ads['conversions'].sum():,}")
print(f"   Sales:        {len(df_sales):,}")
print(f"   Customers:    {len(df_customers):,}")

print("\n💰 FINANCEIRO:")
print(f"   Total Spend:   R$ {df_ads['spend'].sum():,.2f}")
if len(df_sales) > 0:
    print(f"   Total Revenue: R$ {df_sales['revenue'].sum():,.2f}")
    print(f"   ROAS Geral:    {df_sales['revenue'].sum() / df_ads['spend'].sum():.2f}")
else:
    print(f"   Total Revenue: R$ 0.00")
    print(f"   ROAS Geral:    0.00")

print(f"\n👥 CLIENTES:")
if len(df_customers) > 0:
    print(f"   SMB:        {df_customers[df_customers['segment']=='SMB'].shape[0]:,} ({df_customers[df_customers['segment']=='SMB'].shape[0]/len(df_customers)*100:.1f}%)")
    print(f"   Mid-Market: {df_customers[df_customers['segment']=='Mid-Market'].shape[0]:,} ({df_customers[df_customers['segment']=='Mid-Market'].shape[0]/len(df_customers)*100:.1f}%)")
    print(f"   Enterprise: {df_customers[df_customers['segment']=='Enterprise'].shape[0]:,} ({df_customers[df_customers['segment']=='Enterprise'].shape[0]/len(df_customers)*100:.1f}%)")
else:
    print("   Nenhum cliente gerado")

print(f"\n📦 PRODUTOS:")
if len(df_sales) > 0:
    for product in products.keys():
        count = df_sales[df_sales['product']==product].shape[0]
        revenue = df_sales[df_sales['product']==product]['revenue'].sum()
        print(f"   {product:20s}: {count:,} vendas | R$ {revenue:,.2f}")
else:
    print("   Nenhuma venda gerada")

print("\n" + "="*60)
print("KPIs CALCULÁVEIS COM ESSES DADOS:")
print("="*60)
print("""
✓ CAC (Customer Acquisition Cost) = spend / new_customers
✓ ROAS (Return on Ad Spend) = revenue / spend
✓ CTR (Click-Through Rate) = clicks / impressions
✓ CVR (Conversion Rate) = conversions / clicks
✓ CPC (Cost Per Click) = spend / clicks
✓ CPM (Cost Per Mille) = (spend / impressions) * 1000
✓ Bounce Rate = bounced_sessions / total_sessions
✓ LTV (Lifetime Value) = total_revenue per customer
✓ Churn Rate = churned_customers / total_customers
✓ Retention Rate = active_customers / total_customers
✓ Average Order Value = revenue / orders
✓ Purchase Frequency = orders / customers
✓ Revenue by Channel/Campaign/Product/Region/Segment
✓ Cohort Analysis (por data de aquisição)
✓ Payback Period = CAC / (LTV / avg_lifetime_months)
""")