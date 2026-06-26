import os
import tempfile
import json
import traceback
from flask import Flask, jsonify, request, render_template
import pandas as pd
import datetime

# Diretório base do projeto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Caminho para arquivo físico de rastreamento de erros entre múltiplos workers do Gunicorn
PATH_DEBUG_LOG = os.path.join(BASE_DIR, 'last_error.txt')

def salvar_erro_debug(tb):
    try:
        with open(PATH_DEBUG_LOG, 'w', encoding='utf-8') as fl:
            fl.write(tb)
    except:
        pass

def ler_erro_debug():
    if os.path.exists(PATH_DEBUG_LOG):
        try:
            with open(PATH_DEBUG_LOG, 'r', encoding='utf-8') as fl:
                return fl.read()
        except:
            pass
    return "Nenhum erro registrado desde a inicialização."

# Importa as rotinas de ETL criadas no etl.py
from src.etl import atualizar_balanco_energetico, atualizar_pld, extrair_ampere_pdf, atualizar_negocios_bbce, ler_excel_com_copia, atualizar_ena, atualizar_carga, atualizar_ear
from src.bbce_scraper import executar_automacao_bbce
from src.github_storage import github_read_file, github_write_file, github_file_exists, github_get_file_info, usar_github

app = Flask(__name__, static_folder='static', template_folder='templates')

# Caminhos dos arquivos de planilhas
PLANILHAS_DIR = os.path.join(BASE_DIR, 'planilhas_para_atualizar')

PATH_BALANCO = os.path.join(PLANILHAS_DIR, 'f_balanco_energetico.xlsx')
PATH_PLD = os.path.join(PLANILHAS_DIR, 'f_pld.xlsx')
PATH_AMPERE = os.path.join(PLANILHAS_DIR, 'f_rodadas_ampere.xlsx')
PATH_BBCE = os.path.join(PLANILHAS_DIR, 'f_todos_os_negocios_bbce.xlsx')
PATH_ENA = os.path.join(PLANILHAS_DIR, 'ENA_DIARIO_SUBSISTEMA_2026.xlsx')
PATH_MLT = os.path.join(PLANILHAS_DIR, 'mlt_2026.xlsx')
PATH_CARGA = os.path.join(PLANILHAS_DIR, 'CARGA_ENERGIA_2026.xlsx')
PATH_CARGA_PREVS = os.path.join(PLANILHAS_DIR, 'carga_ONS_RVs.xlsx')
PATH_EAR = os.path.join(PLANILHAS_DIR, 'EAR_DIARIO_SUBSISTEMA_2026.xlsx')
PATH_EAR_PREVS = os.path.join(PLANILHAS_DIR, 'ear_ONS_RVs.xlsx')

# Caminhos dos arquivos de cache JSON
CACHE_BALANCO = os.path.join(PLANILHAS_DIR, 'balanco_cache.json')
CACHE_PLD = os.path.join(PLANILHAS_DIR, 'pld_cache.json')
CACHE_AMPERE = os.path.join(PLANILHAS_DIR, 'ampere_cache.json')
CACHE_AMPERE_COMPLETO = os.path.join(PLANILHAS_DIR, 'ampere_completo_cache.json')

CACHE_BALANCO_RECENT = os.path.join(PLANILHAS_DIR, 'balanco_recent_cache.json')
CACHE_PLD_RECENT = os.path.join(PLANILHAS_DIR, 'pld_recent_cache.json')
CACHE_AMPERE_RECENT = os.path.join(PLANILHAS_DIR, 'ampere_recent_cache.json')
CACHE_PLD_HORARIO = os.path.join(PLANILHAS_DIR, 'pld_horario_cache.json')
CACHE_BBCE = os.path.join(PLANILHAS_DIR, 'bbce_diario_cache.json')
CACHE_BBCE_RECENT = os.path.join(PLANILHAS_DIR, 'bbce_recent_cache.json')
CACHE_ENA = os.path.join(PLANILHAS_DIR, 'ena_cache.json')
CACHE_ENA_RECENT = os.path.join(PLANILHAS_DIR, 'ena_recent_cache.json')
CACHE_CARGA = os.path.join(PLANILHAS_DIR, 'carga_cache.json')
CACHE_CARGA_RECENT = os.path.join(PLANILHAS_DIR, 'carga_recent_cache.json')
CACHE_EAR = os.path.join(PLANILHAS_DIR, 'ear_cache.json')
CACHE_EAR_RECENT = os.path.join(PLANILHAS_DIR, 'ear_recent_cache.json')

PATH_METADADOS = os.path.join(PLANILHAS_DIR, 'metadata.json')

# Garante que o diretorio de planilhas exista
os.makedirs(PLANILHAS_DIR, exist_ok=True)

# Se o diretório de planilhas estiver vazio ou faltarem arquivos essenciais, restaura o backup inicial
BACKUP_DIR = os.path.join(BASE_DIR, 'planilhas_originais_backup')
if os.path.exists(BACKUP_DIR):
    arquivos_essenciais = [
        'f_balanco_energetico.xlsx',
        'f_pld.xlsx',
        'f_rodadas_ampere.xlsx',
        'f_todos_os_negocios_bbce.xlsx',
        'ENA_DIARIO_SUBSISTEMA_2026.xlsx',
        'CARGA_ENERGIA_2026.xlsx',
        'EAR_DIARIO_SUBSISTEMA_2026.xlsx',
        'metadata.json'
    ]
    import shutil
    for arq in arquivos_essenciais:
        caminho_destino = os.path.join(PLANILHAS_DIR, arq)
        
        if usar_github():
            # No modo GitHub (produção), inicializa o repositório remoto caso o arquivo de dados não exista nele
            try:
                if not github_file_exists(caminho_destino):
                    caminho_origem = os.path.join(BACKUP_DIR, arq)
                    if os.path.exists(caminho_origem):
                        print(f"[Boot] Inicializando arquivo no GitHub a partir do backup: {arq}")
                        with open(caminho_origem, 'rb') as f:
                            github_write_file(caminho_destino, f.read(), message=f"Initial seed: {arq}")
            except Exception as e:
                print(f"[Boot] AVISO: Falha ao verificar/inicializar {arq} no GitHub: {str(e)}")
        else:
            # Modo local tradicional
            if not os.path.exists(caminho_destino):
                caminho_origem = os.path.join(BACKUP_DIR, arq)
                if os.path.exists(caminho_origem):
                    print(f"Restaurando arquivo padrão de backup: {arq} para {caminho_destino}")
                    shutil.copy2(caminho_origem, caminho_destino)

# ----------------- AUXILIARES DE ATUALIZAÇÃO DE CACHE E METADADOS -----------------

