# Streamlit Community Cloud

Configuração do aplicativo:

- Repositório: `dionatandiego11/simulador-chapas-2028`
- Branch: `main`
- Main file path: `app.py`
- Python: `3.12`, em Advanced settings

Abra https://share.streamlit.io, escolha Create app e preencha os campos acima. O repositório é privado; se ele não aparecer, autorize o acesso do Streamlit ao repositório no GitHub.

O `requirements.txt` da raiz referencia as versões testadas no diretório do aplicativo. Os CSVs históricos estão no repositório. Não é necessário cadastrar secrets para esta versão.

O envio para o GitHub prepara a publicação, mas o deploy só termina após criar o aplicativo no painel do Streamlit e confirmar que ele iniciou sem erros. Cadastros e composições são individuais por sessão e não ficam salvos permanentemente no servidor.

Para publicar futuras alterações:

```bash
git add app.py requirements.txt simulador_chapas_2028
git commit -m "Atualiza o simulador"
git push origin main
```

Documentação oficial: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
