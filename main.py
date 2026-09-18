import pandas as pd
import warnings
import numpy as np
from Funções import valor
from Funções import data
from Funções import ahp

warnings.filterwarnings("ignore")

CRITERIOS_PADRAO = {
    '🧤Goleiros': {
        'colunas': [
            'Valor_Numerico', 'Idade', 'Salario_Numerico', 'Altura', 'Contrato_Numerico',
            'Jogos completos', 'Expected Goals Prevented xGP', 'Falhas/90',
            '% Acerto do goleiro', 'Defesas totais / Jogo', 'Nota média'
        ],
        'nivel_1': ['Jogos completos', 'Falhas/90'],
        'nivel_2': ['Expected Goals Prevented xGP', 'Idade', 'Altura', 'Valor_Numerico', 'Salario_Numerico'],
    },
    '🧱Zagueiros': {
        'colunas': [
            'Valor_Numerico', 'Idade', 'Salario_Numerico', 'Altura', 'Contrato_Numerico',
            'Jogos completos', '% Cabeceios Ganhos',
            'Rem Bloqueados, Interceptações  e Bloqueios/90', '% Des',
            'Desarmes Decisivos / 90', 'Acertos (Cabs, Des, Pres)', 'Acertos/90',
            'Bolas roubadas /90', '% Bolas disputadas e ganhas', 'Erros Defensivos /90',
            'Eficácia defensiva', 'Dist / 90', 'Nota média'
        ],
        'nivel_1': [
            'Desarmes Decisivos / 90', '% Bolas disputadas e ganhas', 'Acertos/90',
            'Eficácia defensiva', '% Cabeceios Ganhos', 'Nota média', 'Jogos completos'
        ],
        'nivel_2': [
            '% Des', 'Altura', 'Dist / 90',
            'Rem Bloqueados, Interceptações  e Bloqueios/90',
            'Acertos (Cabs, Des, Pres)', 'Valor_Numerico', 'Salario_Numerico', 'Idade'
        ],
    },
    '🛡️Laterais': {
        'colunas': [
            'Valor_Numerico', 'Idade', 'Salario_Numerico', 'Altura', 'Jogos completos',
            'Participação / 90', 'Fintas / 90', 'Minutos pra criar uma chance de perigo',
            'Cruzamentos Conseguidos', 'xA + xG /90', 'Gols + A/90',
            'Movimentos ofensivos com sucesso', 'Dist / 90', 'Erros Defensivos /90',
            'Eficácia defensiva', 'Nota média'
        ],
        'nivel_1': [
            'Participação / 90', 'Minutos pra criar uma chance de perigo',
            'xA + xG /90', 'Eficácia defensiva', 'Nota média', 'Jogos completos'
        ],
        'nivel_2': [
            'Valor_Numerico', 'Salario_Numerico', 'Idade', 'Fintas / 90',
            'Gols + A/90', 'Movimentos ofensivos com sucesso'
        ],
    },
    '🛡️Volantes': {
        'colunas': [
            'Valor_Numerico', 'Idade', 'Salario_Numerico', 'Jogos Completos',
            'Contrato_Numerico', 'Cartões por falta cometida', '% Pressão ganha/90',
            '% Bolas disputadas e ganhas (sem falta)', 'Passes certos  - errados / Jogo',
            'Passes em progressão/90', 'Eficácia defensiva', 'xA por passe decisivo',
            'Criação / 90', 'Distância /90', 'Nota média'
        ],
        'nivel_1': [
            'Eficácia defensiva', 'Passes certos  - errados / Jogo', 'xA por passe decisivo',
            'Criação / 90', '% Bolas disputadas e ganhas (sem falta)', 'Nota média', 'Jogos Completos'
        ],
        'nivel_2': [
            '% Pressão ganha/90', 'Passes em progressão/90', 'Distância /90',
            'Valor_Numerico', 'Salario_Numerico', 'Idade'
        ],
    },
    '🏃‍♂️Box-To-Box': {
        'colunas': [
            'Valor_Numerico', 'Idade', 'Salario_Numerico', 'Jogos completos',
            'Contrato_Numerico', 'Taxa de Conversão %',
            'Participação por jogo (passes, fnt, fin, criação, roubadas de bola, etc)',
            '% Acerto', 'xA / Passe Decisivo', 'Dist / 90', 'Último terço/90', 'Nota média'
        ],
        'nivel_1': [
            'Taxa de Conversão %', 'xA / Passe Decisivo', 'Dist / 90',
            'Nota média', 'Jogos completos'
        ],
        'nivel_2': [
            'Participação por jogo (passes, fnt, fin, criação, roubadas de bola, etc)',
            '% Acerto', 'Último terço/90', 'Valor_Numerico', 'Salario_Numerico', 'Idade'
        ],
    },
    '🎯Armadores': {
        'colunas': [
            'Valor_Numerico', 'Idade', 'Salario_Numerico', 'Jogos completos',
            'Contrato_Numerico', 'Gols+ Assist / 90', 'Fintas /90', 'non Pen xG /90',
            'xA /90', '% Cruzamentos certos', 'Passes Decisivos pra uma assistência',
            'xA / Passe Decisivo', 'Finalizações no gol/90',
            'Conversão dos chutes de fora da  área', 'Ações com Bola T/90',
            '% Sucesso de ações com bola', 'Ações que geraram finalizações ao gol /90',
            'Chances de perigo criadas /90',
            'Participação do jogador a cada 90 minutos (fnt, cabs, pass, finalizaçõs)',
            'Participação em passes / 90', 'Passes em construção de jog OF /90',
            'Ações no último terço / 90', 'Tentativas de marcar um gol / 90',
            'Dist / 90', 'Sprints/90', 'Nota média'
        ],
        'nivel_1': [
            'Gols+ Assist / 90', 'xA / Passe Decisivo',
            'Ações no último terço / 90', 'Nota média', 'Jogos completos'
        ],
        'nivel_2': [
            'Fintas /90', 'non Pen xG /90', '% Cruzamentos certos',
            'Passes Decisivos pra uma assistência', 'Tentativas de marcar um gol / 90',
            'Dist / 90', 'Valor_Numerico', 'Salario_Numerico', 'Idade'
        ],
    },
    '⚽Avançados': {
        'colunas': [
            'Valor_Numerico', 'Idade', 'Salario_Numerico', 'Jogos completos',
            'Contrato_Numerico', 'Média de gols em toda a Carreira', 'Média gols / partida',
            'Média gols + ass / partida', 'Gols Sem Pênalti /90', 'Gols de dentro da área /90',
            'Gols de fora da área /90', '% Cabs ganhos', 'Impedimentos / 90',
            'Finalizações no gol/90', 'GPI (Goal Probability Index)',
            'Over xG / Under xG per 90', 'Minutos pra acertar uma finalização no gol',
            'Minutos pra MARCAR um gol', 'Minutos pra PARTICIPAR de um gol',
            'Gols não esperados SEM PÊNALTI', 'xG Conclusion', 'Pass D /90',
            'Fintas/90', '% Des + Pressões concluídas', 'Dist / 90',
            'Eficácia ofensiva', 'Participação do jogador a cada 90 minutos',
            '% Sucesso de ações com bola', 'Tentativas de marcar um gol  /90', 'Nota média'
        ],
        'nivel_1': [
            'Média de gols em toda a Carreira', 'Média gols / partida', 'Nota média',
            'Valor_Numerico', 'Salario_Numerico', 'Jogos completos',
            'GPI (Goal Probability Index)'
        ],
        'nivel_2': [
            'Gols Sem Pênalti /90', 'Gols de dentro da área /90', 'Gols de fora da área /90',
            '% Cabs ganhos', 'Finalizações no gol/90', 'Minutos pra MARCAR um gol',
            'xG Conclusion', 'Pass D /90', 'Fintas/90', 'Dist / 90',
            'Eficácia ofensiva', 'Participação do jogador a cada 90 minutos'
        ],
    },
    '📊Time Estatísticas': {
        'colunas': [
            'Passes Tentados /90', 'Pass Certos / 90', 'Passes errados /90', '% Passes certos /90',
            'Falhas/90', '% passes errados', 'Ações com Bola/90', 'Perda de posse /90 minutos',
            'Ações que geraram finalizações ao gol /90', 'Cruzamentos %', 'xA /90',
            'xG sem pênaltis/90', 'xA + xG sem pen /90', 'Fin/90', 'Finalizações Certas /90',
            '% Finalizações certas', 'Gols/90', 'Ast/90', 'Gols + Ast/90',
            'Cabeceios Disputados/90', 'Cabs Ganhos / 90', '% Cabs', 'Des T /90', 'Desarmes G/90',
            '% Desarmes', 'Faltas/90', '% Aproveitamento das Tentativas de Criar chance em  BP',
            'Pass D / 90', 'Dist / 90', 'Fintas/90', 'Nota média',
        ],
        'nivel_1': [],
        'nivel_2': [],
    },
    '🔍Overall Análise': {
        'colunas': [
            '% de vezes que foi eleito o Homem do Jogo', 'Gols/90', 'Assistência /90',
            'Gols + A/90', 'non Pen xG/90', 'xA /90', 'xG + xA /90', 'Finalizações /90',
            'Fin pra fora /90', 'Finalizações no gol /90', 'Finalizações Def /90',
            '% Finalizações em direção ao gol', '% Finalizações que converteram em gol',
            'Tentativas/90', 'Chances C /90',
            '% Aproveitamento das Tentativas de Criar chance em  BP', '% Conversão de pênalti',
            'Fora de jogo/90', 'Cabeceios Ganhos/90', '% Cabs', 'Des Ganhos/90',
            'Dribles Sofridos/90', '%Des Ganhos', 'Faltas/90', 'Cartão Amarelo/90',
            'Cartão Vermelho/90', '% Cartões por falta cometida',
            '% Pressão pra roubar a bola com sucesso', 'Lances disputados/90', 'Lances ganhos/90',
            '% Lances disputados e ganhos de forma limpa', 'Bolas Int / 90', 'Bolas roubadas / 90',
            'Lances ofensivos tentados/90', 'Lances OF conseguidos/90',
            '% Lances ofensivos conseguidos', 'Lances defensivos tentados/90',
            'Lances DEF conseguidos/90', '% Lances defensivos conseguidos', '% Acertos Global',
            'Fintas/90', 'Criação/90', 'Tentativas de marcar um gol/90',
            'Tentativas de Remates de fora da área /90', 'Participações do jogador /90',
            'Ações que geraram finalizações ao gol /90', 'Cruzamentos T/90', 'Cruzamentos C/90',
            'Pass D /90', 'Passes Tentados /90', 'Passes Completados /90', '% Passes Certos',
            'Passes Errados /90', 'Passes em Prog /90', '% de Passes que são em progressão',
            'Ações com Bola/90', 'Ações com Bola/90.1', '% Ações com sucesso',
            'Distância percorrida/90', 'Sprints/90', 'Posse Desperdiçada /90', 'Posse Perdida/90',
            'Nota média',
        ],
        'nivel_1': [],
        'nivel_2': [],
    },
}

