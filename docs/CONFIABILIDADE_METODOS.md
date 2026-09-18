# Relatório de Métodos — Seção Confiabilidade

Este documento descreve os métodos estatísticos e de **cálculo integral e diferencial**
usados na seção **Confiabilidade** do Scout Moneyball. O objetivo é extrair, dos dados
agregados do Football Manager, sinais que **não aparecem no ranking simples**.

Implementação: [`Funções/confiabilidade.py`](../Funções/confiabilidade.py) (apenas `numpy`/`pandas`).

---

## 0. Premissa honesta sobre os dados

O export do FM é **transversal**: uma linha por jogador, com totais e médias por 90 minutos
da temporada. **Não há série temporal jogo a jogo.**

Consequência direta: **não existe derivada nem integral no tempo** (não é possível medir
"forma ao longo da temporada" ou aceleração de desempenho). Qualquer método aqui opera sobre a
**distribuição transversal dos jogadores da mesma posição** — que é onde o cálculo diferencial e
integral realmente agrega informação nova. `xT`/`EPV` também exigem dados de evento posicionais
que o FM não exporta; usamos *passes em progressão* × *posse perdida* como proxy.

---

## 1. Camada base — Índice Composto Ponderado por Percentis

Para cada posição há um conjunto próprio de métricas **positivas** (recompensa) e **negativas**
(penalidade), porque as colunas do FM mudam de aba para aba. Cada métrica vira um **percentil
dentro da posição**; as negativas são **invertidas** (`g = 1 − percentil`); aplica-se um **peso**
(erro que gera gol pesa muito mais que passe errado). O **Score** é a média ponderada:

$$S = \frac{\sum_i w_i \, g_i}{\sum_i w_i} \times 100$$

Também derivam daí o **Índice Positivo** (só métricas +) e o **Índice de Risco** (percentis brutos
das métricas −), usados na Matriz de Risco.

---

## 2. Camada avançada — integral & derivada sobre a distribuição

### 2.1 Percentil por integral (KDE + CDF)

Em vez do `rank()` bruto, estima-se a **densidade de probabilidade** dos pares por
**KDE gaussiano** e integra-se para obter a CDF. O percentil **é**, por definição, a integral da
densidade:

$$f(x) = \frac{1}{n\,h}\sum_{j=1}^{n} \varphi\!\left(\frac{x - x_j}{h}\right)
\qquad
F(x) = \int_{-\infty}^{x} f(t)\,dt$$

- `φ` = densidade normal padrão; banda `h` de **Silverman robusta** (`min` entre desvio-padrão e
  `IQR/1.349`), `h = 0.9\,\sigma\,n^{-1/5}`.
- A integral `F(x)` é calculada **numericamente pela regra do trapézio** (soma cumulativa) sobre
  uma grade de 512 pontos e normalizada para `[0, 1]`.
- Vantagem sobre o rank: percentil **suave**, menos sensível a empates e a um único outlier.

Fallback para o `rank()` quando `n < 8` (KDE instável em amostra minúscula).

### 2.2 Estabilidade — derivada da CDF (densidade local)

A **derivada da CDF é a própria densidade**: `F'(x) = f(x)`. A densidade local no ponto do jogador
mede **aglomeração**:

- `f(x)` **alto** → muitos pares empatados naquele valor → o ranking é **frágil**: uma pequena
  variação cruza vários concorrentes e derruba o jogador muitas posições.
- `f(x)` **baixo** → jogador **isolado** → posição **robusta**.

Índice de Estabilidade (0–100), com densidade relativa `f/f_{máx}` e média ponderada pelos pesos:

$$\text{Estabilidade} = \left(1 - \frac{\sum_i w_i \, \hat f_i(x_i)}{\sum_i w_i}\right)\times 100
\qquad \hat f_i = \frac{f_i}{\max f_i}$$

Esse é o "deep data" clássico invisível no ranking: **dois jogadores no mesmo percentil podem ter
robustez completamente diferente**.

### 2.3 Alavancagem — gradiente do score

