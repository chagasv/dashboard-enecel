import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANILHAS_DIR = os.path.join(BASE_DIR, 'planilhas_para_atualizar')
CACHE_BBCE = os.path.join(PLANILHAS_DIR, 'bbce_diario_cache.json')

if os.path.exists(CACHE_BBCE):
    with open(CACHE_BBCE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    print("Colunas disponíveis:", df.columns)
    print("Total de linhas:", len(df))
    
    # Encontra a data máxima
    max_date = df['DATA_DIA'].max()
    print("Data máxima na base:", max_date)
    
    # Calcula a data de 3 meses atrás
    max_dt = pd.to_datetime(max_date)
    limit_dt = max_dt - pd.DateOffset(months=3)
    limit_date_str = limit_dt.strftime('%Y-%m-%d')
    print("Data limite de 3 meses atrás:", limit_date_str)
    
    # Filtra dados nos últimos 3 meses
    df_recent = df[df['DATA_DIA'] >= limit_date_str]
    print("Total de linhas nos últimos 3 meses:", len(df_recent))
    
    if len(df_recent) > 0:
        # Agrupa por produto e conta contratos
        grouped = df_recent.groupby('PRODUTO')['total_contratos'].sum().reset_index()
        grouped = grouped.sort_values(by='total_contratos', ascending=False)
        print("\nTop produtos negociados nos últimos 3 meses:")
        print(grouped.head(10))
    else:
        print("Nenhum dado encontrado nos últimos 3 meses.")
else:
    print("Arquivo de cache da BBCE não encontrado.")