CRITERIOS_DE_CUSTO = [
    'Valor_Numerico', 'Salario_Numerico', 'Falhas/90', 'Idade', 'Contrato_Numerico',
    'Erros Defensivos /90', 'Minutos pra criar uma chance de perigo',
    'Cartões por falta cometida', 'Minutos pra acertar uma finalização no gol',
    'Minutos pra MARCAR um gol', 'Minutos pra PARTICIPAR de um gol', 'Impedimentos / 90'
]

COLUNA_VALOR_POR_POSICAO = {
    '🧤Goleiros':     'Valor estimado',
    '🧱Zagueiros':    'Valor',
    '🛡️Laterais':    'Valor Estimado',
    '🛡️Volantes':    'Valor',
    '🏃‍♂️Box-To-Box': 'Valor',
    '🎯Armadores':    'Valor',
    '⚽Avançados':    'Valor Estimado',
}

COLUNA_CONTRATO_POR_POSICAO = {
    '🛡️Volantes':     'Data Final de Contrato',
    '🏃‍♂️Box-To-Box':  'Fim de contrato',
    '🎯Armadores':    'Data Final do contrato',
    '⚽Avançados':    'Data Final do contrato',
}

MIN_CRITERIOS_ATIVOS = 2  # mínimo de critérios para o AHP fazer sentido

