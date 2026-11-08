# EDGY Betting

**EDGY Betting** é um painel mobile-first de **análise de futebol**. Recolhe calendários de jogos, permite registar probabilidades e odds com fontes identificadas, calcula valor esperado e apresenta uma classificação conservadora. **Não faz apostas, não acede a contas de casas de apostas e não inventa odds ou previsões.**

## Aceder e instalar

Site (publicação GitHub Pages verificada pelos workflows): https://bpsbeast.github.io/edgy-betting/

Desenvolvimento local: `python -m http.server 8080`, depois abrir `http://localhost:8080`. A interface não precisa de backend para ler os dados já sincronizados. `npm test` (Node 22+) valida as fórmulas e controlos de risco.

## Fontes de dados: integração e estado real

O programa **não inventa preços ou probabilidades** para preencher lacunas. É importante separar informação que foi recolhida de integrações apenas preparadas.

| Origem | Usado para | Integração | Observações |
| --- | --- | --- | --- |
| ESPN (não oficial) / TheSportsDB | Jogos, datas e resultados | Ativa | A cobertura pode variar e o feed ESPN pode falhar |
| Football-Data.co.uk | Resultados históricos, estatísticas e Poisson exploratório | Ativa | Não são as previsões independentes pedidas |
| Open-Meteo | Chuva, vento e temperatura na hora do jogo | Ativa **apenas quando existe cidade de estádio confirmada** | Previsão urbana não confirma condições no relvado; plano gratuito sujeito a uso não comercial |
| API-Football | Odds e probabilidades justas das casas | **Chave configurada**, cobertura efetiva limitada | API gratuita devolve preços, mas grande parte dos eventos globais não pertence às ligas selecionadas. As odds nunca equivalem ao boletim Betano. |
| API-Football | Lesões, castigos, onzes e previsões 1X2 próprias | **Ainda não há dados do período solicitado** | O plano gratuito não permite consultar fixtures 2026/27 nem o parâmetro `ids`; não substituir automaticamente Statarea/SportyTrader |
| Statarea / SportyTrader | Probabilidades independentes ponderadas | **Não ligadas** | Precisam de alimentação autorizada, sem inventar valores |
| SoccerVital / Statarea golos | Comportamento casa/fora e médias | **Não ligadas** | Exigem alimentação verificável com condições de utilização apropriadas |
| Soccernews.com | Notícias sobre indisponíveis | **Não ligada** | Sem API validada para extracção automática |
| Flashscore | Preços Betano/Betclic/Solverde/bwin | **Não ligado** | O serviço proíbe extração/republicação não autorizada |
| Betano (boletim PT) | Confirmação final da odd | **Não ligada** | A confirmação deve ser feita no boletim ou em feed com licença/consentimento |

### Ativar o fornecedor de odds e contexto