def format_date_str(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')

def atualizar_cache_e_metadata_balanco(df=None):
    """Lê a planilha de balanço, atualiza os caches JSON e reconstrói seu metadado."""
    print("Atualizando caches e metadados de Balanço Energético...")
    if df is None:
        df = ler_excel_com_copia(PATH_BALANCO, sheet_name="balanco_energetico")
    
    df = df.copy()
    df['din_instante'] = pd.to_datetime(df['din_instante'])
    
    # Cache do Gráfico (2026 horário agrupado por hora e subsistema)
    df_2026 = df[df['din_instante'] >= '2026-01-01'].copy()
    df_grouped = df_2026.groupby(['din_instante', 'id_subsistema']).mean(numeric_only=True).reset_index()
    df_grouped['din_instante'] = df_grouped['din_instante'].dt.strftime('%Y-%m-%d %H:%M')
    
    data_balanco = df_grouped.to_dict(orient='records')
    github_write_file(CACHE_BALANCO, json.dumps(data_balanco, ensure_ascii=False, indent=2).encode('utf-8'))
        
    # Cache Recente (100 linhas brutos)
    df_recent = df.sort_values(by=['din_instante', 'id_subsistema'], ascending=[False, True]).head(100).copy()
    df_recent['din_instante'] = df_recent['din_instante'].dt.strftime('%d/%m/%Y %H:%M')
    df_recent = df_recent.fillna("")
    data_recent = df_recent.to_dict(orient='records')
    github_write_file(CACHE_BALANCO_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
        
    # Metadados
    max_date = df['din_instante'].max().strftime('%d/%m/%Y %H:%M')
    
    if github_file_exists(PATH_METADADOS):
        conteudo_meta = github_read_file(PATH_METADADOS)
        meta = json.loads(conteudo_meta.decode('utf-8'))
    else:
        meta = {}
        
    info_balanco = github_get_file_info(PATH_BALANCO)
    meta['balanco'] = {
        'linhas': len(df),
        'max_data': max_date,
        'tamanho': info_balanco['tamanho'],
        'modificado': info_balanco['modificado']
    }
    
    github_write_file(PATH_METADADOS, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
    print("Caches e metadados de Balanço atualizados.")
    import gc
    gc.collect()


def atualizar_cache_e_metadata_pld(df=None):
    """Lê a planilha de PLD, atualiza os caches JSON e reconstrói seu metadado."""
    print("Atualizando caches e metadados de PLD...")
    if df is None:
        df = ler_excel_com_copia(PATH_PLD, sheet_name="pld")
    
    df = df.copy()
    
    # Cache do Gráfico
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
        
    # Cache Recente (100 linhas brutos)
    df_recent = df.sort_values(by=['MES_REFERENCIA', 'DIA', 'HORA', 'SUBMERCADO'], ascending=[False, False, False, True]).head(100).copy()
    df_recent = df_recent.fillna("")
    data_recent = df_recent.to_dict(orient='records')
    github_write_file(CACHE_PLD_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
        
    # Cache Horário de PLD por Data e Submercado - OTIMIZADO com itertuples (100x mais rápido)
    # Estrutura: { "YYYY-MM-DD": { "SUDESTE": [v0, v1, ..., v23], ... } }
    pld_horario_cache = {}
    df_subset = df[['MES_REFERENCIA', 'DIA', 'HORA', 'SUBMERCADO', 'PLD_HORA']]
    for row in df_subset.itertuples(index=False):
        try:
            mes = int(row[0])
            ano = mes // 100
            mes_num = mes % 100
            dia = int(row[1])
            data_str = f"{ano}-{mes_num:02d}-{dia:02d}"
            
            sub = str(row[3]).upper()
            hora = int(row[2])
            valor = float(row[4])
            
            if data_str not in pld_horario_cache:
                pld_horario_cache[data_str] = {}
            if sub not in pld_horario_cache[data_str]:
                pld_horario_cache[data_str][sub] = [None] * 24
                
            if 0 <= hora <= 23:
                pld_horario_cache[data_str][sub][hora] = valor
        except Exception as e:
            continue
            
    github_write_file(CACHE_PLD_HORARIO, json.dumps(pld_horario_cache, ensure_ascii=False, indent=2).encode('utf-8'))
        
    # Metadados
    max_ref = df['MES_REFERENCIA'].max()
    df_last_ref = df[df['MES_REFERENCIA'] == max_ref]
    max_dia = df_last_ref['DIA'].max()
    max_data = f"{str(max_ref)[4:]}/{str(max_ref)[:4]} (Dia {max_dia})"
    
    if github_file_exists(PATH_METADADOS):
        conteudo_meta = github_read_file(PATH_METADADOS)
        meta = json.loads(conteudo_meta.decode('utf-8'))
    else:
        meta = {}
        
    info_pld = github_get_file_info(PATH_PLD)
    meta['pld'] = {
        'linhas': len(df),
        'max_data': max_data,
        'tamanho': info_pld['tamanho'],
        'modificado': info_pld['modificado']
    }
    
    github_write_file(PATH_METADADOS, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
    print("Caches e metadados de PLD atualizados.")
    import gc
    gc.collect()


def atualizar_cache_e_metadata_ampere(df=None):
    """Lê a planilha da Ampere, atualiza os caches JSON e reconstrói seu metadado."""
    print("Atualizando caches e metadados da Ampere...")
    if df is None:
        df = ler_excel_com_copia(PATH_AMPERE, sheet_name="f_dados")
        
    df = df.copy()
    
    if len(df) > 0:
        max_rodada = df['rodada'].max()
        df_last = df[df['rodada'] == max_rodada].copy()
        df_last['data_referencia'] = pd.to_datetime(df_last['data_referencia']).dt.strftime('%Y-%m-%d')
        
        # Cache do Gráfico (Última Rodada)
        df_ena = df_last[df_last['indicador'] == 'ENA']
        ena_data = []
        for _, r in df_ena.iterrows():
            ena_data.append({
                'data': r['data_referencia'],
                'subsistema': r['subsistema'],
                'unidade': r['unidade'],
                'valor': r['valor']
            })
            
        df_arm = df_last[df_last['indicador'] == 'Armazenamento']
        arm_data = []
        for _, r in df_arm.iterrows():
            arm_data.append({
                'data': r['data_referencia'],
                'subsistema': r['subsistema'],
                'valor': r['valor']
            })
            
        df_pld = df_last[df_last['indicador'] == 'PLD']
        pld_data = []
        for _, r in df_pld.iterrows():
            pld_data.append({
                'data': r['data_referencia'],
                'subsistema': r['subsistema'],
                'valor': r['valor']
            })
            
        cache_data = {
            'rodada': int(max_rodada),
            'data_publicacao': pd.to_datetime(df_last['data_publicacao'].iloc[0]).strftime('%d/%m/%Y'),
            'ena': ena_data,
            'armazenamento': arm_data,
            'pld': pld_data
        }
        
        github_write_file(CACHE_AMPERE, json.dumps(cache_data, ensure_ascii=False, indent=2).encode('utf-8'))
            
        # Cache Completo (Todas as rodadas)
        df_sorted = df.sort_values(by=['rodada', 'data_referencia']).copy()
        df_sorted['data_referencia'] = pd.to_datetime(df_sorted['data_referencia']).dt.strftime('%Y-%m-%d')
        df_sorted['data_publicacao'] = pd.to_datetime(df_sorted['data_publicacao']).dt.strftime('%Y-%m-%d')
        df_sorted = df_sorted.fillna("")
        data_completa = df_sorted.to_dict(orient='records')
        github_write_file(CACHE_AMPERE_COMPLETO, json.dumps(data_completa, ensure_ascii=False, indent=2).encode('utf-8'))
            
        # Cache Recente (100 linhas brutos)
        df_recent = df.sort_values(by=['rodada', 'data_referencia', 'indicador'], ascending=[False, False, True]).head(100).copy()
        df_recent['data_referencia'] = pd.to_datetime(df_recent['data_referencia']).dt.strftime('%d/%m/%Y')
        df_recent['data_publicacao'] = pd.to_datetime(df_recent['data_publicacao']).dt.strftime('%d/%m/%Y')
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        github_write_file(CACHE_AMPERE_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
            
        # Metadados
        max_pub = pd.to_datetime(df_last['data_publicacao'].iloc[0]).strftime('%d/%m/%Y')
        max_data = f"Rodada {max_rodada} (Publicado em {max_pub})"
        
        if github_file_exists(PATH_METADADOS):
            conteudo_meta = github_read_file(PATH_METADADOS)
            meta = json.loads(conteudo_meta.decode('utf-8'))
        else:
            meta = {}
            
        info_ampere = github_get_file_info(PATH_AMPERE)
        meta['ampere'] = {
            'linhas': len(df),
            'max_data': max_data,
            'tamanho': info_ampere['tamanho'],
            'modificado': info_ampere['modificado']
        }
        
        github_write_file(PATH_METADADOS, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
        print("Caches e metadados da Ampere atualizados.")
        import gc
        gc.collect()


def atualizar_cache_e_metadata_bbce(df=None):
    """Lê a planilha da BBCE, atualiza os caches JSON agregados e reconstrói seu metadado."""
    print("Atualizando caches e metadados da BBCE...")
    
    if df is None:
        if not github_file_exists(PATH_BBCE):
            print("Planilha BBCE não encontrada. Ignorando atualização de cache.")
            return
        df = ler_excel_com_copia(PATH_BBCE)
        
    df = df.copy()
    
    if len(df) > 0:
        # Garante nomenclatura das colunas correspondentes primeiro para evitar colisão de renomeação
        mapa_colunas = {}
        for c in df.columns:
            c_upper = str(c).upper().strip()
            if 'PRODUTO' in c_upper: mapa_colunas[c] = 'PRODUTO'
            elif c_upper in ['Q.N', 'Q.N.', 'QUANTIDADE NEGOCIAÇÃO']: mapa_colunas[c] = 'Q.N'
            elif 'PRE' in c_upper and ('O' in c_upper or 'Ç' in c_upper): mapa_colunas[c] = 'PREÇO'
            elif 'TIPO' in c_upper and 'CONTRATO' in c_upper: mapa_colunas[c] = 'TIPO DE CONTRATO'
            
        df = df.rename(columns=mapa_colunas)
        
        df['DATA/HORA'] = pd.to_datetime(df['DATA/HORA'])
        
        # Cria colunas auxiliares
        df['DATA_DIA'] = df['DATA/HORA'].dt.strftime('%Y-%m-%d')
        
        # Mapeamento do Submercado
        def extrair_submercado(prod):
            prod = str(prod).upper()
            if ' - SE ' in prod or ' SE ' in prod or prod.startswith('SE '):
                return 'Sudeste/Centro-Oeste'
            elif ' - S ' in prod or ' S ' in prod or prod.startswith('S '):
                return 'Sul'
            elif ' - NE ' in prod or ' NE ' in prod or prod.startswith('NE '):
                return 'Nordeste'
            elif ' - N ' in prod or ' N ' in prod or prod.startswith('N '):
                return 'Norte'
            return 'Outros'
            
        # Mapeamento do Tipo de Produto
        def extrair_tipo_produto(prod):
            prod = str(prod).upper()
            if ' MEN ' in prod: return 'Mensal'
            if ' TRI ' in prod: return 'Trimestral'
            if ' SEM ' in prod: return 'Semestral'
            if ' ANU ' in prod: return 'Anual'
            return 'Outros'
            
        df['SUBMERCADO'] = df['PRODUTO'].apply(extrair_submercado)
        df['TIPO_PRODUTO'] = df['PRODUTO'].apply(extrair_tipo_produto)
        
        # Garante tipos corretos
        df['Q.N'] = df['Q.N'].astype(float)
        df['PREÇO'] = df['PREÇO'].astype(float)
        
        # Coluna auxiliar para média ponderada
        df['PRECO_VOL'] = df['PREÇO'] * df['Q.N']
        
        # Filtra apenas registros ativos (se a coluna STATUS existir)
        df_ativos = df[df['STATUS'].str.upper() == 'ATIVO'].copy() if 'STATUS' in df.columns else df.copy()
        
        # Agrupa os dados por produto e contrato
        gp = df_ativos.groupby(['DATA_DIA', 'PRODUTO', 'SUBMERCADO', 'TIPO DE CONTRATO', 'TIPO_PRODUTO']).agg(
            soma_preco_vol=('PRECO_VOL', 'sum'),
            soma_qn=('Q.N', 'sum'),
            total_contratos=('PRODUTO', 'count')
        ).reset_index()
        
        # Média ponderada por volume (Q.N)
        gp['PRECO_MEDIO'] = gp.apply(lambda r: r['soma_preco_vol'] / r['soma_qn'] if r['soma_qn'] > 0 else 0.0, axis=1)
        gp['PRECO_MEDIO'] = gp['PRECO_MEDIO'].round(2)
        gp['VOLUME_TOTAL'] = gp['soma_qn'].round(2)
        
        # Descarta colunas temporárias
        gp = gp.drop(columns=['soma_preco_vol', 'soma_qn'])
        
        # Salva o cache diário agregador
        data_bbce = gp.to_dict(orient='records')
        github_write_file(CACHE_BBCE, json.dumps(data_bbce, ensure_ascii=False, indent=2).encode('utf-8'))
            
        # Cache Recente (100 linhas brutas para a tabela de auditoria)
        df_recent = df.sort_values(by='DATA/HORA', ascending=False).head(100).copy()
        df_recent['DATA/HORA'] = df_recent['DATA/HORA'].dt.strftime('%d/%m/%Y %H:%M:%S')
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        github_write_file(CACHE_BBCE_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
            
        # Metadados
        max_date = df['DATA/HORA'].max().strftime('%d/%m/%Y %H:%M:%S')
        
        if github_file_exists(PATH_METADADOS):
            conteudo_meta = github_read_file(PATH_METADADOS)
            meta = json.loads(conteudo_meta.decode('utf-8'))
        else:
            meta = {}
            
        info_bbce = github_get_file_info(PATH_BBCE)
        meta['bbce'] = {
            'linhas': len(df),
            'max_data': max_date,
            'tamanho': info_bbce['tamanho'],
            'modificado': info_bbce['modificado']
        }
        
        github_write_file(PATH_METADADOS, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
        print("Caches e metadados da BBCE atualizados.")
        import gc
        gc.collect()


def atualizar_cache_e_metadata_ena(df=None):
    """Lê a planilha de ENA, atualiza os caches JSON e reconstrói seu metadado."""
    print("Atualizando caches e metadados de ENA...")
    if df is None:
        if not github_file_exists(PATH_ENA):
            print("Planilha de ENA não encontrada. Ignorando atualização de cache.")
            return
        df = ler_excel_com_copia(PATH_ENA)
    
    df = df.copy()
    
    if len(df) > 0:
        # Converter coluna de data para datetime
        df['ena_data'] = pd.to_datetime(df['ena_data'])
        df_sorted = df.sort_values(by='ena_data').copy()
        
        # Gera o cache estruturado para os 4 gráficos (Norte, Nordeste, Sul, Sudeste/Centro-Oeste)
        cache_data = {}
        for sub in ['N', 'NE', 'S', 'SE']:
            df_sub = df_sorted[df_sorted['id_subsistema'] == sub]
            cache_data[sub] = {
                'labels': df_sub['ena_data'].dt.strftime('%Y-%m-%d').tolist(),
                'ena_bruta_mwmed': df_sub['ena_bruta_regiao_mwmed'].round(2).tolist(),
                'ena_bruta_percentualmlt': df_sub['ena_bruta_regiao_percentualmlt'].round(2).tolist(),
                'ena_armazenavel_mwmed': df_sub['ena_armazenavel_regiao_mwmed'].round(2).tolist(),
                'ena_armazenavel_percentualmlt': df_sub['ena_armazenavel_regiao_percentualmlt'].round(2).tolist(),
                'nom_subsistema': df_sub['nom_subsistema'].iloc[0] if len(df_sub) > 0 else sub
            }
            
        github_write_file(CACHE_ENA, json.dumps(cache_data, ensure_ascii=False, indent=2).encode('utf-8'))
        
        # Cache Recente (100 linhas brutas para a tabela de Auditoria)
        df_recent = df.sort_values(by='ena_data', ascending=False).head(100).copy()
        df_recent['ena_data'] = df_recent['ena_data'].dt.strftime('%d/%m/%Y')
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        github_write_file(CACHE_ENA_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
        
        # Metadados
        max_date = df['ena_data'].max().strftime('%d/%m/%Y')
        
        if github_file_exists(PATH_METADADOS):
            conteudo_meta = github_read_file(PATH_METADADOS)
            meta = json.loads(conteudo_meta.decode('utf-8'))
        else:
            meta = {}
            
        info_ena = github_get_file_info(PATH_ENA)
        meta['ena'] = {
            'linhas': len(df),
            'max_data': max_date,
            'tamanho': info_ena['tamanho'],
            'modificado': info_ena['modificado']
        }
        
        github_write_file(PATH_METADADOS, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
        print("Caches e metadados de ENA atualizados.")
        
        import gc
        gc.collect()


def atualizar_cache_e_metadata_carga(df=None):
    """Lê a planilha de Carga, atualiza os caches JSON e reconstrói seu metadado."""
    print("Atualizando caches e metadados de Carga...")
    if df is None:
        if not github_file_exists(PATH_CARGA):
            print("Planilha de Carga não encontrada. Ignorando atualização de cache.")
            return
        df = ler_excel_com_copia(PATH_CARGA)
    
    df = df.copy()
    
    if len(df) > 0:
        # Converter coluna de data para datetime
        df['din_instante'] = pd.to_datetime(df['din_instante'])
        df_sorted = df.sort_values(by='din_instante').copy()
        
        # Gera o cache estruturado para os 4 gráficos (Norte, Nordeste, Sul, Sudeste/Centro-Oeste)
        cache_data = {}
        for sub in ['N', 'NE', 'S', 'SE']:
            df_sub = df_sorted[df_sorted['id_subsistema'] == sub]
            cache_data[sub] = {
                'labels': df_sub['din_instante'].dt.strftime('%Y-%m-%d').tolist(),
                'carga_mwmed': df_sub['val_cargaenergiamwmed'].round(2).tolist(),
                'nom_subsistema': df_sub['nom_subsistema'].iloc[0] if len(df_sub) > 0 else sub
            }
            
        github_write_file(CACHE_CARGA, json.dumps(cache_data, ensure_ascii=False, indent=2).encode('utf-8'))
        
        # Cache Recente (100 linhas brutas para a tabela de Auditoria)
        df_recent = df.sort_values(by='din_instante', ascending=False).head(100).copy()
        df_recent['din_instante'] = df_recent['din_instante'].dt.strftime('%d/%m/%Y')
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        github_write_file(CACHE_CARGA_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
        
        # Metadados
        max_date = df['din_instante'].max().strftime('%d/%m/%Y')
        
        if github_file_exists(PATH_METADADOS):
            conteudo_meta = github_read_file(PATH_METADADOS)
            meta = json.loads(conteudo_meta.decode('utf-8'))
        else:
            meta = {}
            
        info_carga = github_get_file_info(PATH_CARGA)
        meta['carga'] = {
            'linhas': len(df),
            'max_data': max_date,
            'tamanho': info_carga['tamanho'],
            'modificado': info_carga['modificado']
        }
        
        github_write_file(PATH_METADADOS, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
        print("Caches e metadados de Carga atualizados.")
        
        import gc
        gc.collect()


def atualizar_cache_e_metadata_ear(df=None):
    """Lê a planilha de EAR, atualiza os caches JSON e reconstrói seu metadado."""
    print("Atualizando caches e metadados de EAR...")
    if df is None:
        if not github_file_exists(PATH_EAR):
            print("Planilha de EAR não encontrada. Ignorando atualização de cache.")
            return
        df = ler_excel_com_copia(PATH_EAR)
    
    df = df.copy()
    
    if len(df) > 0:
        # Converter coluna de data para datetime
        df['ear_data'] = pd.to_datetime(df['ear_data'])
        df_sorted = df.sort_values(by='ear_data').copy()
        
        # Gera o cache estruturado para os 4 gráficos (Norte, Nordeste, Sul, Sudeste/Centro-Oeste)
        cache_data = {}
        for sub in ['N', 'NE', 'S', 'SE']:
            df_sub = df_sorted[df_sorted['id_subsistema'] == sub]
            cache_data[sub] = {
                'labels': df_sub['ear_data'].dt.strftime('%Y-%m-%d').tolist(),
                'ear_verif_percentual': df_sub['ear_verif_subsistema_percentual'].round(2).tolist(),
                'ear_verif_mwmes': df_sub['ear_verif_subsistema_mwmes'].round(2).tolist(),
                'nom_subsistema': df_sub['nom_subsistema'].iloc[0] if len(df_sub) > 0 else sub
            }
            
        github_write_file(CACHE_EAR, json.dumps(cache_data, ensure_ascii=False, indent=2).encode('utf-8'))
        
        # Cache Recente (100 linhas brutas para a tabela de Auditoria)
        df_recent = df.sort_values(by='ear_data', ascending=False).head(100).copy()
        df_recent['ear_data'] = df_recent['ear_data'].dt.strftime('%d/%m/%Y')
        df_recent = df_recent.fillna("")
        data_recent = df_recent.to_dict(orient='records')
        github_write_file(CACHE_EAR_RECENT, json.dumps(data_recent, ensure_ascii=False, indent=2).encode('utf-8'))
        
        # Metadados
        max_date = df['ear_data'].max().strftime('%d/%m/%Y')
        
        if github_file_exists(PATH_METADADOS):
            conteudo_meta = github_read_file(PATH_METADADOS)
            meta = json.loads(conteudo_meta.decode('utf-8'))
        else:
            meta = {}
            
        info_ear = github_get_file_info(PATH_EAR)
        meta['ear'] = {
            'linhas': len(df),
            'max_data': max_date,
            'tamanho': info_ear['tamanho'],
            'modificado': info_ear['modificado']
        }
        
        github_write_file(PATH_METADADOS, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
        print("Caches e metadados de EAR atualizados.")
        
        import gc
        gc.collect()


# ----------------- ROTAS FRONTEND -----------------

@app.route('/')
def index():
    return render_template('index.html', is_cloud=usar_github())

# ----------------- ROTA STATUS (METADADOS LEVES EM 1ms) -----------------

@app.route('/api/status', methods=['GET'])
def get_status():
    if not github_file_exists(PATH_METADADOS):
        from src.gerar_cache import gerar_todos_os_caches
        gerar_todos_os_caches()
        
    conteudo_json = github_read_file(PATH_METADADOS)
    status = json.loads(conteudo_json.decode('utf-8'))
    return jsonify(status)

# ----------------- ROTAS API ATUALIZAÇÃO -----------------

@app.route('/api/update/balanco', methods=['POST'])
def update_balanco():
    if usar_github():
        return jsonify({'success': False, 'message': 'Atualizações automáticas suspensas na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    try:
        novas_linhas, total_linhas, df_final = atualizar_balanco_energetico(PATH_BALANCO)
        atualizar_cache_e_metadata_balanco(df_final)
        return jsonify({
            'success': True,
            'message': f'Balanço Energético atualizado com sucesso!',
            'novos_registros': novas_linhas,
            'total_registros': total_linhas
        })
    except Exception as e:
        tb = traceback.format_exc()
        salvar_erro_debug(tb)
        print(f"[DEBUG ERROR] Ocorreu uma exceção no balanço:\n{tb}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update/ena', methods=['POST'])
def update_ena_ons():
    if usar_github():
        return jsonify({'success': False, 'message': 'Atualizações automáticas suspensas na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    try:
        total_linhas, df_final = atualizar_ena(PATH_ENA)
        atualizar_cache_e_metadata_ena(df_final)
        return jsonify({
            'success': True,
            'message': f'ENA Diária atualizada com sucesso!',
            'novos_registros': total_linhas,
            'total_registros': total_linhas
        })
    except Exception as e:
        tb = traceback.format_exc()
        salvar_erro_debug(tb)
        print(f"[DEBUG ERROR] Ocorreu uma exceção na ENA:\n{tb}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update/carga', methods=['POST'])
def update_carga_ons():
    if usar_github():
        return jsonify({'success': False, 'message': 'Atualizações automáticas suspensas na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    try:
        total_linhas, df_final = atualizar_carga(PATH_CARGA)
        atualizar_cache_e_metadata_carga(df_final)
        return jsonify({
            'success': True,
            'message': f'Carga Diária atualizada com sucesso!',
            'novos_registros': total_linhas,
            'total_registros': total_linhas
        })
    except Exception as e:
        tb = traceback.format_exc()
        salvar_erro_debug(tb)
        print(f"[DEBUG ERROR] Ocorreu uma exceção na Carga:\n{tb}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update/ear', methods=['POST'])
def update_ear_ons():
    if usar_github():
        return jsonify({'success': False, 'message': 'Atualizações automáticas suspensas na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    try:
        total_linhas, df_final = atualizar_ear(PATH_EAR)
        atualizar_cache_e_metadata_ear(df_final)
        return jsonify({
            'success': True,
            'message': f'EAR Diária atualizada com sucesso!',
            'novos_registros': total_linhas,
            'total_registros': total_linhas
        })
    except Exception as e:
        tb = traceback.format_exc()
        salvar_erro_debug(tb)
        print(f"[DEBUG ERROR] Ocorreu uma exceção na EAR:\n{tb}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update/pld', methods=['POST'])
def update_pld_ccee():
    if usar_github():
        return jsonify({'success': False, 'message': 'Atualizações automáticas suspensas na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    try:
        novas_linhas, total_linhas, df_final = atualizar_pld(PATH_PLD)
        atualizar_cache_e_metadata_pld(df_final)
        return jsonify({
            'success': True,
            'message': f'PLD Horário atualizado com sucesso!',
            'novos_registros': novas_linhas,
            'total_registros': total_linhas
        })
    except Exception as e:
        tb = traceback.format_exc()
        salvar_erro_debug(tb)
        print(f"[DEBUG ERROR] Ocorreu uma exceção no PLD:\n{tb}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update/ampere', methods=['POST'])
def update_ampere_pdf():
    if usar_github():
        return jsonify({'success': False, 'message': 'Upload e processamento de PDFs suspensos na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nome do arquivo está vazio.'}), 400
        
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'message': 'O arquivo deve ser um PDF.'}), 400
        
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        novas_linhas, total_linhas, df_final = extrair_ampere_pdf(temp_path, PATH_AMPERE)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        atualizar_cache_e_metadata_ampere(df_final)
            
        return jsonify({
            'success': True,
            'message': f'Dados do relatório Ampere extraídos e importados com sucesso!',
            'novos_registros': novas_linhas,
            'total_registros': total_linhas
        })
    except Exception as e:
        tb = traceback.format_exc()
        salvar_erro_debug(tb)
        print(f"[DEBUG ERROR] Ocorreu uma exceção na Ampere:\n{tb}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ----------------- ROTAS API BBCE -----------------
import threading

# Caminho do log temporário da automação BBCE
BBCE_LOG_FILE = os.path.join(PLANILHAS_DIR, 'bbce_automation.log')

@app.route('/api/bbce/ultimo_registro', methods=['GET'])
def get_bbce_ultimo_registro():
    try:
        if not github_file_exists(PATH_BBCE):
            return jsonify({'max_data': 'Nenhum registro encontrado.'})
        df = ler_excel_com_copia(PATH_BBCE)
        if len(df) > 0:
            df['DATA/HORA'] = pd.to_datetime(df['DATA/HORA'])
            max_date = df['DATA/HORA'].max().strftime('%d/%m/%Y %H:%M:%S')
            return jsonify({'max_data': max_date})
        return jsonify({'max_data': 'Base vazia.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/bbce', methods=['GET'])
def get_data_bbce():
    try:
        if not github_file_exists(CACHE_BBCE):
            atualizar_cache_e_metadata_bbce()
        conteudo_json = github_read_file(CACHE_BBCE)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/update/bbce_upload', methods=['POST'])
def update_bbce_upload():
    if usar_github():
        return jsonify({'success': False, 'message': 'Upload de negócios suspenso na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nome do arquivo está vazio.'}), 400
        
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        novas_linhas, total_linhas, df_final = atualizar_negocios_bbce(PATH_BBCE, planilha_novos_negocios_path=temp_path)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        atualizar_cache_e_metadata_bbce(df_final)
            
        return jsonify({
            'success': True,
            'message': f'Dados da BBCE importados com sucesso!',
            'novos_registros': novas_linhas,
            'total_registros': total_linhas
        })
    except Exception as e:
        tb = traceback.format_exc()
        salvar_erro_debug(tb)
        print(f"[DEBUG ERROR] Ocorreu uma exceção no upload BBCE:\n{tb}")
        return jsonify({'success': False, 'message': str(e)}), 500


def rodar_selenium_bbce_thread(data_inicio, data_fim):
    def escrever_log(msg):
        with open(BBCE_LOG_FILE, 'a', encoding='utf-8') as fl:
            fl.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            
    # Limpa log anterior
    with open(BBCE_LOG_FILE, 'w', encoding='utf-8') as fl:
        fl.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Iniciando automação assistida da BBCE...\n")
        
    try:
        # Roda o scraper
        arquivo_baixado = executar_automacao_bbce(data_inicio, data_fim, logger_func=escrever_log)
        
        # Faz a importação do arquivo baixado
        escrever_log("Processando arquivo baixado e atualizando planilha base...")
        novas, total, df_final = atualizar_negocios_bbce(PATH_BBCE, planilha_novos_negocios_path=arquivo_baixado)
        
        # Remove arquivo temporário baixado
        if os.path.exists(arquivo_baixado):
            os.remove(arquivo_baixado)
            
        # Atualiza caches
        escrever_log("Reconstruindo cache e metadados diários...")
        atualizar_cache_e_metadata_bbce(df_final)
        
        escrever_log(f"[SUCCESS] Importação concluída! Novos negócios: {novas}, Total na base: {total}")
        
    except Exception as e:
        escrever_log(f"[ERROR] Ocorreu uma falha na automação: {str(e)}")


@app.route('/api/update/bbce_auto', methods=['POST'])
def update_bbce_auto():
    if usar_github():
        return jsonify({'success': False, 'message': 'Automação BBCE suspensa na nuvem. Execute a atualização local para sincronizar os dados.'}), 403
    dados = request.get_json() or {}
    data_inicio = dados.get('data_inicio')
    data_fim = dados.get('data_fim')
    
    if not data_inicio or not data_fim:
        return jsonify({'success': False, 'message': 'Datas de início e fim são obrigatórias.'}), 400
        
    # Dispara a thread em background
    threading.Thread(
        target=rodar_selenium_bbce_thread,
        args=(data_inicio, data_fim),
        daemon=True
    ).start()
    
    return jsonify({
        'success': True,
        'message': 'Automação da BBCE iniciada em segundo plano.'
    })


@app.route('/api/update/bbce_auto/logs', methods=['GET'])
def get_bbce_auto_logs():
    if not os.path.exists(BBCE_LOG_FILE):
        return jsonify({'logs': []})
        
    with open(BBCE_LOG_FILE, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
        
    linhas_limpas = [l.strip() for l in linhas]
    return jsonify({'logs': linhas_limpas})


# ----------------- ROTAS API DADOS DASHBOARD (INSTANTÂNEO) -----------------

@app.route('/api/data/balanco', methods=['GET'])
def get_data_balanco():
    try:
        if not github_file_exists(CACHE_BALANCO):
            atualizar_cache_e_metadata_balanco()
        conteudo_json = github_read_file(CACHE_BALANCO)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/ena', methods=['GET'])
def get_data_ena():
    try:
        if not github_file_exists(CACHE_ENA):
            atualizar_cache_e_metadata_ena()
        conteudo_json = github_read_file(CACHE_ENA)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def obter_nome_mes(mes_num):
    nomes = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return nomes.get(mes_num, 'Mês Desconhecido')


def calcular_semanas_operacionais(ano, mes):
    # Dia 1 do mês indicado
    dia_1 = datetime.date(ano, mes, 1)
    wd = dia_1.weekday() # 0=Segunda, ..., 5=Sábado, 6=Domingo
    
    # Sábado anterior ou igual ao dia 1
    if wd >= 5:
        offset = 5 - wd
    else:
        offset = - (wd + 2)
        
    inicio_sem1 = dia_1 + datetime.timedelta(days=offset)
    
    semanas = []
    for i in range(5):
        inicio_sem = inicio_sem1 + datetime.timedelta(days=i*7)
        fim_sem = inicio_sem + datetime.timedelta(days=6)
        semanas.append((inicio_sem, fim_sem))
        
    return semanas


def calcular_dias_intersecao_mes(ini_sem, fim_sem, ano, mes):
    import calendar
    inicio_mes = datetime.date(ano, mes, 1)
    _, ultimo_dia = calendar.monthrange(ano, mes)
    fim_mes = datetime.date(ano, mes, ultimo_dia)
    
    start_inter = max(ini_sem, inicio_mes)
    end_inter = min(fim_sem, fim_mes)
    
    if start_inter <= end_inter:
        return (end_inter - start_inter).days + 1
    return 0


@app.route('/api/data/ena_comparativo/meses', methods=['GET'])
def get_meses_comparativo():
    try:
        if not os.path.exists(PLANILHAS_DIR):
            return jsonify([])
        arquivos = os.listdir(PLANILHAS_DIR)
        meses = []
        for arq in arquivos:
            if arq.startswith('prevs_') and arq.endswith('.xlsx'):
                partes = arq.replace('prevs_', '').replace('.xlsx', '')
                if len(partes) == 6:
                    mes_str = partes[:2]
                    ano_str = partes[2:]
                    meses.append({
                        'id': partes,
                        'label': f"{obter_nome_mes(int(mes_str))} de {ano_str}"
                    })
        # Ordena de forma cronológica decrescente
        def sort_key(m):
            return int(m['id'][2:]) * 100 + int(m['id'][:2])
        meses = sorted(meses, key=sort_key, reverse=True)
        return jsonify(meses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/ena_comparativo', methods=['GET'])
def get_ena_comparativo():
    try:
        mes_ref = request.args.get('mes') # Ex: '062026'
        
        if not mes_ref:
            # Pega o primeiro disponível de forma inteligente
            if not os.path.exists(PLANILHAS_DIR):
                return jsonify({'error': 'Nenhum arquivo de previsões encontrado.'}), 404
            arquivos = [a for a in os.listdir(PLANILHAS_DIR) if a.startswith('prevs_') and a.endswith('.xlsx')]
            if not arquivos:
                return jsonify({'error': 'Nenhum arquivo de previsões encontrado.'}), 404
            # Ordena e pega o mais recente
            def sort_key(arq):
                partes = arq.replace('prevs_', '').replace('.xlsx', '')
                return int(partes[2:]) * 100 + int(partes[:2])
            arquivos_sorted = sorted(arquivos, key=sort_key, reverse=True)
            mes_ref = arquivos_sorted[0].replace('prevs_', '').replace('.xlsx', '')
            
        caminho_prevs = os.path.join(PLANILHAS_DIR, f"prevs_{mes_ref}.xlsx")
        
        if not github_file_exists(caminho_prevs):
            return jsonify({'error': f"Arquivo de previsões para o mês {mes_ref} não encontrado."}), 404
            
        # Lê a planilha de previsões
        df_prevs = ler_excel_com_copia(caminho_prevs)
        
        # Extrai ano e mês do id '062026'
        mes_num = int(mes_ref[:2])
        ano_num = int(mes_ref[2:])
        
        # Calcula as 5 semanas operacionais e os pesos
        semanas = calcular_semanas_operacionais(ano_num, mes_num)
        pesos = []
        for ini, fim in semanas:
            dias_inter = calcular_dias_intersecao_mes(ini, fim, ano_num, mes_num)
            pesos.append(dias_inter)
        
        # Formata informações das semanas para o frontend
        semanas_info = []
        for i, (ini, fim) in enumerate(semanas):
            semanas_info.append({
                'semana': i + 1,
                'label': f"Semana {i + 1}",
                'periodo': f"{ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}",
                'inicio': ini.strftime('%Y-%m-%d'),
                'fim': fim.strftime('%Y-%m-%d'),
                'dias_no_mes': pesos[i]
            })
            
        # Lê a planilha de MLT para obter a MLT correspondente
        mlt_valores = {}
        if github_file_exists(PATH_MLT):
            df_mlt = ler_excel_com_copia(PATH_MLT)
            if len(df_mlt) > 0:
                df_mlt['MÊS_dt'] = pd.to_datetime(df_mlt.iloc[:, 0])
                linha = df_mlt[(df_mlt['MÊS_dt'].dt.year == ano_num) & (df_mlt['MÊS_dt'].dt.month == mes_num)]
                if len(linha) > 0:
                    mlt_valores = {
                        'SE': float(linha['SUDESTE'].iloc[0]),
                        'S': float(linha['SUL'].iloc[0]),
                        'NE': float(linha['NORDESTE'].iloc[0]),
                        'N': float(linha['NORTE'].iloc[0])
                    }

        # Carrega a base diária de ENA realizada para calcular as médias reais
        df_ena = pd.DataFrame()
        if github_file_exists(PATH_ENA):
            df_ena = ler_excel_com_copia(PATH_ENA)
            if len(df_ena) > 0:
                df_ena['ena_data'] = pd.to_datetime(df_ena['ena_data']).dt.date
                
        # Mapeamento do submercado
        sub_map = {
            'SUDESTE': 'SE',
            'SUL': 'S',
            'NORDESTE': 'NE',
            'NORTE': 'N'
        }
        
        dados = {}
        for sub_nome, sub_id in sub_map.items():
            # Filtra previsões daquele subsistema
            df_sub_prevs = df_prevs[df_prevs['SUBMERCADO'].str.upper() == sub_nome].copy()
            
            previsoes = {}
            for _, r in df_sub_prevs.iterrows():
                rv_nome = str(r['rvx']).strip()
                valores_prev = [
                    float(r['sem1']),
                    float(r['sem2']),
                    float(r['sem3']),
                    float(r['sem4']),
                    float(r['sem5'])
                ]
                
                # Calcula média mensal ponderada
                soma_ponderada = sum(v * p for v, p in zip(valores_prev, pesos))
                total_dias_pesos = sum(pesos)
                media_mensal_ponderada = round(soma_ponderada / total_dias_pesos, 2) if total_dias_pesos > 0 else 0
                
                previsoes[rv_nome] = {
                    'valores': valores_prev,
                    'media_mensal': media_mensal_ponderada
                }
                
            # Calcula realizados para esse subsistema nas 5 semanas
            realizado_bruta_valores = []
            realizado_armazenavel_valores = []
            
            df_sub_ena = pd.DataFrame()
            if len(df_ena) > 0:
                df_sub_ena = df_ena[df_ena['id_subsistema'] == sub_id].copy()
                
            for ini, fim in semanas:
                if len(df_sub_ena) > 0:
                    df_sem = df_sub_ena[(df_sub_ena['ena_data'] >= ini) & (df_sub_ena['ena_data'] <= fim)]
                    if len(df_sem) > 0:
                        realizado_bruta_valores.append(round(float(df_sem['ena_bruta_regiao_mwmed'].mean()), 2))
                        realizado_armazenavel_valores.append(round(float(df_sem['ena_armazenavel_regiao_mwmed'].mean()), 2))
                    else:
                        realizado_bruta_valores.append(None)
                        realizado_armazenavel_valores.append(None)
                else:
                    realizado_bruta_valores.append(None)
                    realizado_armazenavel_valores.append(None)
            
            # Calcula médias mensais ponderadas acumuladas para os realizados
            # Bruta
            soma_bruta = sum(v * p for v, p in zip(realizado_bruta_valores, pesos) if v is not None)
            peso_bruta = sum(p for v, p in zip(realizado_bruta_valores, pesos) if v is not None)
            media_bruta = round(soma_bruta / peso_bruta, 2) if peso_bruta > 0 else None
            
            # Armazenável
            soma_armazenavel = sum(v * p for v, p in zip(realizado_armazenavel_valores, pesos) if v is not None)
            peso_armazenavel = sum(p for v, p in zip(realizado_armazenavel_valores, pesos) if v is not None)
            media_armazenavel = round(soma_armazenavel / peso_armazenavel, 2) if peso_armazenavel > 0 else None
            
            dados[sub_id] = {
                'mlt': mlt_valores.get(sub_id, None),
                'previsoes': previsoes,
                'realizado_bruta': {
                    'valores': realizado_bruta_valores,
                    'media_mensal': media_bruta
                },
                'realizado_armazenavel': {
                    'valores': realizado_armazenavel_valores,
                    'media_mensal': media_armazenavel
                }
            }
            
        retorno = {
            'mes_referencia': mes_ref,
            'semanas_info': semanas_info,
            'dados': dados
        }
        
        return jsonify(retorno)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def converter_mes_carga(mes_str):
    # mes_str ex: 'JUN_2026' ou 'JUN/2026' ou 'JUN2026'
    mes_str = str(mes_str).upper().replace('/', '_').replace('-', '_')
    partes = mes_str.split('_')
    if len(partes) != 2:
        import re
        m = re.match(r'([A-Z]{3})(\d{4})', mes_str)
        if m:
            mes_nome, ano_str = m.groups()
        else:
            raise ValueError(f"Formato de mês inválido: {mes_str}")
    else:
        mes_nome, ano_str = partes[0], partes[1]
        
    meses_map = {
        'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 'MAI': '05', 'JUN': '06',
        'JUL': '07', 'AGO': '08', 'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12'
    }
    
    mes_num = meses_map.get(mes_nome)
    if not mes_num:
        raise ValueError(f"Mês não reconhecido: {mes_nome}")
        
    return f"{mes_num}{ano_str}"


def converter_id_para_mes_carga(mes_id):
    # mes_id ex: '062026'
    mes_num = mes_id[:2]
    ano_str = mes_id[2:]
    
    meses_rev_map = {
        '01': 'JAN', '02': 'FEV', '03': 'MAR', '04': 'ABR', '05': 'MAI', '06': 'JUN',
        '07': 'JUL', '08': 'AGO', '09': 'SET', '10': 'OUT', '11': 'NOV', '12': 'DEZ'
    }
    
    mes_nome = meses_rev_map.get(mes_num)
    if not mes_nome:
        raise ValueError(f"ID de mês inválido: {mes_id}")
        
    return f"{mes_nome}_{ano_str}"


@app.route('/api/data/carga_comparativo/meses', methods=['GET'])
def get_carga_meses_comparativo():
    try:
        if not github_file_exists(PATH_CARGA_PREVS):
            return jsonify([])
        
        df_prevs = ler_excel_com_copia(PATH_CARGA_PREVS)
        if len(df_prevs) == 0:
            return jsonify([])
            
        col_mes_nome = df_prevs.columns[9]
        meses_unicos = df_prevs[col_mes_nome].dropna().unique().tolist()
        
        meses = []
        for mes_str in meses_unicos:
            try:
                mes_id = converter_mes_carga(mes_str)
                mes_num = int(mes_id[:2])
                ano_str = mes_id[2:]
                meses.append({
                    'id': mes_id,
                    'label': f"{obter_nome_mes(mes_num)} de {ano_str}"
                })
            except Exception as ex:
                print(f"Erro ao converter mes '{mes_str}': {str(ex)}")
                
        # Ordena de forma cronológica decrescente
        def sort_key(m):
            return int(m['id'][2:]) * 100 + int(m['id'][:2])
        meses = sorted(meses, key=sort_key, reverse=True)
        return jsonify(meses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/carga_comparativo', methods=['GET'])
def get_carga_comparativo():
    try:
        mes_ref = request.args.get('mes') # Ex: '062026'
        
        if not mes_ref:
            if not github_file_exists(PATH_CARGA_PREVS):
                return jsonify({'error': 'Arquivo de previsões de carga não encontrado.'}), 404
            df_prevs = ler_excel_com_copia(PATH_CARGA_PREVS)
            if len(df_prevs) == 0:
                return jsonify({'error': 'Arquivo de previsões de carga vazio.'}), 404
            col_mes_nome = df_prevs.columns[9]
            meses_unicos = df_prevs[col_mes_nome].dropna().unique().tolist()
            if not meses_unicos:
                return jsonify({'error': 'Nenhum mês de previsões de carga encontrado.'}), 404
            
            def sort_key_str(m_str):
                try:
                    m_id = converter_mes_carga(m_str)
                    return int(m_id[2:]) * 100 + int(m_id[:2])
                except:
                    return 0
            meses_unicos_sorted = sorted(meses_unicos, key=sort_key_str, reverse=True)
            mes_ref = converter_mes_carga(meses_unicos_sorted[0])
            
        if not github_file_exists(PATH_CARGA_PREVS):
            return jsonify({'error': f"Arquivo de previsões de carga não encontrado."}), 404
            
        df_prevs = ler_excel_com_copia(PATH_CARGA_PREVS)
        
        # Extrai ano e mês do id '062026'
        mes_num = int(mes_ref[:2])
        ano_num = int(mes_ref[2:])
        
        # Converte o mes_ref de volta para o formato de string do excel (ex: 'JUN_2026')
        mes_excel_str = converter_id_para_mes_carga(mes_ref)
        
        # Filtra a planilha de previsões para o mês de referência
        col_mes_nome = df_prevs.columns[9]
        df_mes_prevs = df_prevs[df_prevs[col_mes_nome].str.upper() == mes_excel_str.upper()].copy()
        
        if len(df_mes_prevs) == 0:
            return jsonify({'error': f"Nenhuma previsão encontrada para o mês {mes_ref} ({mes_excel_str})."}), 404
            
        # Calcula as 5 semanas operacionais e os pesos
        semanas = calcular_semanas_operacionais(ano_num, mes_num)
        pesos = []
        for ini, fim in semanas:
            dias_inter = calcular_dias_intersecao_mes(ini, fim, ano_num, mes_num)
            pesos.append(dias_inter)
            
        # Formata informações das semanas para o frontend
        semanas_info = []
        for i, (ini, fim) in enumerate(semanas):
            semanas_info.append({
                'semana': i + 1,
                'label': f"Semana {i + 1}",
                'periodo': f"{ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}",
                'inicio': ini.strftime('%Y-%m-%d'),
                'fim': fim.strftime('%Y-%m-%d'),
                'dias_no_mes': pesos[i]
            })
            
        # Carrega a base diária de Carga realizada para calcular as médias reais
        df_carga = pd.DataFrame()
        if github_file_exists(PATH_CARGA):
            df_carga = ler_excel_com_copia(PATH_CARGA)
            if len(df_carga) > 0:
                df_carga['din_instante'] = pd.to_datetime(df_carga['din_instante']).dt.date
                
        # Mapeamento do submercado
        sub_map = {
            'SIN': 'SIN',
            'SUDESTE': 'SE',
            'SUL': 'S',
            'NORDESTE': 'NE',
            'NORTE': 'N'
        }
        
        dados = {}
        for sub_nome, sub_id in sub_map.items():
            df_sub_prevs = df_mes_prevs[df_mes_prevs['SUBMERCADO'].str.upper() == sub_nome].copy()
            
            previsoes = {}
            for _, r in df_sub_prevs.iterrows():
                rv_nome = str(r['rvx']).strip()
                valores_prev = [
                    float(r['sem1']) if pd.notna(r['sem1']) else 0.0,
                    float(r['sem2']) if pd.notna(r['sem2']) else 0.0,
                    float(r['sem3']) if pd.notna(r['sem3']) else 0.0,
                    float(r['sem4']) if pd.notna(r['sem4']) else 0.0,
                    float(r['sem5']) if pd.notna(r['sem5']) else 0.0
                ]
                
                # Calcula média mensal ponderada
                soma_ponderada = sum(v * p for v, p in zip(valores_prev, pesos))
                total_dias_pesos = sum(pesos)
                media_mensal_ponderada = round(soma_ponderada / total_dias_pesos, 2) if total_dias_pesos > 0 else 0
                
                previsoes[rv_nome] = {
                    'valores': [round(v) for v in valores_prev],
                    'media_mensal': round(media_mensal_ponderada)
                }
                
            # Calcula realizados para esse subsistema nas 5 semanas
            realizado_valores = []
            
            df_sub_carga = pd.DataFrame()
            if len(df_carga) > 0:
                if sub_id == 'SIN':
                    df_sub_carga = df_carga.groupby('din_instante')['val_cargaenergiamwmed'].sum().reset_index()
                else:
                    df_sub_carga = df_carga[df_carga['id_subsistema'] == sub_id].copy()
                
            for ini, fim in semanas:
                if len(df_sub_carga) > 0:
                    df_sem = df_sub_carga[(df_sub_carga['din_instante'] >= ini) & (df_sub_carga['din_instante'] <= fim)]
                    if len(df_sem) > 0:
                        # Desconsidera valores nulos, NaN ou zero no cálculo da média diária semanal
                        df_sem_valido = df_sem[(df_sem['val_cargaenergiamwmed'] > 0) & (df_sem['val_cargaenergiamwmed'].notna())]
                        if len(df_sem_valido) > 0:
                            realizado_valores.append(round(float(df_sem_valido['val_cargaenergiamwmed'].mean()), 2))
                        else:
                            realizado_valores.append(None)
                    else:
                        realizado_valores.append(None)
                else:
                    realizado_valores.append(None)
                    
            # Média mensal ponderada acumulada para o realizado
            soma_realizado = sum(v * p for v, p in zip(realizado_valores, pesos) if v is not None)
            peso_realizado = sum(p for v, p in zip(realizado_valores, pesos) if v is not None)
            media_realizado = round(soma_realizado / peso_realizado, 2) if peso_realizado > 0 else None
            
            realizado_valores_arred = [round(v) if v is not None else None for v in realizado_valores]
            media_realizado_arred = round(media_realizado) if media_realizado is not None else None
            
            dados[sub_id] = {
                'previsoes': previsoes,
                'realizado': {
                    'valores': realizado_valores_arred,
                    'media_mensal': media_realizado_arred
                }
            }
            
        retorno = {
            'mes_referencia': mes_ref,
            'semanas_info': semanas_info,
            'dados': dados
        }
        
        return jsonify(retorno)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Erro em get_carga_comparativo:\n{tb}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/ear_comparativo/meses', methods=['GET'])
def get_ear_meses_comparativo():
    try:
        if not github_file_exists(PATH_EAR_PREVS):
            return jsonify([])
        
        df_prevs = ler_excel_com_copia(PATH_EAR_PREVS)
        if len(df_prevs) == 0:
            return jsonify([])
            
        col_mes_nome = df_prevs.columns[4]
        meses_unicos = df_prevs[col_mes_nome].dropna().unique().tolist()
        
        meses = []
        for mes_str in meses_unicos:
            try:
                mes_id = converter_mes_carga(mes_str)
                mes_num = int(mes_id[:2])
                ano_str = mes_id[2:]
                meses.append({
                    'id': mes_id,
                    'label': f"{obter_nome_mes(mes_num)} de {ano_str}"
                })
            except Exception as ex:
                print(f"Erro ao converter mes '{mes_str}' em EAR: {str(ex)}")
                
        # Ordena de forma cronológica decrescente
        def sort_key(m):
            return int(m['id'][2:]) * 100 + int(m['id'][:2])
        meses = sorted(meses, key=sort_key, reverse=True)
        return jsonify(meses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/ear_comparativo', methods=['GET'])
def get_ear_comparativo():
    try:
        mes_ref = request.args.get('mes') # Ex: '062026'
        
        if not mes_ref:
            if not github_file_exists(PATH_EAR_PREVS):
                return jsonify({'error': 'Arquivo de previsões de EAR não encontrado.'}), 404
            df_prevs = ler_excel_com_copia(PATH_EAR_PREVS)
            if len(df_prevs) == 0:
                return jsonify({'error': 'Arquivo de previsões de EAR vazio.'}), 404
            col_mes_nome = df_prevs.columns[4]
            meses_unicos = df_prevs[col_mes_nome].dropna().unique().tolist()
            if not meses_unicos:
                return jsonify({'error': 'Nenhum mês de previsões de EAR encontrado.'}), 404
            
            def sort_key_str(m_str):
                try:
                    m_id = converter_mes_carga(m_str)
                    return int(m_id[2:]) * 100 + int(m_id[:2])
                except:
                    return 0
            meses_unicos_sorted = sorted(meses_unicos, key=sort_key_str, reverse=True)
            mes_ref = converter_mes_carga(meses_unicos_sorted[0])
            
        if not github_file_exists(PATH_EAR_PREVS):
            return jsonify({'error': f"Arquivo de previsões de EAR não encontrado."}), 404
            
        df_prevs = ler_excel_com_copia(PATH_EAR_PREVS)
        
        # Extrai ano e mês do id '062026'
        mes_num = int(mes_ref[:2])
        ano_num = int(mes_ref[2:])
        
        # Converte o mes_ref de volta para o formato de string do excel (ex: 'JUN_2026')
        mes_excel_str = converter_id_para_mes_carga(mes_ref)
        
        # Filtra a planilha de previsões para o mês de referência
        col_mes_nome = df_prevs.columns[4]
        df_mes_prevs = df_prevs[df_prevs[col_mes_nome].str.upper() == mes_excel_str.upper()].copy()
        
        if len(df_mes_prevs) == 0:
            return jsonify({'error': f"Nenhuma previsão encontrada para o mês {mes_ref} ({mes_excel_str})."}), 404
            
        # Calcula todos os dias do mês calendário
        import calendar
        _, num_dias = calendar.monthrange(ano_num, mes_num)
        dias_mes = [datetime.date(ano_num, mes_num, d) for d in range(1, num_dias + 1)]
        dias_labels = [d.strftime('%Y-%m-%d') for d in dias_mes]
        
        # Carrega a base diária de EAR realizada
        df_ear = pd.DataFrame()
        if github_file_exists(PATH_EAR):
            df_ear = ler_excel_com_copia(PATH_EAR)
            if len(df_ear) > 0:
                df_ear['ear_data'] = pd.to_datetime(df_ear['ear_data']).dt.date
                
        # Mapeamento do submercado
        sub_map = {
            'SUDESTE': 'SE',
            'SUL': 'S',
            'NORDESTE': 'NE',
            'NORTE': 'N'
        }
        
        dados = {}
        for sub_nome, sub_id in sub_map.items():
            df_sub_prevs = df_mes_prevs[df_mes_prevs['SUBMERCADO'].str.upper() == sub_nome].copy()
            
            # Previsões de fechamento de mês por RV
            previsoes = {}
            col_ear_max_nome = df_prevs.columns[1] # 'EAR Mêx' ou 'EAR Máx'
            for _, r in df_sub_prevs.iterrows():
                rv_nome = str(r['rvx']).strip()
                val_prev = float(r[col_ear_max_nome]) if pd.notna(r[col_ear_max_nome]) else None
                previsoes[rv_nome] = round(val_prev, 2) if val_prev is not None else None
                
            # Filtra realizado do subsistema para o mês
            df_sub_ear = pd.DataFrame()
            if len(df_ear) > 0:
                df_sub_ear = df_ear[df_ear['id_subsistema'] == sub_id].copy()
                
            realizado_pct = []
            realizado_mwmes = []
            capacidades = []
            
            ultimo_val_pct = None
            ultimo_val_mwmes = None
            ultimo_dia_str = "-"
            
            for d in dias_mes:
                df_dia = pd.DataFrame()
                if len(df_sub_ear) > 0:
                    df_dia = df_sub_ear[df_sub_ear['ear_data'] == d]
                    
                if len(df_dia) > 0:
                    pct = float(df_dia['ear_verif_subsistema_percentual'].iloc[0])
                    mwmes = float(df_dia['ear_verif_subsistema_mwmes'].iloc[0])
                    cap = float(df_dia['ear_max_subsistema'].iloc[0])
                    
                    realizado_pct.append(round(pct, 2) if pd.notna(pct) else None)
                    realizado_mwmes.append(round(mwmes, 2) if pd.notna(mwmes) else None)
                    if pd.notna(cap):
                        capacidades.append(cap)
                        
                    if pd.notna(pct):
                        ultimo_val_pct = round(pct, 2)
                        ultimo_val_mwmes = round(mwmes, 2)
                        ultimo_dia_str = d.strftime('%d/%m')
                else:
                    realizado_pct.append(None)
                    realizado_mwmes.append(None)
                    
            capacidade_maxima = round(sum(capacidades) / len(capacidades), 2) if capacidades else None
            
            dados[sub_id] = {
                'previsoes': previsoes,
                'realizado_percentual': realizado_pct,
                'realizado_mwmes': realizado_mwmes,
                'capacidade_maxima': capacidade_maxima,
                'ultimo_realizado': {
                    'data': ultimo_dia_str,
                    'percentual': ultimo_val_pct,
                    'mwmes': ultimo_val_mwmes
                }
            }
            
        retorno = {
            'mes_referencia': mes_ref,
            'dias': dias_labels,
            'dados': dados
        }
        
        return jsonify(retorno)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Erro em get_ear_comparativo:\n{tb}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/pld', methods=['GET'])
def get_data_pld():
    try:
        if not github_file_exists(CACHE_PLD):
            atualizar_cache_e_metadata_pld()
        conteudo_json = github_read_file(CACHE_PLD)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/pld_horario', methods=['GET'])
def get_data_pld_horario():
    try:
        if not github_file_exists(CACHE_PLD_HORARIO):
            atualizar_cache_e_metadata_pld()
        conteudo_json = github_read_file(CACHE_PLD_HORARIO)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/ampere', methods=['GET'])
def get_data_ampere():
    try:
        if not github_file_exists(CACHE_AMPERE):
            atualizar_cache_e_metadata_ampere()
        conteudo_json = github_read_file(CACHE_AMPERE)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/ampere_completo', methods=['GET'])
def get_data_ampere_completo():
    try:
        if not github_file_exists(CACHE_AMPERE_COMPLETO):
            atualizar_cache_e_metadata_ampere()
        conteudo_json = github_read_file(CACHE_AMPERE_COMPLETO)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- ROTA DE VISUALIZAÇÃO DE DADOS BRUTOS (AUDITORIA) ----------------

@app.route('/api/data/view/<base>', methods=['GET'])
def get_data_view(base):
    """
    Retorna as 100 linhas mais recentes da base solicitada para conferência de dados.
    """
    try:
        if base == 'balanco':
            cache_path = CACHE_BALANCO_RECENT
            if not github_file_exists(cache_path):
                atualizar_cache_e_metadata_balanco()
        elif base == 'pld':
            cache_path = CACHE_PLD_RECENT
            if not github_file_exists(cache_path):
                atualizar_cache_e_metadata_pld()
        elif base == 'ampere':
            cache_path = CACHE_AMPERE_RECENT
            if not github_file_exists(cache_path):
                atualizar_cache_e_metadata_ampere()
        elif base == 'bbce':
            cache_path = CACHE_BBCE_RECENT
            if not github_file_exists(cache_path):
                atualizar_cache_e_metadata_bbce()
        elif base == 'ena':
            cache_path = CACHE_ENA_RECENT
            if not github_file_exists(cache_path):
                atualizar_cache_e_metadata_ena()
        elif base == 'carga':
            cache_path = CACHE_CARGA_RECENT
            if not github_file_exists(cache_path):
                atualizar_cache_e_metadata_carga()
        elif base == 'ear':
            cache_path = CACHE_EAR_RECENT
            if not github_file_exists(cache_path):
                atualizar_cache_e_metadata_ear()
        else:
            return jsonify({'error': 'Base inválida.'}), 400
            
        conteudo_json = github_read_file(cache_path)
        data = json.loads(conteudo_json.decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/error', methods=['GET'])
def get_debug_error():
    tb = ler_erro_debug()
    return f"<pre style='font-family: monospace; padding: 20px; background: #1e1e1e; color: #f8f8f2; border-radius: 8px; overflow: auto;'>{tb}</pre>"

@app.route('/api/debug/github', methods=['GET'])
def get_debug_github():
    if not usar_github():
        return jsonify({
            'github_ativo': False,
            'status': 'Modo local (GITHUB_TOKEN não configurado).'
        })
        
    try:
        from github_storage import GITHUB_REPO, GITHUB_BRANCH, GITHUB_TOKEN
        token_mascarado = f"{GITHUB_TOKEN[:6]}...{GITHUB_TOKEN[-4:]}" if GITHUB_TOKEN else "Nenhum"
        
        import requests
        url = f"https://api.github.com/repos/{GITHUB_REPO}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = requests.get(url, headers=headers, timeout=10)
        
        rep_status = res.status_code
        rep_msg = res.json().get("message", "OK") if rep_status != 200 else "Acesso ao Repositório Confirmado"
        
        # Testar existência do metadata.json no GitHub
        url_file = f"https://api.github.com/repos/{GITHUB_REPO}/contents/planilhas_para_atualizar/metadata.json"
        res_file = requests.head(url_file, headers=headers, timeout=10)
        file_status = res_file.status_code
        
        return jsonify({
            'github_ativo': True,
            'repositorio': GITHUB_REPO,
            'branch': GITHUB_BRANCH,
            'token_configurado': token_mascarado,
            'conexao_repositorio': f"Status {rep_status} ({rep_msg})",
            'metadata_existente_no_github': f"Status {file_status} (200 = Sim, 404 = Não)"
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    # Roda o servidor local na porta 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
