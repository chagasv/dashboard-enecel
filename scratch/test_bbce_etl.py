import os
import pandas as pd
import datetime
import sys

# Adiciona o diretório do projeto no path para importar o etl
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from etl import atualizar_negocios_bbce

base_teste = "scratch/base_teste_bbce.xlsx"
novos_teste = "scratch/novos_teste_bbce.xlsx"

try:
    print("=== INICIANDO TESTE DA ROTINA BBCE ETL ===")
    
    # 1. Cria dados fictícios da planilha base local
    dados_base = [
        {
            'PRODUTO': 'FEN - SE CON MEN MAI/26 - Preço Fixo',
            'DATA/HORA': datetime.datetime(2026, 6, 12, 10, 0, 0),
            'Q.N': 10.0, 'U.N.': 'MWm', 'Q.M': 7200, 'U.M.': 'MWh',
            'PREÇO': 200.0, 'TIPO DE CONTRATO': 'Negócio/Balcão',
            'TENDÊNCIA': 'Compra', 'STATUS': 'Ativo'
        },
        {
            'PRODUTO': 'FEN - SE CON MEN JUN/26 - Preço Fixo',
            'DATA/HORA': datetime.datetime(2026, 6, 12, 11, 0, 0),
            'Q.N': 5.0, 'U.N.': 'MWm', 'Q.M': 3600, 'U.M.': 'MWh',
            'PREÇO': 195.0, 'TIPO DE CONTRATO': 'Negócio/Balcão',
            'TENDÊNCIA': 'Venda', 'STATUS': 'Ativo'
        }
    ]
    df_base = pd.DataFrame(dados_base)
    df_base.to_excel(base_teste, index=False)
    print("Planilha base local de testes criada.")
    
    # 2. Cria dados novos contendo duplicatas e novos registros legítimos
    dados_novos = [
        # DUPLICADO EXATO da linha 1
        {
            'PRODUTO': 'FEN - SE CON MEN MAI/26 - Preço Fixo',
            'DATA/HORA': datetime.datetime(2026, 6, 12, 10, 0, 0),
            'Q.N': 10.0, 'U.N.': 'MWm', 'Q.M': 7200, 'U.M.': 'MWh',
            'PREÇO': 200.0, 'TIPO DE CONTRATO': 'Negócio/Balcão',
            'TENDÊNCIA': 'Compra', 'STATUS': 'Ativo'
        },
        # Legítimo: Novo negócio ocorrido após o último negócio local
        {
            'PRODUTO': 'FEN - SE CON MEN JUN/26 - Preço Fixo',
            'DATA/HORA': datetime.datetime(2026, 6, 12, 12, 0, 0),
            'Q.N': 15.0, 'U.N.': 'MWm', 'Q.M': 10800, 'U.M.': 'MWh',
            'PREÇO': 198.5, 'TIPO DE CONTRATO': 'Negócio/Balcão',
            'TENDÊNCIA': 'Compra', 'STATUS': 'Ativo'
        },
        # Legítimo: Novo negócio ocorrido em data anterior (para testar reordenação)
        {
            'PRODUTO': 'FEN - SE CON MEN MAI/26 - Preço Fixo',
            'DATA/HORA': datetime.datetime(2026, 6, 12, 9, 0, 0),
            'Q.N': 8.0, 'U.N.': 'MWm', 'Q.M': 5760, 'U.M.': 'MWh',
            'PREÇO': 201.0, 'TIPO DE CONTRATO': 'Negócio/Balcão',
            'TENDÊNCIA': 'Compra', 'STATUS': 'Ativo'
        }
    ]
    df_novos = pd.DataFrame(dados_novos)
    df_novos.to_excel(novos_teste, index=False)
    print("Planilha de novos negócios de testes criada.")
    
    # 3. Executa a função de atualização
    novos_adicionados, total_registros = atualizar_negocios_bbce(
        planilha_base_path=base_teste,
        planilha_novos_negocios_path=novos_teste
    )
    
    print(f"\nResultado da Importação:")
    print(f"Novas linhas adicionadas (esperado: 2): {novos_adicionados}")
    print(f"Total de registros na base final (esperado: 4): {total_registros}")
    
    # 4. Valida os registros gravados e a ordenação
    df_resultado = pd.read_excel(base_teste)
    print("\nPlanilha resultante ordenada:")
    print(df_resultado)
    
    # Verifica ordem cronológica das datas/horas
    datas = pd.to_datetime(df_resultado['DATA/HORA']).tolist()
    ordenado = (datas == sorted(datas))
    print(f"\nPlanilha está em ordem cronológica? {ordenado}")
    
    assert novos_adicionados == 2, f"Erro: Esperava 2 novos registros, obteve {novos_adicionados}"
    assert total_registros == 4, f"Erro: Esperava 4 registros no total, obteve {total_registros}"
    assert ordenado, "Erro: A planilha final não está reordenada cronologicamente!"
    
    print("\n=== TODOS OS TESTES PASSARAM COM SUCESSO! ===")
    
except Exception as e:
    print(f"\nFAILED: Erro durante a validação: {e}", file=sys.stderr)
    sys.exit(1)
    
finally:
    # Remove arquivos de teste
    for f in [base_teste, novos_teste]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Arquivo temporário de teste {f} removido.")
