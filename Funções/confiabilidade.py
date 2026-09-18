"""
confiabilidade.py — Score de Confiabilidade do jogador (0–100), position-aware.

Metodologia (Índice Composto Ponderado por Percentis):
- Cada posição tem seu próprio conjunto de métricas positivas (recompensa) e
  negativas (penalidade), porque as colunas do export do FM mudam de aba para aba
  (goleiro não desarma; o nome de "erros que geraram gol" varia por posição).
- Cada métrica é convertida em PERCENTIL dentro da própria posição (rank pct),
  para comparar o jogador contra os pares diretos — é o que dá o "95º percentil".
  Percentil é mais robusto a outliers do que um MinMax puro.
- Métricas negativas são INVERTIDAS (menos erros/posse perdida/faltas → nota maior).
- Pesos customizados: um erro que gera gol pesa muito mais que um passe errado.
- Resultado: Score de Confiabilidade 0–100, mais um Índice Positivo (produção)
  e um Índice de Risco (erros), usados na Matriz de Risco.

Observação honesta sobre xT/EPV: essas métricas exigem dados de evento posicionais
(StatsBomb/Opta) que o FM não exporta. Usamos "Passes em progressão" como proxy de
progressão de bola e "Posse perdida" como proxy de risco de progressão.

Cada métrica é um dict:
    {'label': <rótulo curto>, 'cols': [<candidatos de coluna, em ordem>],
     'peso': <float>, 'sentido': +1 (positiva) | -1 (negativa)}
"""

import numpy as np
import pandas as pd


