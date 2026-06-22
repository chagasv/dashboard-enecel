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
from etl import atualizar_balanco_energetico, atualizar_pld, extrair_ampere_pdf, atualizar_negocios_bbce, ler_excel_com_copia
from bbce_scraper import executar_automacao_bbce
from github_storage import github_read_file, github_write_file, github_file_exists, github_get_file_info, usar_github

app = Flask(__name__, static_folder='static', template_folder='templates')

# Caminhos dos arquivos de planilhas
PLANILHAS_DIR = os.path.join(BASE_DIR, 'planilhas_para_atualizar')

PATH_BALANCO = os.path.join(PLANILHAS_DIR, 'f_balanco_energetico.xlsx')
PATH_PLD = os.path.join(PLANILHAS_DIR, 'f_pld.xlsx')
PATH_AMPERE = os.path.join(PLANILHAS_DIR, 'f_rodadas_ampere.xlsx')
PATH_BBCE = os.path.join(PLANILHAS_DIR, 'f_todos_os_negocios_bbce.xlsx')

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


# ----------------- ROTAS FRONTEND -----------------

@app.route('/')
def index():
    return render_template('index.html', is_cloud=usar_github())

# ----------------- ROTA STATUS (METADADOS LEVES EM 1ms) -----------------

@app.route('/api/status', methods=['GET'])
def get_status():
    if not github_file_exists(PATH_METADADOS):
        from gerar_cache import gerar_todos_os_caches
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
