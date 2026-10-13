# Simulador de chapas municipais

Inicie a versão principal com:

```bash
bash simulador_chapas_2028/iniciar.sh
```

O arquivo `app.py` da raiz também abre essa mesma versão. A implementação e a documentação detalhada ficam em `simulador_chapas_2028/app_2028.py` e `simulador_chapas_2028/LEIA-ME.md`.

A versão anterior foi preservada em `app_legado.py` para consulta; ela não tem as reservas locais de federação nem os novos controles de composição.

Para executar os testes:

```bash
cd simulador_chapas_2028
.venv/bin/python -m unittest discover -s tests -v
```
