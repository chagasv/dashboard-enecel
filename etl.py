import os
import io
import datetime
import requests
import pandas as pd
import pdfplumber
try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None
from github_storage import github_read_file, github_write_file, github_file_exists

# Mapeamentos para a planilha Ampere
SUB_MAP = {
    'SE/CO': 'Sudeste/Centro-Oeste',
    'SE': 'Sudeste/Centro-Oeste',
    'S': 'Sul',
    'NE': 'Nordeste',
    'N': 'Norte',
    'SIN': 'SIN'
}

def parse_mes_ano(mes_ano_str):
    mes_ano_str = mes_ano_str.strip().lower()
    partes = mes_ano_str.split('/')
    if len(partes) != 2:
        raise ValueError(f"Formato de mês/ano inválido: {mes_ano_str}")
    
    mes_nome = partes[0]
    ano_digito = partes[1]
    
    meses_map = {
        'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
    }
    
    meses_en_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    mes = meses_map.get(mes_nome[:3]) or meses_en_map.get(mes_nome[:3])
    if not mes:
        raise ValueError(f"Mês não reconhecido: {mes_nome}")
    
    ano = 2000 + int(ano_digito)
    return datetime.date(ano, mes, 1)

def parse_float(val_str):
    if not val_str or str(val_str).strip() == '':
        return None
    val_str = str(val_str).strip().replace('%', '')
    if ',' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return None

def atualizar_balanco_energetico(planilha_base_path, ons_url=None):
    """
    Baixa os dados do ONS do ano corrente (2026) e adiciona de forma incremental
    na planilha base de balanço energético.
    """
    if ons_url is None:
        ons_url = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/balanco_energia_subsistema_ho/BALANCO_ENERGIA_SUBSISTEMA_2026.xlsx"
    
    print(f"[{datetime.datetime.now()}] Iniciando atualização do Balanço Energético...")
    print(f"Lendo base local: {planilha_base_path}")
    
    if not github_file_exists(planilha_base_path):
        raise FileNotFoundError(f"Planilha base não encontrada no caminho: {planilha_base_path}")
    
    # Carrega a planilha base existente
    conteudo_excel = github_read_file(planilha_base_path)
    df_base = pd.read_excel(io.BytesIO(conteudo_excel), sheet_name="balanco_energetico")
    print(f"Base local carregada. Total de linhas: {len(df_base)}")
    
    # Converte coluna de data para datetime
    df_base['din_instante'] = pd.to_datetime(df_base['din_instante'])
    
    # Encontra a data máxima na base local
    max_date = df_base['din_instante'].max()
    print(f"Última data registrada localmente: {max_date}")
    
    # Baixa o arquivo novo da ONS
    print(f"Baixando dados da ONS: {ons_url}")
    response = requests.get(ons_url, timeout=60)
    if response.status_code != 200:
        raise Exception(f"Erro ao baixar arquivo da ONS. Status Code: {response.status_code}")
    
    print("Download concluído com sucesso. Processando dados da ONS...")
    # Lê os dados baixados usando pandas
    df_ons = pd.read_excel(io.BytesIO(response.content))
    df_ons['din_instante'] = pd.to_datetime(df_ons['din_instante'])
    
    # Filtra apenas registros mais recentes do que a última data local
    df_novos = df_ons[df_ons['din_instante'] > max_date]
    print(f"Total de novos registros encontrados para adicionar: {len(df_novos)}")
    
    if len(df_novos) > 0:
        # Ordena os dados novos por data
        df_novos = df_novos.sort_values(by=['din_instante', 'id_subsistema']).reset_index(drop=True)
        
        # Concatena a base local com os novos dados
        df_final = pd.concat([df_base, df_novos], ignore_index=True)
        
        # Salva de volta na planilha
        print(f"Gravando dados atualizados em {planilha_base_path} (isso pode levar alguns segundos)...")
        buffer = io.BytesIO()
        df_final.to_excel(buffer, sheet_name="balanco_energetico", index=False)
        github_write_file(planilha_base_path, buffer.getvalue())
        print(f"Sucesso! Planilha de Balanço Energético atualizada. Total de linhas agora: {len(df_final)}")
        return len(df_novos), len(df_final)
    else:
        print("Nenhum dado novo encontrado. A planilha já está atualizada.")
        return 0, len(df_base)


