import os
import base64
import requests
import datetime

# Diretório raiz do projeto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configurações do GitHub extraídas das variáveis de ambiente
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'chagasv/dashboard-enecel')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')

def _obter_caminho_relativo(caminho):
    """
    Converte um caminho absoluto ou relativo para um formato relativo padronizado
    com barras normais (/), adequado para a API do GitHub.
    """
    if os.path.isabs(caminho):
        rel_path = os.path.relpath(caminho, BASE_DIR)
    else:
        rel_path = caminho
    
    # Padroniza para uso com barras normais (requisito da API do GitHub)
    rel_path = rel_path.replace('\\', '/')
    
    # Remove eventuais prefixos './'
    if rel_path.startswith('./'):
        rel_path = rel_path[2:]
        
    return rel_path

def _obter_caminho_absoluto(caminho):
    """
    Garante o retorno do caminho absoluto para operações locais em disco.
    """
    if os.path.isabs(caminho):
        return caminho
    return os.path.abspath(os.path.join(BASE_DIR, caminho))

def usar_github():
    """
    Retorna True se o token do GitHub estiver presente, indicando modo de produção na nuvem.
    """
    return bool(GITHUB_TOKEN)

def github_read_file(caminho):
    """
    Lê o conteúdo de um arquivo. Se GITHUB_TOKEN estiver presente e o arquivo estiver no projeto,
    busca via API do GitHub, caso contrário lê do disco local.
    Retorna bytes.
    """
    rel_path = _obter_caminho_relativo(caminho)
    abs_path = _obter_caminho_absoluto(caminho)
    
    # Se estiver fora do projeto (ex: arquivo temporário de upload), lê localmente
    if usar_github() and not rel_path.startswith('..'):
        print(f"[Storage] Lendo '{rel_path}' do GitHub...")
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{rel_path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.raw"
        }
        params = {"ref": GITHUB_BRANCH}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.content
        elif response.status_code == 404:
            raise FileNotFoundError(f"Arquivo não encontrado no GitHub: {rel_path}")
        else:
            raise Exception(f"Erro ao ler arquivo do GitHub ({response.status_code}): {response.text}")
    else:
        # Modo local
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Arquivo não encontrado localmente: {abs_path}")
        with open(abs_path, 'rb') as f:
            return f.read()

def github_write_file(caminho, content_bytes, message=None):
    """
    Escreve o conteúdo em um arquivo. Se GITHUB_TOKEN estiver presente e o arquivo estiver no projeto,
    envia para a API do GitHub como um novo commit. Caso contrário, salva no disco local.
    """
    rel_path = _obter_caminho_relativo(caminho)
    abs_path = _obter_caminho_absoluto(caminho)
    
    if message is None:
        message = f"Atualização automática dos dados: {os.path.basename(rel_path)}"
        
    # Se estiver fora do projeto (ex: pasta temp externa), grava localmente
    if usar_github() and not rel_path.startswith('..'):
        print(f"[Storage] Gravando '{rel_path}' no GitHub...")
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{rel_path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 1. Tenta obter o SHA do arquivo atual se ele existir
        sha = None
        params = {"ref": GITHUB_BRANCH}
        get_response = requests.get(url, headers=headers, params=params, timeout=15)
        if get_response.status_code == 200:
            sha = get_response.json().get("sha")
            
        # 2. Codifica o conteúdo em Base64
        content_b64 = base64.b64encode(content_bytes).decode('utf-8')
        
        # 3. Prepara o payload
        payload = {
            "message": message,
            "content": content_b64,
            "branch": GITHUB_BRANCH
        }
        if sha:
            payload["sha"] = sha
            
        # 4. Envia o PUT
        put_response = requests.put(url, headers=headers, json=payload, timeout=30)
        
        if put_response.status_code not in [200, 201]:
            raise Exception(f"Erro ao gravar arquivo no GitHub ({put_response.status_code}): {put_response.text}")
            
        print(f"[Storage] Arquivo '{rel_path}' gravado com sucesso no GitHub.")
    else:
        # Modo local
        # Garante a existência do diretório pai
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'wb') as f:
            f.write(content_bytes)
        print(f"[Storage] Arquivo '{abs_path}' gravado com sucesso localmente.")