# Abas que usam Rating Overall (sem custo/benefício, sem valor/salário/idade)
POSICOES_OVERALL = ['📊Time Estatísticas', '🔍Overall Análise']

# Colunas de identificação a excluir do cálculo nas abas Overall
COLUNAS_IDENTIFICACAO_OVERALL = {
    '📊Time Estatísticas': ['Jogador', 'Posição'],
    '🔍Overall Análise': [
        'Unnamed: 0', 'Jogador', 'NAC', 'Equipe', 'Posição', 'Idade',
        'Data Final do contrato', 'Salário'
    ],
}


def gerar_ranking(df_bruto, posicao, niveis_usuario=None):
    """
    Calcula o ranking Moneyball para uma posição.

    niveis_usuario: dict { criterio: 0|1|2|3 }
                    0 = Ignorar (excluído), 1/2/3 = níveis AHP.
                    None = usa padrão do CRITERIOS_PADRAO.

    Retorna: DataFrame com colunas [Jogador, Equipe, Nota_Moneyball, Valor estimado, Idade]
             ou lança ValueError com mensagem amigável em caso de erro recuperável.
    """
    # ── 1. Validação de entrada ────────────────────────────────────────────────
    if posicao not in CRITERIOS_PADRAO:
        raise ValueError(f"Posição '{posicao}' não reconhecida pelo sistema.")

    if df_bruto is None or df_bruto.empty:
        raise ValueError(f"A aba '{posicao}' está vazia na planilha.")

    # ── 2. Corte e limpeza do DataFrame ───────────────────────────────────────
    try:
        df = df_bruto.loc[:, 'Jogador':'Nota média'].copy()
    except KeyError:
        raise ValueError(
            f"Não foi possível localizar as colunas 'Jogador' e/ou 'Nota média' "
            f"na aba '{posicao}'. Verifique se a planilha está no formato correto."
        )

    df = df.dropna(subset=[df.columns[0]])
    if df.empty:
        raise ValueError(f"Nenhum jogador encontrado na aba '{posicao}' após remover linhas vazias.")

    # ── 3. Valor de mercado ────────────────────────────────────────────────────
    nome_col_valor = COLUNA_VALOR_POR_POSICAO.get(posicao, 'Valor estimado')
    if nome_col_valor not in df.columns:
        raise ValueError(
            f"Coluna de valor '{nome_col_valor}' não encontrada na aba '{posicao}'."
        )

    df['Valor_Numerico'] = df[nome_col_valor].apply(valor.limpar_valor_mercado)
    valores_positivos = df[df['Valor_Numerico'] > 0]['Valor_Numerico']

    if valores_positivos.empty:
        # Todos inegociáveis ou inválidos — usa fallback neutro
        df['Valor_Numerico'] = 0.0
    else:
        val_max_real = valores_positivos.max()
        val_min_real = valores_positivos.min()
        df.loc[df['Valor_Numerico'] == -1, 'Valor_Numerico'] = val_max_real * 2
        df.loc[df['Valor_Numerico'] == -2, 'Valor_Numerico'] = val_min_real + (val_max_real + val_min_real) / 2

    # ── 4. Salário ─────────────────────────────────────────────────────────────
    if 'Salário' not in df.columns:
        df['Salario_Numerico'] = 0.0
    else:
        df['Salario_Numerico'] = df['Salário'].apply(valor.limpar_salario)

    # ── 5. Contrato ────────────────────────────────────────────────────────────
    nome_col_contrato = COLUNA_CONTRATO_POR_POSICAO.get(posicao, 'Data final de contrato')
    if nome_col_contrato in df.columns:
        df['Contrato_Numerico'] = df[nome_col_contrato].apply(data.limpar_data_contrato)

    # ── 6. Critérios e níveis ──────────────────────────────────────────────────
    padrao = CRITERIOS_PADRAO[posicao]
    colunas_para_ver = [c for c in padrao['colunas'] if c in df.columns]

    if niveis_usuario:
        ignorados   = {c for c, n in niveis_usuario.items() if n == 0}
        nivel_1     = [c for c, n in niveis_usuario.items() if n == 1 and c in df.columns and c not in ignorados]
        nivel_2     = [c for c, n in niveis_usuario.items() if n == 2 and c in df.columns and c not in ignorados]
        nivel_3     = [c for c, n in niveis_usuario.items() if n == 3 and c in df.columns and c not in ignorados]
        colunas_para_ver = [c for c in colunas_para_ver if c not in ignorados]

        ativos = nivel_1 + nivel_2 + nivel_3
        if len(ativos) < MIN_CRITERIOS_ATIVOS:
            raise ValueError(
                f"São necessários pelo menos {MIN_CRITERIOS_ATIVOS} critérios ativos "
                f"para calcular o ranking de {posicao}. "
                f"Você marcou todos como 'Ignorar' ou deixou menos de {MIN_CRITERIOS_ATIVOS} ativos."
            )
    else:
        nivel_1 = [c for c in padrao['nivel_1'] if c in df.columns]
        nivel_2 = [c for c in padrao['nivel_2'] if c in df.columns]
        nivel_3 = [c for c in df.columns if c not in nivel_1 and c not in nivel_2]

    if not colunas_para_ver:
        raise ValueError(
            f"Nenhuma coluna de critério encontrada na aba '{posicao}'. "
            f"Verifique se os nomes das colunas da planilha estão corretos."
        )

    def obter_nivel(criterio):
        if criterio in nivel_1: return 1
        if criterio in nivel_2: return 2
        return 3

    criterios = nivel_1 + nivel_2 + nivel_3
    n = len(criterios)

    if n == 0:
        raise ValueError(f"Nenhum critério ativo para calcular o ranking de {posicao}.")

    # ── 7. Matriz AHP ──────────────────────────────────────────────────────────
    matriz_saaty = np.ones((n, n))  # diagonal 1 por padrão
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            t_i = obter_nivel(criterios[i])
            t_j = obter_nivel(criterios[j])
            if   t_i == 1 and t_j == 2: v = 2.0
            elif t_i == 1 and t_j == 3: v = 9.0
            elif t_i == 2 and t_j == 3: v = 5.0
            elif t_i == 2 and t_j == 1: v = 1/2
            elif t_i == 3 and t_j == 1: v = 1/9
            elif t_i == 3 and t_j == 2: v = 1/5
            else: v = 1.0
            matriz_saaty[i, j] = v

    try:
        pesos, cr, consistente = ahp.calcular_pesos_ahp(matriz_saaty)
    except Exception as e:
        raise ValueError(f"Erro no cálculo AHP para {posicao}: {e}")

    if pesos is None or len(pesos) != n:
        raise ValueError(f"O cálculo AHP retornou pesos inválidos para {posicao}.")

    # ── 8. Ranking ─────────────────────────────────────────────────────────────
    df_ranking = df[colunas_para_ver].copy()

    # Garante que todas as colunas de critério são numéricas
    for col in colunas_para_ver:
        df_ranking[col] = pd.to_numeric(df_ranking[col], errors='coerce').fillna(0)

    df_ranking['Nota_Moneyball'] = 0.0

    for criterio, peso in zip(criterios, pesos):
        if criterio not in df_ranking.columns:
            continue
        vmax = df_ranking[criterio].max()
        vmin = df_ranking[criterio].min()
        if vmax == vmin:
            df_ranking[f'{criterio}_Norm'] = 0.0
        elif criterio in CRITERIOS_DE_CUSTO:
            df_ranking[f'{criterio}_Norm'] = (vmax - df_ranking[criterio]) / (vmax - vmin)
        else:
            df_ranking[f'{criterio}_Norm'] = (df_ranking[criterio] - vmin) / (vmax - vmin)
        df_ranking['Nota_Moneyball'] += df_ranking[f'{criterio}_Norm'] * peso

    df_ranking['Nota_Moneyball'] *= 100

    # ── 9. Resultado ───────────────────────────────────────────────────────────
    df_final = pd.DataFrame()
    df_final['Jogador']        = df['Jogador'].values
    df_final['Nota_Moneyball'] = df_ranking['Nota_Moneyball'].values
    df_final['Equipe']         = df['Equipe'].values if 'Equipe' in df.columns else '—'
    df_final['Valor estimado'] = df['Valor_Numerico'].values
    df_final['Idade']          = pd.to_numeric(df['Idade'], errors='coerce').values if 'Idade' in df.columns else 0

    df_final = df_final.sort_values(by='Nota_Moneyball', ascending=False).reset_index(drop=True)

    return df_final[['Jogador', 'Equipe', 'Nota_Moneyball', 'Valor estimado', 'Idade']]