1. Criar conta no [API-Football](https://dashboard.api-football.com/) (plano gratuito limitado de 100 pedidos/dia, com limitações de cobertura de época).
2. No GitHub ir a **Settings → Secrets and variables → Actions → New repository secret**.
3. Criar a secret **`API_FOOTBALL_KEY`** com a chave da API. Nunca colocar esta chave em `app.js`, HTML, no chat público ou em `data/`.
4. Em **Actions**, executar o workflow **Refresh fixtures and publish EDGY Betting** manualmente ou deixar o agendamento regular atualizar.
5. Verificar os sinais das fontes na interface do jogo. Se um mercado não estiver disponível no fornecedor, permanece marcado como não verificado.

**A chave já foi configurada.** No plano gratuito a API devolve `Free plans do not have access to this season, try from 2022 to 2024` para a época atual e proíbe `ids`. Assim, definimos `API_FOOTBALL_FIXTURE_MAX_LEAGUES=0` e a associação das odds usa apenas os metadados do próprio feed, sem pedidos proibidos. A recolha direcionada de odds consulta por omissão até 3 competições/datas próximas, interrompendo as tentativas se surgir um erro de plano. Mesmo com chave ativa, **não há garantia de preço Betano, de jogos 2026/27 ou de cobertura de todos os mercados**.

Os ficheiros de dados incluem `data/context.json` (meteorologia, onzes, lesões, previsões e proveniência) e `data/market_odds.json` (odds e consenso justo de várias casas quando disponíveis). `scripts/sync_odds.py` também guarda alterações dos preços observados ao longo das sincronizações, mas isso **não mede dinheiro efetivamente apostado**. Os scripts nunca tentam contornar proteções do Flashscore ou Betano.

### Correspondência entre odds e calendário

Os identificadores ESPN e API-Football são diferentes. No plano gratuito, **não existe confirmação automática das equipas para um preço recolhido**. A app preserva a separação entre:

- `linkedFixtureIds`: apenas correspondências por identidade verificada, nunca fabricadas.
- `provisionalFixtureIds`: correspondências únicas por competição e hora, **não verificadas nas equipas**. São sinalizadas na interface, não podem fundamentar uma aposta aprovada.
- Sem correspondência: odds não são atribuídas a qualquer jogo.

O feed gratuito pode apresentar início `00:00 UTC` para vários encontros; essa hora não equivale necessariamente à hora de jogo. Se a liga e o horário não identificarem univocamente um encontro, o programa não deve associar preços. A recolha global anteriormente devolvia sobretudo mercados fora das seis ligas pedidas, pelo que agora é feita uma pesquisa direcionada por competição e data.

### Critérios que continuam a bloquear Aposta

Sem 2 fontes independentes favoráveis, sem preço confirmado no boletim, com onzes/contexto não verificados ou com sinais de risco relevantes, a decisão é **OBSERVAR** e nunca **APOSTA**. Os parâmetros de incerteza e o Poisson histórico não foram estatisticamente calibrados/backtestados e não representam uma garantia de lucratividade.

## O que funciona nesta versão

### Radar automático — versão 1.1

A página principal já mostra os **jogos reais** automaticamente, sem obrigar a selecionar e preencher tudo manualmente. Ao selecionar um encontro:
- Distribuição de **resultados 1 / X / 2**, **mais/menos de 1,5 e 2,5 golos**, **ambas marcam** e **dois resultados exatos** com maior probabilidade, sempre identificados como **Poisson exploratório**.
- Estimativa de golos por equipa e médias das últimas partidas em casa/fora.
- **Odd mínima teórica** que corresponderia a 3 pontos de edge após a penalização de incerteza do modelo exploratório, **não é recomendação validada**.
- Preço de referência, nome da casa e probabilidade justa sem margem **quando** houver API-Football configurada e mercado disponível.
- Filtros "Com análise", "Com odds" e "Sem dados suficientes".
- **Zero apostas aprovadas automaticamente** sem Statarea, SportyTrader/SoccerVital, consenso real, preço validado e verificações contextuais.

Os resultados históricos são obtidos em CSV de **[Football-Data.co.uk](https://www.football-data.co.uk/)** para a época corrente (até 11 divisões quando disponíveis). São dados diferentes das previsões da Statarea e SportyTrader: servem **só** para uma projeção estatística exploratória, não contam automaticamente como as duas fontes de consenso das regras.

O código de recolha está em `scripts/sync_analysis.py` e o resultado em `data/analysis.json`. Não inclui dados inventados; quando o histórico ou um mercado falta, a UI mostra esse estado.

**Odds opcionais:** a integração `scripts/sync_odds.py` consome odds pré-jogo da API-Football (máximo 3 páginas por dia de dois dias), reconhece mercados 1X2, over/under 1,5 ou 2,5 e ambas marcam, e grava preços com identificação da casa em `data/market_odds.json`. Sem a secret `API_FOOTBALL_KEY`, não apresenta odds. Mesmo uma odd de um bookmaker chamado Betano na API é uma **referência**, não uma odd confirmada no boletim.

- Interface responsiva com jogos pesquisáveis, filtros Hoje / Amanhã / Em direto, seleção de competições e inspeção por jogo.
- Sincronização real em `scripts/sync_fixtures.py` via GitHub Actions (quatro vezes por dia e quando há alterações no código).
- **ESPN:** feed público não oficial; pode mudar, falhar, ou não cobrir algumas competições.
- **TheSportsDB:** API gratuita, usada como fallback limitado. A edição gratuita pode devolver apenas um próximo jogo por liga. Respeita os termos e atribuição do fornecedor.
- **API-Football (opcional):** se criares o secret GitHub Actions `API_FOOTBALL_KEY`, o sincronizador inclui fixtures via API autenticada. Este serviço tem limites de utilização e cobertura por plano/temporada.
- Zero odds inventadas: a app recolhe preços de referência com credenciais ou o utilizador introduz a odd observada e assinala se a confirmou na Betano.
- Probabilidades por fonte: odds **justas sem margem** do mercado (peso 3), Statarea (1), SportyTrader (1), SoccerVital (0,5), Statarea golos (0,5; entre ligas 0,15), ESPN cantos/remates (1).
- Ajustes contextuais **apenas nas fontes não-mercado**, com origem manual explícita: ausências, rotação, descanso, onzes, importância e meteorologia.
- Edge, edge ajustado, retorno esperado e sugestão teórica de stake (menor entre 1% da banca e 10% de Kelly prudente).
- Stop semanal de -3%, máximo diário configurável, máximo duas seleções por jogo e bloqueio de mercados correlacionados.
- Registos locais em `localStorage` com possibilidade de remoção; não existe conta nem sincronização remota.

## Avaliação e critérios

1. **Casa**: `1 / odd`. **Nossa**: média ponderada de fontes preenchidas que façam sentido para o mercado.
2. **Incerteza**: base por mercado, divergência entre probabilidades e penalização por poucas fontes; a incerteza é **10% maior** nas segundas divisões. Os valores-base são parâmetros conservadores da implementação, não parâmetros estatisticamente calibrados.
3. **Edge**: `p_nossa - 1/odd`. **Edge ajustado**: `edge - prudencia * incerteza`.
4. **EV para aposta binária**: `p_nossa * odd - 1`. Para mercados com devolução total (empate anula, asiáticos inteiros), o EV é `p_vitoria*(odd-1)-p_derrota` e o Kelly é calculado com a probabilidade condicional à não devolução. Asiáticos com 1/4 de linha ficam em observar por não estarem modelados.
5. **Aposta** exige 3 p.p. de edge ajustado, duas fontes independentes favoráveis, odd nos limites, nenhuma exclusão crítica, sem alerta de mercado ou correlação, e Betano marcada como confirmada manualmente.
6. **Verificar** passa nos critérios mas a odd é de referência ou não está confirmada. A **odd mínima** calculada permite verificar se a odd Betano oferece o edge ajustado pretendido.
7. **Observar** quando falta consenso, existe incerteza, risco, preço divergente (>18 p.p. como limiar inicial configurado em código), mercado contrário ou dados insuficientes. Cantos e remates ficam sempre em observar nesta versão porque só a ESPN fornece a estatística dedicada.
8. **Excluída** quando há rotação forte ou meteorologia crítica assinaladas pelo utilizador.
9. As probabilidades justas na abertura e agora, de várias casas, podem ser introduzidas. Redução da probabilidade justa em mais de 1,5 p.p. na maioria de pelo menos duas casas faz a análise descer para observar. Isto é um **proxy de pressão de preço**, não mede volumes reais nem prova entrada/saída de dinheiro.

**Limites iniciais editáveis:** odd de 1,30 a 5,00, máximo 3 seleções guardadas/dia, prudência 1, banca exemplo 100 €. Estes números não foram fornecidos pelo utilizador como parâmetros obrigatórios: podem ser alterados no painel.

## O que falta para automação completa da especificação

- Odds de todos os mercados da **Betano / Flashscore**: **não integradas**. Essas plataformas não oferecem aqui um feed gratuito, público e documentado de todos os mercados. A recolha automática depende de fornecedor licenciado, termos e credenciais válidas; não usar automação de login, contornar proteção nem alegar odds em tempo real sem dados.
- Históricos justos de cinco casas: introdução manual possível, integração automática pendente.
- Statarea, SportyTrader, SoccerVital e Soccernews: fontes **a consultar/importar**, sem ligação oficial automática nesta versão.
- Onzes, lesões, cartões e estatísticas de cantos/remates: não recolhidos automaticamente para avaliação; a ESPN pode fornecer dados desportivos, mas a transformação em probabilidades calibradas está pendente.
- Tempo via Open-Meteo: previsto, não utilizado até existirem localizações validadas dos estádios e horários fiáveis.
- A projeção exploratória por Poisson já inclui resultados exatos; cantos, remates, intervalos, minutos, combinadas e asiáticos de quarto ainda não têm modelos automáticos calibrados para aprovação. Isto **não é** um sinal automático de aposta.

## Segurança e credibilidade

Os caches `data/fixtures.json`, `data/analysis.json` e `data/market_odds.json` identificam respetivamente os jogos, as projeções históricas e as odds de referência. Se faltar o feed, o painel mostra indisponibilidade em vez de criar partidas. Não coloques chaves em ficheiros públicos: usa **Settings → Secrets and variables → Actions**. O JavaScript corre no navegador e nunca envia informações bancárias a servidores nossos; os dados manuais só ficam no dispositivo via armazenamento local.

Dados desportivos: [TheSportsDB](https://www.thesportsdb.com/) e [ESPN](https://www.espn.com/soccer/) (integração de calendário não oficial), [API-Football](https://www.api-football.com/) se configurado. O utilizador é responsável por confirmar as odds e respeitar as condições aplicáveis. Nenhum algoritmo garante lucro.

## Estrutura

```text
index.html             Interface
styles.css             Design responsivo
app.js                 Calendário, formulários e lista local
src/engine.js          Fórmulas, classificação e risco
scripts/sync_fixtures.py  Ingestão do calendário
scripts/sync_analysis.py  Modelos históricos com CSVs de resultados
scripts/sync_odds.py      Odds de referência opcionais
data/fixtures.json     Calendário sincronizado
data/analysis.json     Projeções exploratórias por jogo
data/market_odds.json  Odds de referência, quando configuradas
tests/engine.test.js   Testes do motor de decisão
tests/test_analysis.py  Testes do modelo e dos nomes de equipas
.github/workflows/refresh.yml  Sincronizar, testar e publicar
```
