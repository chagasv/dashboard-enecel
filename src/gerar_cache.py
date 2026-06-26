import os
import json
import pandas as pd
import datetime
import io
from src.github_storage import github_read_file, github_write_file, github_file_exists, github_get_file_info

# Diretório raiz do projeto (sobe 1 nível por estar na pasta src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

PATH_ENA = os.path.join(PLANILHAS_DIR, 'ENA_DIARIO_SUBSISTEMA_2026.xlsx')
CACHE_ENA = os.path.join(PLANILHAS_DIR, 'ena_cache.json')
CACHE_ENA_RECENT = os.path.join(PLANILHAS_DIR, 'ena_recent_cache.json')

PATH_CARGA = os.path.join(PLANILHAS_DIR, 'CARGA_ENERGIA_2026.xlsx')
CACHE_CARGA = os.path.join(PLANILHAS_DIR, 'carga_cache.json')
CACHE_CARGA_RECENT = os.path.join(PLANILHAS_DIR, 'carga_recent_cache.json')

PATH_EAR = os.path.join(PLANILHAS_DIR, 'EAR_DIARIO_SUBSISTEMA_2026.xlsx')
CACHE_EAR = os.path.join(PLANILHAS_DIR, 'ear_cache.json')
CACHE_EAR_RECENT = os.path.join(PLANILHAS_DIR, 'ear_recent_cache.json')

PATH_METADADOS = os.path.join(PLANILHAS_DIR, 'metadata.json')