def atualizar_pld(planilha_base_path, ccee_url=None):
    """
    Baixa os dados horários do PLD da CCEE e atualiza a planilha base de PLD
    deletando os dados do ano corrente de 2026 e inserindo o novo lote completo.
    """
    if ccee_url is None:
        ccee_url = "https://pda-download.ccee.org.br/6A5wq97KTCWv_bvs3CqsQQ/content"
        
    print(f"[{datetime.datetime.now()}] Iniciando atualização do PLD Horário...")
    print(f"Lendo base local: {planilha_base_path}")
    
    if not github_file_exists(planilha_base_path):
        raise FileNotFoundError(f"Planilha base não encontrada no caminho: {planilha_base_path}")
        
    # Carrega base local
    conteudo_excel = github_read_file(planilha_base_path)
    df_base = pd.read_excel(io.BytesIO(conteudo_excel), sheet_name="pld")
    print(f"Base local carregada. Total de linhas: {len(df_base)}")
    
    # Baixa os novos dados da CCEE usando requests ou curl_cffi
    print(f"Baixando dados do PLD da CCEE: {ccee_url}")
    
    from github_storage import usar_github
    
    if usar_github() or cffi_requests is None:
        print("[ETL] Usando requests padrão (modo nuvem/resiliente) para baixar dados da CCEE...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(ccee_url, headers=headers, timeout=60)
    else:
        print("[ETL] Usando curl_cffi (modo local) para baixar dados da CCEE...")
        response = cffi_requests.get(ccee_url, impersonate="chrome", timeout=60)
    
    if response.status_code != 200:
        raise Exception(f"Erro ao baixar arquivo de PLD da CCEE. Status Code: {response.status_code}")
        
    print("Download concluído. Processando arquivo CSV da CCEE...")
    
    # Decodifica e carrega o CSV
    csv_text = response.content.decode('utf-8', errors='ignore')
    df_new = pd.read_csv(io.StringIO(csv_text), sep=';', decimal='.')
    
    # Garante os tipos corretos compatíveis com o Excel
    df_new['MES_REFERENCIA'] = df_new['MES_REFERENCIA'].astype(int)
    df_new['PERIODO_COMERCIALIZACAO'] = df_new['PERIODO_COMERCIALIZACAO'].astype(int)
    df_new['DIA'] = df_new['DIA'].astype(int)
    df_new['HORA'] = df_new['HORA'].astype(int)
    df_new['PLD_HORA'] = df_new['PLD_HORA'].astype(float)
    df_new['SUBMERCADO'] = df_new['SUBMERCADO'].astype(str)
    
    print(f"Novos dados lidos com sucesso. Total de linhas no arquivo baixado: {len(df_new)}")
    
    # Filtra a base local deletando os dados do ano de 2026 (MES_REFERENCIA >= 202601)
    # 202601 é maior que 202600.
    df_base_filtered = df_base[df_base['MES_REFERENCIA'] < 202600]
    linhas_deletadas = len(df_base) - len(df_base_filtered)
    print(f"Dados locais de 2026 removidos: {linhas_deletadas} linhas.")
    
    # Concatena a base limpa com os novos dados de 2026
    df_final = pd.concat([df_base_filtered, df_new], ignore_index=True)
    
    # Salva de volta
    print(f"Gravando dados atualizados em {planilha_base_path}...")
    buffer = io.BytesIO()
    df_final.to_excel(buffer, sheet_name="pld", index=False)
    github_write_file(planilha_base_path, buffer.getvalue())
    print(f"Sucesso! Planilha de PLD Horário atualizada. Total de linhas agora: {len(df_final)}")
    return len(df_new), len(df_final)


def extrair_ampere_pdf(pdf_path, planilha_base_path):
    """
    Extrai as tabelas de ENA, Armazenamento e PLD do PDF semanal da Ampere
    e as anexa na planilha base de rodadas da Ampere.
    """
    print(f"[{datetime.datetime.now()}] Iniciando processamento do relatório Ampere...")
    print(f"Arquivo PDF: {pdf_path}")
    print(f"Lendo base local: {planilha_base_path}")
    
    if not github_file_exists(planilha_base_path):
        raise FileNotFoundError(f"Planilha base não encontrada no caminho: {planilha_base_path}")
        
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Relatório PDF não encontrado no caminho: {pdf_path}")
        
    # Carrega planilha base
    conteudo_excel = github_read_file(planilha_base_path)
    df_base = pd.read_excel(io.BytesIO(conteudo_excel), sheet_name="f_dados")
    print(f"Base local de rodadas carregada. Total de linhas: {len(df_base)}")
    
    # Converte colunas de data para datetime
    df_base['data_referencia'] = pd.to_datetime(df_base['data_referencia'])
    df_base['data_publicacao'] = pd.to_datetime(df_base['data_publicacao'])
    
    # Extrai metadados do nome do arquivo
    filename = os.path.basename(pdf_path)
    # Espera-se formato como "Ampere_semanal_AAAAMMDD.pdf" ou similar
    # Vamos limpar qualquer texto e pegar apenas os digitos numéricos seguidos de 8 números
    import re
    date_match = re.search(r'\d{8}', filename)
    if not date_match:
        raise ValueError(f"Não foi possível extrair a data da rodada a partir do nome do arquivo: {filename}. O nome do arquivo deve conter a data em formato AAAAMMDD (ex: Ampere_semanal_20260609.pdf).")
    
    rodada_str = date_match.group(0)
    rodada = int(rodada_str)
    data_pub = datetime.datetime.strptime(rodada_str, "%Y%m%d").date()
    print(f"Metadados extraídos - Rodada: {rodada}, Data de Publicação: {data_pub}")
    
    # Verifica se esta rodada já existe na planilha base para evitar duplicidade
    if rodada in df_base['rodada'].unique():
        formatted_rod = f"{rodada_str[6:8]}/{rodada_str[4:6]}/{rodada_str[0:4]}"
        raise ValueError(f"A rodada de {formatted_rod} já foi cadastrada anteriormente no banco de dados!")
    
    records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        # Encontra as páginas corretas dinamicamente procurando por palavras-chave
        pag_ena_idx = None
        pag_arm_idx = None
        pag_pld_idx = None
        
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if "Tabela 4:" in text or ("Tabela 4" in text and "Cenários de Energia Natural Afluente" in text):
                pag_ena_idx = idx
            if "Tabela 12:" in text or ("Tabela 12" in text and "Níveis de Energia Armazenada" in text):
                pag_arm_idx = idx
            if "Tabela 21:" in text or ("Tabela 21" in text and "Resultados das simulações DECOMP" in text):
                pag_pld_idx = idx
                
        if pag_ena_idx is None:
            # Fallback para as páginas padrão caso não ache o texto exato
            pag_ena_idx = 12
            print("Página da ENA não encontrada por texto. Usando padrão Página 13.")
        else:
            print(f"Página da ENA encontrada: Página {pag_ena_idx + 1}")
            
        if pag_arm_idx is None:
            pag_arm_idx = 14
            print("Página do Armazenamento não encontrada por texto. Usando padrão Página 15.")
        else:
            print(f"Página do Armazenamento encontrada: Página {pag_arm_idx + 1}")
            
        if pag_pld_idx is None:
            pag_pld_idx = 17
            print("Página do PLD não encontrada por texto. Usando padrão Página 18.")
        else:
            print(f"Página do PLD encontrada: Página {pag_pld_idx + 1}")
            
        # 1. Extração ENA (Página da ENA)
        page_ena = pdf.pages[pag_ena_idx]
        tables_ena = page_ena.extract_tables()
        if not tables_ena:
            raise Exception("Nenhuma tabela encontrada na página da ENA.")
            
        # Filtra a tabela correta procurando os subsistemas ou títulos
        tabela_ena = None
        for t in tables_ena:
            # Verifica se contém termos de subsistema
            flat_table = [str(cell) for row in t for cell in row if cell]
            if any(sub in flat_table for sub in ['SE/CO', 'SUDESTE', 'SUL', 'NORDESTE', 'NORTE']):
                # Queremos a tabela simplificada dos subsistemas (que vem primeiro)
                if 'SUDESTE' not in flat_table or ('SE/CO' in flat_table and 'SUDESTE' in flat_table):
                    tabela_ena = t
                    break
        if tabela_ena is None:
            tabela_ena = tables_ena[0]
            
        row_meses = [str(x).strip() for x in tabela_ena[1] if x and '/' in str(x)]
        meses_ref = [parse_mes_ano(m) for m in row_meses]
        print(f"Meses de ENA detectados: {row_meses}")
        
        # Lógica de extração de valores robusta
        for row in tabela_ena[2:]:
            clean_row = [str(x).strip() for x in row if x is not None and str(x).strip() != '']
            if 'BASE' in clean_row:
                clean_row.remove('BASE')
                
            if len(clean_row) > 0 and clean_row[0] in SUB_MAP:
                sub_raw = clean_row[0]
                sub_nome = SUB_MAP[sub_raw]
                valores_restantes = clean_row[1:]
                
                for m_idx, mes_ref in enumerate(meses_ref):
                    mw_raw = valores_restantes[m_idx * 2]
                    pct_raw = valores_restantes[m_idx * 2 + 1]
                    
                    mw_val = parse_float(mw_raw.replace('.', ''))
                    pct_val = parse_float(pct_raw)
                    
                    # Registro MWmed
                    records.append({
                        'data_referencia': pd.to_datetime(mes_ref), 'ano': int(mes_ref.year), 'mês': int(mes_ref.month),
                        'indicador': 'ENA', 'unidade': 'MWmed', 'valor': mw_val,
                        'subsistema': sub_nome, 'reservtorio_equivalente': None, 'tipo_valor': 'Previsto',
                        'fonte': 'Ampere', 'rodada': rodada, 'cenario': 'BASE', 'data_publicacao': pd.to_datetime(data_pub)
                    })
                    # Registro %
                    records.append({
                        'data_referencia': pd.to_datetime(mes_ref), 'ano': int(mes_ref.year), 'mês': int(mes_ref.month),
                        'indicador': 'ENA', 'unidade': '%', 'valor': pct_val,
                        'subsistema': sub_nome, 'reservtorio_equivalente': None, 'tipo_valor': 'Previsto',
                        'fonte': 'Ampere', 'rodada': rodada, 'cenario': 'BASE', 'data_publicacao': pd.to_datetime(data_pub)
                    })
        print(f"Extraídos {len(records)} registros de ENA.")
        
        # 2. Extração Armazenamento (Página do Armazenamento)
        page_arm = pdf.pages[pag_arm_idx]
        tables_arm = page_arm.extract_tables()
        if not tables_arm:
            raise Exception("Nenhuma tabela encontrada na página do Armazenamento.")
            
        tabela_arm = None
        for t in tables_arm:
            flat_table = [str(cell) for row in t for cell in row if cell]
            if any("Armazenamentos ao fim de cada" in cell for cell in flat_table):
                # Verifica se é a tabela por subsistema (contém SIN e não REEs detalhados)
                if 'SIN' in flat_table and 'SUDESTE' not in flat_table and 'Paranapanema' not in flat_table:
                    tabela_arm = t
                    break
        if tabela_arm is None:
            # Fallback para a de index 5
            tabela_arm = tables_arm[5] if len(tables_arm) > 5 else tables_arm[0]
            
        row_meses_arm = [str(x).strip() for x in tabela_arm[1] if x and '/' in str(x)]
        meses_ref_arm = [parse_mes_ano(m) for m in row_meses_arm]
        print(f"Meses de Armazenamento detectados: {row_meses_arm}")
        
        count_arm = 0
        for row in tabela_arm[2:]:
            clean_row = [str(x).strip() for x in row if x is not None and str(x).strip() != '']
            if 'BASE' in clean_row:
                clean_row.remove('BASE')
                
            if len(clean_row) > 0 and clean_row[0] in SUB_MAP:
                sub_raw = clean_row[0]
                sub_nome = SUB_MAP[sub_raw]
                valores_restantes = clean_row[1:]
                
                for m_idx, mes_ref in enumerate(meses_ref_arm):
                    val_raw = valores_restantes[m_idx]
                    val = parse_float(val_raw)
                    
                    records.append({
                        'data_referencia': pd.to_datetime(mes_ref), 'ano': int(mes_ref.year), 'mês': int(mes_ref.month),
                        'indicador': 'Armazenamento', 'unidade': '%', 'valor': val,
                        'subsistema': sub_nome, 'reservtorio_equivalente': None, 'tipo_valor': 'Previsto',
                        'fonte': 'Ampere', 'rodada': rodada, 'cenario': 'BASE', 'data_publicacao': pd.to_datetime(data_pub)
                    })
                    count_arm += 1
        print(f"Extraídos {count_arm} registros de Armazenamento.")
        
        # 3. Extração PLD (Página do PLD)
        page_pld = pdf.pages[pag_pld_idx]
        tables_pld = page_pld.extract_tables()
        if not tables_pld:
            raise Exception("Nenhuma tabela encontrada na página do PLD.")
            
        tabela_pld = None
        for t in tables_pld:
            flat_table = [str(cell) for row in t for cell in row if cell]
            if any("simulações DECOMP" in cell for cell in flat_table):
                # Queremos a primeira tabela de simulações do cenário BASE
                if 'DIF' not in flat_table and 'REF' not in flat_table:
                    tabela_pld = t
                    break
        if tabela_pld is None:
            tabela_pld = tables_pld[0]
            
        row_meses_pld = [str(x).strip() for x in tabela_pld[0] if x and '/' in str(x)]
        meses_ref_pld = [parse_mes_ano(m) for m in row_meses_pld]
        print(f"Meses de PLD detectados: {row_meses_pld}")
        
        count_pld = 0
        for row in tabela_pld[2:]:
            clean_row = [str(x).strip() for x in row if x is not None and str(x).strip() != '']
            if 'BASE' in clean_row:
                clean_row.remove('BASE')
                
            if len(clean_row) > 0 and clean_row[0] in SUB_MAP:
                sub_raw = clean_row[0]
                sub_nome = SUB_MAP[sub_raw]
                valores_restantes = clean_row[1:]
                
                for m_idx, mes_ref in enumerate(meses_ref_pld):
                    # O PLD é o segundo valor do par (PLD_sem_limite, PLD)
                    pld_val_raw = valores_restantes[m_idx * 2 + 1]
                    val = parse_float(pld_val_raw)
                    
                    records.append({
                        'data_referencia': pd.to_datetime(mes_ref), 'ano': int(mes_ref.year), 'mês': int(mes_ref.month),
                        'indicador': 'PLD', 'unidade': 'R$/MWh', 'valor': val,
                        'subsistema': sub_nome, 'reservtorio_equivalente': None, 'tipo_valor': 'Previsto',
                        'fonte': 'Ampere', 'rodada': rodada, 'cenario': 'BASE', 'data_publicacao': pd.to_datetime(data_pub)
                    })
                    count_pld += 1
        print(f"Extraídos {count_pld} registros de PLD.")

    # Converte a lista de registros novos para um DataFrame
    df_novos = pd.DataFrame(records)
    print(f"Total de novos registros extraídos do PDF: {len(df_novos)}")
    if len(df_novos) != 68:
        print(f"AVISO: O número de registros extraídos ({len(df_novos)}) difere das 68 linhas esperadas!")
    
    # Garante os tipos de dados correspondentes
    df_novos['ano'] = df_novos['ano'].astype(int)
    df_novos['mês'] = df_novos['mês'].astype(int)
    df_novos['rodada'] = df_novos['rodada'].astype(int)
    df_novos['valor'] = df_novos['valor'].astype(float)
    df_novos['indicador'] = df_novos['indicador'].astype(str)
    df_novos['unidade'] = df_novos['unidade'].astype(str)
    df_novos['subsistema'] = df_novos['subsistema'].astype(str)
    df_novos['cenario'] = df_novos['cenario'].astype(str)
    df_novos['fonte'] = df_novos['fonte'].astype(str)
    df_novos['tipo_valor'] = df_novos['tipo_valor'].astype(str)
    
    # Concatena os dados
    df_final = pd.concat([df_base, df_novos], ignore_index=True)
    
    # Salva de volta
    print(f"Gravando dados atualizados em {planilha_base_path}...")
    buffer = io.BytesIO()
    df_final.to_excel(buffer, sheet_name="f_dados", index=False)
    github_write_file(planilha_base_path, buffer.getvalue())
    print("Sucesso! Planilha de rodadas Ampere atualizada.")
    return len(df_novos), len(df_final)


def ler_excel_com_copia(caminho_excel, **kwargs):
    """
    Lê uma planilha Excel criando uma cópia temporária para evitar
    erros de permissão/locks (Permission denied) no Windows.
    No modo GitHub, faz o download do conteúdo da API do GitHub.
    """
    from github_storage import usar_github, github_read_file
    
    # Se o storage for o GitHub e o arquivo pertencer ao projeto, faz a leitura da API
    # (Note que arquivos temporários de upload estarão fora do projeto, começando com '..')
    from github_storage import _obter_caminho_relativo
    rel_path = _obter_caminho_relativo(caminho_excel)
    
    if usar_github() and not rel_path.startswith('..'):
        conteudo = github_read_file(caminho_excel)
        return pd.read_excel(io.BytesIO(conteudo), **kwargs)
        
    # Lógica tradicional em disco local
    import shutil
    import tempfile
    
    if not os.path.exists(caminho_excel):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_excel}")
        
    temp_dir = tempfile.gettempdir()
    caminho_temp = os.path.join(temp_dir, f"temp_read_{os.path.basename(caminho_excel)}")
    
    try:
        shutil.copy2(caminho_excel, caminho_temp)
        df = pd.read_excel(caminho_temp, **kwargs)
        return df
    finally:
        if os.path.exists(caminho_temp):
            try: os.remove(caminho_temp)
            except: pass