def _preparar_ahp(df_bruto, posicao, niveis_usuario=None):
    """Reproduz o pré-processamento do ranking Moneyball e devolve as peças do AHP
    (critérios, matriz de Saaty e a matriz normalizada X de jogadores × critérios),
    para a análise de margem de erro. Segue exatamente os mesmos passos de
    gerar_ranking, garantindo que a nota reconstruída (100·X·pesos) seja idêntica.
    """
    if posicao not in CRITERIOS_PADRAO:
        raise ValueError(f"Posição '{posicao}' não reconhecida pelo sistema.")
    if df_bruto is None or df_bruto.empty:
        raise ValueError(f"A aba '{posicao}' está vazia na planilha.")

    try:
        df = df_bruto.loc[:, 'Jogador':'Nota média'].copy()
    except KeyError:
        raise ValueError(
            f"Não foi possível localizar as colunas 'Jogador' e/ou 'Nota média' na aba '{posicao}'."
        )
    df = df.dropna(subset=[df.columns[0]])
    if df.empty:
        raise ValueError(f"Nenhum jogador encontrado na aba '{posicao}' após remover linhas vazias.")

    nome_col_valor = COLUNA_VALOR_POR_POSICAO.get(posicao, 'Valor estimado')
    if nome_col_valor not in df.columns:
        raise ValueError(f"Coluna de valor '{nome_col_valor}' não encontrada na aba '{posicao}'.")
    df['Valor_Numerico'] = df[nome_col_valor].apply(valor.limpar_valor_mercado)
    valores_positivos = df[df['Valor_Numerico'] > 0]['Valor_Numerico']
    if valores_positivos.empty:
        df['Valor_Numerico'] = 0.0
    else:
        val_max_real = valores_positivos.max()
        val_min_real = valores_positivos.min()
        df.loc[df['Valor_Numerico'] == -1, 'Valor_Numerico'] = val_max_real * 2
        df.loc[df['Valor_Numerico'] == -2, 'Valor_Numerico'] = val_min_real + (val_max_real + val_min_real) / 2

    if 'Salário' not in df.columns:
        df['Salario_Numerico'] = 0.0
    else:
        df['Salario_Numerico'] = df['Salário'].apply(valor.limpar_salario)

    nome_col_contrato = COLUNA_CONTRATO_POR_POSICAO.get(posicao, 'Data final de contrato')
    if nome_col_contrato in df.columns:
        df['Contrato_Numerico'] = df[nome_col_contrato].apply(data.limpar_data_contrato)

    padrao = CRITERIOS_PADRAO[posicao]
    colunas_para_ver = [c for c in padrao['colunas'] if c in df.columns]
    if niveis_usuario:
        ignorados = {c for c, nv in niveis_usuario.items() if nv == 0}
        nivel_1 = [c for c, nv in niveis_usuario.items() if nv == 1 and c in df.columns and c not in ignorados]
        nivel_2 = [c for c, nv in niveis_usuario.items() if nv == 2 and c in df.columns and c not in ignorados]
        nivel_3 = [c for c, nv in niveis_usuario.items() if nv == 3 and c in df.columns and c not in ignorados]
        colunas_para_ver = [c for c in colunas_para_ver if c not in ignorados]
        if len(nivel_1 + nivel_2 + nivel_3) < MIN_CRITERIOS_ATIVOS:
            raise ValueError(
                f"São necessários pelo menos {MIN_CRITERIOS_ATIVOS} critérios ativos para {posicao}."
            )
    else:
        nivel_1 = [c for c in padrao['nivel_1'] if c in df.columns]
        nivel_2 = [c for c in padrao['nivel_2'] if c in df.columns]
        nivel_3 = [c for c in df.columns if c not in nivel_1 and c not in nivel_2]

    if not colunas_para_ver:
        raise ValueError(f"Nenhuma coluna de critério encontrada na aba '{posicao}'.")

    def obter_nivel(criterio):
        if criterio in nivel_1: return 1
        if criterio in nivel_2: return 2
        return 3

    criterios = nivel_1 + nivel_2 + nivel_3
    n = len(criterios)
    if n == 0:
        raise ValueError(f"Nenhum critério ativo para calcular o ranking de {posicao}.")

    matriz_saaty = np.ones((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            t_i = obter_nivel(criterios[i])
            t_j = obter_nivel(criterios[j])
            if   t_i == 1 and t_j == 2: v = 2.0
            elif t_i == 1 and t_j == 3: v = 9.0
            elif t_i == 2 and t_j == 3: v = 5.0
            elif t_i == 2 and t_j == 1: v = 1/2
            elif t_i == 3 and t_j == 1: v = 1/9
            elif t_i == 3 and t_j == 2: v = 1/5
            else: v = 1.0
            matriz_saaty[i, j] = v

    # Matriz normalizada X (mesma normalização benefício/custo do ranking)
    df_ranking = df[colunas_para_ver].copy()
    for col in colunas_para_ver:
        df_ranking[col] = pd.to_numeric(df_ranking[col], errors='coerce').fillna(0)
    X = np.zeros((len(df_ranking), n))
    for k, criterio in enumerate(criterios):
        if criterio not in df_ranking.columns:
            continue
        vmax = df_ranking[criterio].max()
        vmin = df_ranking[criterio].min()
        if vmax == vmin:
            continue
        if criterio in CRITERIOS_DE_CUSTO:
            X[:, k] = ((vmax - df_ranking[criterio]) / (vmax - vmin)).values
        else:
            X[:, k] = ((df_ranking[criterio] - vmin) / (vmax - vmin)).values

    return {'df': df, 'criterios': criterios, 'matriz': matriz_saaty, 'X': X}


def estimar_margem_ahp(df_bruto, posicao, niveis_usuario=None, n_sim=300, sigma=0.30, seed=42):
    """Estima a margem de erro da Nota Moneyball devida à subjetividade dos pesos do AHP.

    Os pesos vêm de julgamentos discretos de importância (níveis 1/2/3 → escala de
    Saaty). Como esses julgamentos são subjetivos, perturbamos a matriz de comparação
    par-a-par com ruído lognormal, recalculamos os pesos e as notas em `n_sim`
    simulações e medimos a dispersão da nota de cada jogador. A escala do ruído cresce
    com a Razão de Consistência (CR): julgamentos menos consistentes → maior incerteza.

    Retorna dict: jogadores, nota (base), lo/hi (IC ~95%), margem (meia-largura),
    cr, consistente, margem_media, n_sim.
    """
    prep = _preparar_ahp(df_bruto, posicao, niveis_usuario)
    criterios, X, M = prep['criterios'], prep['X'], prep['matriz']
    n = len(criterios)
    pesos0, cr, consistente = ahp.calcular_pesos_ahp(M)
    nota0 = 100.0 * (X @ pesos0)

    base = {
        'jogadores': prep['df']['Jogador'].values,
        'nota': nota0, 'cr': float(cr), 'consistente': bool(consistente),
    }
    if n < 2 or len(X) == 0:
        base.update({'lo': nota0, 'hi': nota0, 'margem': np.zeros(len(X)),
                     'margem_media': 0.0, 'n_sim': 0})
        return base

    rng = np.random.default_rng(seed)
    escala = sigma * (1.0 + 2.0 * min(float(cr), 0.5))
    iu = np.triu_indices(n, k=1)
    notas_sim = np.empty((n_sim, len(X)))
    for s in range(n_sim):
        Mp = M.copy()
        fatores = np.exp(rng.normal(0.0, escala, size=iu[0].shape[0]))
        Mp[iu] = M[iu] * fatores
        Mp[(iu[1], iu[0])] = 1.0 / Mp[iu]  # mantém a reciprocidade da matriz
        w, _, _ = ahp.calcular_pesos_ahp(Mp)
        notas_sim[s] = 100.0 * (X @ w)

    lo = np.percentile(notas_sim, 2.5, axis=0)
    hi = np.percentile(notas_sim, 97.5, axis=0)
    margem = (hi - lo) / 2.0
    base.update({'lo': lo, 'hi': hi, 'margem': margem,
                 'margem_media': float(np.mean(margem)), 'n_sim': int(n_sim)})
    return base


def gerar_rating_overall(df_bruto, posicao, niveis_usuario=None):
    """
    Calcula o Rating Overall para abas que não usam a lógica Moneyball
    (Time Estatísticas, Overall Análise).

    Diferente de gerar_ranking:
    - NÃO considera valor de mercado, salário, idade ou contrato.
    - NÃO possui critérios de custo (todos os critérios são "quanto maior, melhor").
    - Todos os critérios começam como nível 3 (menos importante) por padrão,
      e o usuário define manualmente os pesos via niveis_usuario.

    niveis_usuario: dict { criterio: 0|1|2|3 }
                    0 = Ignorar (excluído), 1/2/3 = níveis AHP.
                    None = todos nível 3 (padrão).

    Retorna: DataFrame com colunas [Jogador, Equipe, Rating_Overall]
             ('Equipe' = '—' quando a aba não possuir essa coluna).
             Lança ValueError com mensagem amigável em caso de erro recuperável.
    """
    # ── 1. Validação de entrada ────────────────────────────────────────────────
    if posicao not in CRITERIOS_PADRAO:
        raise ValueError(f"Aba '{posicao}' não reconhecida pelo sistema.")

    if df_bruto is None or df_bruto.empty:
        raise ValueError(f"A aba '{posicao}' está vazia na planilha.")

    if 'Jogador' not in df_bruto.columns:
        raise ValueError(f"Coluna 'Jogador' não encontrada na aba '{posicao}'.")

    # ── 2. Corte e limpeza do DataFrame ───────────────────────────────────────
    try:
        df = df_bruto.loc[:, 'Jogador':'Nota média'].copy()
    except KeyError:
        raise ValueError(
            f"Não foi possível localizar as colunas 'Jogador' e/ou 'Nota média' "
            f"na aba '{posicao}'. Verifique se a planilha está no formato correto."
        )

    df = df.dropna(subset=[df.columns[0]])
    if df.empty:
        raise ValueError(f"Nenhum jogador encontrado na aba '{posicao}' após remover linhas vazias.")

    # Remove linhas de seções auxiliares (ex: "Análise da Equipe" no Time Estatísticas),
    # que não representam jogadores. Identificadas por não terem uma posição válida (string).
    if 'Posição' in df.columns:
        df = df[df['Posição'].apply(lambda x: isinstance(x, str))]
        if df.empty:
            raise ValueError(f"Nenhum jogador válido encontrado na aba '{posicao}'.")

    # ── 3. Critérios e níveis ──────────────────────────────────────────────────
    padrao = CRITERIOS_PADRAO[posicao]
    colunas_id = COLUNAS_IDENTIFICACAO_OVERALL.get(posicao, ['Jogador'])
    colunas_para_ver = [c for c in padrao['colunas'] if c in df.columns and c not in colunas_id]

    if niveis_usuario:
        ignorados = {c for c, n in niveis_usuario.items() if n == 0}
        nivel_1 = [c for c, n in niveis_usuario.items() if n == 1 and c in df.columns and c not in ignorados and c not in colunas_id]
        nivel_2 = [c for c, n in niveis_usuario.items() if n == 2 and c in df.columns and c not in ignorados and c not in colunas_id]
        nivel_3 = [c for c, n in niveis_usuario.items() if n == 3 and c in df.columns and c not in ignorados and c not in colunas_id]
        colunas_para_ver = [c for c in colunas_para_ver if c not in ignorados]

        ativos = nivel_1 + nivel_2 + nivel_3
        if len(ativos) < MIN_CRITERIOS_ATIVOS:
            raise ValueError(
                f"São necessários pelo menos {MIN_CRITERIOS_ATIVOS} critérios ativos "
                f"para calcular o Rating Overall de {posicao}. "
                f"Você marcou todos como 'Ignorar' ou deixou menos de {MIN_CRITERIOS_ATIVOS} ativos."
            )
    else:
        # Padrão: todos os critérios começam em nível 3 (menos importante)
        nivel_1 = []
        nivel_2 = []
        nivel_3 = list(colunas_para_ver)

    if not colunas_para_ver:
        raise ValueError(
            f"Nenhuma coluna de critério encontrada na aba '{posicao}'. "
            f"Verifique se os nomes das colunas da planilha estão corretos."
        )

    def obter_nivel(criterio):
        if criterio in nivel_1: return 1
        if criterio in nivel_2: return 2
        return 3

    criterios = nivel_1 + nivel_2 + nivel_3
    n = len(criterios)

    if n == 0:
        raise ValueError(f"Nenhum critério ativo para calcular o Rating Overall de {posicao}.")

    # ── 4. Matriz AHP ──────────────────────────────────────────────────────────
    if n == 1:
        # Caso degenerado: um único critério ativo => peso 100%
        pesos = [1.0]
    else:
        matriz_saaty = np.ones((n, n))
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                t_i = obter_nivel(criterios[i])
                t_j = obter_nivel(criterios[j])
                if   t_i == 1 and t_j == 2: v = 2.0
                elif t_i == 1 and t_j == 3: v = 9.0
                elif t_i == 2 and t_j == 3: v = 5.0
                elif t_i == 2 and t_j == 1: v = 1/2
                elif t_i == 3 and t_j == 1: v = 1/9
                elif t_i == 3 and t_j == 2: v = 1/5
                else: v = 1.0
                matriz_saaty[i, j] = v

        try:
            pesos, cr, consistente = ahp.calcular_pesos_ahp(matriz_saaty)
        except Exception as e:
            raise ValueError(f"Erro no cálculo AHP para {posicao}: {e}")

        if pesos is None or len(pesos) != n:
            raise ValueError(f"O cálculo AHP retornou pesos inválidos para {posicao}.")

    # ── 5. Rating ──────────────────────────────────────────────────────────────
    df_rating = df[colunas_para_ver].copy()

    # Garante que todas as colunas de critério são numéricas
    for col in colunas_para_ver:
        df_rating[col] = pd.to_numeric(df_rating[col], errors='coerce').fillna(0)

    df_rating['Rating_Overall'] = 0.0

    for criterio, peso in zip(criterios, pesos):
        if criterio not in df_rating.columns:
            continue
        vmax = df_rating[criterio].max()
        vmin = df_rating[criterio].min()
        if vmax == vmin:
            df_rating[f'{criterio}_Norm'] = 0.0
        else:
            # Todos os critérios são de benefício: quanto maior, melhor
            df_rating[f'{criterio}_Norm'] = (df_rating[criterio] - vmin) / (vmax - vmin)
        df_rating['Rating_Overall'] += df_rating[f'{criterio}_Norm'] * peso

    df_rating['Rating_Overall'] *= 100

    # ── 6. Resultado ───────────────────────────────────────────────────────────
    df_final = pd.DataFrame()
    df_final['Jogador']        = df['Jogador'].values
    df_final['Rating_Overall'] = df_rating['Rating_Overall'].values
    df_final['Equipe']         = df['Equipe'].values if 'Equipe' in df.columns else '—'

    df_final = df_final.sort_values(by='Rating_Overall', ascending=False).reset_index(drop=True)

    return df_final[['Jogador', 'Equipe', 'Rating_Overall']]


def extrair_estatisticas_time(df_bruto):
    """
    Extrai as estatísticas agregadas do time a partir da seção "Análise da Equipe"
    presente na aba 📊Time Estatísticas (abaixo da lista de 11 titulares).

    A seção é organizada como pares (label, valor) em duas colunas lado a lado,
    a partir da linha onde a coluna 0 contém o texto "Análise da Equipe".

    Retorna: dict {nome_da_metrica: valor} ou {} se a seção não for encontrada.
    """
    try:
        df_raw = df_bruto.copy()
        df_raw.columns = range(df_raw.shape[1])  # normaliza nomes de colunas para índices

        # Localiza a linha que contém "Análise da Equipe" na coluna 0
        col0 = df_raw[0].astype(str)
        linhas_match = df_raw.index[col0.str.contains('Análise da Equipe', na=False)]
        if len(linhas_match) == 0:
            return {}

        start_row = linhas_match[0]
        pares = {}
        for r in range(start_row, df_raw.shape[0]):
            for c_label, c_val in [(0, 1), (2, 3)]:
                if c_val >= df_raw.shape[1]:
                    continue
                label = df_raw.iloc[r, c_label]
                val = df_raw.iloc[r, c_val]
                if pd.notna(label) and pd.notna(val) and str(label) != 'Análise da Equipe':
                    pares[str(label)] = val

        return pares
    except Exception:
        return {}


def gerar_olheiro_time_prompt(stats_time, jogadores_titulares, perspectiva='proprio'):
    """
    Monta o prompt para o Olheiro IA analisar o desempenho agregado do time.

    stats_time: dict retornado por extrair_estatisticas_time
    jogadores_titulares: lista de dicts com dados dos 11 titulares (Jogador, Posição, Nota média, etc.)
    perspectiva: 'proprio'    -> análise interna, focada em pontos de melhoria e reforços
                 'adversario' -> visão de scout rival, focada em como explorar o time
    """
    if perspectiva == 'adversario':
        instrucoes = """
    Você está analisando este time como o OLHEIRO DE UM CLUBE ADVERSÁRIO que vai enfrentá-lo.
    Seu objetivo é identificar como explorar as fraquezas desta equipe.

    Escreva uma análise direta e profissional do ponto de vista do adversário:
    - Identifique as principais fragilidades estatísticas do time (defensivas, de posse, de criação
      de chances etc.) que podem ser exploradas taticamente.
    - Aponte quais jogadores titulares têm notas mais baixas e podem ser visados como "elos fracos"
      durante o jogo (ex: pressão alta sobre eles, duelos individuais).
    - Sugira no máximo 2 estratégias táticas concretas para o time adversário aproveitar essas
      fraquezas (ex: explorar lado fraco, pressionar saída de bola, etc.).
    - Seja objetivo e baseado em números, evitando opiniões sem fundamento estatístico.

    Assine o final como Olheiro Adversário IA."""
    else:
        instrucoes = """
    Você é o analista técnico DESTE PRÓPRIO TIME, avaliando o desempenho coletivo da equipe.

    Escreva uma análise direta e profissional sobre o desempenho coletivo da equipe:
    - Identifique pontos fortes e fracos com base nas estatísticas de equipe (passes, finalizações,
      eficiência defensiva, posse de bola, etc.)
    - Questione o desempenho da equipe: a equipe está criando chances suficientes? A defesa está sólida?
    - Com base nas notas médias dos titulares, sugira no máximo 2 posições onde uma troca/reforço
      poderia trazer mais impacto, justificando com os dados.
    - Seja objetivo e baseado em números, evitando opiniões sem fundamento estatístico.

    Assine o final como Olheiro IA."""

    return f"""
    Você é um analista técnico de futebol especializado em estatísticas avançadas (Football Manager).

    Aqui estão as estatísticas agregadas do time (médias por 90 minutos e totais):
    {stats_time}

    Aqui está a escalação titular analisada (11 jogadores com suas notas):
    {jogadores_titulares}
    {instrucoes}
    """