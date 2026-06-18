import os
import json
import pandas as pd
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLANILHAS_DIR = os.path.join(BASE_DIR, 'planilhas_para_atualizar')

PATH_BALANCO = os.path.join(PLANILHAS_DIR, 'f_balanco_energetico.xlsx')
PATH_PLD = os.path.join(PLANILHAS_DIR, 'f_pld.xlsx')
PATH_AMPERE = os.path.join(PLANILHAS_DIR, 'f_rodadas_ampere.xlsx')

CACHE_BALANCO = os.path.join(PLANILHAS_DIR, 'balanco_cache.json')
CACHE_PLD = os.path.join(PLANILHAS_DIR, 'pld_cache.json')
CACHE_AMPERE = os.path.join(PLANILHAS_DIR, 'ampere_cache.json')
CACHE_AMPERE_COMPLETO = os.path.join(PLANILHAS_DIR, 'ampere_completo_cache.json')

CACHE_BALANCO_RECENT = os.path.join(PLANILHAS_DIR, 'balanco_recent_cache.json')
CACHE_PLD_RECENT = os.path.join(PLANILHAS_DIR, 'pld_recent_cache.json')
CACHE_AMPERE_RECENT = os.path.join(PLANILHAS_DIR, 'ampere_recent_cache.json')
CACHE_PLD_HORARIO = os.path.join(PLANILHAS_DIR, 'pld_horario_cache.json')

PATH_METADADOS = os.path.join(PLANILHAS_DIR, 'metadata.json')