def github_file_exists(caminho):
    """
    Verifica se um arquivo existe (localmente ou no GitHub).
    """
    rel_path = _obter_caminho_relativo(caminho)
    abs_path = _obter_caminho_absoluto(caminho)
    
    if usar_github() and not rel_path.startswith('..'):
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{rel_path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        params = {"ref": GITHUB_BRANCH}
        
        response = requests.head(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            # Em caso de erro de API, fazemos o fallback de checar se existe localmente
            print(f"[Storage] AVISO: Erro na chamada HEAD da API ({response.status_code}). Fazendo checagem local.")
            return os.path.exists(abs_path)
    else:
        return os.path.exists(abs_path)

def github_get_file_info(caminho):
    """
    Retorna informações do arquivo para metadados (tamanho e data de modificação).
    Retorna um dict: {'tamanho': str, 'modificado': str}
    """
    rel_path = _obter_caminho_relativo(caminho)
    abs_path = _obter_caminho_absoluto(caminho)
    
    def format_tamanho(bytes_size):
        if bytes_size >= 1024 * 1024:
            return f"{bytes_size / (1024*1024):.2f} MB"
        return f"{bytes_size / 1024:.2f} KB"
        
    def format_date_str(timestamp):
        return datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
        
    if usar_github() and not rel_path.startswith('..'):
        try:
            # 1. Obtém o tamanho do arquivo via API de Conteúdos
            url_contents = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{rel_path}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            params = {"ref": GITHUB_BRANCH}
            
            res_content = requests.get(url_contents, headers=headers, params=params, timeout=15)
            tamanho_bytes = 0
            if res_content.status_code == 200:
                tamanho_bytes = res_content.json().get("size", 0)
            
            # 2. Obtém a data do último commit para este arquivo específico
            url_commits = f"https://api.github.com/repos/{GITHUB_REPO}/commits"
            params_commits = {
                "path": rel_path,
                "sha": GITHUB_BRANCH,
                "page": 1,
                "per_page": 1
            }
            res_commits = requests.get(url_commits, headers=headers, params=params_commits, timeout=15)
            
            modificado_str = "Desconhecido"
            if res_commits.status_code == 200 and len(res_commits.json()) > 0:
                commit_info = res_commits.json()[0]
                # Pega a data de modificação no formato ISO (ex: "2026-06-18T13:40:00Z")
                date_iso = commit_info.get("commit", {}).get("committer", {}).get("date")
                if date_iso:
                    # Converte para data/hora local formatada
                    dt = datetime.datetime.strptime(date_iso, "%Y-%m-%dT%H:%M:%SZ")
                    # Ajusta fuso horário de Brasília (geralmente UTC-3) para exibição formatada
                    dt = dt - datetime.timedelta(hours=3)
                    modificado_str = dt.strftime('%d/%m/%Y %H:%M:%S')
                    
            return {
                'tamanho': format_tamanho(tamanho_bytes),
                'modificado': modificado_str
            }
        except Exception as e:
            print(f"[Storage] Erro ao buscar metadados do GitHub para '{rel_path}': {str(e)}")
            # Fallback seguro caso falhe a API de metadados
            if os.path.exists(abs_path):
                return {
                    'tamanho': format_tamanho(os.path.getsize(abs_path)),
                    'modificado': format_date_str(os.path.getmtime(abs_path))
                }
            return {'tamanho': "0.00 KB", 'modificado': "Erro de conexão"}
    else:
        # Modo local
        if not os.path.exists(abs_path):
            return {'tamanho': "0.00 KB", 'modificado': "Não existe"}
        return {
            'tamanho': format_tamanho(os.path.getsize(abs_path)),
            'modificado': format_date_str(os.path.getmtime(abs_path))
        }
