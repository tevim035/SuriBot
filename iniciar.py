"""
Liga o bot usando as bibliotecas da venv312 sem executar venv312\\Scripts\\python.exe,
que o Controle Inteligente de Aplicativos do Windows bloqueia (o arquivo não é assinado).
Rode com o Python base da venv (o caminho está em venv312\\pyvenv.cfg, na linha "home").
"""

import os
import runpy
import site
import sys

pasta = os.path.dirname(os.path.abspath(__file__))
site.addsitedir(os.path.join(pasta, "venv312", "Lib", "site-packages"))

os.chdir(pasta)
sys.argv = [os.path.join(pasta, "main.py")]
runpy.run_path(sys.argv[0], run_name="__main__")
