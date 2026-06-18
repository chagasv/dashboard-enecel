import os
import shutil
import pandas as pd

src = "planilhas_para_atualizar/f_todos_os_negocios_bbce.xlsx"
dst = "scratch/temp_bbce_stats.xlsx"

try:
    print("Copiando planilha...")
    shutil.copy2(src, dst)
    print("Lendo planilha inteira...")
    df = pd.read_excel(dst)
    
    # 1. Total de registros
    print(f"Total de registros: {len(df)}")
    
    # 2. Produtos únicos
    produtos_unicos = df['PRODUTO'].nunique()
    print(f"Produtos únicos: {produtos_unicos}")
    print("\nTop 15 produtos mais negociados:")
    print(df['PRODUTO'].value_counts().head(15))
    
    # 3. Tipos de contrato únicos
    print("\nTipos de contrato únicos:")
    print(df['TIPO DE CONTRATO'].value_counts())
    
    # 4. Tendências únicas
    # O nome da coluna pode ter caracteres especiais, vamos achar o nome exato
    tendencia_col = [c for c in df.columns if 'tend' in c.lower()][0]
    print(f"\nTendências únicas ({tendencia_col}):")
    print(df[tendencia_col].value_counts(dropna=False))
    
    # 5. Status únicos
    print("\nStatus únicos:")
    print(df['STATUS'].value_counts())
    
    # 6. Agrupamento por dia (quantos dias únicos?)
    df['DATA_DIA'] = pd.to_datetime(df['DATA/HORA']).dt.date
    dias_unicos = df['DATA_DIA'].nunique()
    print(f"\nDias únicos de negociação: {dias_unicos}")
    
    # 7. Distribuição por Submercado (se der para extrair do produto)
    # Produtos costumam ter "SE" (Sudeste), "S" (Sul), "NE" (Nordeste), "N" (Norte) no nome
    # Vamos ver se podemos criar uma coluna de submercado extraída do produto
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
        
    df['SUBMERCADO'] = df['PRODUTO'].apply(extrair_submercado)
    print("\nDistribuição aproximada por Submercado extraído do Produto:")
    print(df['SUBMERCADO'].value_counts())
    
    # 8. Extrair também o tipo de produto (Mensal, Trimestral, Anual etc)
    # Ex: "MEN" (Mensal), "TRI" (Trimestral), "SEM" (Semestral), "ANU" (Anual)
    def extrair_tipo_produto(prod):
        prod = str(prod).upper()
        if ' MEN ' in prod: return 'Mensal'
        if ' TRI ' in prod: return 'Trimestral'
        if ' SEM ' in prod: return 'Semestral'
        if ' ANU ' in prod: return 'Anual'
        return 'Outros'
        
    df['TIPO_PRODUTO'] = df['PRODUTO'].apply(extrair_tipo_produto)
    print("\nDistribuição por Tipo de Produto extraído:")
    print(df['TIPO_PRODUTO'].value_counts())

except Exception as e:
    print(f"Erro: {e}")
finally:
    if os.path.exists(dst):
        os.remove(dst)
        print("Arquivo temporário removido.")
