# EDGY Betting

**EDGY Betting** é um painel mobile-first de **análise de futebol**. Recolhe calendários de jogos, permite registar probabilidades e odds com fontes identificadas, calcula valor esperado e apresenta uma classificação conservadora. **Não faz apostas, não acede a contas de casas de apostas e não inventa odds ou previsões.**

## Aceder e instalar

Site (depois de ativares o GitHub Pages em **Settings → Pages → Source: GitHub Actions**): https://bpsbeast.github.io/edgy-betting/

Desenvolvimento local: `python -m http.server 8080`, depois abrir `http://localhost:8080`. A interface não precisa de backend para análise manual. `npm test` (Node 22+) valida as fórmulas e controlos de risco.

## O que funciona nesta versão

- Interface responsiva com jogos pesquisáveis, filtros Hoje / Amanhã / Em direto, seleção de competições e inspeção por jogo.
- Sincronização real em `scripts/sync_fixtures.py` via GitHub Actions (quatro vezes por dia e quando há alterações no código).
- **ESPN:** feed público não oficial; pode mudar, falhar, ou não cobrir algumas competições.
- **TheSportsDB:** API gratuita, usada como fallback limitado. A edição gratuita pode devolver apenas um próximo jogo por liga. Respeita os termos e atribuição do fornecedor.
- **API-Football (opcional):** se criares o secret GitHub Actions `API_FOOTBALL_KEY`, o sincronizador inclui fixtures via API autenticada. Este serviço tem limites de utilização e cobertura por plano/temporada.
- Zero odds inventadas: o utilizador introduz a odd observada e assinala se a confirmou na Betano.
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
- Resultados e eventos de mercado (exato, cantos, remates, combinadas): o motor aceita probabilidades para esses mercados, mas ainda não dispõe de modelos próprios calibrados (Poisson/correlações). Isto **não é** um sinal automático de aposta.

## Segurança e credibilidade

O cache `data/fixtures.json` contém apenas jogos reais de feeds com origem identificada. Se faltar o feed, o painel mostra indisponibilidade em vez de criar partidas. Não coloques chaves em ficheiros públicos: usa **Settings → Secrets and variables → Actions**. O JavaScript corre no navegador e nunca envia informações bancárias a servidores nossos; os dados manuais só ficam no dispositivo via armazenamento local.

Dados desportivos: [TheSportsDB](https://www.thesportsdb.com/) e [ESPN](https://www.espn.com/soccer/) (integração de calendário não oficial), [API-Football](https://www.api-football.com/) se configurado. O utilizador é responsável por confirmar as odds e respeitar as condições aplicáveis. Nenhum algoritmo garante lucro.

## Estrutura

```text
index.html             Interface
styles.css             Design responsivo
app.js                 Calendário, formulários e lista local
src/engine.js          Fórmulas, classificação e risco
scripts/sync_fixtures.py  Ingestão do calendário
data/fixtures.json     Cache público identificado
tests/engine.test.js   Testes automáticos
.github/workflows/refresh.yml  Sincronizar, testar e publicar
```