# ==========================================================================
# CONFIGURAÇÃO DE MÉTRICAS POR POSIÇÃO
# 'cols' lista candidatos — usa-se a primeira coluna que existir na aba.
# Preferimos métricas /90 e % para não penalizar quem jogou menos minutos.
# ==========================================================================
CONFIG_CONFIABILIDADE = {
    "🧤Goleiros": [
        {"label": "Defesas seguras %", "cols": ["% Def Seguras", "% de Defesas Realizadas"], "peso": 1.5, "sentido": 1},
        {"label": "xG defendidos /90", "cols": ["xG defendidos / 90", "xG Defendidos / 90"], "peso": 1.5, "sentido": 1},
        {"label": "Jogos sem sofrer %", "cols": ["% de jogos sem sofrer gol"], "peso": 1.0, "sentido": 1},
        {"label": "Pênaltis defend. %", "cols": ["% Pênaltis defendidos"], "peso": 0.8, "sentido": 1},
        {"label": "Saídas certas %", "cols": ["% De Acerto nas Saídas do gol"], "peso": 1.0, "sentido": 1},
        {"label": "Passes certos %", "cols": ["% Passes certos"], "peso": 1.0, "sentido": 1},
        {"label": "Falhas /90", "cols": ["Falhas/90", "Falhas /90"], "peso": 3.0, "sentido": -1},
        {"label": "Saídas falhas /90", "cols": ["Saídas do gol falhas /90"], "peso": 1.5, "sentido": -1},
        {"label": "Passes errados /90", "cols": ["Passes Errados/90", "Passes Errados /90"], "peso": 1.0, "sentido": -1},
        {"label": "Posse perdida /90", "cols": ["Posse Perdida /90"], "peso": 1.0, "sentido": -1},
    ],
    "🧱Zagueiros": [
        {"label": "Passes certos %", "cols": ["% Acerto dos passes", "% Passes certos"], "peso": 1.2, "sentido": 1},
        {"label": "Desarmes ganhos /90", "cols": ["Desarmes Ganhos/90", "Desarmes Ganhos /90"], "peso": 1.2, "sentido": 1},
        {"label": "Interceptações /90", "cols": ["Interceptações /90"], "peso": 1.2, "sentido": 1},
        {"label": "Cabeceios ganhos %", "cols": ["% Cabeceios Ganhos"], "peso": 1.0, "sentido": 1},
        {"label": "Duelos ganhos %", "cols": ["% Bolas disputadas e ganhas"], "peso": 1.0, "sentido": 1},
        {"label": "Passes em prog. /90", "cols": ["Passes em progressão/90"], "peso": 0.8, "sentido": 1},
        {"label": "Erros → gol /90", "cols": ["Erros que originaram gols /90", "Erros que geraram gol/90"], "peso": 3.0, "sentido": -1},
        {"label": "Erros defensivos /90", "cols": ["Erros Defensivos /90"], "peso": 1.5, "sentido": -1},
        {"label": "Posse perdida /90", "cols": ["Posse perdida /90", "Posse Desperdiçada /90"], "peso": 1.2, "sentido": -1},
        {"label": "Faltas /90", "cols": ["Faltas cometidas/90", "Faltas cometidas /90"], "peso": 1.0, "sentido": -1},
        {"label": "Driblado /90", "cols": ["Dribles sofridos /90"], "peso": 1.0, "sentido": -1},
    ],
    "🛡️Laterais": [
        {"label": "Passes certos %", "cols": ["% Passes Certos"], "peso": 1.2, "sentido": 1},
        {"label": "Desarmes ganhos /90", "cols": ["Desarmes Conseguidos / 90"], "peso": 1.1, "sentido": 1},
        {"label": "Duelos ganhos %", "cols": ["% Lances disputados e ganhos"], "peso": 1.0, "sentido": 1},
        {"label": "Cruzam. certos /90", "cols": ["Cruzamentos C/90"], "peso": 0.9, "sentido": 1},
        {"label": "Chances criadas /90", "cols": ["Chances criadas /90"], "peso": 1.0, "sentido": 1},
        {"label": "Passes em prog. /90", "cols": ["Passes em progressão/90"], "peso": 0.8, "sentido": 1},
        {"label": "Erros → gol /90", "cols": ["Erros que geraram gol/90"], "peso": 3.0, "sentido": -1},
        {"label": "Erros defensivos /90", "cols": ["Erros Defensivos /90"], "peso": 1.5, "sentido": -1},
        {"label": "Posse perdida /90", "cols": ["Posse perdida /90", "Posse Desperdiçada /90"], "peso": 1.2, "sentido": -1},
        {"label": "Faltas /90", "cols": ["Faltas cometidas /90"], "peso": 1.0, "sentido": -1},
        {"label": "Driblado /90", "cols": ["Dribles Sofridos /90"], "peso": 1.0, "sentido": -1},
    ],
    "🛡️Volantes": [
        {"label": "Passes certos %", "cols": ["% Passes certos"], "peso": 1.2, "sentido": 1},
        {"label": "Desarmes ganhos /90", "cols": ["Desarmes ganhos/90"], "peso": 1.1, "sentido": 1},
        {"label": "Int.+roubos /90", "cols": ["Bolas Int + Roub /90"], "peso": 1.1, "sentido": 1},
        {"label": "Duelos ganhos %", "cols": ["% Bolas disputadas e ganhas (sem falta)"], "peso": 1.0, "sentido": 1},
        {"label": "Pressão ganha %", "cols": ["% Pressão ganha/90"], "peso": 0.9, "sentido": 1},
        {"label": "Passes em prog. /90", "cols": ["Passes em progressão/90"], "peso": 0.8, "sentido": 1},
        {"label": "Erros defensivos /90", "cols": ["Erros Defensivos /90"], "peso": 2.0, "sentido": -1},
        {"label": "Erros → gol", "cols": ["Erros que deram em Golo"], "peso": 2.5, "sentido": -1},
        {"label": "Posse perdida /90", "cols": ["Posse perdida /90", "Posse Desperdiçada /90"], "peso": 1.2, "sentido": -1},
        {"label": "Faltas /90", "cols": ["Faltas/90"], "peso": 1.0, "sentido": -1},
        {"label": "Cartões /90", "cols": ["Total de Cartões /90"], "peso": 0.8, "sentido": -1},
    ],
    "🏃‍♂️Box-To-Box": [
        {"label": "Passes certos %", "cols": ["% Passes certos"], "peso": 1.1, "sentido": 1},
        {"label": "Desarmes ganhos /90", "cols": ["Desarmes G/90"], "peso": 1.0, "sentido": 1},
        {"label": "Bolas recup. /90", "cols": ["Bolas recuperadas / 90"], "peso": 1.0, "sentido": 1},
        {"label": "Chances criadas /90", "cols": ["Chances criadas / 90"], "peso": 1.0, "sentido": 1},
        {"label": "Pressão ganha %", "cols": ["% Pressão ganha/90"], "peso": 0.9, "sentido": 1},
        {"label": "xG+xA /90", "cols": ["xA + xG /90"], "peso": 1.0, "sentido": 1},
        {"label": "Erros → gol", "cols": ["Erros que deram em Golo"], "peso": 2.5, "sentido": -1},
        {"label": "Posse perdida /90", "cols": ["Posse perdida /90", "Posse Desperdiçada /90"], "peso": 1.3, "sentido": -1},
        {"label": "Perdas posse/jogo", "cols": ["Perdas de posse da bola por jogo"], "peso": 1.0, "sentido": -1},
        {"label": "Faltas /90", "cols": ["Faltas/90"], "peso": 1.0, "sentido": -1},
    ],
    "🎯Armadores": [
        {"label": "Passes certos %", "cols": ["% Passes Certos"], "peso": 1.2, "sentido": 1},
        {"label": "Passes decis. /90", "cols": ["Passes Decisivos /90"], "peso": 1.1, "sentido": 1},
        {"label": "Chances perigo /90", "cols": ["Chances de perigo criadas /90"], "peso": 1.1, "sentido": 1},
        {"label": "xA /90", "cols": ["xA /90"], "peso": 1.0, "sentido": 1},
        {"label": "Ações → finaliz. /90", "cols": ["Ações que geraram finalizações ao gol /90"], "peso": 1.0, "sentido": 1},
        {"label": "Ações c/ bola sucesso %", "cols": ["% Sucesso de ações com bola"], "peso": 0.9, "sentido": 1},
        {"label": "Posse desperd. /90", "cols": ["Posse Desperdiçada /90", "Posse perdida /90"], "peso": 1.5, "sentido": -1},
        {"label": "Passes errados /90", "cols": ["Passes Errados /90"], "peso": 1.2, "sentido": -1},
        {"label": "Erros → gol", "cols": ["Erros que deram em Golo"], "peso": 2.0, "sentido": -1},
        {"label": "Perdas posse/jogo", "cols": ["Perdas de posse da bola por jogo"], "peso": 1.0, "sentido": -1},
    ],
    "⚽Avançados": [
        {"label": "G−xG /90 (s/pên)", "cols": ["Gols não esperados SEM PÊNALTI", "Gols não esperados"], "peso": 1.6, "sentido": 1},
        {"label": "xG /90 (s/pên)", "cols": ["xG (Sem pênaltis) /90"], "peso": 1.1, "sentido": 1},
        {"label": "Finaliz. no gol %", "cols": ["% Finalizações que foram em direção gol"], "peso": 1.0, "sentido": 1},
        {"label": "GPI (prob. gol)", "cols": ["GPI (Goal Probability Index)"], "peso": 1.0, "sentido": 1},
        {"label": "Ações → finaliz. /90", "cols": ["Ações que geraram finalizações ao gol /90"], "peso": 0.9, "sentido": 1},
        {"label": "Cabeceios ganhos %", "cols": ["% Cabs ganhos"], "peso": 0.7, "sentido": 1},
        {"label": "Posse perdida /90", "cols": ["Posse Perdida /90", "Posse Desperdiçada /90"], "peso": 1.3, "sentido": -1},
        {"label": "Impedimentos /90", "cols": ["Impedimentos / 90"], "peso": 1.0, "sentido": -1},
        {"label": "Perdas posse/jogo", "cols": ["Perdas de posse da bola por jogo"], "peso": 1.0, "sentido": -1},
        {"label": "Faltas cometidas", "cols": ["Faltas Cometidas"], "peso": 0.6, "sentido": -1},
    ],
}


