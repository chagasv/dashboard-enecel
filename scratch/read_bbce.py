import os
import shutil
import pandas as pd

src = "planilhas_para_atualizar/f_todos_os_negocios_bbce.xlsx"
dst = "scratch/temp_bbce.xlsx"

try:
    print("Tentando copiar planilha...")
    shutil.copy2(src, dst)
    print("Cópia realizada. Lendo dados...")
    df = pd.read_excel(dst, nrows=10)
    print("Colunas encontradas:")
    print(df.columns.tolist())
    print("\nPrimeiras linhas:")
    print(df.head())
    print("\nInformações de tipos:")
    print(df.dtypes)
    
    # Vamos ver também o tamanho total da planilha (número de linhas)
    print("\nLendo planilha inteira para contar linhas...")
    df_all = pd.read_excel(dst)
    print(f"Total de registros na base atual: {len(df_all)}")
    
    # Encontrar a data/hora mais recente
    # Vamos procurar colunas que pareçam data
    date_cols = [c for c in df_all.columns if 'data' in c.lower() or 'hora' in c.lower()]
    print(f"Colunas de data potenciais: {date_cols}")
    for col in date_cols:
        try:
            max_val = df_all[col].max()
            print(f"Valor máximo em {col}: {max_val}")
        except Exception as ex:
            print(f"Erro ao obter máximo da coluna {col}: {ex}")
            
except Exception as e:
    print(f"Erro geral: {e}")
finally:
    if os.path.exists(dst):
        os.remove(dst)
        print("Arquivo temporário removido.")