def format_date_str(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')

def gerar_todos_os_caches():
    print("Iniciando geracao de caches JSON e metadados...")
    
    metadata = {}
    
    # 1. Balanço Energético
    if os.path.exists(PATH_BALANCO):
        print("Processando Balanco Energetico...")
        df = pd.read_excel(PATH_BALANCO, sheet_name="balanco_energetico")
        df['din_instante'] = pd.to_datetime(df['din_instante'])
        
        # 1.1 Cache do Gráfico (2026 horário agrupado por hora e subsistema)
        df_2026 = df[df['din_instante'] >= '2026-01-01'].copy()
        df_grouped = df_2026.groupby(['din_instante', 'id_subsistema']).mean(numeric_only=True).reset_index()
        df_grouped['din_instante'] = df_grouped['din_instante'].dt.strftime('%Y-%m-%d %H:%M')
        data_balanco = df_grouped.to_dict(orient='records')
        with open(CACHE_BALANCO, 'w', encoding='utf-8') as f:
            json.dump(data_balanco, f, ensure_ascii=False, indent=2)
            
        # 1.2 Cache das 100 linhas mais recentes (dados brutos ordenados de forma decrescente)
        df_recent = df.sort_values(by=['din_instante', 'id_subsistema'], ascending=[False, True]).head(100).copy()
        df_recent['din_instante'] = df_recent['din_instante'].dt.strftime('%d/%m/%Y %H:%M')
        # Limpa nulos para JSON valido
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        with open(CACHE_BALANCO_RECENT, 'w', encoding='utf-8') as f:
            json.dump(data_recent, f, ensure_ascii=False, indent=2)
            
        max_date = df['din_instante'].max().strftime('%d/%m/%Y %H:%M')
        metadata['balanco'] = {
            'linhas': len(df),
            'max_data': max_date,
            'tamanho': f"{os.path.getsize(PATH_BALANCO) / (1024*1024):.2f} MB",
            'modificado': format_date_str(os.path.getmtime(PATH_BALANCO))
        }
        print(f"Cache do Balanco salvo. Max Data: {max_date}")
    else:
        print("Planilha de Balanco nao encontrada.")
        metadata['balanco'] = {'status': 'Não Encontrado'}
        
    # 2. PLD
    if os.path.exists(PATH_PLD):
        print("Processando PLD...")
        df = pd.read_excel(PATH_PLD, sheet_name="pld")
        
        # 2.1 Cache do Gráfico
        df_2026 = df[df['MES_REFERENCIA'] >= 202601]
        df_day = df_2026.groupby(['MES_REFERENCIA', 'DIA', 'SUBMERCADO']).mean(numeric_only=True).reset_index()
        
        def format_date(row):
            ano = int(str(row['MES_REFERENCIA'])[:4])
            mes = int(str(row['MES_REFERENCIA'])[4:])
            dia = int(row['DIA'])
            return f"{ano}-{mes:02d}-{dia:02d}"
            
        df_day['data'] = df_day.apply(format_date, axis=1)
        df_day = df_day.sort_values(by='data')
        
        submercados = df_day['SUBMERCADO'].unique().tolist()
        data_by_sub = {}
        for sub in submercados:
            df_sub = df_day[df_day['SUBMERCADO'] == sub]
            data_by_sub[sub] = {
                'labels': df_sub['data'].tolist(),
                'valores': df_sub['PLD_HORA'].round(2).tolist()
            }
            
        with open(CACHE_PLD, 'w', encoding='utf-8') as f:
            json.dump(data_by_sub, f, ensure_ascii=False, indent=2)
            
        # 2.2 Cache das 100 linhas mais recentes
        # Ordenado por MES_REFERENCIA, DIA, HORA de forma decrescente
        df_recent = df.sort_values(by=['MES_REFERENCIA', 'DIA', 'HORA', 'SUBMERCADO'], ascending=[False, False, False, True]).head(100).copy()
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        with open(CACHE_PLD_RECENT, 'w', encoding='utf-8') as f:
            json.dump(data_recent, f, ensure_ascii=False, indent=2)
            
        # 2.3 Cache Horário de PLD por Data e Submercado
        # Estrutura: { "YYYY-MM-DD": { "SUDESTE": [v0, v1, ..., v23], ... } }
        pld_horario_cache = {}
        for _, row in df.iterrows():
            try:
                mes = int(row['MES_REFERENCIA'])
                ano = mes // 100
                mes_num = mes % 100
                dia = int(row['DIA'])
                data_str = f"{ano}-{mes_num:02d}-{dia:02d}"
                
                sub = str(row['SUBMERCADO']).upper()
                hora = int(row['HORA'])
                valor = float(row['PLD_HORA'])
                
                if data_str not in pld_horario_cache:
                    pld_horario_cache[data_str] = {}
                if sub not in pld_horario_cache[data_str]:
                    pld_horario_cache[data_str][sub] = [None] * 24
                    
                if 0 <= hora <= 23:
                    pld_horario_cache[data_str][sub][hora] = valor
            except Exception as e:
                continue
                
        with open(CACHE_PLD_HORARIO, 'w', encoding='utf-8') as f:
            json.dump(pld_horario_cache, f, ensure_ascii=False, indent=2)
            
        max_ref = df['MES_REFERENCIA'].max()
        df_last_ref = df[df['MES_REFERENCIA'] == max_ref]
        max_dia = df_last_ref['DIA'].max()
        max_data = f"{str(max_ref)[4:]}/{str(max_ref)[:4]} (Dia {max_dia})"
        
        metadata['pld'] = {
            'linhas': len(df),
            'max_data': max_data,
            'tamanho': f"{os.path.getsize(PATH_PLD) / (1024*1024):.2f} MB",
            'modificado': format_date_str(os.path.getmtime(PATH_PLD))
        }
        print("Cache do PLD salvo.")
    else:
        print("Planilha de PLD nao encontrada.")
        metadata['pld'] = {'status': 'Não Encontrado'}
        
    # 3. Ampere
    if os.path.exists(PATH_AMPERE):
        print("Processando Ampere...")
        df = pd.read_excel(PATH_AMPERE, sheet_name="f_dados")
        if len(df) > 0:
            max_rodada = df['rodada'].max()
            df_last = df[df['rodada'] == max_rodada].copy()
            df_last['data_referencia'] = pd.to_datetime(df_last['data_referencia']).dt.strftime('%Y-%m-%d')
            
            # ENA
            df_ena = df_last[df_last['indicador'] == 'ENA']
            ena_data = []
            for _, r in df_ena.iterrows():
                ena_data.append({
                    'data': r['data_referencia'],
                    'subsistema': r['subsistema'],
                    'unidade': r['unidade'],
                    'valor': r['valor']
                })
                
            # Armazenamento
            df_arm = df_last[df_last['indicador'] == 'Armazenamento']
            arm_data = []
            for _, r in df_arm.iterrows():
                arm_data.append({
                    'data': r['data_referencia'],
                    'subsistema': r['subsistema'],
                    'valor': r['valor']
                })
                
            # PLD
            df_pld = df_last[df_last['indicador'] == 'PLD']
            pld_data = []
            for _, r in df_pld.iterrows():
                pld_data.append({
                    'data': r['data_referencia'],
                    'subsistema': r['subsistema'],
                    'valor': r['valor']
                })
                
            cache_ampere_data = {
                'rodada': int(max_rodada),
                'data_publicacao': pd.to_datetime(df_last['data_publicacao'].iloc[0]).strftime('%d/%m/%Y'),
                'ena': ena_data,
                'armazenamento': arm_data,
                'pld': pld_data
            }
            
            with open(CACHE_AMPERE, 'w', encoding='utf-8') as f:
                json.dump(cache_ampere_data, f, ensure_ascii=False, indent=2)
                
            # Cache Completo (Todas as rodadas)
            df_sorted = df.sort_values(by=['rodada', 'data_referencia']).copy()
            df_sorted['data_referencia'] = pd.to_datetime(df_sorted['data_referencia']).dt.strftime('%Y-%m-%d')
            df_sorted['data_publicacao'] = pd.to_datetime(df_sorted['data_publicacao']).dt.strftime('%Y-%m-%d')
            df_sorted = df_sorted.fillna("")
            data_completa = df_sorted.to_dict(orient='records')
            with open(CACHE_AMPERE_COMPLETO, 'w', encoding='utf-8') as f:
                json.dump(data_completa, f, ensure_ascii=False, indent=2)
                
            # 3.2 Cache das 100 linhas mais recentes
            # Ordenado por rodada decrescente, data_referencia decrescente
            df_recent = df.sort_values(by=['rodada', 'data_referencia', 'indicador'], ascending=[False, False, True]).head(100).copy()
            df_recent['data_referencia'] = pd.to_datetime(df_recent['data_referencia']).dt.strftime('%d/%m/%Y')
            df_recent['data_publicacao'] = pd.to_datetime(df_recent['data_publicacao']).dt.strftime('%d/%m/%Y')
            df_recent = df_recent.fillna("")
            data_recent = df_recent.to_dict(orient='records')
            with open(CACHE_AMPERE_RECENT, 'w', encoding='utf-8') as f:
                json.dump(data_recent, f, ensure_ascii=False, indent=2)
                
            max_pub = pd.to_datetime(df_last['data_publicacao'].iloc[0]).strftime('%d/%m/%Y')
            max_data = f"Rodada {max_rodada} (Publicado em {max_pub})"
            
            metadata['ampere'] = {
                'linhas': len(df),
                'max_data': max_data,
                'tamanho': f"{os.path.getsize(PATH_AMPERE) / 1024:.2f} KB",
                'modificado': format_date_str(os.path.getmtime(PATH_AMPERE))
            }
            print("Cache da Ampere salvo.")
    else:
        print("Planilha da Ampere nao encontrada.")
        metadata['ampere'] = {'status': 'Não Encontrado'}
        
    with open(PATH_METADADOS, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print("Arquivo de metadados metadata.json gerado com sucesso!")

if __name__ == '__main__':
    gerar_todos_os_caches()
