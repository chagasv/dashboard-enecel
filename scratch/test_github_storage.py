import os
import sys

# Adiciona o diretório raiz ao path para conseguir importar github_storage
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from github_storage import github_read_file, github_write_file, github_file_exists, github_get_file_info, usar_github

def testar_modo_local():
    print("\n--- TESTANDO MODO LOCAL ---")
    caminho_teste = os.path.join(BASE_DIR, 'planilhas_para_atualizar', 'test_local.json')
    conteudo_esperado = b'{"status": "ok", "ambiente": "local"}'
    
    # 1. Teste de Escrita
    print(f"Escrevendo arquivo local em: {caminho_teste}")
    github_write_file(caminho_teste, conteudo_esperado)
    
    # 2. Teste de Existência
    existe = github_file_exists(caminho_teste)
    print(f"Arquivo existe localmente? {existe}")
    assert existe == True, "Falha: O arquivo deveria existir!"
    
    # 3. Teste de Leitura
    conteudo_lido = github_read_file(caminho_teste)
    print(f"Conteúdo lido: {conteudo_lido}")
    assert conteudo_lido == conteudo_esperado, "Falha: O conteúdo lido não corresponde ao gravado!"
    
    # 4. Teste de Metadados
    info = github_get_file_info(caminho_teste)
    print(f"Metadados locais obtidos: {info}")
    assert 'tamanho' in info and 'modificado' in info, "Falha: Metadados locais incompletos!"
    
    # Limpa arquivo temporário
    if os.path.exists(caminho_teste):
        os.remove(caminho_teste)
        print("Arquivo de teste local limpo.")
        
    print(">>> MODO LOCAL APROVADO! <<<")

def testar_modo_github():
    print("\n--- TESTANDO MODO GITHUB (API) ---")
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO', 'chagasv/dashboard-enecel')
    branch = os.environ.get('GITHUB_BRANCH', 'main')
    
    print(f"Modo GitHub ativo? {usar_github()}")
    print(f"Repositório: {repo}")
    print(f"Branch: {branch}")
    
    if not token:
        print("AVISO: Variável GITHUB_TOKEN não configurada. Pulando teste real da API do GitHub.")
        print("Para testar de verdade, rode o script definindo o token, por exemplo:")
        print("cmd /C \"set GITHUB_TOKEN=seu_token_aqui && python scratch/test_github_storage.py\"")
        return
        
    caminho_teste = os.path.join(BASE_DIR, 'planilhas_para_atualizar', 'test_github_api_connection.json')
    conteudo_esperado = b'{"status": "ok", "ambiente": "github_api_test"}'
    
    try:
        # 1. Teste de Escrita / Commit
        print(f"Efetuando commit de teste em '{caminho_teste}' no GitHub...")
        github_write_file(caminho_teste, conteudo_esperado, message="Test Connection from Dashboard Storage Helper")
        
        # 2. Teste de Existência
        print("Verificando se o arquivo existe no repositório...")
        existe = github_file_exists(caminho_teste)
        print(f"Arquivo existe no repositório? {existe}")
        assert existe == True, "Falha: O arquivo deveria existir no GitHub!"
        
        # 3. Teste de Leitura
        print("Lendo arquivo recém-criado do GitHub...")
        conteudo_lido = github_read_file(caminho_teste)
        print(f"Conteúdo lido do GitHub: {conteudo_lido}")
        assert conteudo_lido == conteudo_esperado, "Falha: O conteúdo lido do GitHub não corresponde ao gravado!"
        
        # 4. Teste de Metadados
        print("Consultando informações e commits do arquivo...")
        info = github_get_file_info(caminho_teste)
        print(f"Metadados do GitHub obtidos: {info}")
        assert 'tamanho' in info and 'modificado' in info, "Falha: Metadados do GitHub incompletos!"
        
        print(">>> MODO GITHUB API APROVADO COM SUCESSO! <<<")
        
    except Exception as e:
        print(f"FALHA NO TESTE DO GITHUB: {str(e)}")
        raise e

if __name__ == '__main__':
    print("Iniciando testes funcionais do github_storage.py...")
    testar_modo_local()
    testar_modo_github()
    print("\nTestes concluídos!")