def posicao_suportada(posicao: str) -> bool:
    """True se há configuração de confiabilidade para a posição."""
    return posicao in CONFIG_CONFIABILIDADE


def _achar_col(df: pd.DataFrame, candidatos):
    """Retorna o primeiro nome de coluna candidato presente no df, ou None."""
    for c in candidatos:
        if c in df.columns:
            return c
    return None


def _to_num(serie: pd.Series) -> pd.Series:
    """Converte uma coluna para numérico de forma tolerante (%, vírgula decimal)."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.astype(float)
    limpa = (
        serie.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(".", "", regex=False)   # separador de milhar
        .str.replace(",", ".", regex=False)  # vírgula decimal -> ponto
        .str.strip()
    )
    return pd.to_numeric(limpa, errors="coerce")


def calcular_confiabilidade(df_posicao: pd.DataFrame, posicao: str):
    """
    Calcula o Score de Confiabilidade dos jogadores de uma posição.

    Retorna (df_scores, df_percentis, metricas_usadas):
      - df_scores: [Jogador, Equipe, Score_Confiabilidade, Indice_Positivo, Indice_Risco]
                   ordenado por Score desc.
      - df_percentis: indexado por Jogador, uma coluna por métrica com o percentil
                   de "confiabilidade" 0–100 (negativas já invertidas: maior = melhor).
      - metricas_usadas: lista de dicts {'label', 'sentido'} efetivamente usados.
    Retorna (None, None, None) se a posição não é suportada ou faltam dados.
    """
    if posicao not in CONFIG_CONFIABILIDADE:
        return None, None, None
    if df_posicao is None or df_posicao.empty or "Jogador" not in df_posicao.columns:
        return None, None, None

    df = df_posicao.copy()
    # Mantém só linhas com nome de jogador (remove linhas auxiliares/agregados)
    df = df[df["Jogador"].apply(lambda x: isinstance(x, str) and x.strip() != "")]
    df = df.drop_duplicates(subset="Jogador", keep="first").reset_index(drop=True)
    if len(df) < 3:
        return None, None, None

    metricas = CONFIG_CONFIABILIDADE[posicao]

    perc_bom = {}    # percentil de confiabilidade (negativas invertidas) por métrica
    perc_risco = {}  # percentil bruto das métricas negativas (para o Índice de Risco)
    pesos = {}
    sentidos = {}
    usadas = []

    for m in metricas:
        col = _achar_col(df, m["cols"])
        if col is None:
            continue
        valores = _to_num(df[col])
        if valores.notna().sum() < 3 or valores.nunique(dropna=True) < 2:
            continue  # sem variação suficiente para ranquear
        percentil = valores.rank(pct=True)  # 0–1, maior valor -> maior percentil
        bom = percentil if m["sentido"] == 1 else (1.0 - percentil)
        perc_bom[m["label"]] = bom
        pesos[m["label"]] = m["peso"]
        sentidos[m["label"]] = m["sentido"]
        if m["sentido"] == -1:
            perc_risco[m["label"]] = percentil  # maior = mais arriscado
        usadas.append({"label": m["label"], "sentido": m["sentido"]})

    if len(usadas) < 3:
        return None, None, None

    df_bom = pd.DataFrame(perc_bom, index=df.index)  # linhas=jogadores, cols=métricas (0–1)

    # Score = média ponderada das métricas presentes por jogador (renormaliza pelos
    # pesos das métricas efetivamente disponíveis naquele jogador).
    w = pd.Series(pesos)
    mask = df_bom.notna()
    num = (df_bom.fillna(0.0) * w).sum(axis=1)
    den = (mask * w).sum(axis=1)
    score = np.where(den > 0, num / den, np.nan) * 100.0

    # Índice Positivo: só métricas de sentido +1
    labels_pos = [l for l, s in sentidos.items() if s == 1]
    labels_neg = [l for l, s in sentidos.items() if s == -1]
    w_pos = w[labels_pos] if labels_pos else pd.Series(dtype=float)
    ind_pos = _media_ponderada(df_bom[labels_pos] if labels_pos else None, w_pos)

    # Índice de Risco: média ponderada dos percentis BRUTOS das negativas (maior = pior)
    df_risco = pd.DataFrame(perc_risco, index=df.index) if perc_risco else None
    w_neg = w[labels_neg] if labels_neg else pd.Series(dtype=float)
    ind_risco = _media_ponderada(df_risco, w_neg)

    df_scores = pd.DataFrame({
        "Jogador": df["Jogador"].values,
        "Equipe": df["Equipe"].values if "Equipe" in df.columns else "",
        "Score_Confiabilidade": np.round(score, 1),
        "Indice_Positivo": np.round(ind_pos * 100.0, 1),
        "Indice_Risco": np.round(ind_risco * 100.0, 1),
    })
    df_scores = df_scores.sort_values("Score_Confiabilidade", ascending=False).reset_index(drop=True)

    df_percentis = (df_bom * 100.0).round(1)
    df_percentis.index = df["Jogador"].values

    return df_scores, df_percentis, usadas


def _media_ponderada(df_metricas, pesos: pd.Series):
    """Média ponderada linha a linha, ignorando NaN e renormalizando os pesos."""
    if df_metricas is None or df_metricas.shape[1] == 0 or pesos.empty:
        # sem métricas -> devolve série neutra (0.5) para não quebrar o gráfico
        n = 0 if df_metricas is None else len(df_metricas)
        return pd.Series([0.5] * n)
    mask = df_metricas.notna()
    num = (df_metricas.fillna(0.0) * pesos).sum(axis=1)
    den = (mask * pesos).sum(axis=1)
    return pd.Series(np.where(den > 0, num / den, 0.5), index=df_metricas.index)
