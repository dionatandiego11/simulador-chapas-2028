# Simulador de chapas 2028

## Iniciar

No diretório do projeto:

```bash
bash simulador_chapas_2028/iniciar.sh
```

O script cria o ambiente virtual e instala as dependências. O `app.py` da raiz abre a mesma versão. A versão anterior fica em `app_legado.py`.

## Fluxo de trabalho

1. Na lateral, confira o município e selecione partidos ou federações. Os CSVs locais são carregados automaticamente; uploads têm preferência.
2. Configure as reservas da federação e a base da pré-seleção. Para Itaguara/MG, o cenário inicial usa PT até 5, PV até 5 e PCdoB zero, dentro do limite conjunto de 10. A divisão é editável.
3. Cadastre estreantes se necessário. Eles ficam disponíveis em todos os destinos, com gênero, estimativa e observação.
4. Monte e edite as listas. A composição ativa é a única tabela exibida em cada cartão.
5. Confira os gêneros, a votação e os totais. Exporte a composição por pessoa e o resumo por chapa.

A consulta ao histórico fica em um único painel recolhível, com busca por nome e opção de aplicar os filtros.

## Montagem e edição

Cada partido de destino tem um seletor de nomes e um painel “Buscar e trocar nomes”. O painel permite consultar pessoas de outras siglas e filtrar pelo último partido observado. O histórico original permanece no CSV.

Para trocar numa lista cheia, selecione quem sai e quem entra e clique em “Aplicar edição”. Para apenas retirar ou incluir, deixe o outro campo em “Nenhum”. Também é possível remover pelo × do seletor ou esvaziar uma lista. Para mover alguém entre destinos, retire-o da origem primeiro.

A primeira seleção de uma chapa recebe uma sugestão automática. “Aplicar pré-seleção” substitui as listas ativas pelas sugestões calculadas naquele momento. Alterar o recorte atualiza listas ainda intactas, mas preserva listas editadas manualmente. Alterar pesos, estimativas ou gêneros atualiza os cálculos sem sobrescrever a composição. Desmarcar e remarcar uma chapa preserva suas escolhas na sessão. Trocar município ou arquivos inicia uma composição para os novos dados.

Reduzir uma reserva retira os nomes excedentes do fim da lista e informa quantos foram retirados. Reservas cuja soma ultrapassa o limite conjunto impedem edição e exportação até o ajuste.

## Votação

Pré-seleção e projeção usam os mesmos pesos: inicialmente 2 para 2016, 3 para 2020 e 5 para 2024. A pré-seleção compara a média ponderada relativa ao QE, priorizando vínculos históricos. A projeção calcula a média ponderada dos votos nominais de cada pessoa.

Por padrão, anos sem candidatura não entram no denominador. Quem teve 100 votos em 2016 e 400 em 2024 recebe `(100 × 2 + 400 × 5) / 7 = 314,29` votos projetados. A opção de tratar ausência como zero inclui as ausências no cálculo.

Anos cujo arquivo não foi carregado têm peso zero e nunca são tratados como ausência de candidatura. Sem peso positivo, as médias ficam pendentes e a aplicação de pré-seleção fica desativada; as listas continuam editáveis manualmente.

Estreantes usam a estimativa informada. Campo vazio é uma pendência; zero é uma estimativa explícita. Cadastros em lote aceitam `Nome;Observação`; suas estimativas são editáveis no painel dos novos nomes.

Total da chapa = soma dos nominais projetados + votos exclusivamente de legenda informados. A legenda é contada uma única vez por chapa, inclusive na federação. Pendências são indicadas como projeção parcial.

Os valores são cenários aritméticos baseados no histórico e em estimativas, sem cálculo de probabilidade de vitória ou distribuição de cadeiras.

## Gênero e dados históricos

O mínimo de 30% arredonda toda fração para cima. Uma lista com 5 nomes exige ao menos 2 de cada gênero; com 8, exige 3. A conferência acontece por membro e no conjunto da federação. Partidos isolados exibem uma única conferência. Gêneros desconhecidos impedem a confirmação, mas permitem exportar uma composição exploratória.

O sistema usa `ds_genero` quando disponível ou os dados informados no cadastro e no campo em lote. Não deduz gênero pelo nome.

Os CSVs aceitam UTF-8, UTF-8 com BOM e ISO-8859-1. Linhas exatamente duplicadas são removidas na leitura. Nomes vazios não viram “nan”. O município é distinguido pela UF para evitar misturar localidades homônimas. Homônimos entre pessoas e mudanças de nome ainda exigem conferência.

Federações, equivalências e limites têm referência em 2024. Participação local, filiação atual, disponibilidade e regras de 2028 precisam ser conferidas. Os dados fornecidos não individualizam votos exclusivamente de legenda.

## Estrutura e testes

- `app_2028.py`: interface e estado do cenário.
- `motor.py`: leitura, histórico, filtros, pré-seleção, edição e cotas.
- `projecao.py`: médias e totais de votação.
- `tests/`: testes de cálculo e dos fluxos da interface.

```bash
cd simulador_chapas_2028
.venv/bin/python -m unittest discover -s tests -v
```

Cadastros e composições ficam na sessão. Exporte antes de encerrar.