def atualizar_negocios_bbce(planilha_base_path, planilha_novos_negocios_path=None, dados_novos_df=None):
    """
    Atualiza de forma incremental a base de negócios da BBCE (f_todos_os_negocios_bbce.xlsx)
    com novos dados (seja de um arquivo Excel de upload ou de um DataFrame do scraper),
    desduplicando de forma rigorosa as transações.
    """
    print(f"[{datetime.datetime.now()}] Iniciando atualização da base BBCE...")
    print(f"Lendo base local: {planilha_base_path}")
    
    if not github_file_exists(planilha_base_path):
        raise FileNotFoundError(f"Planilha base BBCE não encontrada no caminho: {planilha_base_path}")
        
    # Carrega a base local usando cópia temporária resiliente a locks
    df_base = ler_excel_com_copia(planilha_base_path)
    print(f"Base local carregada. Total de registros: {len(df_base)}")
    
    # Garante tipo datetime e nomes de colunas corretos
    df_base['DATA/HORA'] = pd.to_datetime(df_base['DATA/HORA'])
    
    # Carrega ou obtém os novos dados
    if dados_novos_df is not None:
        df_nova = dados_novos_df.copy()
    elif planilha_novos_negocios_path is not None:
        print(f"Lendo nova planilha: {planilha_novos_negocios_path}")
        df_nova = ler_excel_com_copia(planilha_novos_negocios_path)
    else:
        raise ValueError("Nenhum dado novo fornecido para atualização.")
        
    if len(df_nova) == 0:
        print("A planilha de novos negócios está vazia.")
        return 0, len(df_base)
        
    # Padroniza tipos da nova planilha
    df_nova['DATA/HORA'] = pd.to_datetime(df_nova['DATA/HORA'])
    
    # Encontra a menor data presente na nova planilha
    min_date_nova = df_nova['DATA/HORA'].min()
    print(f"Menor data presente nos novos dados: {min_date_nova}")
    
    if pd.isnull(min_date_nova):
        df_novos = df_nova
    else:
        # Mapeia variações comuns de colunas na nova planilha para bater com a base local
        mapa_colunas = {}
        for c in df_nova.columns:
            c_upper = str(c).upper().strip()
            if 'PRODUTO' in c_upper: mapa_colunas[c] = 'PRODUTO'
            elif 'DATA' in c_upper and 'HORA' in c_upper: mapa_colunas[c] = 'DATA/HORA'
            elif c_upper in ['Q.N', 'Q.N.', 'QUANTIDADE NEGOCIAÇÃO', 'QUANTIDADE NEGOCIACAO']: mapa_colunas[c] = 'Q.N'
            elif c_upper in ['U.N.', 'U.N', 'UN']: mapa_colunas[c] = 'U.N.'
            elif c_upper in ['Q.M', 'Q.M.', 'QUANTIDADE MENSURAÇÃO', 'QUANTIDADE MENSURACAO']: mapa_colunas[c] = 'Q.M'
            elif c_upper in ['U.M.', 'U.M', 'UM']: mapa_colunas[c] = 'U.M.'
            elif 'PRE' in c_upper and ('O' in c_upper or 'Ç' in c_upper): mapa_colunas[c] = 'PREÇO'
            elif 'TIPO' in c_upper and 'CONTRATO' in c_upper: mapa_colunas[c] = 'TIPO DE CONTRATO'
            elif 'TEND' in c_upper: mapa_colunas[c] = 'TENDÊNCIA'
            elif 'STATUS' in c_upper: mapa_colunas[c] = 'STATUS'
            
        df_nova = df_nova.rename(columns=mapa_colunas)
        
        # Garante tipos corretos e remove espaços em branco extras para evitar falhas de comparação de strings
        if 'PRODUTO' in df_nova.columns:
            df_nova['PRODUTO'] = df_nova['PRODUTO'].astype(str).str.strip()
        if 'TIPO DE CONTRATO' in df_nova.columns:
            df_nova['TIPO DE CONTRATO'] = df_nova['TIPO DE CONTRATO'].astype(str).str.strip()
        if 'STATUS' in df_nova.columns:
            df_nova['STATUS'] = df_nova['STATUS'].astype(str).str.strip()
            
        # Desduplica internamente a planilha de novos negócios antes do processamento
        df_nova = df_nova.drop_duplicates(subset=['DATA/HORA', 'PRODUTO', 'Q.N', 'PREÇO', 'TIPO DE CONTRATO', 'STATUS'], keep='first')
        
        # Filtra a base local a partir da menor data da planilha nova (com margem de segurança de 1 dia)
        data_corte_busca = min_date_nova - pd.Timedelta(days=1)
        df_base_recent = df_base[df_base['DATA/HORA'] >= data_corte_busca]
        
        # Cria conjunto de tuplas chave da base local recente
        set_existente = set()
        for _, r in df_base_recent.iterrows():
            chave = (
                str(r.get('PRODUTO', '')).strip(),
                r['DATA/HORA'],
                float(r.get('Q.N', 0.0)),
                float(r.get('PREÇO', 0.0)),
                str(r.get('TIPO DE CONTRATO', '')).strip(),
                str(r.get('STATUS', '')).strip()
            )
            set_existente.add(chave)
            
        # Filtra candidatos que não estão na base local recente
        novos_registros = []
        for _, r in df_nova.iterrows():
            chave = (
                str(r.get('PRODUTO', '')).strip(),
                r['DATA/HORA'],
                float(r.get('Q.N', 0.0)),
                float(r.get('PREÇO', 0.0)),
                str(r.get('TIPO DE CONTRATO', '')).strip(),
                str(r.get('STATUS', '')).strip()
            )
            if chave not in set_existente:
                novos_registros.append(r)
                
        if len(novos_registros) > 0:
            df_novos = pd.DataFrame(novos_registros)
        else:
            df_novos = pd.DataFrame(columns=df_base.columns)
            
    print(f"Total de novos registros válidos a adicionar: {len(df_novos)}")
    
    if len(df_novos) > 0:
        # Garante a ordem correta das colunas
        for col in df_base.columns:
            if col not in df_novos.columns:
                df_novos[col] = None
        df_novos = df_novos[df_base.columns]
        
        # Garante tipos de dados correspondentes
        df_novos['Q.N'] = df_novos['Q.N'].astype(float)
        df_novos['Q.M'] = df_novos['Q.M'].astype(float)
        df_novos['PREÇO'] = df_novos['PREÇO'].astype(float)
        df_novos['PRODUTO'] = df_novos['PRODUTO'].astype(str)
        df_novos['U.N.'] = df_novos['U.N.'].fillna('').astype(str)
        df_novos['U.M.'] = df_novos['U.M.'].fillna('').astype(str)
        df_novos['TIPO DE CONTRATO'] = df_novos['TIPO DE CONTRATO'].astype(str)
        df_novos['TENDÊNCIA'] = df_novos['TENDÊNCIA'].fillna('').astype(str)
        df_novos['STATUS'] = df_novos['STATUS'].astype(str)
        
        # Concatena a base limpa com os novos dados
        df_final = pd.concat([df_base, df_novos], ignore_index=True)
        
        # Garante remoção total de duplicados em toda a base histórica final combinada
        df_final = df_final.drop_duplicates(subset=['DATA/HORA', 'PRODUTO', 'Q.N', 'PREÇO', 'TIPO DE CONTRATO', 'STATUS'], keep='first')
        
        # Ordena a base por DATA/HORA de forma ascendente
        df_final = df_final.sort_values(by='DATA/HORA').reset_index(drop=True)
        
        # Grava de volta na planilha
        print(f"Gravando dados atualizados em {planilha_base_path}...")
        buffer = io.BytesIO()
        df_final.to_excel(buffer, index=False)
        github_write_file(planilha_base_path, buffer.getvalue())
        print(f"Sucesso! Base BBCE atualizada. Total de linhas agora: {len(df_final)}")
        return len(df_novos), len(df_final)
    else:
        print("Nenhum registro novo encontrado. A planilha já está atualizada.")
        return 0, len(df_base)

