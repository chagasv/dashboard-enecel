import os
import sys
import datetime
import subprocess
import time

# Força o modo de escrita e leitura local no disco, desativando acessos de gravação via API HTTP GitHub do github_storage
os.environ['GITHUB_TOKEN'] = ''

# Adiciona o diretório atual ao path para importação correta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from etl import atualizar_balanco_energetico, atualizar_pld, atualizar_negocios_bbce
    from app import (
        atualizar_cache_e_metadata_balanco, 
        atualizar_cache_e_metadata_pld, 
        atualizar_cache_e_metadata_bbce,
        PATH_BALANCO, 
        PATH_PLD, 
        PATH_BBCE
    )
    from bbce_scraper import executar_automacao_bbce
except ImportError as e:
    print(f"\n[ERRO] Falha ao importar dependências do projeto: {str(e)}")
    print("Certifique-se de que está executando o script dentro da pasta raiz do projeto.")
    input("\nPressione Enter para fechar...")
    sys.exit(1)

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def rodar_git(comandos):
    """Executa comandos do Git no terminal do usuário."""
    for cmd in comandos:
        print(f"\n> {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            # Filtra avisos não prejudiciais do Git
            if "warning" in result.stderr.lower() or "everything up-to-date" in result.stderr.lower():
                print(result.stderr.strip())
            else:
                print(f"Aviso/Erro Git: {result.stderr.strip()}")
        if result.returncode != 0 and cmd[0] == "git" and "push" in cmd:
            print("[ALERTA] Falha ao enviar alterações para o GitHub. Verifique sua conexão e credenciais do Git.")
            return False
    return True

def sincronizar_github():
    print("\n" + "="*60)
    print(" INICIANDO SINCRONIZAÇÃO COM O GITHUB ")
    print("="*60)
    
    data_hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # Comandos para adicionar as planilhas e caches e fazer commit/push
    comandos = [
        ["git", "add", "planilhas_para_atualizar/"],
        ["git", "commit", "-m", f"Atualização automática de dados local - {data_hora}"],
        ["git", "push", "origin", "main"]
    ]
    
    success = rodar_git(comandos)
    if success:
        print("\n[SUCESSO] Base de dados local sincronizada com o GitHub com sucesso!")
        print("O Render detectará o envio e atualizará o dashboard online em instantes.")
    else:
        print("\n[AVISO] A sincronização via Git encontrou problemas. Seus arquivos locais estão salvos, mas não foram subidos para a nuvem.")

def executar_ons_ccee():
    print("\n" + "="*60)
    print(" ATUALIZAÇÃO: BALANÇO ONS & PLD CCEE ")
    print("="*60)
    
    # 1. Balanço Energético (ONS)
    print("\n[1/2] Acessando API do ONS para Balanço Energético...")
    try:
        novas_balanco, total_balanco, df_balanco = atualizar_balanco_energetico(PATH_BALANCO)
        print(f"Geração ONS atualizada! Novos registros: {novas_balanco} | Total na base: {total_balanco}")
        
        print("-> Reconstruindo caches e metadados locais de Geração...")
        atualizar_cache_e_metadata_balanco(df_balanco)
    except Exception as e:
        print(f"[ERRO - ONS] Falha ao atualizar Balanço Energético: {str(e)}")
        
    # 2. PLD CCEE
    print("\n[2/2] Acessando API da CCEE para PLD Horário...")
    try:
        novas_pld, total_pld, df_pld = atualizar_pld(PATH_PLD)
        print(f"PLD CCEE atualizado! Novos registros: {novas_pld} | Total na base: {total_pld}")
        
        print("-> Reconstruindo caches e metadados locais de PLD...")
        atualizar_cache_e_metadata_pld(df_pld)
    except Exception as e:
        print(f"[ERRO - CCEE] Falha ao atualizar PLD Horário: {str(e)}")
    
    print("\nAtualização de Balanço ONS e PLD CCEE concluída localmente.")

def executar_bbce():
    print("\n" + "="*60)
    print(" ATUALIZAÇÃO: HISTÓRICO DE NEGÓCIOS BBCE ")
    print("="*60)
    
    print("\n[IMPORTANTE] Para esta automação:")
    print("1. Certifique-se de que o Chrome depurado está aberto na porta 9222.")
    print("   (Você pode abrir via run.bat ou rodando no terminal:")
    print('   chrome.exe --remote-debugging-port=9222 )')
    print("2. Certifique-se de que você já realizou o login e passou pelo 2FA na janela do Chrome.")
    
    confirmar = input("\nO Chrome na porta 9222 está aberto e configurado? (S/N): ").strip().upper()
    if confirmar != 'S':
        print("[CANCELADO] Automação BBCE abortada pelo usuário.")
        return False
        
    # Define intervalo de data padrão (Últimos 7 dias)
    hoje = datetime.date.today()
    d_inicio_sugestao = (hoje - datetime.timedelta(days=7)).strftime('%d/%m/%Y')
    d_fim_sugestao = hoje.strftime('%d/%m/%Y')
    
    print(f"\nSugerido (últimos 7 dias): {d_inicio_sugestao} até {d_fim_sugestao}")
    data_inicio = input(f"Digite a data de início (DD/MM/AAAA) [ou Enter para {d_inicio_sugestao}]: ").strip()
    if not data_inicio:
        data_inicio = d_inicio_sugestao
        
    data_fim = input(f"Digite a data de fim (DD/MM/AAAA) [ou Enter para {d_fim_sugestao}]: ").strip()
    if not data_fim:
        data_fim = d_fim_sugestao
        
    print(f"\nIniciando scraper do portal eHub BBCE para o período {data_inicio} a {data_fim}...")
    
    arquivo_baixado = None
    try:
        # Chama o Selenium local
        arquivo_baixado = executar_automacao_bbce(data_inicio, data_fim, logger_func=print)
        
        if not arquivo_baixado or not os.path.exists(arquivo_baixado):
            raise FileNotFoundError("Não foi possível localizar o arquivo Excel baixado.")
            
        print("\nProcessando arquivo Excel baixado e mesclando novos negócios...")
        novas, total, df_final = atualizar_negocios_bbce(PATH_BBCE, planilha_novos_negocios_path=arquivo_baixado)
        
        # Remove arquivo temporário baixado
        try:
            os.remove(arquivo_baixado)
        except:
            pass
            
        print(f"Planilha base de negócios BBCE atualizada! Novos: {novas} | Total: {total}")
        print("-> Reconstruindo caches e metadados locais da BBCE...")
        atualizar_cache_e_metadata_bbce(df_final)
        print("[SUCESSO] Processo da BBCE concluído localmente com sucesso!")
        return True
        
    except Exception as e:
        print(f"\n[ERRO - BBCE] Falha durante o processo de automação/importação da BBCE: {str(e)}")
        # Tenta remover o arquivo temporário caso tenha sobrado
        if arquivo_baixado and os.path.exists(arquivo_baixado):
            try: os.remove(arquivo_baixado)
            except: pass
        return False

def main():
    while True:
        limpar_tela()
        print("="*60)
        print("      SISTEMA DE ATUALIZAÇÃO E ETL LOCAL - ENECEL")
        print("="*60)
        print("  [1] Atualizar Balanço Energético (ONS) + PLD Horário (CCEE)")
        print("  [2] Atualizar Histórico de Negócios BBCE (Automação Chrome)")
        print("  [3] Atualizar Tudo (ONS + CCEE + BBCE)")
        print("  [4] Apenas Sincronizar Arquivos Locais com o GitHub (Git Push)")
        print("  [5] Sair")
        print("="*60)
        
        opcao = input("Escolha uma opção (1-5): ").strip()
        
        if opcao == '1':
            executar_ons_ccee()
            sincronizar_github()
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == '2':
            sucesso = executar_bbce()
            if sucesso:
                sincronizar_github()
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == '3':
            executar_ons_ccee()
            sucesso = executar_bbce()
            sincronizar_github()
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == '4':
            sincronizar_github()
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == '5':
            print("\nFinalizando utilitário de ETL. Até logo!")
            time.sleep(1)
            break
        else:
            print("\nOpção inválida! Tente novamente.")
            time.sleep(1.5)

if __name__ == '__main__':
    main()