def format_date_str(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')

def gerar_todos_os_caches():
    print("Iniciando geracao de caches JSON e metadados...")
    
    metadata = {}
    if github_file_exists(PATH_METADADOS):
        try:
            conteudo_meta = github_read_file(PATH_METADADOS)
            metadata = json.loads(conteudo_meta.decode('utf-8'))
        except Exception as e:
            print(f"Aviso: Erro ao carregar metadados existentes: {str(e)}")
    
    # 1. Balanço Energético
    if github_file_exists(PATH_BALANCO):
        print("Processando Balanco Energetico...")
        conteudo = github_read_file(PATH_BALANCO)
        df = pd.read_excel(io.BytesIO(conteudo), sheet_name="balanco_energetico")
        df['din_instante'] = pd.to_datetime(df['din_instante'])
        
        # 1.1 Cache do Gráfico (2026 horário agrupado por hora e subsistema)
        df_2026 = df[df['din_instante'] >= '2026-01-01'].copy()
        df_grouped = df_2026.groupby(['din_instante', 'id_subsistema']).mean(numeric_only=True).reset_index()
        df_grouped['din_instante'] = df_grouped['din_instante'].dt.strftime('%Y-%m-%d %H:%M')
        data_balanco = df_grouped.to_dict(orient='records')
        github_write_file(CACHE_BALANCO, json.dumps(data_balanco, ensure_ascii=False, indent=2).encode('utf-8'))
            
        # 1.2 Cache das 100 linhas mais recentes (dados brutos ordenados de forma decrescente)
        df_recent = df.sort_values(by=['din_instante', 'id_subsistema'], ascending=[False, True]).head(100).copy()
        df_recent['din_instante'] = df_recent['din_instante'].dt.strftime('%d/%m/%Y %H:%M')
        # Limpa nulos para JSON valido
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        github_write_file(CACHE_BALANCO_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
            
        max_date = df['din_instante'].max().strftime('%d/%m/%Y %H:%M')
        info_balanco = github_get_file_info(PATH_BALANCO)
        metadata['balanco'] = {
            'linhas': len(df),
            'max_data': max_date,
            'tamanho': info_balanco['tamanho'],
            'modificado': info_balanco['modificado']
        }
        print(f"Cache do Balanco salvo. Max Data: {max_date}")
    else:
        print("Planilha de Balanco nao encontrada.")
        metadata['balanco'] = {'status': 'Não Encontrado'}
        
    # 2. PLD
    if github_file_exists(PATH_PLD):
        print("Processando PLD...")
        conteudo = github_read_file(PATH_PLD)
        df = pd.read_excel(io.BytesIO(conteudo), sheet_name="pld")
        
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
            
        github_write_file(CACHE_PLD, json.dumps(data_by_sub, ensure_ascii=False, indent=2).encode('utf-8'))
            
        # 2.2 Cache das 100 linhas mais recentes
        # Ordenado por MES_REFERENCIA, DIA, HORA de forma decrescente
        df_recent = df.sort_values(by=['MES_REFERENCIA', 'DIA', 'HORA', 'SUBMERCADO'], ascending=[False, False, False, True]).head(100).copy()
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        github_write_file(CACHE_PLD_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
            
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
                
        github_write_file(CACHE_PLD_HORARIO, json.dumps(pld_horario_cache, ensure_ascii=False, indent=2).encode('utf-8'))
            
        max_ref = df['MES_REFERENCIA'].max()
        df_last_ref = df[df['MES_REFERENCIA'] == max_ref]
        max_dia = df_last_ref['DIA'].max()
        max_data = f"{str(max_ref)[4:]}/{str(max_ref)[:4]} (Dia {max_dia})"
        
        info_pld = github_get_file_info(PATH_PLD)
        metadata['pld'] = {
            'linhas': len(df),
            'max_data': max_data,
            'tamanho': info_pld['tamanho'],
            'modificado': info_pld['modificado']
        }
        print("Cache do PLD salvo.")
    else:
        print("Planilha de PLD nao encontrada.")
        metadata['pld'] = {'status': 'Não Encontrado'}
        
    # 3. Ampere
    if github_file_exists(PATH_AMPERE):
        print("Processando Ampere...")
        conteudo = github_read_file(PATH_AMPERE)
        df = pd.read_excel(io.BytesIO(conteudo), sheet_name="f_dados")
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
            
            github_write_file(CACHE_AMPERE, json.dumps(cache_ampere_data, ensure_ascii=False, indent=2).encode('utf-8'))
                
            # Cache Completo (Todas as rodadas)
            df_sorted = df.sort_values(by=['rodada', 'data_referencia']).copy()
            df_sorted['data_referencia'] = pd.to_datetime(df_sorted['data_referencia']).dt.strftime('%Y-%m-%d')
            df_sorted['data_publicacao'] = pd.to_datetime(df_sorted['data_publicacao']).dt.strftime('%Y-%m-%d')
            df_sorted = df_sorted.fillna("")
            data_completa = df_sorted.to_dict(orient='records')
            github_write_file(CACHE_AMPERE_COMPLETO, json.dumps(data_completa, ensure_ascii=False, indent=2).encode('utf-8'))
                
            # 3.2 Cache das 100 linhas mais recentes
            # Ordenado por rodada decrescente, data_referencia decrescente
            df_recent = df.sort_values(by=['rodada', 'data_referencia', 'indicador'], ascending=[False, False, True]).head(100).copy()
            df_recent['data_referencia'] = pd.to_datetime(df_recent['data_referencia']).dt.strftime('%d/%m/%Y')
            df_recent['data_publicacao'] = pd.to_datetime(df_recent['data_publicacao']).dt.strftime('%d/%m/%Y')
            df_recent = df_recent.fillna("")
            data_recent = df_recent.to_dict(orient='records')
            github_write_file(CACHE_AMPERE_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
                
            max_pub = pd.to_datetime(df_last['data_publicacao'].iloc[0]).strftime('%d/%m/%Y')
            max_data = f"Rodada {max_rodada} (Publicado em {max_pub})"
            
            info_ampere = github_get_file_info(PATH_AMPERE)
            metadata['ampere'] = {
                'linhas': len(df),
                'max_data': max_data,
                'tamanho': info_ampere['tamanho'],
                'modificado': info_ampere['modificado']
            }
            print("Cache da Ampere salvo.")
    else:
        print("Planilha da Ampere nao encontrada.")
        metadata['ampere'] = {'status': 'Não Encontrado'}

    # 4. ENA
    if github_file_exists(PATH_ENA):
        print("Processando ENA...")
        try:
            from etl import ler_excel_com_copia
            df = ler_excel_com_copia(PATH_ENA)
        except Exception as e:
            print(f"Aviso: erro ao ler ENA com cópia ({str(e)}). Tentando leitura direta...")
            conteudo = github_read_file(PATH_ENA)
            df = pd.read_excel(io.BytesIO(conteudo))
        
        if len(df) > 0:
            df['ena_data'] = pd.to_datetime(df['ena_data'])
            df_sorted = df.sort_values(by='ena_data').copy()
            
            cache_ena_data = {}
            for sub in ['N', 'NE', 'S', 'SE']:
                df_sub = df_sorted[df_sorted['id_subsistema'] == sub]
                cache_ena_data[sub] = {
                    'labels': df_sub['ena_data'].dt.strftime('%Y-%m-%d').tolist(),
                    'ena_bruta_mwmed': df_sub['ena_bruta_regiao_mwmed'].round(2).tolist(),
                    'ena_bruta_percentualmlt': df_sub['ena_bruta_regiao_percentualmlt'].round(2).tolist(),
                    'ena_armazenavel_mwmed': df_sub['ena_armazenavel_regiao_mwmed'].round(2).tolist(),
                    'ena_armazenavel_percentualmlt': df_sub['ena_armazenavel_regiao_percentualmlt'].round(2).tolist(),
                    'nom_subsistema': df_sub['nom_subsistema'].iloc[0] if len(df_sub) > 0 else sub
                }
                
            github_write_file(CACHE_ENA, json.dumps(cache_ena_data, ensure_ascii=False, indent=2).encode('utf-8'))
            
            # Cache Recente (100 linhas)
            df_recent = df.sort_values(by='ena_data', ascending=False).head(100).copy()
            df_recent['ena_data'] = df_recent['ena_data'].dt.strftime('%d/%m/%Y')
            df_recent = df_recent.fillna("")
            data_recent = df_recent.to_dict(orient='records')
            github_write_file(CACHE_ENA_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
            
            max_date = df['ena_data'].max().strftime('%d/%m/%Y')
            info_ena = github_get_file_info(PATH_ENA)
            metadata['ena'] = {
                'linhas': len(df),
                'max_data': max_date,
                'tamanho': info_ena['tamanho'],
                'modificado': info_ena['modificado']
            }
            print("Cache da ENA salvo.")
    else:
        print("Planilha da ENA nao encontrada.")
        metadata['ena'] = {'status': 'Não Encontrado'}
        
    # 5. Carga
    if github_file_exists(PATH_CARGA):
        print("Processando Carga...")
        try:
            from etl import ler_excel_com_copia
            df = ler_excel_com_copia(PATH_CARGA)
        except Exception as e:
            print(f"Aviso: erro ao ler Carga com cópia ({str(e)}). Tentando leitura direta...")
            conteudo = github_read_file(PATH_CARGA)
            df = pd.read_excel(io.BytesIO(conteudo))
        
        if len(df) > 0:
            df['din_instante'] = pd.to_datetime(df['din_instante'])
            df_sorted = df.sort_values(by='din_instante').copy()
            
            cache_carga_data = {}
            for sub in ['N', 'NE', 'S', 'SE']:
                df_sub = df_sorted[df_sorted['id_subsistema'] == sub]
                cache_carga_data[sub] = {
                    'labels': df_sub['din_instante'].dt.strftime('%Y-%m-%d').tolist(),
                    'carga_mwmed': df_sub['val_cargaenergiamwmed'].round(2).tolist(),
                    'nom_subsistema': df_sub['nom_subsistema'].iloc[0] if len(df_sub) > 0 else sub
                }
                
            github_write_file(CACHE_CARGA, json.dumps(cache_carga_data, ensure_ascii=False, indent=2).encode('utf-8'))
            
            # Cache Recente (100 linhas)
            df_recent = df.sort_values(by='din_instante', ascending=False).head(100).copy()
            df_recent['din_instante'] = df_recent['din_instante'].dt.strftime('%d/%m/%Y')
            df_recent = df_recent.fillna("")
            data_recent = df_recent.to_dict(orient='records')
            github_write_file(CACHE_CARGA_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
            
            max_date = df['din_instante'].max().strftime('%d/%m/%Y')
            info_carga = github_get_file_info(PATH_CARGA)
            metadata['carga'] = {
                'linhas': len(df),
                'max_data': max_date,
                'tamanho': info_carga['tamanho'],
                'modificado': info_carga['modificado']
            }
            print("Cache da Carga salvo.")
    else:
        print("Planilha da Carga nao encontrada.")
        metadata['carga'] = {'status': 'Não Encontrado'}
        
    # 6. Reservatório (EAR)
    if github_file_exists(PATH_EAR):
        print("Processando EAR...")
        try:
            from etl import ler_excel_com_copia
            df = ler_excel_com_copia(PATH_EAR)
        except Exception as e:
            print(f"Aviso: erro ao ler EAR com cópia ({str(e)}). Tentando leitura direta...")
            conteudo = github_read_file(PATH_EAR)
            df = pd.read_excel(io.BytesIO(conteudo))
        
        if len(df) > 0:
            df['ear_data'] = pd.to_datetime(df['ear_data'])
            df_sorted = df.sort_values(by='ear_data').copy()
            
            cache_ear_data = {}
            for sub in ['N', 'NE', 'S', 'SE']:
                df_sub = df_sorted[df_sorted['id_subsistema'] == sub]
                cache_ear_data[sub] = {
                    'labels': df_sub['ear_data'].dt.strftime('%Y-%m-%d').tolist(),
                    'ear_verif_percentual': df_sub['ear_verif_subsistema_percentual'].round(2).tolist(),
                    'ear_verif_mwmes': df_sub['ear_verif_subsistema_mwmes'].round(2).tolist(),
                    'nom_subsistema': df_sub['nom_subsistema'].iloc[0] if len(df_sub) > 0 else sub
                }
                
            github_write_file(CACHE_EAR, json.dumps(cache_ear_data, ensure_ascii=False, indent=2).encode('utf-8'))
            
            # Cache Recente (100 linhas)
            df_recent = df.sort_values(by='ear_data', ascending=False).head(100).copy()
            df_recent['ear_data'] = df_recent['ear_data'].dt.strftime('%d/%m/%Y')
            df_recent = df_recent.fillna("")
            data_recent = df_recent.to_dict(orient='records')
            github_write_file(CACHE_EAR_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
            
            max_date = df['ear_data'].max().strftime('%d/%m/%Y')
            info_ear = github_get_file_info(PATH_EAR)
            metadata['ear'] = {
                'linhas': len(df),
                'max_data': max_date,
                'tamanho': info_ear['tamanho'],
                'modificado': info_ear['modificado']
            }
            print("Cache do Reservatório (EAR) salvo.")
    else:
        print("Planilha do Reservatório (EAR) nao encontrada.")
        metadata['ear'] = {'status': 'Não Encontrado'}
        
    github_write_file(PATH_METADADOS, json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8'))
    print("Arquivo de metadados metadata.json gerado com sucesso!")

if __name__ == '__main__':
    gerar_todos_os_caches()