Como `S = \sum_i w_i F_i(x_i)`, a **derivada parcial** em relação a cada métrica é o peso vezes a
densidade local:

$$\frac{\partial S}{\partial x_i} = w_i \, F_i'(x_i) = w_i \, f_i(x_i)$$

Interpretação prática **por jogador**: a métrica com maior `w_i f_i(x_i)` é onde uma melhora
rende **mais pontos de score por unidade** — porque ali existem muitos pares para ultrapassar
(densidade alta). A seção lista as 3 maiores alavancas, indicando se é para *aumentar* (métrica
positiva) ou *reduzir* (negativa).

### 2.4 Consistência — entropia de Shannon (integral)

Confiabilidade é ser bom em **todas** as dimensões, não só em uma. Mede-se isso pela **entropia**
normalizada do perfil de percentis do jogador. Com `p_i = g_i / \sum_j g_j`:

$$H = -\sum_i p_i \ln p_i
\qquad
\text{Consistência} = \frac{H}{\ln k}\times 100$$

- Máxima (100) quando o jogador é **equilibrado** em todas as `k` métricas.
- Baixa quando o score depende de **poucas** métricas ("one-trick") — menos confiável.

A entropia é a medida-integral canônica de dispersão de uma distribuição.

### 2.5 Confiança e banda — integração sobre a incerteza amostral

Médias por 90 minutos de quem jogou pouco são **ruidosas**. Modela-se o erro relativo de cada
métrica como decrescente com o tamanho de amostra (número de "90 min", `n_{90} = \text{minutos}/90`):

$$\text{rel\_se} \approx \frac{1}{\sqrt{n_{90}}}$$

- **Confiança (0–100)**: saturação exponencial `100\,(1 - e^{-n_{90}/8})` (~63% em ~720 min).
- **Banda ± no score (IC ~95%)** pelo **método delta**, propagando o ruído de cada métrica ao
  score via a derivada da CDF:

$$\delta g_i = f_i(x_i)\,|x_i|\,\text{rel\_se}
\qquad
\text{SE}(S) = \sqrt{\sum_i \left(\tfrac{w_i}{\sum w}\right)^2 \delta g_i^{\,2}}
\qquad
\text{Banda} = 1.96\,\text{SE}(S)\times 100$$

Isso separa "confiável de verdade" de "amostra pequena que pode ser sorte".

### 2.6 Índice Acadêmico — veredito combinado

> No app este índice aparece com o nome **"Índice geral"** e os textos são simplificados;
> a formulação matemática abaixo fica só neste relatório.

O Score base é **descontado** por desequilíbrio (consistência) e por amostra pequena (confiança):

$$\text{IA} = S \times \underbrace{(0.6 + 0.4\,\tfrac{\text{Consist.}}{100})}_{\text{equilíbrio}}
\times \underbrace{(0.7 + 0.3\,\tfrac{\text{Confiança}}{100})}_{\text{amostra}}$$

Um jogador com Score alto mas dependente de uma métrica só, ou com poucos minutos, **cai** no
Índice Acadêmico — refletindo a confiabilidade real.

---

## 3. Visualizações

- **Ranking acadêmico** — tabela com Índice Acadêmico, Score, Estabilidade, Consistência,
  Confiança e ± Banda.
- **Gráfico KDE** — a curva de densidade da métrica, com a **área integral** (percentil)
  sombreada até o valor do jogador e a **densidade local** (derivada) marcada. É a prova visual
  direta dos conceitos de 2.1 e 2.2.
- **Robustez × Qualidade** — dispersão Estabilidade × Índice Acadêmico, cor pela Consistência.

---

## 4. Limitações

- Todos os índices são **relativos à posição** na amostra carregada — não são absolutos entre ligas.
- O modelo de ruído amostral (2.5) é uma aproximação (assume erro `∝ 1/\sqrt{n}` e independência
  entre métricas); serve para ordenar confiança, não como IC exato.
- KDE exige `n ≥ 8`; abaixo disso a análise avançada não é exibida.
- Sem dados de evento/tempo, não há análise de trajetória, forma ou sequência de jogos.
