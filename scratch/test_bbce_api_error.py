import os
import sys

# Adiciona o diretorio do projeto ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import atualizar_cache_e_metadata_bbce, PATH_BBCE

print("Caminho do BBCE:", PATH_BBCE)
print("Existe?", os.path.exists(PATH_BBCE))

try:
    atualizar_cache_e_metadata_bbce()
    print("Sucesso!")
except Exception as e:
    import traceback
    traceback.print_exc()
