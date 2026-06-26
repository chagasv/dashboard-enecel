import pandas as pd
import os

PLANILHAS_DIR = r"c:\Users\User\OneDrive\Cursos\Antigraviti + ClaudeCode - YT\projeto8_enecel\planilhas_para_atualizar"

print("--- CARGA_ENERGIA_2026.xlsx ---")
path_carga = os.path.join(PLANILHAS_DIR, "CARGA_ENERGIA_2026.xlsx")
if os.path.exists(path_carga):
    df_carga = pd.read_excel(path_carga)
    print("Colunas:", df_carga.columns.tolist())
    print("Tipos de dados:\n", df_carga.dtypes)
    print("Amostra:\n", df_carga.head(3))
    print("Subsistemas únicos:", df_carga['id_subsistema'].unique() if 'id_subsistema' in df_carga.columns else "Não encontrado")
else:
    print("Arquivo CARGA_ENERGIA_2026.xlsx não existe.")

print("\n--- carga_ONS_RVs.xlsx ---")
path_prevs = os.path.join(PLANILHAS_DIR, "carga_ONS_RVs.xlsx")
if os.path.exists(path_prevs):
    df_prevs = pd.read_excel(path_prevs)
    print("Colunas:", df_prevs.columns.tolist())
    print("Tipos de dados:\n", df_prevs.dtypes)
    print("Amostra:\n", df_prevs.head(3))
    print("Meses únicos:", df_prevs.iloc[:, 9].unique() if len(df_prevs.columns) > 9 else "Menos de 10 colunas")
else:
    print("Arquivo carga_ONS_RVs.xlsx não existe.")
