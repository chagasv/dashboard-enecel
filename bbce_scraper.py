import os
import time
import glob
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def executar_automacao_bbce(data_inicio_str, data_fim_str, logger_func=print):
    """
    Executa a automação no portal eHub BBCE para extrair negócios no período especificado.
    
    data_inicio_str: data no formato DD/MM/AAAA (ex: "13/06/2026")
    data_fim_str: data no formato DD/MM/AAAA (ex: "16/06/2026")
    """
    logger_func(f"Iniciando automação BBCE. Período: {data_inicio_str} até {data_fim_str}")
    
    # Configura pasta temporária de downloads dentro do projeto
    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_download_dir = os.path.join(base_dir, 'temp_downloads')
    os.makedirs(temp_download_dir, exist_ok=True)
    
    # Limpa arquivos xlsx antigos na pasta temporária para evitar ler arquivo errado
    for f in glob.glob(os.path.join(temp_download_dir, "*.xlsx")):
        try: os.remove(f)
        except: pass
    for f in glob.glob(os.path.join(temp_download_dir, "*.xls")):
        try: os.remove(f)
        except: pass
        
    logger_func("Configurando conexão com o navegador Chrome ativo...")
    driver = None
    try:
        # Bloco de conexão isolado
        try:
            logger_func("Tentando se conectar ao Google Chrome ativo na porta 9222...")
            options = webdriver.ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except Exception as e_driver:
                logger_func(f"Aviso na inicialização do serviço: {str(e_driver)}. Tentando inicialização direta...")
                driver = webdriver.Chrome(options=options)
                
            logger_func("Conectado com sucesso ao Chrome ativo!")
            
            # 1. Gerenciar abas/guias
            logger_func("Localizando abas do Chrome...")
            abas = driver.window_handles
            aba_bbce_handle = None
            
            for handle in abas:
                try:
                    driver.switch_to.window(handle)
                    current_url = driver.current_url
                    if "ehub.bbce.com.br" in current_url:
                        aba_bbce_handle = handle
                        logger_func("Aba do eHub BBCE detectada. Reutilizando a sessão ativa.")
                        break
                except Exception:
                    continue
                    
            if aba_bbce_handle is None:
                logger_func("Nenhuma aba da BBCE aberta encontrada. Abrindo nova aba...")
                driver.execute_script("window.open('about:blank', '_blank');")
                # Alterna para a aba aberta (última na lista)
                driver.switch_to.window(driver.window_handles[-1])
                logger_func("Acessando portal eHub BBCE...")
                driver.get("https://ehub.bbce.com.br/pos-negociacao/relatorios")
                
        except Exception as e:
            logger_func("[ERROR] Não foi possível conectar ao navegador Chrome na porta 9222.")
            logger_func("Isso ocorre porque o Chrome ativo não está com a depuração remota habilitada.")
            logger_func("Para corrigir:")
            logger_func("1. Feche todas as janelas do Google Chrome abertas.")
            logger_func("2. Inicie o dashboard através do 'run.bat' (ele tentará habilitar a depuração).")
            logger_func("3. Ou execute no seu terminal (cmd/PowerShell):")
            logger_func('   start chrome "http://localhost:5000" --remote-debugging-port=9222')
            logger_func("4. Abra seu Chrome normalmente a partir daí e tente novamente.")
            logger_func(f"Detalhes técnicos do erro: {str(e)}")
            raise Exception("Erro de conexão com o Chrome ativo. Certifique-se de que a depuração remota na porta 9222 está ativa.")
        
        # 1. Espera de login assistida (Até 10 minutos)
        logger_func("Aguardando login do usuário. Se você não estiver logado, por favor, realize a autenticação e passe pelo 2FA na janela do navegador.")
        logado = False
        for i in range(200): # 200 iterações * 3s = 600s (10 minutos)
            if not driver:
                break
            try:
                current_url = driver.current_url
                if "/login" in current_url:
                    if i % 10 == 0:
                        logger_func("Por favor, digite seu login e senha e resolva o MFA/Captcha na janela aberta do Chrome...")
                elif "/pos-negociacao/relatorios" in current_url or "/relatorios" in current_url:
                    logger_func("Autenticação bem-sucedida! Entrando na área de relatórios...")
                    logado = True
                    break
            except Exception as e:
                # O usuário pode ter fechado a janela
                raise Exception("Navegador fechado pelo usuário ou erro de conexão.")
            time.sleep(3)
            
        if not logado:
            raise Exception("Tempo limite esgotado para o login do usuário.")
            
        # Espera carregamento da página de relatórios
        time.sleep(5)
        
        # 2. Localizar inputs de data e preenchê-los
        logger_func("Localizando campos de filtro na página...")
        
        # Procura inputs de data
        inputs = driver.find_elements(By.XPATH, "//input")
        inputs_data = []
        for inp in inputs:
            try:
                if inp.is_displayed() and inp.is_enabled():
                    placeholder = str(inp.get_attribute("placeholder")).lower()
                    val = str(inp.get_attribute("value"))
                    inp_type = str(inp.get_attribute("type")).lower()
                    
                    if "/" in val or "/" in placeholder or "data" in placeholder or "date" in placeholder or inp_type == "date":
                        inputs_data.append(inp)
            except:
                continue
                
        # Se não acharmos por esse critério, pegamos os primeiros inputs visíveis de texto
        if len(inputs_data) < 2:
            inputs_data = []
            for inp in inputs:
                try:
                    if inp.is_displayed() and inp.is_enabled():
                        t = inp.get_attribute("type")
                        if t not in ["checkbox", "radio", "hidden", "file", "submit", "button"]:
                            inputs_data.append(inp)
                except:
                    continue
                    
        if len(inputs_data) < 2:
            raise Exception("Não foi possível localizar os dois campos de filtro de data na página da BBCE.")
            
        input_inicio = inputs_data[0]
        input_fim = inputs_data[1]
        
        logger_func(f"Preenchendo Data Inicial: {data_inicio_str}")
        input_inicio.click()
        time.sleep(0.5)
        input_inicio.send_keys(Keys.CONTROL + "a")
        time.sleep(0.2)
        input_inicio.send_keys(Keys.BACKSPACE)
        time.sleep(0.2)
        input_inicio.send_keys(data_inicio_str)
        input_inicio.send_keys(Keys.TAB)
        time.sleep(0.5)
        
        logger_func(f"Preenchendo Data Final: {data_fim_str}")
        input_fim.click()
        time.sleep(0.5)
        input_fim.send_keys(Keys.CONTROL + "a")
        time.sleep(0.2)
        input_fim.send_keys(Keys.BACKSPACE)
        time.sleep(0.2)
        input_fim.send_keys(data_fim_str)
        input_fim.send_keys(Keys.TAB)
        time.sleep(1.0)
        
        # 3. Clicar no botão CONSULTAR
        logger_func("Clicando no botão CONSULTAR...")
        botoes_consultar = driver.find_elements(By.XPATH, "//*[contains(text(), 'CONSULTAR') or contains(text(), 'Consultar')]")
        if not botoes_consultar:
            raise Exception("Não foi possível localizar o botão 'CONSULTAR' na página.")
        
        # Tenta clicar no primeiro botão visível
        clicado_consultar = False
        for btn in botoes_consultar:
            try:
                if btn.is_displayed():
                    btn.click()
                    clicado_consultar = True
                    break
            except:
                continue
                
        if not clicado_consultar:
            # Fallback direto via click javascript
            driver.execute_script("arguments[0].click();", botoes_consultar[0])
            clicado_consultar = True
            
        time.sleep(4) # Espera carregar a consulta
        logger_func("Consulta realizada. Solicitando exportação para planilha...")
        
        # 4. Clicar no link/ícone Planilha
        links_planilha = driver.find_elements(By.XPATH, "//*[contains(text(), 'Planilha')]")
        if not links_planilha:
            raise Exception("Não foi possível encontrar o botão 'Planilha' para exportação.")
            
        clicado_planilha = False
        for link in links_planilha:
            try:
                if link.is_displayed():
                    link.click()
                    clicado_planilha = True
                    break
            except:
                continue
                
        if not clicado_planilha:
            driver.execute_script("arguments[0].click();", links_planilha[0])
            
        # 5. Esperar alguns segundos para geração da planilha
        logger_func("Exportação solicitada. Aguardando processamento da planilha (10 segundos)...")
        time.sleep(10)
        
        # 6. Clicar em Alertas (ícone do sino)
        logger_func("Abrindo notificações (Alertas)...")
        # Procura o sino por ícone de notificação ou classe
        sinos = driver.find_elements(By.XPATH, "//*[contains(@class, 'bell') or contains(@class, 'notification') or contains(@class, 'sino') or text()='notifications' or text()='notifications_none']")
        
        # Se não achar por classes, procura elementos no topo superior direito
        if not sinos:
            # No print, o sino é o penúltimo ícone no cabeçalho superior direito.
            # Vamos tentar procurar elementos mat-icon ou spans de alerta
            sinos = driver.find_elements(By.TAG_NAME, "mat-icon")
            
        clicado_sino = False
        for sino in sinos:
            try:
                if sino.is_displayed():
                    sino.click()
                    clicado_sino = True
                    break
            except:
                continue
                
        if not clicado_sino:
            # Caso não consiga clicar, vamos tentar buscar especificamente na área superior
            # Usando uma busca genérica e clicando no penúltimo/último mat-icon
            elementos_cabecalho = driver.find_elements(By.XPATH, "//header//mat-icon | //div[contains(@class, 'header')]//mat-icon")
            if elementos_cabecalho:
                elementos_cabecalho[-1].click()
                clicado_sino = True
                
        if not clicado_sino:
            raise Exception("Não foi possível encontrar o ícone de notificações (Sino) no topo da tela.")
            
        time.sleep(3) # Aguarda gaveta de notificações abrir
        
        # 7. Clicar no link "Clique Aqui" da última notificação
        logger_func("Localizando link de download da planilha...")
        links_download = driver.find_elements(By.XPATH, "//a[contains(text(), 'Clique Aqui') or contains(text(), 'Clique aqui') or contains(text(), 'clique aqui') or contains(text(), 'aqui')]")
        if not links_download:
            # Tenta buscar por links gerais dentro da lista de notificações se houver
            # Geralmente é uma tag <a> com href ou contendo texto de download
            links_download = driver.find_elements(By.XPATH, "//div[contains(@class, 'notific')]//a | //mat-list-item//a")
            
        if not links_download:
            raise Exception("Nenhuma notificação com link de download ('Clique Aqui') foi encontrada na lista.")
            
        # O último alerta (mais recente) costuma ser o primeiro na lista
        logger_func("Disparando download do arquivo Excel...")
        links_download[0].click()
        
        # 8. Aguardar o download ser concluído
        logger_func("Aguardando conclusão do download...")
        arquivo_baixado = None
        user_download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        for _ in range(60): # Até 60 segundos
            # Verifica se há arquivos temporários de download em andamento
            temp_files_project = glob.glob(os.path.join(temp_download_dir, "*.crdownload"))
            temp_files_user = glob.glob(os.path.join(user_download_dir, "*.crdownload"))
            
            if not temp_files_project and not temp_files_user:
                # Procura por xlsx ou xls
                candidatos = []
                for pasta in [temp_download_dir, user_download_dir]:
                    if os.path.exists(pasta):
                        arquivos = glob.glob(os.path.join(pasta, "*.xlsx")) + glob.glob(os.path.join(pasta, "*.xls"))
                        for arq in arquivos:
                            mtime = os.path.getmtime(arq)
                            # Se foi modificado após o início da automação (com folga de 5 segundos)
                            if mtime > (inicio_automacao - 5):
                                candidatos.append((arq, mtime, pasta == user_download_dir))
                
                if candidatos:
                    # Ordena pelos mais recentes
                    candidatos.sort(key=lambda x: x[1], reverse=True)
                    arq_escolhido, _, is_user_dir = candidatos[0]
                    
                    if is_user_dir:
                        # Se estiver no diretório do usuário, faz uma cópia para o projeto para evitar deletar o arquivo original dele
                        import shutil
                        nome_temp = f"bbce_temp_{int(time.time())}_{os.path.basename(arq_escolhido)}"
                        caminho_copia = os.path.join(temp_download_dir, nome_temp)
                        shutil.copy2(arq_escolhido, caminho_copia)
                        logger_func(f"Download detectado em Downloads do usuário: {os.path.basename(arq_escolhido)}. Copiado para processamento.")
                        arquivo_baixado = caminho_copia
                    else:
                        logger_func(f"Download detectado na pasta do projeto: {os.path.basename(arq_escolhido)}")
                        arquivo_baixado = arq_escolhido
                    break
            time.sleep(1)
            
        if not arquivo_baixado:
            raise Exception("Tempo limite esgotado para o download do arquivo.")
            
        logger_func(f"Download concluído com sucesso: {os.path.basename(arquivo_baixado)}")
        return arquivo_baixado
        
    finally:
        if driver:
            logger_func("Conclusão do processo. Desconectando do Chrome...")
            # Nota: Não chamamos driver.quit() para evitar fechar a janela ativa do próprio usuário.
