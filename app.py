import streamlit as st
import pandas as pd
import re
import main
import historico as hist
from main import CRITERIOS_PADRAO, POSICOES_OVERALL, COLUNAS_IDENTIFICACAO_OVERALL, extrair_estatisticas_time, gerar_olheiro_time_prompt
import google.generativeai as genai
import altair as alt
import math
from Funções import pix
from Funções import confiabilidade as confi

# Identificação do usuário via UUID persistido em query_params
# (executado antes de qualquer outro código para garantir que o UUID existe)
try:
    _usuario_id = hist.obter_ou_criar_usuario_id()
except Exception:
    _usuario_id = "anonimo"

st.set_page_config(
    page_title="Scout Moneyball",
    page_icon=":material/sports_soccer:",
    layout="wide",
)

# ==========================================
# ANIMAÇÃO CSS
# ==========================================
st.markdown("""
<style>
div[data-testid="stTabsContent"] > div {
    animation: fadeSlideIn 0.35s ease;
}
@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0);    }
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# CONSTANTES
# ==========================================
POSICOES = ['🧤Goleiros', '🧱Zagueiros', '🛡️Laterais', '🛡️Volantes',
            '🏃‍♂️Box-To-Box', '🎯Armadores', '⚽Avançados']

# Aba de Time (dashboard agregado + olheiro do time, sem ranking de jogadores)
POSICAO_TIME = '📊Time Estatísticas'
# Aba de Overall (Rating Overall via AHP)
POSICAO_OVERALL = '🔍Overall Análise'

# Abas que usam Rating Overall (sem lógica de custo/benefício Moneyball)
POSICOES_TODAS = POSICOES + POSICOES_OVERALL


# ==========================================
# NORMALIZAÇÃO DAS ABAS DA PLANILHA
# O app casa as abas pelo NOME (ex.: "Zagueiros"), tolerando diferenças de
# emoji na frente entre versões da planilha. Sem isso, uma aba "🛡️Zagueiros"
# não seria reconhecida quando o app espera "🧱Zagueiros", e a posição
# simplesmente não apareceria para escolher.
# ==========================================
def _nome_base_aba(nome):
    """Remove emojis/símbolos e espaços iniciais, deixando só o texto do nome.
    Ex.: '🛡️Zagueiros' -> 'Zagueiros'."""
    return re.sub(r'^[^0-9A-Za-zÀ-ÿ]+', '', str(nome)).strip()


# nome-base (sem emoji) -> nome canônico que o app usa internamente
_MAPA_NOME_CANONICO = {_nome_base_aba(p): p for p in POSICOES_TODAS}


def normalizar_banco(banco):
    """Renomeia as abas lidas da planilha para os nomes canônicos do app,
    casando pelo nome-base (ignorando o emoji). Abas sem correspondência
    mantêm o nome original."""
    if not isinstance(banco, dict):
        return banco
    banco_norm = {}
    for nome, df in banco.items():
        canonico = _MAPA_NOME_CANONICO.get(_nome_base_aba(nome), nome)
        banco_norm[canonico] = df
    return banco_norm

# Modos de análise disponíveis
MODOS = {
    'posicoes': {
        'label': 'Posições',
        'icone': '⚽',
        'descricao': 'Rankings Moneyball por posição (Goleiros, Zagueiros, Laterais...)',
        'abas': POSICOES,
    },
    'time': {
        'label': 'Time',
        'icone': '📊',
        'descricao': 'Dashboard agregado da equipe e Olheiro do Time',
        'abas': [POSICAO_TIME],
    },
    'overall': {
        'label': 'Overall',
        'icone': '🔍',
        'descricao': 'Rating Overall dos jogadores via AHP, baseado em desempenho',
        'abas': [POSICAO_OVERALL],
    },
}

COLUNAS_POR_POSICAO = {
    '🧤Goleiros': ['Jogador', 'Equipe', 'Valor estimado', 'Idade', 'Salário', 'Altura',
                   'Data final de contrato', 'Jogos completos', 'Expected Goals Prevented xGP',
                   'Falhas/90', '% Acerto do goleiro', 'Defesas totais / Jogo', 'Nota média'],
    '🧱Zagueiros': ['Jogador', 'Equipe', 'Valor', 'Idade', 'Salário', 'Altura',
                    'Data final de contrato', 'Jogos completos', 'Desarmes Decisivos / 90',
                    'Acertos (Cabs, Des, Pres)', 'Acertos/90', 'Bolas roubadas /90',
                    '% Bolas disputadas e ganhas', 'Erros Defensivos /90', 'Eficácia defensiva', 'Nota média'],
    '🛡️Laterais': ['Jogador', 'Equipe', 'Valor Estimado', 'Idade', 'Salário', 'Altura',
                    'Jogos completos', 'Participação / 90', 'Fintas / 90',
                    'Minutos pra criar uma chance de perigo', 'Cruzamentos Conseguidos',
                    'xA + xG /90', 'Gols + A/90', 'Movimentos ofensivos com sucesso',
                    'Dist / 90', 'Erros Defensivos /90', 'Eficácia defensiva', 'Nota média'],
    '🛡️Volantes': ['Jogador', 'Equipe', 'Valor', 'Idade', 'Salário', 'Jogos Completos',
                    'Data Final de Contrato', 'Cartões por falta cometida',
                    '% Pressão ganha/90', '% Bolas disputadas e ganhas (sem falta)',
                    'Passes certos  - errados / Jogo', 'Passes em progressão/90',
                    'Eficácia defensiva', 'xA por passe decisivo', 'Criação / 90',
                    'Distância /90', 'Nota média'],
    '🏃‍♂️Box-To-Box': ['Jogador', 'Equipe', 'Valor', 'Idade', 'Salário', 'Jogos completos',
                       'Fim de contrato', 'Taxa de Conversão %',
                       'Participação por jogo (passes, fnt, fin, criação, roubadas de bola, etc)',
                       '% Acerto', 'xA / Passe Decisivo', 'Dist / 90', 'Último terço/90', 'Nota média'],
    '🎯Armadores': ['Jogador', 'Equipe', 'Valor', 'Idade', 'Salário', 'Jogos completos',
                    'Data Final do contrato', 'Gols+ Assist / 90', 'Fintas /90',
                    'non Pen xG /90', 'xA /90', '% Cruzamentos certos',
                    'Passes Decisivos pra uma assistência', 'xA / Passe Decisivo',
                    'Finalizações no gol/90', 'Ações com Bola T/90', '% Sucesso de ações com bola',
                    'Dist / 90', 'Nota média'],
    '⚽Avançados': ['Jogador', 'Equipe', 'Valor Estimado', 'Idade', 'Salário', 'Jogos completos',
                    'Data Final do contrato', 'Gols Sem Pênalti /90', 'Gols de dentro da área /90',
                    'Finalizações no gol/90', 'GPI (Goal Probability Index)',
                    'Over xG / Under xG per 90', 'Minutos pra MARCAR um gol',
                    'Gols não esperados SEM PÊNALTI', 'Fintas/90', 'Eficácia ofensiva', 'Nota média'],
}

COLUNAS_INFO = {'Jogador', 'Equipe', 'Altura', 'Data final de contrato',
                'Data Final de Contrato', 'Data Final do contrato',
                'Fim de contrato', 'Salário', 'Valor estimado', 'Valor Estimado', 'Valor'}

CUSTO = {'Idade', 'Falhas/90', 'Erros Defensivos /90', 'Cartões por falta cometida',
         'Impedimentos / 90', 'Minutos pra MARCAR um gol',
         'Minutos pra acertar uma finalização no gol',
         'Minutos pra PARTICIPAR de um gol',
         'Minutos pra criar uma chance de perigo'}

COLUNAS_ABSOLUTAS_CANDIDATAS = [
    'Jogos completos', 'Jogos Completos', 'Partidas',
    'Gols', 'Assistências', 'Nota média', 'Altura', 'Nacionalidade', 'Pé preferido',
    'Data final de contrato', 'Data Final de Contrato',
    'Data Final do contrato', 'Fim de contrato', 'Contrato', 'Clube',
]

# ==========================================
# SESSION STATE
# ==========================================
if 'ja_calculou' not in st.session_state:
    st.session_state['ja_calculou'] = False
if 'rankings' not in st.session_state:
    st.session_state['rankings'] = {}  # {posicao: df_resultado}
if 'niveis_usuario' not in st.session_state:
    st.session_state['niveis_usuario'] = {}  # {posicao: {criterio: nivel}}
if 'configurado' not in st.session_state:
    st.session_state['configurado'] = {}  # {posicao: bool}
if 'modo_analise' not in st.session_state:
    st.session_state['modo_analise'] = None  # 'posicoes' | 'time' | 'overall'
if 'modo_confirmado' not in st.session_state:
    st.session_state['modo_confirmado'] = False

# ==========================================
# CSS GLOBAL
# ==========================================
st.markdown("""
<style>
/* Sidebar: "Feito por" fixo no rodapé */
[data-testid="stSidebar"] > div:first-child {
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
    overflow: hidden !important;
}
[data-testid="stSidebarContent"] {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
}
.sidebar-footer {
    position: sticky;
    bottom: 0;
    background: #080E0A;
    padding: 10px 0 6px 0;
    text-align: center;
    color: #6B7280;
    font-size: 11px;
    border-top: 1px solid #1E3A24;
    flex-shrink: 0;
}
.sidebar-footer strong { color: #9CA3AF; }

/* Navegação: botões nativos da sidebar estilizados como pills */
[data-testid="stSidebar"] .nav-section div[data-testid="stButton"] > button {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 9px 14px;
    border-radius: 10px;
    border: 1px solid transparent;
    background: transparent;
    color: #9CA3AF;
    font-size: 0.87rem;
    font-weight: 500;
    text-align: left;
    margin-bottom: 3px;
    transition: background 0.18s, border-color 0.18s, color 0.18s,
                transform 0.18s, box-shadow 0.18s;
    position: relative;
}
[data-testid="stSidebar"] .nav-section div[data-testid="stButton"] > button:hover {
    background: #0D1A0F;
    border-color: #1E3A24;
    color: #D1FAE5;
    transform: translateX(4px);
    box-shadow: 0 2px 12px rgba(34,197,94,0.07);
}
[data-testid="stSidebar"] .nav-section div[data-testid="stButton"] > button[kind="primary"] {
    background: #052E0A;
    border-color: #22C55E;
    color: #22C55E;
    font-weight: 700;
    box-shadow: 0 2px 14px rgba(34,197,94,0.13);
}
[data-testid="stSidebar"] .nav-section div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateX(4px);
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("⚙️ Configurações")

arquivo_upload = st.sidebar.file_uploader(
    "Planilha Moneyball (.xlsx ou .xlsm)",
    type=["xlsx", "xlsm"],
    disabled=st.session_state['ja_calculou']
)

st.sidebar.markdown("**🔍 Filtros de jogadores**")
ocultar_nao_a_venda = st.sidebar.checkbox(
    "Ocultar jogadores não à venda",
    value=False,
    disabled=st.session_state['ja_calculou'],
    help="Remove jogadores com valor marcado como 'Não está à venda' ou equivalente."
)
ocultar_valor_desconhecido = st.sidebar.checkbox(
    "Ocultar jogadores com valor desconhecido",
    value=False,
    disabled=st.session_state['ja_calculou'],
    help="Remove jogadores cujo valor de mercado não foi informado."
)

# Navegação por seção — depende do modo de análise escolhido
SECOES_POR_MODO = {
    'posicoes': [
        ("📊", "Dashboard", "dashboard"),
        ("📈", "Comparativo", "comparativo"),
        ("🛡️", "Confiabilidade", "confiabilidade"),
        ("🤖", "Olheiro IA", "scout"),
        ("🔍", "Ficha do Jogador", "ficha"),
        ("📋", "Planilha", "planilha"),
    ],
    'time': [
        ("📊", "Dashboard do Time", "dashboard_time"),
        ("🤖", "Olheiro do Time", "scout_time"),
    ],
    'overall': [
        ("📊", "Dashboard", "dashboard"),
        ("📈", "Comparação", "comparativo"),
        ("📋", "Planilha", "planilha"),
    ],
}

if st.session_state['ja_calculou']:
    modo_atual = st.session_state.get('modo_analise', 'posicoes')
    SECOES_LISTA = SECOES_POR_MODO.get(modo_atual, SECOES_POR_MODO['posicoes'])

    if 'secao_ativa' not in st.session_state or st.session_state['secao_ativa'] not in [c for _, _, c in SECOES_LISTA]:
        st.session_state['secao_ativa'] = SECOES_LISTA[0][2]

    st.sidebar.markdown("**📂 Seção**")
    st.sidebar.markdown('<div class="nav-section">', unsafe_allow_html=True)
    for icone, label, chave in SECOES_LISTA:
        ativo = st.session_state['secao_ativa'] == chave
        if st.sidebar.button(
            f"{icone}  {label}",
            key=f"nav_{chave}",
            use_container_width=True,
            type="primary" if ativo else "secondary"
        ):
            st.session_state['secao_ativa'] = chave
            st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    secao_ativa = st.session_state['secao_ativa']
else:
    secao_ativa = "dashboard"

col_btn1, col_btn2 = st.sidebar.columns(2)

# Abas a processar de acordo com o modo escolhido
_modo_atual_calc = st.session_state.get('modo_analise')
if _modo_atual_calc == 'posicoes':
    # Usa as posições confirmadas no popover (salvas no session_state)
    # Fallback para todas as posições se ainda não configurado
    _posicoes_sel = st.session_state.get('posicoes_confirmadas', POSICOES)
    _abas_do_modo = _posicoes_sel
elif _modo_atual_calc in MODOS:
    _abas_do_modo = MODOS[_modo_atual_calc]['abas']
else:
    _abas_do_modo = []

# Aba de Time não precisa de cálculo AHP — só extração de estatísticas
_abas_para_ahp = [a for a in _abas_do_modo if a != POSICAO_TIME]

# Para modo Overall, exige que todas as abas AHP estejam configuradas antes de habilitar
_overall_pendente = any(
    pos in POSICOES_OVERALL and not st.session_state['configurado'].get(pos)
    for pos in _abas_para_ahp
)

if (arquivo_upload is not None and not st.session_state['ja_calculou']
        and st.session_state['modo_confirmado']):
    if _overall_pendente:
        col_btn1.button("🚀 Calcular", use_container_width=True, disabled=True,
                        help="Confirme os critérios da aba Overall Análise primeiro.")
    elif col_btn1.button("🚀 Calcular", use_container_width=True):
        with st.spinner("Processando..."):
            try:
                banco = st.session_state.get('banco_de_dados_completo') or normalizar_banco(
                    pd.read_excel(arquivo_upload, sheet_name=None, engine='openpyxl'))
                st.session_state['banco_de_dados_completo'] = banco
            except Exception as e:
                st.error(f"Não foi possível ler a planilha: {e}")
                st.stop()

            rankings = {}
            erros_calc = {}
            for pos in _abas_para_ahp:
                if pos in banco:
                    try:
                        niveis = st.session_state['niveis_usuario'].get(pos)
                        if pos in POSICOES_OVERALL:
                            resultado = main.gerar_rating_overall(banco[pos], pos, niveis_usuario=niveis)
                        else:
                            resultado = main.gerar_ranking(banco[pos], pos, niveis_usuario=niveis)
                        if isinstance(resultado, str):
                            erros_calc[pos] = resultado
                        else:
                            rankings[pos] = resultado
                            st.session_state['configurado'][pos] = True
                    except ValueError as e:
                        erros_calc[pos] = str(e)
                    except Exception as e:
                        erros_calc[pos] = f"Erro inesperado: {e}"

            # Aba de Time: não gera ranking, mas precisa estar presente no banco
            time_disponivel = POSICAO_TIME in _abas_do_modo and POSICAO_TIME in banco

            if erros_calc:
                st.session_state['erros_calculo'] = erros_calc

            if not rankings and not time_disponivel:
                st.error("Nada pôde ser calculado. Verifique os critérios e a planilha.")
                if erros_calc:
                    for pos, msg in erros_calc.items():
                        st.warning(f"**{pos}:** {msg}")
            else:
                st.session_state['rankings'] = rankings
                st.session_state['ja_calculou'] = True

                # Salva no histórico (silencioso — não bloqueia em caso de erro)
                if rankings and hist.supabase_disponivel():
                    try:
                        _modo_salvo = st.session_state.get('modo_analise', 'posicoes')
                        hist.salvar_calculo(_usuario_id, rankings, _modo_salvo)
                    except Exception:
                        pass

                st.rerun()

if st.session_state['ja_calculou']:
    if col_btn2.button("🔄 Recomeçar", use_container_width=True):
        st.session_state['reiniciando'] = True
        st.rerun()

if st.session_state.get('reiniciando'):
    for key in ['ja_calculou', 'rankings', 'banco_de_dados_completo',
                'secao_ativa', 'niveis_usuario', 'configurado', 'erros_calculo', 'reiniciando',
                'modo_analise', 'modo_confirmado', 'posicoes_selecionadas', 'posicoes_confirmadas']:
        if key in st.session_state:
            del st.session_state[key]
    for pos in POSICOES_TODAS:
        for k in (f'relatorio_ia_{pos}', f'margem_ahp_{pos}'):
            if k in st.session_state:
                del st.session_state[k]
    k_time = f'relatorio_ia_{POSICAO_TIME}'
    if k_time in st.session_state:
        del st.session_state[k_time]
    st.session_state['ja_calculou'] = False
    # Restaura as abas padrão de posicoes (podem ter sido filtradas pelo popover)
    MODOS['posicoes']['abas'] = POSICOES
    st.rerun()

# Botão de histórico — aparece sempre; mostra diagnóstico se Supabase falhar
st.sidebar.markdown("---")
st.sidebar.markdown("**📜 Histórico**")
col_h1, col_h2 = st.sidebar.columns(2)
if col_h1.button("📊 Ranking", use_container_width=True, key="btn_historico"):
    st.session_state['ver_historico'] = not st.session_state.get('ver_historico', False)
    st.session_state['ver_emails_olheiro'] = False
    st.rerun()
if col_h2.button("📬 Olheiro", use_container_width=True, key="btn_emails_olheiro"):
    st.session_state['ver_emails_olheiro'] = not st.session_state.get('ver_emails_olheiro', False)
    st.session_state['ver_historico'] = False
    st.rerun()

# ==========================================
# APOIO VIA PIX
# ==========================================
# A chave fica nos secrets (CHAVE_PIX) para não expor dado pessoal no repositório.
# Sem a chave configurada, o botão simplesmente não aparece.
try:
    _chave_pix = str(st.secrets.get("CHAVE_PIX", "")).strip()
    _nome_pix = str(st.secrets.get("PIX_NOME", "Vinicius Rogato")).strip()
    _cidade_pix = str(st.secrets.get("PIX_CIDADE", "Sao Paulo")).strip()
except Exception:
    _chave_pix = ""

if _chave_pix:
    with st.sidebar:
        with st.popover("💚 Apoiar o projeto (Pix)", use_container_width=True):
            st.markdown("**Gostou do Scout Moneyball?**")
            st.caption(
                "O app é gratuito e mantido por uma pessoa só. "
                "Se ele te ajudou a montar seu elenco, considere apoiar com qualquer valor. 💚"
            )
            _payload_pix = pix.gerar_payload_pix(_chave_pix, _nome_pix, _cidade_pix)
            _qr_pix = pix.gerar_qr_pix(_payload_pix)
            if _qr_pix is not None:
                _col_qr = st.columns([1, 2, 1])[1]
                _col_qr.image(_qr_pix, caption="Escaneie no app do seu banco", width=180)
            st.markdown("**Chave Pix**")
            st.code(_chave_pix, language=None)
            st.markdown("**Pix copia e cola**")
            st.code(_payload_pix, language=None, wrap_lines=True)

st.sidebar.markdown(
    "<div class='sidebar-footer'>Feito por <strong>Vinícius Rogato</strong></div>",
    unsafe_allow_html=True
)

# ==========================================
# TELA DE BOAS-VINDAS
# ==========================================
# ==========================================
# PRÉ-CARREGAMENTO: lê a planilha assim que o upload acontece
# (antes de calcular, para mostrar as abas e tela de critérios)
# ==========================================
if arquivo_upload is None and not st.session_state['ja_calculou']:
    # Planilha removida — limpa banco para voltar à tela inicial
    if 'banco_de_dados_completo' in st.session_state:
        del st.session_state['banco_de_dados_completo']
        if 'configurado' in st.session_state:
            del st.session_state['configurado']
        if 'niveis_usuario' in st.session_state:
            del st.session_state['niveis_usuario']
        st.session_state['modo_analise'] = None
        st.session_state['modo_confirmado'] = False
        st.rerun()

if arquivo_upload is not None and 'banco_de_dados_completo' not in st.session_state:
    with st.spinner("⏳ Lendo planilha..."):
        _banco_lido = pd.read_excel(
            arquivo_upload, sheet_name=None, engine='openpyxl'
        )
        st.session_state['banco_de_dados_completo'] = normalizar_banco(_banco_lido)
    st.rerun()

# Tela intermediária de reiniciando (renderiza antes do rerun limpar o estado)
if st.session_state.get('reiniciando'):
    st.markdown("""
    <style>
    .mb-loading-screen {
        position: fixed; inset: 0;
        background: #070C09;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        gap: 24px; z-index: 9999;
    }
    .mb-loading-spinner {
        width: 52px; height: 52px;
        border: 3px solid #1E3A24;
        border-top-color: #22C55E;
        border-radius: 50%;
        animation: mbspin 0.75s linear infinite;
    }
    @keyframes mbspin { to { transform: rotate(360deg); } }
    .mb-loading-label {
        font-size: 0.8rem; font-weight: 700;
        color: #4ADE80; letter-spacing: 3px;
        text-transform: uppercase;
    }
    </style>
    <div class="mb-loading-screen">
        <div class="mb-loading-spinner"></div>
        <div class="mb-loading-label">Reiniciando...</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ==========================================
# TELA DE HISTÓRICO
# (disponível a qualquer momento, inclusive sem planilha carregada)
# ==========================================
if st.session_state.get('ver_historico'):
    st.markdown("## 📊 Histórico de Ranking")
    st.caption(f"ID de sessão: `{_usuario_id[:8]}...` · Últimos {hist.MAX_HISTORICO} cálculos salvos.")
    if not hist.supabase_disponivel():
        _diag = hist.diagnostico_supabase()
        st.error(f"Não foi possível conectar ao banco de dados. **Diagnóstico:** {_diag}")
        if st.button("← Voltar", key="fechar_historico_erro"):
            st.session_state['ver_historico'] = False
            st.rerun()
        st.stop()

    st.info(
        "🕐 **Limpeza automática:** registros com mais de 7 dias são removidos automaticamente "
        "todos os dias às 5h da manhã (horário de Brasília).",
        icon="🗑️"
    )

    with st.spinner("Carregando histórico..."):
        entradas = hist.carregar_historico(_usuario_id)

    if not entradas:
        st.info("Nenhum cálculo salvo ainda. Faça seu primeiro cálculo para começar a registrar o histórico.")
    else:
        for i, entrada in enumerate(entradas):
            dt = entrada.get("criado_em", "")
            try:
                dt_fmt = dt[:16].replace("T", " ")
            except Exception:
                dt_fmt = dt

            modo_entry = entrada.get("modo", "posicoes")
            modo_label = {"posicoes": "⚽ Posições", "time": "📊 Time", "overall": "🔍 Overall"}.get(modo_entry, modo_entry)
            dados = entrada.get("dados", {})
            n_pos = len(dados)

            with st.expander(f"**{dt_fmt}** · {modo_label} · {n_pos} posição(ões)", expanded=(i == 0)):
                if not dados:
                    st.caption("Sem dados salvos nesta entrada.")
                else:
                    for posicao, jogadores in dados.items():
                        st.markdown(f"**{posicao}**")
                        if jogadores:
                            df_hist = pd.DataFrame(jogadores)
                            nota_col = "Nota_Moneyball" if "Nota_Moneyball" in df_hist.columns else "Rating_Overall"
                            col_config_h = {}
                            if nota_col in df_hist.columns:
                                col_config_h[nota_col] = st.column_config.ProgressColumn(
                                    nota_col.replace("_", " "), min_value=0, max_value=100, format="%.1f")
                            st.dataframe(df_hist, column_config=col_config_h, hide_index=True)
                        else:
                            st.caption("Sem jogadores nesta posição.")

                col_del, _ = st.columns([1, 4])
                if col_del.button("🗑️ Remover entrada", key=f"del_hist_{entrada['id']}", type="secondary"):
                    if hist.deletar_entrada(entrada["id"]):
                        st.success("Entrada removida.")
                        st.rerun()
                    else:
                        st.error("Erro ao remover entrada.")

    st.markdown("---")
    if st.button("← Voltar", key="fechar_historico"):
        st.session_state['ver_historico'] = False
        st.rerun()


# ==========================================
# TELA DE E-MAILS DO OLHEIRO
# ==========================================
if st.session_state.get('ver_emails_olheiro'):
    st.markdown("## 📬 E-mails do Olheiro")
    st.caption(f"ID de sessão: `{_usuario_id[:8]}...` · Últimos {hist.MAX_EMAILS} relatórios salvos.")
    if not hist.supabase_disponivel():
        _diag = hist.diagnostico_supabase()
        st.error(f"Não foi possível conectar ao banco de dados. **Diagnóstico:** {_diag}")
        if st.button("← Voltar", key="fechar_emails_erro"):
            st.session_state['ver_emails_olheiro'] = False
            st.rerun()
        st.stop()

    st.info(
        "🕐 **Limpeza automática:** registros com mais de 7 dias são removidos automaticamente "
        "todos os dias às 5h da manhã (horário de Brasília).",
        icon="🗑️"
    )

    with st.spinner("Carregando e-mails..."):
        emails = hist.carregar_emails_olheiro(_usuario_id)

    if not emails:
        st.info("Nenhum relatório salvo ainda. Gere uma análise com o Olheiro IA para começar.")
    else:
        MODO_LABELS = {"posicoes": "⚽ Posições", "time": "📊 Time", "overall": "🔍 Overall"}
        PERSP_LABELS = {"proprio": "🛡️ Meu Time", "adversario": "🎯 Adversário", "": ""}

        for i, email in enumerate(emails):
            dt = email.get("criado_em", "")
            try:
                from datetime import datetime as _dt
                dt_obj = _dt.fromisoformat(dt.replace("Z", "+00:00"))
                dt_fmt = dt_obj.strftime("%d/%m %H:%M")
            except Exception:
                dt_fmt = dt[:16].replace("T", " ")

            posicao_e  = email.get("posicao", "—")
            persp_e    = PERSP_LABELS.get(email.get("perspectiva", ""), "")
            titulo = f"{posicao_e} · {dt_fmt}" + (f" · {persp_e}" if persp_e else "")

            with st.expander(titulo, expanded=(i == 0)):
                st.markdown(email.get("texto", "—"))
                col_del, _ = st.columns([1, 4])
                if col_del.button("🗑️ Remover", key=f"del_email_{email['id']}", type="secondary"):
                    if hist.deletar_email_olheiro(email["id"]):
                        st.success("Relatório removido.")
                        st.rerun()
                    else:
                        st.error("Erro ao remover.")

    st.markdown("---")
    if st.button("← Voltar", key="fechar_emails_olheiro"):
        st.session_state['ver_emails_olheiro'] = False
        st.rerun()

    st.stop()

    st.stop()


if not st.session_state['ja_calculou'] and 'banco_de_dados_completo' not in st.session_state:

    st.markdown("""
    <style>
    /* Hero */
    .hero-title { font-size:2.6rem; font-weight:800; letter-spacing:-0.5px; margin-bottom:0; }
    .hero-sub   { font-size:1rem; color:#6B7280; margin-top:4px; margin-bottom:0; }

    /* Steps grid */
    .steps-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin:0; }
    .step-card {
        background:#080E0A;
        border:1px solid #1E3A24;
        border-radius:10px;
        padding:14px 12px;
        transition: border-color 0.2s, transform 0.2s;
        cursor:default;
    }
    .step-card:hover { border-color:#22C55E; transform:translateY(-3px); }
    .step-n { font-size:1.4rem; font-weight:800; color:#22C55E; margin-bottom:6px; }
    .step-t { font-size:0.82rem; font-weight:700; color:#E8F5E9; margin-bottom:4px; }
    .step-d { font-size:0.75rem; color:#6B7280; line-height:1.4; }

    /* Channel cards */
    .partners-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .partner-card {
        background:#080E0A;
        border:1px solid #1E3A24;
        border-radius:12px;
        padding:16px;
        text-decoration:none;
        display:flex;
        flex-direction:column;
        align-items:center;
        gap:10px;
        transition: border-color 0.25s, transform 0.25s, box-shadow 0.25s;
        text-align:center;
    }
    .partner-card:hover {
        border-color:#22C55E;
        transform:translateY(-4px);
        box-shadow:0 8px 24px rgba(34,197,94,0.12);
        text-decoration:none;
    }
    .yt-logo { width:36px; height:36px; }
    .partner-name { font-weight:700; font-size:0.92rem; color:#E8F5E9; }
    .partner-handle { font-size:0.75rem; color:#6B7280; }
    .yt-badge {
        display:inline-flex; align-items:center; gap:5px;
        background:#FF0000; color:#fff;
        border-radius:5px; padding:2px 8px;
        font-size:0.7rem; font-weight:700; margin-top:2px;
    }
    .twitch-badge {
        display:inline-flex; align-items:center; gap:5px;
        background:#9146FF; color:#fff;
        border-radius:5px; padding:2px 8px;
        font-size:0.7rem; font-weight:700; margin-top:2px;
    }

    /* Update */
    .update-tag {
        display:inline-block; background:#052E0A; color:#22C55E;
        border:1px solid #1E3A24; border-radius:6px;
        padding:2px 10px; font-size:0.75rem; font-weight:600; margin-bottom:6px;
    }
    .update-item { font-size:0.82rem; color:#9CA3AF; padding:3px 0; }
    </style>
    """, unsafe_allow_html=True)

    # Hero
    st.markdown('<p class="hero-title">🏆 Scout Moneyball</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Análise estatística de jogadores do Football Manager com método AHP</p>', unsafe_allow_html=True)

    if arquivo_upload is not None:
        st.success("✅ Planilha carregada! Escolha o modo de análise para continuar.")

    st.markdown("---")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        # ---- Tutorial compacto em grid ----
        st.markdown("### 📖 Como usar")
        st.space("small")
        st.markdown("""
        <div class="steps-grid">
          <div class="step-card">
            <div class="step-n">1</div>
            <div class="step-t">Upload</div>
            <div class="step-d">Arraste sua planilha .xlsx ou .xlsm na barra lateral</div>
          </div>
          <div class="step-card">
            <div class="step-n">2</div>
            <div class="step-t">Modo</div>
            <div class="step-d">Escolha entre Posições, Time ou Overall</div>
          </div>
          <div class="step-card">
            <div class="step-n">3</div>
            <div class="step-t">Critérios</div>
            <div class="step-d">Ajuste os pesos AHP (opcional em Posições, obrigatório em Overall)</div>
          </div>
          <div class="step-card">
            <div class="step-n">4</div>
            <div class="step-t">Calcular</div>
            <div class="step-d">Clique em 🚀 Calcular para processar as abas do modo escolhido</div>
          </div>
          <div class="step-card">
            <div class="step-n">5</div>
            <div class="step-t">Seções</div>
            <div class="step-d">Use o menu lateral para navegar pelas seções do modo</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.space("medium")

        # ---- Patch notes ----
        st.markdown("### 🔄 Última atualização")
        st.space("small")

        st.markdown('<span class="update-tag">v2.6 · Set 2026</span>', unsafe_allow_html=True)
        v26 = [
            "Nova seção Confiabilidade — Score de Confiabilidade (0–100) por jogador, com métricas específicas de cada posição",
            "Índice composto ponderado por percentis: compara o jogador contra os pares da mesma posição e penaliza mais os erros graves (ex.: erro que gera gol)",
            "Barras de percentil por métrica, radar comparativo entre dois jogadores e matriz de risco (produção × erros)",
            "Confiabilidade agora tem duas abas: Análise padrão e Análise avançada (Índice geral, Estabilidade, Consistência, Confiança e prioridade de evolução por jogador)",
            "Botão de download do plugin Ctrl+P (Vinteset) na tela inicial",
            "Margem de erro do cálculo no Dashboard — mostra o quanto a nota pode variar conforme os pesos escolhidos",
        ]
        for n in v26:
            st.markdown(f'<div class="update-item">• {n}</div>', unsafe_allow_html=True)

        st.space("small")
        with st.expander("📋 v2.5 · Ago 2026 — notas anteriores"):
            v25 = [
                "Compatibilidade com diferentes versões da planilha — as posições agora são reconhecidas pelo nome da aba, independentemente do emoji (corrige posições que não apareciam para seleção)",
                "Botão de download da planilha Moneyball (Allan FCL) na tela inicial",
            ]
            for n in v25:
                st.markdown(f'<div class="update-item">• {n}</div>', unsafe_allow_html=True)

        st.space("small")
        with st.expander("📋 v2.4 · Jun 2025 — notas anteriores"):
            v24 = [
                "Seleção de posições via popover — escolha quais posições analisar antes de calcular",
                "Histórico de cálculos por usuário via Supabase (top 10 por posição, últimas 10 sessões)",
                "Histórico acessível a qualquer momento, mesmo sem planilha carregada",
                "Limpeza automática do histórico a cada 24h às 5h (via pg_cron no Supabase)",
                "Perspectiva dupla no Olheiro do Time: análise interna ou visão de scout adversário",
            ]
            for n in v24:
                st.markdown(f'<div class="update-item">• {n}</div>', unsafe_allow_html=True)

        st.space("small")
        with st.expander("📋 v2.3 · Jun 2025 — notas anteriores"):
            v23 = [
                "Seleção de modo de análise: Posições, Time ou Overall",
                "Modo Time: dashboard agregado da equipe (por 90 min) + Olheiro do Time",
                "Modo Overall: Rating Overall via AHP com configuração de critérios obrigatória",
                "Sidebar dinâmica — seções mudam conforme o modo escolhido",
                "Critérios das abas Overall filtrados para métricas por 90 minutos e percentuais",
            ]
            for n in v23:
                st.markdown(f'<div class="update-item">• {n}</div>', unsafe_allow_html=True)

        st.space("small")
        with st.expander("📋 v2.2 · Jun 2025 — notas anteriores"):
            v22 = [
                "Configuração de critérios AHP por posição com interface estilo menu de jogo",
                "Opção de Ignorar critérios — excluídos do cálculo AHP",
                "Cálculo automático com pesos padrão para posições não configuradas",
                "Tratamento completo de erros e exceções em todo o sistema",
                "Tela de loading ao fazer upload e ao reiniciar",
                "Ficha do jogador reformulada com design de cartão e gráfico de nota circular",
                "Planilha completa com todos os dados originais do upload",
                "Ranking visual no comparativo substituindo gráfico de barras",
            ]
            for n in v22:
                st.markdown(f'<div class="update-item">• {n}</div>', unsafe_allow_html=True)

        st.space("small")
        with st.expander("📋 v2.1 · Jun 2025 — notas anteriores"):
            v21 = [
                "Abas por posição — todas processadas de uma vez",
                "Navegação por seções na barra lateral com botões animados",
                "Ficha do jogador com estatísticas completas e comparativo vs líder",
                "Filtros de disponibilidade (à venda / valor desconhecido)",
                "Comparativo interativo com scatter e ranking por atributo",
                "Olheiro IA individual por posição",
                "Tela inicial com tutorial, parceiros e changelog",
                "Banner FM26 com degradê na área principal",
                "Canais recomendados com cards animados e descrição dos plugins",
                "Assinatura do criador fixada no rodapé da sidebar",
            ]
            for n in v21:
                st.markdown(f'<div class="update-item">• {n}</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown("### 📺 Canais recomendados")
        st.space("small")

        yt_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="#FF0000"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>'
        twitch_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="#9146FF"><path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/></svg>'

        st.markdown(f"""
        <style>
        .ch-row {{ display:flex; gap:8px; margin-bottom:12px; }}
        .ch-card {{
            flex:1; background:#080E0A; border:1px solid #1E3A24;
            border-radius:10px; padding:10px 8px; text-decoration:none !important;
            display:flex; flex-direction:column; align-items:center; gap:4px;
            text-align:center; transition: border-color .2s, transform .2s, box-shadow .2s;
        }}
        .ch-card:hover {{
            border-color:#22C55E; transform:translateY(-4px);
            box-shadow:0 8px 22px rgba(34,197,94,0.13); text-decoration:none !important;
        }}
        .ch-name {{ font-weight:700; font-size:0.8rem; color:#E8F5E9; }}
        .ch-handle {{ font-size:0.66rem; color:#6B7280; }}
        .ch-badge-yt {{
            display:inline-flex; align-items:center; gap:3px;
            background:#FF0000; color:#fff; border-radius:4px;
            padding:1px 5px; font-size:0.6rem; font-weight:700;
        }}
        .ch-badge-tw {{
            display:inline-flex; align-items:center; gap:3px;
            background:#9146FF; color:#fff; border-radius:4px;
            padding:1px 5px; font-size:0.6rem; font-weight:700;
        }}
        .ch-info {{
            background:#080E0A; border:1px solid #1E3A24;
            border-radius:10px; padding:10px 12px; margin-bottom:8px;
        }}
        .ch-info-title {{ font-size:0.77rem; font-weight:700; color:#22C55E; margin-bottom:3px; }}
        .ch-info-desc {{ font-size:0.72rem; color:#9CA3AF; line-height:1.45; }}
        .ch-dl {{
            display:inline-flex; align-items:center; gap:4px; margin-top:8px;
            background:#22C55E; color:#04120A !important; border-radius:6px;
            padding:4px 9px; font-size:0.68rem; font-weight:700;
            text-decoration:none !important; transition: background .2s, transform .2s;
        }}
        .ch-dl:hover {{
            background:#4ADE80; transform:translateY(-1px); text-decoration:none !important;
        }}
        </style>
        <div class="ch-row">
          <a href="https://www.youtube.com/@AllanFCL" target="_blank" class="ch-card">
            {yt_svg}
            <div class="ch-name">Allan FCL</div>
            <div class="ch-handle">@AllanFCL</div>
            <span class="ch-badge-yt">▶ YouTube</span>
          </a>
          <a href="https://www.youtube.com/@Vinteset" target="_blank" class="ch-card">
            {yt_svg}
            <div class="ch-name">Vinteset</div>
            <div class="ch-handle">@Vinteset</div>
            <span class="ch-badge-yt">▶ YouTube</span>
          </a>
          <a href="https://www.twitch.tv/vinteset" target="_blank" class="ch-card">
            {twitch_svg}
            <div class="ch-name">Vinteset</div>
            <div class="ch-handle">vinteset</div>
            <span class="ch-badge-tw">● Twitch</span>
          </a>
        </div>
        <div class="ch-info">
          <div class="ch-info-title">📊 Planilha Moneyball — Allan FCL</div>
          <div class="ch-info-desc">A planilha usada neste app foi desenvolvida pelo Allan FCL.
          Ela estrutura os dados exportados do FM em abas por posição com métricas específicas para cada
          função tática e compatíveis com o cálculo AHP.</div>
          <a href="https://www.mediafire.com/file/8iewmh1973mrz9q/Allan+FCL+-+Moneyball+-+FM2026.rar/file"
             target="_blank" class="ch-dl">⬇ Baixar a planilha (MediaFire)</a>
        </div>
        <div class="ch-info">
          <div class="ch-info-title">⌨️ Plugin Ctrl+P — Vinteset</div>
          <div class="ch-info-desc">O plugin <strong style="color:#E8F5E9">Ctrl+P</strong> criado pelo
          Vinteset é essencial para exportar os dados dos jogadores do FM para a planilha. Sem ele, a
          extração de estatísticas não seria possível. Acesse o canal dele para aprender a instalar e usar.</div>
          <a href="https://www.mediafire.com/file/6294gatujtsflr6/FM26PlayerExport_v5.1.rar/file"
             target="_blank" class="ch-dl">⬇ Baixar o plugin Ctrl+P (MediaFire)</a>
        </div>
        <p style="font-size:0.72rem; color:#6B7280; line-height:1.4; margin-top:4px;">
          🙏 Agradecimento especial ao <strong style="color:#9CA3AF">Allan FCL</strong> e ao
          <strong style="color:#9CA3AF">Vinteset</strong> — acompanhe os canais para aprender mais
          sobre FM26 e montar elencos competitivos!
        </p>
        """, unsafe_allow_html=True)

    st.stop()


# ==========================================
# SELEÇÃO DE MODO DE ANÁLISE
# (aparece após o upload, antes do cálculo)
# ==========================================
if not st.session_state['ja_calculou'] and not st.session_state['modo_confirmado']:

    banco_pre = st.session_state.get('banco_de_dados_completo', {})

    st.markdown("""
    <style>
    .mode-title { font-size:1.8rem; font-weight:800; margin-bottom:4px; }
    .mode-sub   { font-size:0.92rem; color:#6B7280; margin-bottom:24px; }
    .mode-card {
        background:#080E0A; border:1px solid #1E3A24; border-radius:14px;
        padding:24px 20px; text-align:center; height:100%;
        transition: border-color .2s, transform .2s, box-shadow .2s;
    }
    .mode-card:hover {
        border-color:#22C55E; transform:translateY(-4px);
        box-shadow:0 10px 28px rgba(34,197,94,0.12);
    }
    .mode-icon { font-size:2.4rem; margin-bottom:8px; }
    .mode-name { font-size:1.1rem; font-weight:800; color:#E8F5E9; margin-bottom:6px; }
    .mode-desc { font-size:0.8rem; color:#9CA3AF; line-height:1.4; min-height:3.4em; }
    .mode-unavailable { opacity:0.4; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="mode-title">🎯 O que você quer analisar?</p>', unsafe_allow_html=True)
    st.markdown('<p class="mode-sub">Escolha um modo para continuar. Para trocar depois, use 🔄 Recomeçar.</p>', unsafe_allow_html=True)

    cols_modo = st.columns(3)
    for col, (chave_modo, info) in zip(cols_modo, MODOS.items()):
        abas_presentes = [a for a in info['abas'] if a in banco_pre]
        disponivel = len(abas_presentes) > 0

        with col:
            card_class = "mode-card" if disponivel else "mode-card mode-unavailable"
            st.markdown(f"""
            <div class="{card_class}">
                <div class="mode-icon">{info['icone']}</div>
                <div class="mode-name">{info['label']}</div>
                <div class="mode-desc">{info['descricao']}</div>
            </div>
            """, unsafe_allow_html=True)

            if disponivel:
                # Modo Posições: popover com checkboxes para selecionar quais posições analisar
                if chave_modo == 'posicoes':
                    with st.popover(f"Selecionar {info['label']}", use_container_width=True):
                        st.markdown("**Escolha as posições a analisar:**")
                        st.caption("Nenhuma selecionada por padrão — marque as que deseja.")

                        chave_sel = 'posicoes_selecionadas'
                        if chave_sel not in st.session_state:
                            # Padrão: todas desmarcadas
                            st.session_state[chave_sel] = {p: False for p in abas_presentes}

                        # Garante que posições novas da planilha entrem como desmarcadas
                        for p in abas_presentes:
                            if p not in st.session_state[chave_sel]:
                                st.session_state[chave_sel][p] = False

                        for posicao_opt in abas_presentes:
                            st.session_state[chave_sel][posicao_opt] = st.checkbox(
                                posicao_opt,
                                value=st.session_state[chave_sel].get(posicao_opt, False),
                                key=f"chk_{posicao_opt}"
                            )

                        ativas = [p for p in abas_presentes if st.session_state[chave_sel].get(p)]
                        st.caption(f"{len(ativas)} de {len(abas_presentes)} posições selecionadas.")

                        if len(ativas) == 0:
                            st.warning("⚠️ Selecione ao menos uma posição para continuar.")

                        if st.button("✅ Confirmar seleção", key="confirmar_posicoes",
                                     use_container_width=True, type="primary",
                                     disabled=len(ativas) == 0):
                            st.session_state['posicoes_confirmadas'] = ativas
                            st.session_state['modo_analise'] = 'posicoes'
                            st.session_state['modo_confirmado'] = True
                            st.rerun()
                else:
                    if st.button(f"Selecionar {info['label']}", key=f"modo_{chave_modo}",
                                 use_container_width=True):
                        st.session_state['modo_analise'] = chave_modo
                        st.session_state['modo_confirmado'] = True
                        st.rerun()
            else:
                st.caption("⚠️ Aba não encontrada na planilha")

    st.stop()


# ==========================================
# DADOS CARREGADOS
# ==========================================
banco_completo = st.session_state.get('banco_de_dados_completo', {})
rankings = st.session_state.get('rankings', {})

# Mostra erros de cálculo por posição (se houver)
erros_calculo = st.session_state.get('erros_calculo', {})

# ==========================================
# HELPER: monta df_filtrado para uma posição
# ==========================================
def montar_df(posicao):
    if posicao not in rankings or posicao not in banco_completo:
        return None, None

    # Abas Overall têm sua própria lógica de montagem (sem Moneyball)
    if posicao in POSICOES_OVERALL:
        return montar_df_overall(posicao)

    try:
        df_resultado = rankings[posicao].copy()
        df_da_posicao = banco_completo[posicao].copy()

        colunas_candidatas = COLUNAS_POR_POSICAO.get(posicao, ['Jogador', 'Equipe', 'Idade', 'Nota média'])
        colunas_existentes = [c for c in colunas_candidatas if c in df_da_posicao.columns]

        if not colunas_existentes:
            return None, df_da_posicao

        df_res = df_da_posicao[colunas_existentes].copy().reset_index(drop=True)
        df_notas = df_resultado[["Jogador", "Nota_Moneyball"]].reset_index(drop=True)
        df_res = df_res.merge(df_notas, on="Jogador", how="inner")
        df_res = df_res.sort_values(by="Nota_Moneyball", ascending=False).reset_index(drop=True)
        df_filtrado = df_res.copy()

        # Filtros de disponibilidade
        if ocultar_nao_a_venda or ocultar_valor_desconhecido:
            val_col_filtro = next((c for c in ['Valor estimado', 'Valor Estimado', 'Valor']
                                   if c in df_da_posicao.columns), None)
            if val_col_filtro:
                lookup_valor = (
                    df_da_posicao[['Jogador', val_col_filtro]]
                    .drop_duplicates(subset='Jogador', keep='first')
                    .set_index('Jogador')[val_col_filtro]
                )
                val_str = df_filtrado['Jogador'].map(lookup_valor).astype(str).str.strip().str.lower()
                if ocultar_nao_a_venda:
                    mask = val_str.isin(['não está à venda', 'nao esta a venda', 'not for sale',
                                         'n/d', 'indisponível', '-', 'nan', ''])
                    df_filtrado = df_filtrado[~mask]
                if ocultar_valor_desconhecido:
                    mask = val_str.isin(['desconhecido', 'unknown', 'n/a', 'nan', '', '-'])
                    df_filtrado = df_filtrado[~mask]
                df_filtrado = df_filtrado.reset_index(drop=True)

        return df_filtrado, df_da_posicao
    except Exception:
        return None, banco_completo.get(posicao)


def montar_df_overall(posicao):
    """
    Monta df_filtrado para abas de Rating Overall (Time Estatísticas, Overall Análise).
    Não aplica filtros de valor/venda (essas abas não têm essas colunas).
    """
    try:
        df_resultado = rankings[posicao].copy()  # [Jogador, Equipe, Rating_Overall]
        df_da_posicao = banco_completo[posicao].copy()

        # Remove linhas auxiliares (ex: "Análise da Equipe") usando a mesma regra do main.py
        if 'Posição' in df_da_posicao.columns:
            df_da_posicao_jog = df_da_posicao[df_da_posicao['Posição'].apply(lambda x: isinstance(x, str))].copy()
        else:
            df_da_posicao_jog = df_da_posicao.dropna(subset=['Jogador']).copy()

        # Todas as colunas numéricas relevantes (exclui colunas de identificação)
        colunas_id = set(COLUNAS_IDENTIFICACAO_OVERALL.get(posicao, ['Jogador']))
        idx_nota = df_da_posicao_jog.columns.get_loc('Nota média') if 'Nota média' in df_da_posicao_jog.columns else len(df_da_posicao_jog.columns) - 1
        colunas_metricas = [c for c in df_da_posicao_jog.columns[:idx_nota+1] if c not in colunas_id]

        colunas_existentes = ['Jogador'] + [c for c in colunas_metricas if c in df_da_posicao_jog.columns]
        if 'Equipe' in df_da_posicao_jog.columns and 'Equipe' not in colunas_existentes:
            colunas_existentes.insert(1, 'Equipe')

        df_res = df_da_posicao_jog[colunas_existentes].copy().reset_index(drop=True)
        df_rating = df_resultado[["Jogador", "Rating_Overall"]].reset_index(drop=True)
        df_res = df_res.merge(df_rating, on="Jogador", how="inner")
        df_res = df_res.sort_values(by="Rating_Overall", ascending=False).reset_index(drop=True)

        return df_res, df_da_posicao
    except Exception:
        return None, banco_completo.get(posicao)

# ==========================================
# HELPER: renderiza seção de uma posição
# ==========================================
def render_secao(posicao, df_filtrado, df_da_posicao, secao):
    # Mostra erro de cálculo se houver
    if posicao in erros_calculo:
        st.error(f"⚠️ Erro ao calcular {posicao}: {erros_calculo[posicao]}")
        if "Ignorar" in erros_calculo[posicao] or "critérios" in erros_calculo[posicao].lower():
            st.info("💡 Use 🔄 Recomeçar na sidebar para reconfigurar os critérios e recalcular.")
        return

    if df_filtrado is None or df_filtrado.empty:
        st.warning(f"Nenhum jogador encontrado para {posicao} com os filtros aplicados.")
        return

    if 'Jogador' not in df_filtrado.columns:
        st.error(f"Estrutura de dados inválida para {posicao}.")
        return

    # Abas de Rating Overall têm renderização própria
    if posicao in POSICOES_OVERALL:
        render_secao_overall(posicao, df_filtrado, df_da_posicao, secao)
        return

    alvo = df_filtrado.iloc[0]
    colunas_numericas = df_filtrado.select_dtypes(include=['float64', 'int64']).columns.tolist()
    if not colunas_numericas:
        st.warning(f"Nenhuma coluna numérica encontrada para {posicao}.")
        return

    # ------------------------------------------
    if secao == "dashboard":
        st.subheader("🥇 Principal alvo")
        with st.container(horizontal=True):
            st.metric("Melhor contratação", alvo['Jogador'],
                      delta=f"Nota: {alvo['Nota_Moneyball']:.1f}/100", border=True)
            val_col = next((c for c in ['Valor estimado', 'Valor Estimado', 'Valor']
                            if c in alvo.index), None)
            if val_col:
                val = alvo[val_col]
                if isinstance(val, (int, float)) and not math.isnan(val):
                    st.metric("Valor estimado", f"€ {val/1_000_000:.1f}M", border=True)
            st.metric("Idade", f"{int(alvo['Idade'])} anos", border=True)
            sal_col = 'Salário' if 'Salário' in alvo.index else None
            if sal_col:
                sal = alvo[sal_col]
                if isinstance(sal, (int, float)) and not math.isnan(sal):
                    st.metric("Salário", f"€ {sal/1_000:.0f}k/mês", border=True)

        st.space("medium")
        st.subheader("🏆 Top 10 recomendados")
        col_lista, col_dist = st.columns([1, 2], gap="medium")

        with col_lista:
            with st.container(border=True, height=400):
                for i, row in enumerate(df_filtrado.head(10).itertuples(), 1):
                    medalha = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}º")
                    cols_row = st.columns([1, 3, 2])
                    cols_row[0].markdown(medalha)
                    cols_row[1].markdown(f"**{row.Jogador}**")
                    cols_row[2].caption(f"{row.Nota_Moneyball:.1f} pts")

        with col_dist:
            with st.container(border=True, height=400):
                atrib_grafico = st.selectbox(
                    "Dado a exibir:",
                    colunas_numericas,
                    index=colunas_numericas.index("Nota_Moneyball") if "Nota_Moneyball" in colunas_numericas else 0,
                    key=f"dash_atrib_{posicao}"
                )
                chart_dist = alt.Chart(df_filtrado.head(10)).mark_bar(
                    color='#22C55E', cornerRadiusEnd=3
                ).encode(
                    x=alt.X(f'{atrib_grafico}:Q', title=atrib_grafico),
                    y=alt.Y('Jogador:N', sort='-x', title=''),
                    tooltip=['Jogador', 'Equipe',
                             alt.Tooltip(f'{atrib_grafico}:Q', title=atrib_grafico, format='.2f')]
                ).properties(height=310)
                st.altair_chart(chart_dist)

        st.space("medium")
        st.subheader("📊 Nota Moneyball vs Nota média FM")
        with st.container(border=True):
            if 'Nota média' in df_filtrado.columns:
                scatter = alt.Chart(df_filtrado.head(10)).mark_circle(size=90, opacity=0.8).encode(
                    x=alt.X('Nota_Moneyball:Q', title='Nota Moneyball', scale=alt.Scale(zero=False)),
                    y=alt.Y('Nota média:Q', title='Nota média FM', scale=alt.Scale(zero=False)),
                    color=alt.Color('Nota_Moneyball:Q', scale=alt.Scale(scheme='greens'), legend=None),
                    tooltip=['Jogador', 'Equipe',
                             alt.Tooltip('Nota_Moneyball:Q', title='Nota Moneyball', format='.1f'),
                             alt.Tooltip('Nota média:Q', title='Nota média FM', format='.1f')]
                ).properties(height=340)
                labels = scatter.mark_text(dy=-10, fontSize=11).encode(text='Jogador:N')
                st.altair_chart(scatter + labels)
            else:
                st.caption("Coluna 'Nota média' não encontrada para esta posição.")

        # Margem de erro do cálculo — discreta, no rodapé do dashboard
        _mk = f"margem_ahp_{posicao}"
        if _mk not in st.session_state:
            try:
                st.session_state[_mk] = main.estimar_margem_ahp(
                    df_da_posicao, posicao, st.session_state['niveis_usuario'].get(posicao))
            except Exception:
                st.session_state[_mk] = None
        margem_info = st.session_state[_mk]

        if margem_info is not None and len(margem_info.get('margem', [])):
            st.space("small")
            with st.expander(f"🎯 Margem de erro do cálculo · ± {margem_info['margem_media']:.1f} pts"):
                m_lookup = {j: (no, lo, hi, mg) for j, no, lo, hi, mg in zip(
                    margem_info['jogadores'], margem_info['nota'], margem_info['lo'],
                    margem_info['hi'], margem_info['margem'])}
                st.caption("A nota depende dos pesos dados aos critérios. Como esses pesos são um "
                           "julgamento, testamos centenas de variações plausíveis e medimos o quanto "
                           "a nota oscila. Quanto menor a margem, mais firme é a nota.")
                cons_txt = "coerentes ✅" if margem_info['consistente'] else "atenção ⚠️"
                st.caption(f"Margem média da posição: **± {margem_info['margem_media']:.1f} pts** · "
                           f"pesos {cons_txt} (CR {margem_info['cr']:.2f}).")
                alvo_m = m_lookup.get(alvo['Jogador'])
                if alvo_m:
                    empatados = [j for j, (no, lo, hi, mg) in m_lookup.items()
                                 if j != alvo['Jogador'] and hi >= alvo_m[1]]
                    st.caption(f"Líder **{alvo['Jogador']}**: {alvo_m[0]:.1f} ± {alvo_m[3]:.1f} pts.")
                    if empatados:
                        st.caption(f"⚠️ {len(empatados)} jogador(es) dentro da margem do líder — "
                                   f"a vantagem não é definitiva.")
                    else:
                        st.caption("✅ O líder se mantém à frente mesmo considerando a margem.")



    # ------------------------------------------
    elif secao == "comparativo":
        jogadores_disponiveis = df_filtrado['Jogador'].tolist()
        col_ctrl, col_charts = st.columns([1, 2], gap="medium")

        with col_ctrl:
            with st.container(border=True):
                st.markdown("**Selecione jogadores**")
                selecionados = st.multiselect(
                    "Até 5 jogadores:",
                    options=jogadores_disponiveis,
                    default=jogadores_disponiveis[:3],
                    max_selections=5,
                    placeholder="Digite o nome do jogador...",
                    key=f"comp_sel_{posicao}"
                )
                atributo_barra = st.selectbox(
                    "Atributo para comparar:",
                    colunas_numericas,
                    index=colunas_numericas.index('Nota_Moneyball') if 'Nota_Moneyball' in colunas_numericas else 0,
                    key=f"atrib_barra_{posicao}"
                )
                atributo_x = st.selectbox(
                    "Scatter — Eixo X:",
                    colunas_numericas,
                    index=colunas_numericas.index('Nota_Moneyball') if 'Nota_Moneyball' in colunas_numericas else 0,
                    key=f"eixo_x_{posicao}"
                )
                atributo_y = st.selectbox(
                    "Scatter — Eixo Y:",
                    colunas_numericas,
                    index=min(1, len(colunas_numericas) - 1),
                    key=f"eixo_y_{posicao}"
                )

        with col_charts:
            if selecionados:
                df_comp = df_filtrado[df_filtrado['Jogador'].isin(selecionados)].copy()
                df_comp_sorted = df_comp.sort_values(by=atributo_barra, ascending=False).reset_index(drop=True)
                val_max = df_comp_sorted[atributo_barra].max()
                val_min = df_comp_sorted[atributo_barra].min()
                with st.container(border=True):
                    st.markdown(f"**🏆 Ranking: {atributo_barra}**")
                    for i, row in df_comp_sorted.iterrows():
                        pos = i + 1
                        medalha = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}º")
                        val = row[atributo_barra]
                        pct = ((val - val_min) / (val_max - val_min) * 100) if val_max != val_min else 100
                        val_fmt = f"{val:.2f}" if isinstance(val, float) else str(int(val))
                        r_cols = st.columns([1, 4, 2, 3])
                        r_cols[0].markdown(medalha)
                        r_cols[1].markdown(f"**{row['Jogador']}**")
                        r_cols[2].caption(val_fmt)
                        r_cols[3].progress(int(pct))

                st.space("small")
                with st.container(border=True):
                    st.markdown(f"**{atributo_x} vs {atributo_y}**")
                    scatter_comp = alt.Chart(df_comp).mark_circle(size=150).encode(
                        x=alt.X(f'{atributo_x}:Q', scale=alt.Scale(zero=False)),
                        y=alt.Y(f'{atributo_y}:Q', scale=alt.Scale(zero=False)),
                        color=alt.Color('Jogador:N', legend=alt.Legend(title='Jogador')),
                        tooltip=['Jogador', 'Equipe',
                                 alt.Tooltip(f'{atributo_x}:Q', format='.2f'),
                                 alt.Tooltip(f'{atributo_y}:Q', format='.2f')]
                    ).properties(height=220)
                    labels = scatter_comp.mark_text(dy=-12, fontSize=11).encode(text='Jogador:N')
                    st.altair_chart(scatter_comp + labels)

        if selecionados:
            st.space("medium")
            st.subheader("📋 Tabela comparativa")
            df_tabela = df_filtrado[df_filtrado['Jogador'].isin(selecionados)].copy()
            col_config_comp = {
                'Nota_Moneyball': st.column_config.ProgressColumn(
                    'Nota Moneyball', min_value=0, max_value=100, format='%.1f'),
            }
            if 'Nota média' in df_tabela.columns:
                col_config_comp['Nota média'] = st.column_config.ProgressColumn(
                    'Nota média FM', min_value=0, max_value=20, format='%.1f')
            st.dataframe(df_tabela, column_config=col_config_comp, hide_index=True)

    # ------------------------------------------
    elif secao == "scout":
        st.subheader("🤖 Opinião do Olheiro Chefe")
        st.caption("Análise gerada por inteligência artificial com base nos dados Moneyball.")

        chave_ia = f'relatorio_ia_{posicao}'
        CHAVE_API = st.secrets["CHAVE_API_GEMINI"]
        genai.configure(api_key=CHAVE_API)
        modelo_ia = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

        if chave_ia not in st.session_state:
            if st.button(":material/play_arrow: Gerar relatório do olheiro", type="primary",
                         key=f"btn_ia_{posicao}"):
                with st.spinner("O Olheiro IA está analisando e redigindo o relatório..."):
                    dados_top = df_filtrado.head(10).to_dict('records')
                    prompt = f"""
                    Você é o Olheiro Chefe de um time de futebol que usa a filosofia Moneyball.
                    Aqui estão os melhores candidatos para a posição {posicao}:
                    {dados_top}

                    Escreva um texto direto e profissional para o treinador.
                    Recomende a contratação de 3 jogadores justificando o custo-benefício e analisando os dados
                    em relação aos outros candidatos. Ignore a data de contrato.
                    Observe que m é mil e M é milhão. 200m € é igual a 200 mil de euros por exemplo.
                    Compare a quantidade de partidas — poucos jogos tornam dados menos confiáveis.
                    Faça uma análise breve de cada um e depois uma conclusão final recomendando o melhor alvo.

                    Assine o final como Olheiro IA.
                    """
                    try:
                        resposta = modelo_ia.generate_content(prompt)
                        st.session_state[chave_ia] = resposta.text
                        if hist.supabase_disponivel():
                            try:
                                hist.salvar_email_olheiro(
                                    _usuario_id, posicao,
                                    st.session_state.get('modo_analise', 'posicoes'),
                                    '', resposta.text
                                )
                            except Exception:
                                pass
                        st.rerun()
                    except Exception:
                        st.session_state[chave_ia] = "⚠️ Limite de velocidade do Google atingido. Aguarde 1 minuto e tente novamente."
                        st.rerun()
        else:
            with st.container(border=True):
                st.write(st.session_state[chave_ia])
            if st.button(":material/refresh: Gerar novo relatório", key=f"btn_ia_refresh_{posicao}"):
                del st.session_state[chave_ia]
                st.rerun()

    # ------------------------------------------
    elif secao == "ficha":
        todos_jogadores = df_filtrado['Jogador'].tolist()
        lider = df_filtrado.iloc[0]

        jogador_sel = st.selectbox(
            "Busque o jogador pelo nome:",
            options=todos_jogadores,
            key=f"ficha_sel_{posicao}",
            placeholder="Digite o nome do jogador..."
        )

        jogador = df_filtrado[df_filtrado['Jogador'] == jogador_sel].iloc[0]
        eh_lider = (jogador_sel == lider['Jogador'])
        rank_pos = todos_jogadores.index(jogador_sel) + 1
        cols_metricas = [c for c in colunas_numericas if c not in COLUNAS_INFO]

        linha_bruta = df_da_posicao[df_da_posicao['Jogador'] == jogador_sel]
        val_col = next((c for c in ['Valor estimado', 'Valor Estimado', 'Valor']
                        if c in df_da_posicao.columns), None)
        sal_col = 'Salário' if 'Salário' in df_da_posicao.columns else None
        nota_jog = jogador['Nota_Moneyball']
        nota_lider = lider['Nota_Moneyball']
        delta_nota = nota_jog - nota_lider if not eh_lider else None
        nota_pct = int(nota_jog)

        # Monta strings de valor e salário
        val_str_fmt = "—"
        if val_col and not linha_bruta.empty:
            v = linha_bruta.iloc[0][val_col]
            try:
                v_num = float(str(v).replace("€","").replace("M","e6").replace("m","e3").replace(",",".").replace(" ",""))
                val_str_fmt = f"€ {v_num/1_000_000:.1f}M"
            except Exception:
                val_str_fmt = str(v)

        sal_str_fmt = "—"
        if sal_col and not linha_bruta.empty:
            s = linha_bruta.iloc[0][sal_col]
            try:
                s_num = float(str(s).replace("€","").replace("m","e3").replace(",",".").replace(" ","").replace("/sem","").replace("p/s",""))
                sal_str_fmt = f"€ {s_num/1_000:.0f}k/sem"
            except Exception:
                sal_str_fmt = str(s)

        # Stat gerais da planilha bruta
        linha_estat = df_da_posicao[df_da_posicao['Jogador'] == jogador_sel]
        colunas_abs = [c for c in COLUNAS_ABSOLUTAS_CANDIDATAS if c in df_da_posicao.columns]
        stats_gerais = {}
        if not linha_estat.empty:
            for c in colunas_abs:
                v = linha_estat.iloc[0][c]
                stats_gerais[c] = "—" if pd.isna(v) else str(v) if not isinstance(v, float) else f"{v:.1f}"

        # CSS da ficha
        rank_badge = {1:"🥇",2:"🥈",3:"🥉"}.get(rank_pos, f"#{rank_pos}")
        delta_color_css = "#22C55E" if (delta_nota is None or delta_nota >= 0) else "#EF4444"
        delta_txt = "Melhor do ranking" if eh_lider else f"{delta_nota:+.1f} vs 1º"

        st.markdown(f"""
        <style>
        .ficha-card {{
            background: #080E0A;
            border: 1px solid #1E3A24;
            border-radius: 16px;
            padding: 24px 28px;
            margin-bottom: 16px;
        }}
        .ficha-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 20px;
        }}
        .ficha-nome {{
            font-size: 1.6rem;
            font-weight: 800;
            color: #E8F5E9;
            line-height: 1.1;
            margin-bottom: 4px;
        }}
        .ficha-equipe {{
            font-size: 0.85rem;
            color: #6B7280;
        }}
        .ficha-nota-circle {{
            min-width: 96px;
            height: 88px;
            border-radius: 50%;
            background: conic-gradient(#22C55E {nota_pct}%, #1E3A24 0%);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        .ficha-nota-inner {{
            width: 68px;
            height: 68px;
            border-radius: 50%;
            background: #080E0A;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .ficha-nota-num {{
            font-size: 1.2rem;
            font-weight: 800;
            color: #22C55E;
            line-height: 1;
        }}
        .ficha-nota-label {{
            font-size: 0.55rem;
            color: #6B7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .ficha-pills {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }}
        .ficha-pill {{
            background: #111A14;
            border: 1px solid #1E3A24;
            border-radius: 8px;
            padding: 6px 12px;
            display: flex;
            flex-direction: column;
            min-width: 90px;
        }}
        .ficha-pill-label {{
            font-size: 0.65rem;
            color: #6B7280;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            margin-bottom: 2px;
        }}
        .ficha-pill-value {{
            font-size: 0.92rem;
            font-weight: 700;
            color: #E8F5E9;
        }}
        .ficha-pill-delta {{
            font-size: 0.68rem;
            font-weight: 600;
            color: {delta_color_css};
        }}
        .ficha-section-title {{
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #22C55E;
            margin: 18px 0 10px 0;
            padding-bottom: 4px;
            border-bottom: 1px solid #1E3A24;
        }}
        .ficha-metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 8px;
        }}
        .ficha-metric-item {{
            background: #111A14;
            border: 1px solid #1E3A24;
            border-radius: 10px;
            padding: 10px 12px;
        }}
        .ficha-metric-name {{
            font-size: 0.68rem;
            color: #6B7280;
            margin-bottom: 4px;
            line-height: 1.3;
        }}
        .ficha-metric-val {{
            font-size: 1rem;
            font-weight: 700;
            color: #E8F5E9;
        }}
        .ficha-metric-ref {{
            font-size: 0.65rem;
            margin-top: 2px;
        }}
        </style>

        <div class="ficha-card">
          <div class="ficha-header">
            <div>
              <div class="ficha-nome">{jogador['Jogador']}</div>
              <div class="ficha-equipe">{jogador.get('Equipe','—')} · {rank_badge} {rank_pos}º de {len(todos_jogadores)}</div>
              <div class="ficha-pills">
                <div class="ficha-pill">
                  <span class="ficha-pill-label">Idade</span>
                  <span class="ficha-pill-value">{int(jogador['Idade'])} anos</span>
                </div>
                <div class="ficha-pill">
                  <span class="ficha-pill-label">Valor</span>
                  <span class="ficha-pill-value">{val_str_fmt}</span>
                </div>
                <div class="ficha-pill">
                  <span class="ficha-pill-label">Salário</span>
                  <span class="ficha-pill-value">{sal_str_fmt}</span>
                </div>
                {"".join(f'<div class="ficha-pill"><span class="ficha-pill-label">{k}</span><span class="ficha-pill-value">{v}</span></div>' for k,v in stats_gerais.items())}
              </div>
            </div>
            <div class="ficha-nota-circle">
              <div class="ficha-nota-inner">
                <span class="ficha-nota-num">{nota_jog:.0f}</span>
                <span class="ficha-nota-label">/ 100</span>
              </div>
            </div>
          </div>
          <div style="font-size:0.75rem; color:{delta_color_css}; margin-top:10px;">{delta_txt}</div>
        </div>
        """, unsafe_allow_html=True)

        # Métricas vs líder em grid
        st.markdown('<div class="ficha-section-title">Métricas vs melhor do ranking</div>', unsafe_allow_html=True)

        items_html = ""
        for metrica in cols_metricas:
            try:
                val_jog_m = jogador[metrica]
                val_ref_m = lider[metrica]
                if pd.isna(val_jog_m) or pd.isna(val_ref_m):
                    val_display = "—"
                    ref_html = ""
                else:
                    val_display = f"{val_jog_m:.2f}" if isinstance(val_jog_m, float) else str(int(val_jog_m))
                    if not eh_lider:
                        diff = val_jog_m - val_ref_m
                        is_better = (diff < 0) if metrica in CUSTO else (diff > 0)
                        diff_color = "#22C55E" if is_better else ("#EF4444" if diff != 0 else "#6B7280")
                        ref_val = f"{val_ref_m:.2f}" if isinstance(val_ref_m, float) else str(int(val_ref_m))
                        ref_html = f'<div class="ficha-metric-ref" style="color:{diff_color}">{"+" if diff>0 else ""}{diff:.2f} vs {lider["Jogador"][:10]}</div>'
                    else:
                        ref_html = '<div class="ficha-metric-ref" style="color:#22C55E">🥇 Referência</div>'
            except Exception:
                val_display = "—"
                ref_html = ""

            items_html += f"""
            <div class="ficha-metric-item">
              <div class="ficha-metric-name">{metrica}</div>
              <div class="ficha-metric-val">{val_display}</div>
              {ref_html}
            </div>"""

        st.markdown(f'<div class="ficha-metric-grid">{items_html}</div>', unsafe_allow_html=True)

# ==========================================
# HELPER: renderiza seção para abas de Rating Overall
# (Time Estatísticas, Overall Análise — sem lógica Moneyball)
# ==========================================
def render_secao_overall(posicao, df_filtrado, df_da_posicao, secao):
    alvo = df_filtrado.iloc[0]
    colunas_numericas = df_filtrado.select_dtypes(include=['float64', 'int64']).columns.tolist()
    if not colunas_numericas:
        st.warning(f"Nenhuma coluna numérica encontrada para {posicao}.")
        return

    COLUNAS_INFO_OVERALL = {'Jogador', 'Equipe'}
    cols_metricas = [c for c in colunas_numericas if c not in COLUNAS_INFO_OVERALL]

    # ------------------------------------------
    if secao == "dashboard":
        st.subheader("🥇 Melhor Rating Overall")
        with st.container(horizontal=True):
            st.metric("Jogador", alvo['Jogador'],
                      delta=f"Rating: {alvo['Rating_Overall']:.1f}/100", border=True)
            if 'Equipe' in alvo.index:
                st.metric("Equipe", str(alvo['Equipe']), border=True)
            st.metric("Jogadores avaliados", len(df_filtrado), border=True)

        st.space("medium")
        st.subheader("🏆 Top 10 — Rating Overall")
        col_lista, col_dist = st.columns([1, 2], gap="medium")

        with col_lista:
            with st.container(border=True, height=400):
                for i, row in enumerate(df_filtrado.head(10).itertuples(), 1):
                    medalha = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}º")
                    cols_row = st.columns([1, 3, 2])
                    cols_row[0].markdown(medalha)
                    cols_row[1].markdown(f"**{row.Jogador}**")
                    cols_row[2].caption(f"{row.Rating_Overall:.1f} pts")

        with col_dist:
            with st.container(border=True, height=400):
                atrib_grafico = st.selectbox(
                    "Dado a exibir:",
                    colunas_numericas,
                    index=colunas_numericas.index("Rating_Overall") if "Rating_Overall" in colunas_numericas else 0,
                    key=f"dash_atrib_{posicao}"
                )
                tooltip_cols = ['Jogador']
                if 'Equipe' in df_filtrado.columns:
                    tooltip_cols.append('Equipe')
                tooltip_cols.append(alt.Tooltip(f'{atrib_grafico}:Q', title=atrib_grafico, format='.2f'))
                chart_dist = alt.Chart(df_filtrado.head(10)).mark_bar(
                    color='#22C55E', cornerRadiusEnd=3
                ).encode(
                    x=alt.X(f'{atrib_grafico}:Q', title=atrib_grafico),
                    y=alt.Y('Jogador:N', sort='-x', title=''),
                    tooltip=tooltip_cols
                ).properties(height=310)
                st.altair_chart(chart_dist)

        st.space("medium")
        st.subheader("📊 Rating Overall vs Nota média FM")
        with st.container(border=True):
            if 'Nota média' in df_filtrado.columns:
                tooltip_cols = ['Jogador']
                if 'Equipe' in df_filtrado.columns:
                    tooltip_cols.append('Equipe')
                tooltip_cols += [
                    alt.Tooltip('Rating_Overall:Q', title='Rating Overall', format='.1f'),
                    alt.Tooltip('Nota média:Q', title='Nota média FM', format='.1f')
                ]
                scatter = alt.Chart(df_filtrado.head(10)).mark_circle(size=90, opacity=0.8).encode(
                    x=alt.X('Rating_Overall:Q', title='Rating Overall', scale=alt.Scale(zero=False)),
                    y=alt.Y('Nota média:Q', title='Nota média FM', scale=alt.Scale(zero=False)),
                    color=alt.Color('Rating_Overall:Q', scale=alt.Scale(scheme='greens'), legend=None),
                    tooltip=tooltip_cols
                ).properties(height=340)
                labels = scatter.mark_text(dy=-10, fontSize=11).encode(text='Jogador:N')
                st.altair_chart(scatter + labels)
            else:
                st.caption("Coluna 'Nota média' não encontrada para esta aba.")

    # ------------------------------------------
    elif secao == "comparativo":
        jogadores_disponiveis = df_filtrado['Jogador'].tolist()
        col_ctrl, col_charts = st.columns([1, 2], gap="medium")

        with col_ctrl:
            with st.container(border=True):
                st.markdown("**Selecione jogadores**")
                selecionados = st.multiselect(
                    "Até 5 jogadores:",
                    options=jogadores_disponiveis,
                    default=jogadores_disponiveis[:3],
                    max_selections=5,
                    placeholder="Digite o nome do jogador...",
                    key=f"comp_sel_{posicao}"
                )
                atributo_barra = st.selectbox(
                    "Atributo para comparar:",
                    colunas_numericas,
                    index=colunas_numericas.index('Rating_Overall') if 'Rating_Overall' in colunas_numericas else 0,
                    key=f"atrib_barra_{posicao}"
                )
                atributo_x = st.selectbox(
                    "Scatter — Eixo X:",
                    colunas_numericas,
                    index=colunas_numericas.index('Rating_Overall') if 'Rating_Overall' in colunas_numericas else 0,
                    key=f"eixo_x_{posicao}"
                )
                atributo_y = st.selectbox(
                    "Scatter — Eixo Y:",
                    colunas_numericas,
                    index=min(1, len(colunas_numericas) - 1),
                    key=f"eixo_y_{posicao}"
                )

        with col_charts:
            if selecionados:
                df_comp = df_filtrado[df_filtrado['Jogador'].isin(selecionados)].copy()
                df_comp_sorted = df_comp.sort_values(by=atributo_barra, ascending=False).reset_index(drop=True)
                val_max = df_comp_sorted[atributo_barra].max()
                val_min = df_comp_sorted[atributo_barra].min()
                with st.container(border=True):
                    st.markdown(f"**🏆 Ranking: {atributo_barra}**")
                    for i, row in df_comp_sorted.iterrows():
                        pos = i + 1
                        medalha = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}º")
                        val = row[atributo_barra]
                        pct = ((val - val_min) / (val_max - val_min) * 100) if val_max != val_min else 100
                        val_fmt = f"{val:.2f}" if isinstance(val, float) else str(int(val))
                        r_cols = st.columns([1, 4, 2, 3])
                        r_cols[0].markdown(medalha)
                        r_cols[1].markdown(f"**{row['Jogador']}**")
                        r_cols[2].caption(val_fmt)
                        r_cols[3].progress(int(pct))

                st.space("small")
                with st.container(border=True):
                    st.markdown(f"**{atributo_x} vs {atributo_y}**")
                    tooltip_cols = ['Jogador']
                    if 'Equipe' in df_comp.columns:
                        tooltip_cols.append('Equipe')
                    tooltip_cols += [
                        alt.Tooltip(f'{atributo_x}:Q', format='.2f'),
                        alt.Tooltip(f'{atributo_y}:Q', format='.2f')
                    ]
                    scatter_comp = alt.Chart(df_comp).mark_circle(size=150).encode(
                        x=alt.X(f'{atributo_x}:Q', scale=alt.Scale(zero=False)),
                        y=alt.Y(f'{atributo_y}:Q', scale=alt.Scale(zero=False)),
                        color=alt.Color('Jogador:N', legend=alt.Legend(title='Jogador')),
                        tooltip=tooltip_cols
                    ).properties(height=220)
                    labels = scatter_comp.mark_text(dy=-12, fontSize=11).encode(text='Jogador:N')
                    st.altair_chart(scatter_comp + labels)

        if selecionados:
            st.space("medium")
            st.subheader("📋 Tabela comparativa")
            df_tabela = df_filtrado[df_filtrado['Jogador'].isin(selecionados)].copy()
            col_config_comp = {
                'Rating_Overall': st.column_config.ProgressColumn(
                    'Rating Overall', min_value=0, max_value=100, format='%.1f'),
            }
            if 'Nota média' in df_tabela.columns:
                col_config_comp['Nota média'] = st.column_config.ProgressColumn(
                    'Nota média FM', min_value=0, max_value=20, format='%.1f')
            st.dataframe(df_tabela, column_config=col_config_comp, hide_index=True)

    # ------------------------------------------
    elif secao == "scout":
        st.subheader("🤖 Opinião do Olheiro Chefe")
        st.caption("Análise gerada por inteligência artificial com base no Rating Overall.")

        chave_ia = f'relatorio_ia_{posicao}'
        CHAVE_API = st.secrets["CHAVE_API_GEMINI"]
        genai.configure(api_key=CHAVE_API)
        modelo_ia = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

        if chave_ia not in st.session_state:
            if st.button(":material/play_arrow: Gerar relatório do olheiro", type="primary",
                         key=f"btn_ia_{posicao}"):
                with st.spinner("O Olheiro IA está analisando e redigindo o relatório..."):
                    dados_top = df_filtrado.head(10).to_dict('records')
                    prompt = f"""
                    Você é um analista de desempenho de futebol.
                    Aqui está o Rating Overall (0-100) calculado via AHP com base em estatísticas
                    de desempenho dos jogadores da aba "{posicao}":
                    {dados_top}

                    Escreva uma análise direta e profissional destacando os 3 jogadores com melhor
                    Rating Overall, explicando quais estatísticas mais contribuíram para o desempenho
                    de cada um. Não fale sobre valor de mercado, salário ou contrato — foque apenas
                    em desempenho em campo.

                    Assine o final como Olheiro IA.
                    """
                    try:
                        resposta = modelo_ia.generate_content(prompt)
                        st.session_state[chave_ia] = resposta.text
                        if hist.supabase_disponivel():
                            try:
                                hist.salvar_email_olheiro(
                                    _usuario_id, posicao, 'overall',
                                    '', resposta.text
                                )
                            except Exception:
                                pass
                        st.rerun()
                    except Exception:
                        st.session_state[chave_ia] = "⚠️ Limite de velocidade do Google atingido. Aguarde 1 minuto e tente novamente."
                        st.rerun()
        else:
            with st.container(border=True):
                st.write(st.session_state[chave_ia])
            if st.button(":material/refresh: Gerar novo relatório", key=f"btn_ia_refresh_{posicao}"):
                del st.session_state[chave_ia]
                st.rerun()

    # ------------------------------------------
    elif secao == "ficha":
        todos_jogadores = df_filtrado['Jogador'].tolist()
        lider = df_filtrado.iloc[0]

        jogador_sel = st.selectbox(
            "Busque o jogador pelo nome:",
            options=todos_jogadores,
            key=f"ficha_sel_{posicao}",
            placeholder="Digite o nome do jogador..."
        )

        jogador = df_filtrado[df_filtrado['Jogador'] == jogador_sel].iloc[0]
        eh_lider = (jogador_sel == lider['Jogador'])
        rank_pos = todos_jogadores.index(jogador_sel) + 1

        rating_jog = jogador['Rating_Overall']
        rating_lider = lider['Rating_Overall']
        delta_rating = rating_jog - rating_lider if not eh_lider else None
        rating_pct = int(max(0, min(100, rating_jog)))

        rank_badge = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank_pos, f"#{rank_pos}")
        delta_color_css = "#22C55E" if (delta_rating is None or delta_rating >= 0) else "#EF4444"
        delta_txt = "Melhor do ranking" if eh_lider else f"{delta_rating:+.1f} vs 1º"

        st.markdown(f"""
        <style>
        .ov-card {{
            background: #080E0A;
            border: 1px solid #1E3A24;
            border-radius: 16px;
            padding: 24px 28px;
            margin-bottom: 16px;
        }}
        .ov-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 20px;
        }}
        .ov-nome {{
            font-size: 1.6rem;
            font-weight: 800;
            color: #E8F5E9;
            line-height: 1.1;
            margin-bottom: 4px;
        }}
        .ov-equipe {{
            font-size: 0.85rem;
            color: #6B7280;
        }}
        .ov-rating-circle {{
            min-width: 96px;
            height: 88px;
            border-radius: 50%;
            background: conic-gradient(#22C55E {rating_pct}%, #1E3A24 0%);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .ov-rating-inner {{
            width: 68px;
            height: 68px;
            border-radius: 50%;
            background: #080E0A;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .ov-rating-num {{
            font-size: 1.2rem;
            font-weight: 800;
            color: #22C55E;
            line-height: 1;
        }}
        .ov-rating-label {{
            font-size: 0.55rem;
            color: #6B7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .ov-section-title {{
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #22C55E;
            margin: 18px 0 10px 0;
            padding-bottom: 4px;
            border-bottom: 1px solid #1E3A24;
        }}
        .ov-metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 8px;
        }}
        .ov-metric-item {{
            background: #111A14;
            border: 1px solid #1E3A24;
            border-radius: 10px;
            padding: 10px 12px;
        }}
        .ov-metric-name {{
            font-size: 0.68rem;
            color: #6B7280;
            margin-bottom: 4px;
            line-height: 1.3;
        }}
        .ov-metric-val {{
            font-size: 1rem;
            font-weight: 700;
            color: #E8F5E9;
        }}
        .ov-metric-ref {{
            font-size: 0.65rem;
            margin-top: 2px;
        }}
        </style>

        <div class="ov-card">
          <div class="ov-header">
            <div>
              <div class="ov-nome">{jogador['Jogador']}</div>
              <div class="ov-equipe">{jogador.get('Equipe','—')} · {rank_badge} {rank_pos}º de {len(todos_jogadores)}</div>
            </div>
            <div class="ov-rating-circle">
              <div class="ov-rating-inner">
                <span class="ov-rating-num">{rating_jog:.0f}</span>
                <span class="ov-rating-label">/ 100</span>
              </div>
            </div>
          </div>
          <div style="font-size:0.75rem; color:{delta_color_css}; margin-top:10px;">{delta_txt}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ov-section-title">Métricas vs melhor do ranking</div>', unsafe_allow_html=True)

        items_html = ""
        for metrica in cols_metricas:
            try:
                val_jog_m = jogador[metrica]
                val_ref_m = lider[metrica]
                if pd.isna(val_jog_m) or pd.isna(val_ref_m):
                    val_display = "—"
                    ref_html = ""
                else:
                    val_display = f"{val_jog_m:.2f}" if isinstance(val_jog_m, float) else str(int(val_jog_m))
                    if not eh_lider:
                        diff = val_jog_m - val_ref_m
                        # Todas as métricas overall são de benefício: maior é melhor
                        is_better = diff > 0
                        diff_color = "#22C55E" if is_better else ("#EF4444" if diff != 0 else "#6B7280")
                        ref_html = f'<div class="ov-metric-ref" style="color:{diff_color}">{"+" if diff>0 else ""}{diff:.2f} vs {lider["Jogador"][:10]}</div>'
                    else:
                        ref_html = '<div class="ov-metric-ref" style="color:#22C55E">🥇 Referência</div>'
            except Exception:
                val_display = "—"
                ref_html = ""

            items_html += f"""
            <div class="ov-metric-item">
              <div class="ov-metric-name">{metrica}</div>
              <div class="ov-metric-val">{val_display}</div>
              {ref_html}
            </div>"""

        st.markdown(f'<div class="ov-metric-grid">{items_html}</div>', unsafe_allow_html=True)


# ==========================================
# HELPER: renderiza seção para a aba de Time
# (Dashboard agregado + Olheiro do Time — sem ranking individual)
# ==========================================
def render_secao_time(posicao, secao):
    df_bruto = banco_completo.get(posicao)
    if df_bruto is None or df_bruto.empty:
        st.warning(f"Aba '{posicao}' não encontrada ou vazia na planilha.")
        return

    # Extrai estatísticas agregadas da equipe (seção "Análise da Equipe")
    stats_time = extrair_estatisticas_time(df_bruto)

    # Extrai os 11 titulares (linhas com Posição válida)
    if 'Posição' in df_bruto.columns:
        df_titulares = df_bruto[df_bruto['Posição'].apply(lambda x: isinstance(x, str))].copy()
    else:
        df_titulares = df_bruto.dropna(subset=['Jogador']).copy()

    cols_titulares = [c for c in ['Jogador', 'Posição', 'Nota média', 'Gols', 'Assistências'] if c in df_titulares.columns]

    if not stats_time and df_titulares.empty:
        st.warning(f"Não foi possível extrair dados da aba '{posicao}'.")
        return

    # ------------------------------------------
    if secao == "dashboard_time":
        st.subheader("📊 Dashboard do Time")
        st.caption("Estatísticas agregadas da equipe (médias por 90 minutos e totais).")

        if not stats_time:
            st.info("Seção 'Análise da Equipe' não encontrada nesta planilha.")
        else:
            # Separa métricas /90 (rate) das demais (totais/médias gerais)
            metricas_90 = {k: v for k, v in stats_time.items() if '/90' in k or '/ 90' in k or '90 min' in k.lower()}
            metricas_outras = {k: v for k, v in stats_time.items() if k not in metricas_90}

            st.markdown("**Por 90 minutos**")
            cols_90 = st.columns(4)
            for i, (k, v) in enumerate(metricas_90.items()):
                val_fmt = f"{v:.2f}" if isinstance(v, float) else str(v)
                cols_90[i % 4].metric(k, val_fmt, border=True)

            st.space("small")
            st.markdown("**Outras estatísticas**")
            cols_outras = st.columns(4)
            for i, (k, v) in enumerate(metricas_outras.items()):
                if isinstance(v, float):
                    val_fmt = f"{v*100:.1f}%" if 0 <= v <= 1 and ('%' in k) else f"{v:.2f}"
                else:
                    val_fmt = str(v)
                cols_outras[i % 4].metric(k, val_fmt, border=True)

        st.space("medium")
        st.subheader("🧑‍🤝‍🧑 Escalação titular analisada")
        if not df_titulares.empty and cols_titulares:
            col_config = {}
            if 'Nota média' in cols_titulares:
                col_config['Nota média'] = st.column_config.ProgressColumn(
                    'Nota média', min_value=0, max_value=10, format='%.2f')
            st.dataframe(df_titulares[cols_titulares], column_config=col_config, hide_index=True)
        else:
            st.caption("Nenhum titular encontrado.")

    # ------------------------------------------
    elif secao == "scout_time":
        st.subheader("🤖 Olheiro do Time")
        st.caption("Escolha a perspectiva da análise: como o próprio time ou como um olheiro adversário.")

        PERSPECTIVAS = {
            "proprio":    ("🛡️ Meu Time", "Análise interna — pontos de melhoria e sugestões de reforço"),
            "adversario": ("🎯 Time Adversário", "Visão de scout rival — fraquezas a explorar taticamente"),
        }

        chave_persp = f'perspectiva_time_{posicao}'
        if chave_persp not in st.session_state:
            st.session_state[chave_persp] = "proprio"

        col_a, col_b = st.columns(2)
        for col, (chave_persp_opt, (label, desc)) in zip([col_a, col_b], PERSPECTIVAS.items()):
            ativo = st.session_state[chave_persp] == chave_persp_opt
            with col:
                if st.button(label, key=f"persp_{posicao}_{chave_persp_opt}",
                              use_container_width=True,
                              type="primary" if ativo else "secondary"):
                    if st.session_state[chave_persp] != chave_persp_opt:
                        st.session_state[chave_persp] = chave_persp_opt
                        # Limpa relatório anterior ao trocar de perspectiva
                        chave_ia_old = f'relatorio_ia_{posicao}_{chave_persp_opt}'
                        st.rerun()
                st.caption(desc)

        perspectiva_ativa = st.session_state[chave_persp]
        chave_ia = f'relatorio_ia_{posicao}_{perspectiva_ativa}'

        CHAVE_API = st.secrets["CHAVE_API_GEMINI"]
        genai.configure(api_key=CHAVE_API)
        modelo_ia = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

        st.space("small")

        if chave_ia not in st.session_state:
            label_btn = "Gerar análise do time" if perspectiva_ativa == "proprio" else "Gerar análise do adversário"
            if st.button(f":material/play_arrow: {label_btn}", type="primary", key=f"btn_ia_{posicao}_{perspectiva_ativa}"):
                with st.spinner("O Olheiro IA está analisando o desempenho da equipe..."):
                    titulares_dict = df_titulares[cols_titulares].to_dict('records') if cols_titulares else []
                    prompt = gerar_olheiro_time_prompt(stats_time, titulares_dict, perspectiva=perspectiva_ativa)
                    try:
                        resposta = modelo_ia.generate_content(prompt)
                        st.session_state[chave_ia] = resposta.text
                        if hist.supabase_disponivel():
                            try:
                                hist.salvar_email_olheiro(
                                    _usuario_id, posicao, 'time',
                                    perspectiva_ativa, resposta.text
                                )
                            except Exception:
                                pass
                        st.rerun()
                    except Exception:
                        st.session_state[chave_ia] = "⚠️ Limite de velocidade do Google atingido. Aguarde 1 minuto e tente novamente."
                        st.rerun()
        else:
            with st.container(border=True):
                st.write(st.session_state[chave_ia])
            if st.button(":material/refresh: Gerar nova análise", key=f"btn_ia_refresh_{posicao}_{perspectiva_ativa}"):
                del st.session_state[chave_ia]
                st.rerun()

    else:
        st.warning(f"Seção '{secao}' não disponível para a aba de Time.")


# ==========================================
# ÁREA PRINCIPAL — abas por posição
# ==========================================

# Hero com imagem FM26 como banner + degradê
st.markdown("""
<style>
.fm-hero {
    width: 100%;
    border-radius: 14px;
    overflow: hidden;
    position: relative;
    height: 160px;
    margin-bottom: 20px;
    background:
        linear-gradient(to right,
            #0A0F0D 0%,
            #0A0F0D 15%,
            rgba(10,15,13,0.7) 40%,
            rgba(10,15,13,0) 65%),
        linear-gradient(to top,
            #0A0F0D 0%,
            rgba(10,15,13,0) 40%),
        url("https://raw.githubusercontent.com/viniciusmorenorogato-crypto/ProjetoMoneyball/main/assets/fm26_banner.jpg")
        center/cover no-repeat;
    display: flex;
    align-items: center;
    padding: 0 28px;
}
.fm-hero-text h1 {
    margin: 0;
    font-size: 2rem;
    font-weight: 800;
    color: #E8F5E9;
    letter-spacing: -0.5px;
    text-shadow: 0 2px 8px rgba(0,0,0,0.6);
}
.fm-hero-text p {
    margin: 4px 0 0 0;
    font-size: 0.85rem;
    color: #9CA3AF;
}
</style>
<div class="fm-hero">
  <div class="fm-hero-text">
    <h1>🏆 Scout Moneyball</h1>
    <p>Análise AHP de jogadores do Football Manager</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# HELPER: seção Confiabilidade (Score de Confiabilidade por posição)
# ==========================================
def _radar_confiabilidade(df_perc, jogador_a, jogador_b, plt):
    """Radar (matplotlib) comparando os percentis de confiabilidade de 2 jogadores."""
    import numpy as np
    rotulos = list(df_perc.columns)
    n = len(rotulos)
    angulos = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angulos += angulos[:1]

    fig, ax = plt.subplots(figsize=(4.3, 4.3), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('#0A0F0C')
    ax.set_facecolor('#0A0F0C')

    pares = [(jogador_a, '#22C55E')]
    if jogador_b and jogador_b != jogador_a:
        pares.append((jogador_b, '#38BDF8'))

    for jog, cor in pares:
        vals = df_perc.loc[jog].tolist()
        vals += vals[:1]
        ax.plot(angulos, vals, color=cor, linewidth=2, label=jog)
        ax.fill(angulos, vals, color=cor, alpha=0.18)

    ax.set_xticks(angulos[:-1])
    ax.set_xticklabels(rotulos, fontsize=7, color='#CBD5E1')
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(['25', '50', '75', '100'], fontsize=6, color='#6B7280')
    ax.set_ylim(0, 100)
    ax.spines['polar'].set_color('#1E3A24')
    ax.grid(color='#1E3A24', linewidth=0.8)
    ax.set_title('Percentis de confiabilidade (0–100)', color='#E8F5E9', fontsize=10, pad=16)
    ax.legend(loc='upper right', bbox_to_anchor=(1.22, 1.14), facecolor='#0A0F0C',
              edgecolor='#1E3A24', labelcolor='#E8F5E9', fontsize=7)
    fig.tight_layout()
    return fig


def _fig_kde_confiabilidade(grid, dens, cdf, x_jogador, rotulo, coluna, plt):
    """Curva de densidade (KDE) de uma métrica com a área integral até o valor do
    jogador (= percentil) sombreada e a densidade local (= derivada da CDF) anotada."""
    import numpy as np
    perc = float(np.interp(x_jogador, grid, cdf, left=0.0, right=1.0))
    dloc = float(np.interp(x_jogador, grid, dens, left=0.0, right=0.0))

    fig, ax = plt.subplots(figsize=(5.4, 2.6))
    fig.patch.set_facecolor('#0A0F0C')
    ax.set_facecolor('#0A0F0C')
    ax.plot(grid, dens, color='#4ADE80', linewidth=2)
    mask = grid <= x_jogador
    ax.fill_between(grid[mask], dens[mask], color='#22C55E', alpha=0.30)
    ax.axvline(x_jogador, color='#F59E0B', linewidth=2)
    ax.plot([x_jogador], [dloc], marker='o', color='#F59E0B', markersize=7, zorder=5)

    ax.set_title(f"{rotulo} — distribuição dos jogadores", color='#E8F5E9', fontsize=11)
    ax.set_xlabel(str(coluna), color='#9CA3AF', fontsize=8)
    ax.set_ylabel('nº de jogadores', color='#9CA3AF', fontsize=8)
    ax.tick_params(colors='#6B7280', labelsize=7)
    ax.set_yticks([])
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    for lado in ('left', 'bottom'):
        ax.spines[lado].set_color('#1E3A24')
    ax.grid(color='#132018', linewidth=0.7)
    ax.annotate(f"Percentil: {perc * 100:.0f}",
                xy=(0.98, 0.94), xycoords='axes fraction', ha='right', va='top',
                fontsize=9, color='#E8F5E9',
                bbox=dict(boxstyle='round', facecolor='#08120C', edgecolor='#1E3A24'))
    fig.tight_layout()
    return fig


def render_confiabilidade(posicao, df_da_posicao):
    """Renderiza a seção de Score de Confiabilidade para uma posição, em duas abas:
    análise padrão e análise avançada."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    st.subheader("🛡️ Score de Confiabilidade")
    st.caption("Índice composto ponderado por percentis, comparando cada jogador contra os "
               "pares da **mesma posição**. Métricas negativas (erros, posse perdida) são "
               "invertidas: quanto maior o score, mais confiável.")

    if not confi.posicao_suportada(posicao):
        st.info("A análise de confiabilidade não está disponível para esta aba.")
        return

    df_scores, df_perc, usadas = confi.calcular_confiabilidade(df_da_posicao, posicao)
    if df_scores is None:
        st.warning("Dados insuficientes para calcular a confiabilidade desta posição "
                   "(mínimo de jogadores ou de métricas não atingido).")
        return

    aba_padrao, aba_avancada = st.tabs(["📊 Análise padrão", "🔬 Análise avançada"])
    with aba_padrao:
        _render_confiabilidade_padrao(posicao, df_scores, df_perc, usadas, plt)
    with aba_avancada:
        _render_confiabilidade_avancada(posicao, df_da_posicao, plt)


def _render_confiabilidade_padrao(posicao, df_scores, df_perc, usadas, plt):
    """Aba de análise padrão da confiabilidade (ranking, percentis, radar, matriz de risco)."""
    sent = {u['label']: u['sentido'] for u in usadas}
    pos_labels = [l for l, s in sent.items() if s == 1]
    neg_labels = [l for l, s in sent.items() if s == -1]

    with st.expander("ℹ️ Como o score é calculado"):
        st.markdown(f"""
        - **Positivas (recompensa):** {', '.join(pos_labels)}
        - **Negativas (penalidade, invertidas):** {', '.join(neg_labels)}
        - Cada métrica vira **percentil dentro da posição** (0 = pior, 100 = melhor dos pares).
        - As negativas pesam mais quando são erros graves (ex.: *erro que gera gol* pesa muito
          mais que um passe errado).
        - O **Score** é a média ponderada de todas as métricas; o **Índice Positivo** usa só as
          de produção e o **Índice de Risco** só as de erro (usados na matriz de risco).
        - ⚠️ *xT/EPV* exigem dados de evento que o FM não exporta — usamos *passes em progressão*
          e *posse perdida* como proxy de progressão segura vs. arriscada.
        """)

    lider = df_scores.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("🥇 Mais confiável", str(lider['Jogador']), f"{lider['Score_Confiabilidade']:.0f}/100")
    c2.metric("Índice positivo (líder)", f"{lider['Indice_Positivo']:.0f}")
    c3.metric("Índice de risco (líder)", f"{lider['Indice_Risco']:.0f}", delta_color="inverse")

    st.markdown("#### 📊 Ranking de confiabilidade")
    col_cfg = {
        'Score_Confiabilidade': st.column_config.ProgressColumn(
            'Score', min_value=0, max_value=100, format='%.1f'),
        'Indice_Positivo': st.column_config.NumberColumn('Produção', format='%.0f'),
        'Indice_Risco': st.column_config.NumberColumn('Risco', format='%.0f'),
    }
    st.dataframe(df_scores, column_config=col_cfg, hide_index=True, use_container_width=True)

    jogadores = df_scores['Jogador'].tolist()

    # ---- 1) Barras de percentil ----
    st.markdown("#### 📈 Percentis por métrica")
    st.caption("Onde o jogador está frente aos pares (já ajustado para 'quanto maior, melhor').")
    jogador_sel = st.selectbox("Jogador", jogadores, key=f"confi_bar_{posicao}")
    serie = df_perc.loc[jogador_sel]
    df_bars = pd.DataFrame({'Métrica': serie.index.tolist(), 'Percentil': serie.values})
    df_bars['Tipo'] = df_bars['Métrica'].map(
        lambda l: 'Positiva' if sent.get(l, 1) == 1 else 'Negativa (invertida)')
    grafico_bars = alt.Chart(df_bars).mark_bar().encode(
        x=alt.X('Percentil:Q', scale=alt.Scale(domain=[0, 100]), title='Percentil'),
        y=alt.Y('Métrica:N', sort='-x', title=None),
        color=alt.Color('Tipo:N',
                        scale=alt.Scale(domain=['Positiva', 'Negativa (invertida)'],
                                        range=['#22C55E', '#F59E0B']),
                        legend=alt.Legend(title=None, orient='top')),
        tooltip=['Métrica:N', alt.Tooltip('Percentil:Q', format='.0f'), 'Tipo:N'],
    ).properties(height=max(200, 30 * len(df_bars)))
    st.altair_chart(grafico_bars, use_container_width=True)

    # ---- 2) Radar comparativo ----
    st.markdown("#### 🎯 Comparativo (radar)")
    cc1, cc2 = st.columns(2)
    j_a = cc1.selectbox("Jogador A", jogadores, index=0, key=f"confi_radar_a_{posicao}")
    j_b = cc2.selectbox("Jogador B", jogadores,
                        index=1 if len(jogadores) > 1 else 0, key=f"confi_radar_b_{posicao}")
    fig = _radar_confiabilidade(df_perc, j_a, j_b, plt)
    col_r = st.columns([1, 2, 1])[1]
    col_r.pyplot(fig, use_container_width=False)
    plt.close(fig)

    # ---- 3) Matriz de risco (nome só no hover) ----
    st.markdown("#### ⚠️ Matriz de risco")
    st.caption("Canto **superior-esquerdo** = alta produção e baixo risco: os jogadores mais "
               "confiáveis. Passe o mouse sobre um ponto para ver o jogador.")
    base = alt.Chart(df_scores).encode(
        x=alt.X('Indice_Risco:Q', scale=alt.Scale(domain=[0, 100]), title='Índice de risco (erros) →'),
        y=alt.Y('Indice_Positivo:Q', scale=alt.Scale(domain=[0, 100]), title='Índice positivo (produção) →'),
    )
    pontos = base.mark_circle(size=150, opacity=0.85).encode(
        color=alt.Color('Score_Confiabilidade:Q', scale=alt.Scale(scheme='greens'), title='Score'),
        tooltip=['Jogador:N', alt.Tooltip('Score_Confiabilidade:Q', title='Score', format='.0f'),
                 alt.Tooltip('Indice_Positivo:Q', title='Produção', format='.0f'),
                 alt.Tooltip('Indice_Risco:Q', title='Risco', format='.0f')],
    )
    reg_x = alt.Chart(pd.DataFrame({'x': [float(df_scores['Indice_Risco'].median())]})).mark_rule(
        color='#6B7280', strokeDash=[4, 4]).encode(x='x:Q')
    reg_y = alt.Chart(pd.DataFrame({'y': [float(df_scores['Indice_Positivo'].median())]})).mark_rule(
        color='#6B7280', strokeDash=[4, 4]).encode(y='y:Q')
    st.altair_chart((reg_x + reg_y + pontos).properties(height=420).interactive(),
                    use_container_width=True)


def _render_confiabilidade_avancada(posicao, df_da_posicao, plt):
    """Aba de análise avançada: métricas derivadas de integral (KDE/CDF, entropia) e
    derivada (densidade local, gradiente do score)."""
    st.caption("Uma leitura mais fina de cada jogador, além do ranking simples.")

    bundle = confi.calcular_avancado(df_da_posicao, posicao)
    if bundle is None:
        st.info("Poucos jogadores nesta posição para a análise avançada.")
        return

    df_adv = bundle['df']
    sent = bundle['sent']
    grids = bundle['grids']
    valores = bundle['valores']
    alavancas = bundle['alavancas']

    with st.expander("ℹ️ O que cada índice significa"):
        st.markdown("""
        - **Índice geral** — a nota principal desta análise. Ela parte do score e ajusta para
          baixo quem depende de poucas qualidades ou jogou poucos minutos.
        - **Estabilidade** — o quanto o desempenho do jogador se sustenta. Alta significa
          confiável de forma consistente; baixa significa que ele está muito próximo de outros
          e pode oscilar com facilidade.
        - **Consistência** — se o jogador é equilibrado em tudo ou se depende de uma qualidade
          só. Quanto mais parelho, mais confiável.
        - **Confiança e a margem ±** — o quanto dá para confiar na nota. Quem jogou mais minutos
          tem uma leitura mais firme; poucos minutos deixam a nota com uma margem maior.
        - **Prioridade de evolução** — a qualidade onde ele ganharia nota mais rápido se melhorasse.
        """)

    st.markdown("#### 🏆 Ranking detalhado")
    col_cfg = {
        'Indice_Academico': st.column_config.ProgressColumn('Índice geral', min_value=0, max_value=100, format='%.1f'),
        'Score': st.column_config.NumberColumn('Score base', format='%.0f'),
        'Estabilidade': st.column_config.NumberColumn('Estabilidade', format='%.0f'),
        'Consistencia': st.column_config.NumberColumn('Consistência', format='%.0f'),
        'Confianca': st.column_config.NumberColumn('Confiança', format='%.0f'),
        'Banda': st.column_config.NumberColumn('± Margem', format='%.0f'),
    }
    st.dataframe(df_adv, column_config=col_cfg, hide_index=True, use_container_width=True)

    jogadores = df_adv['Jogador'].tolist()
    jog = st.selectbox("Inspecionar jogador", jogadores, key=f"adv_jog_{posicao}")
    linha = df_adv[df_adv['Jogador'] == jog].iloc[0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Índice geral", f"{linha['Indice_Academico']:.0f}")
    m2.metric("Estabilidade", f"{linha['Estabilidade']:.0f}", help="O quanto o desempenho se sustenta")
    m3.metric("Consistência", f"{linha['Consistencia']:.0f}", help="Equilíbrio entre todas as qualidades")
    banda_txt = "—" if pd.isna(linha['Banda']) else f"± {linha['Banda']:.0f}"
    m4.metric("Score ± margem", f"{linha['Score']:.0f}", banda_txt, delta_color="off",
              help="Margem de incerteza conforme os minutos jogados")

    # Prioridade de evolução
    st.markdown("**🎚️ Prioridade de evolução** — onde este jogador melhoraria mais rápido:")
    lev = alavancas.get(jog, [])
    if lev:
        linhas_lev = []
        for lab, val in lev:
            direcao = "aumentar" if sent.get(lab, 1) == 1 else "reduzir"
            linhas_lev.append(f"- **{lab}** — {direcao} · prioridade {val:.0f}/100")
        st.markdown("\n".join(linhas_lev))
    else:
        st.caption("Jogador já muito completo — pouca coisa a melhorar.")

    # Distribuição da métrica na posição
    st.markdown("#### 📐 Onde o jogador está na métrica")
    st.caption("A curva mostra como os jogadores da posição se espalham nessa métrica. "
               "A linha laranja é onde este jogador está, e a parte preenchida indica o percentil dele.")
    metrica_sel = st.selectbox("Métrica", bundle['usadas'],
                               index=0, key=f"adv_kde_{posicao}")
    if metrica_sel in grids and jog in valores.index:
        grid, dens, cdf, coluna = grids[metrica_sel]
        x_jog = float(valores.loc[jog, metrica_sel])
        if pd.notna(x_jog):
            fig = _fig_kde_confiabilidade(grid, dens, cdf, x_jog, metrica_sel, coluna, plt)
            col_k = st.columns([1, 3, 1])[1]
            col_k.pyplot(fig, use_container_width=False)
            plt.close(fig)
        else:
            st.caption("Sem valor válido desta métrica para o jogador.")

    # Estabilidade × Score — mapa robustez vs qualidade (nome só no hover)
    st.markdown("#### 🧭 Robustez × Qualidade")
    st.caption("Direita e acima = confiável **e** robusto. Baixa estabilidade = score sujeito a "
               "oscilar. Passe o mouse sobre um ponto para ver o jogador.")
    disp = alt.Chart(df_adv).mark_circle(size=140, opacity=0.85).encode(
        x=alt.X('Estabilidade:Q', scale=alt.Scale(domain=[0, 100]), title='Estabilidade (robustez) →'),
        y=alt.Y('Indice_Academico:Q', scale=alt.Scale(domain=[0, 100]), title='Índice geral →'),
        color=alt.Color('Consistencia:Q', scale=alt.Scale(scheme='greens'), title='Consistência'),
        tooltip=['Jogador:N', alt.Tooltip('Indice_Academico:Q', title='Índice geral', format='.0f'),
                 alt.Tooltip('Estabilidade:Q', title='Estabilidade', format='.0f'),
                 alt.Tooltip('Consistencia:Q', title='Consistência', format='.0f')],
    )
    st.altair_chart(disp.properties(height=420).interactive(), use_container_width=True)


# Abas disponíveis de acordo com o modo de análise escolhido
modo_atual = st.session_state.get('modo_analise', 'posicoes')
if modo_atual == 'posicoes':
    abas_do_modo = st.session_state.get('posicoes_confirmadas', POSICOES)
else:
    abas_do_modo = MODOS.get(modo_atual, MODOS['posicoes'])['abas']

if st.session_state['ja_calculou']:
    # Time não entra em "rankings" (não usa AHP) — sempre disponível se estiver no banco
    posicoes_disponiveis = [
        p for p in abas_do_modo
        if p in rankings or (p == POSICAO_TIME and p in banco_completo)
    ]
    if not posicoes_disponiveis:
        st.warning("Nenhuma aba processada com sucesso.")
        st.stop()
else:
    banco_pre = st.session_state.get('banco_de_dados_completo', {})
    posicoes_disponiveis = [p for p in abas_do_modo if p in banco_pre]
    if not posicoes_disponiveis:
        st.info("Faça o upload da planilha e clique em **🚀 Calcular** para começar.")
        st.stop()

abas = st.tabs(posicoes_disponiveis)

# Nomes amigáveis para os critérios internos
NOMES_AMIGAVEIS = {
    'Valor_Numerico': 'Valor de mercado',
    'Salario_Numerico': 'Salário',
    'Contrato_Numerico': 'Fim de contrato',
}

NIVEL_LABELS = {
    1: ("🔴 Muito importante",   1),
    2: ("🟡 Importante",          2),
    3: ("⚪ Menos importante",    3),
}

for aba, posicao in zip(abas, posicoes_disponiveis):
    with aba:

        # ---- Aba de Time: não precisa de configuração de critérios AHP ----
        if posicao == POSICAO_TIME:
            render_secao_time(posicao, secao_ativa)
            continue

        # ---- Configuração de critérios — estilo menu de jogo ----
        if not st.session_state['ja_calculou'] or not st.session_state['configurado'].get(posicao):

            padrao = CRITERIOS_PADRAO.get(posicao, {})
            colunas_cfg = padrao.get('colunas', [])
            nivel_1_pad = padrao.get('nivel_1', [])
            nivel_2_pad = padrao.get('nivel_2', [])

            def nivel_padrao(c):
                if c in nivel_1_pad: return 1
                if c in nivel_2_pad: return 2
                return 3

            niveis_atuais = st.session_state['niveis_usuario'].get(posicao, {})

            st.markdown("""
            <style>
            /* ── Painel principal ── */
            .gm-panel {
                background: #070C09;
                border: 1px solid #1A3020;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 20px;
                box-shadow: 0 0 40px rgba(34,197,94,0.04);
            }
            /* ── Topo estilo HUD ── */
            .gm-topbar {
                background: #0A1A0E;
                border-bottom: 2px solid #22C55E;
                padding: 14px 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .gm-topbar-title {
                font-size: 0.65rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 3px;
                color: #22C55E;
            }
            .gm-topbar-pos {
                font-size: 0.75rem;
                color: #4ADE80;
                font-weight: 600;
                letter-spacing: 1px;
            }
            .gm-topbar-hint {
                font-size: 0.6rem;
                color: #374151;
                text-transform: uppercase;
                letter-spacing: 1.5px;
            }
            /* ── Legenda de níveis ── */
            .gm-legend {
                display: flex;
                gap: 0;
                border-bottom: 1px solid #1A3020;
            }
            .gm-legend-item {
                flex: 1;
                padding: 8px 16px;
                display: flex;
                align-items: center;
                gap: 8px;
                border-right: 1px solid #1A3020;
            }
            .gm-legend-item:last-child { border-right: none; }
            .gm-legend-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
            .gm-legend-label { font-size:0.68rem; color:#6B7280; }
            .gm-legend-label b { color:#9CA3AF; }
            /* ── Separador de grupo ── */
            .gm-group-sep {
                background: #0A1A0E;
                border-top: 1px solid #1A3020;
                border-bottom: 1px solid #1A3020;
                padding: 6px 24px;
                font-size: 0.58rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 2.5px;
                color: #22C55E55;
            }
            /* ── Linha de critério ── */
            .gm-row {
                display: flex;
                align-items: center;
                padding: 0 24px;
                border-bottom: 1px solid #0F1F14;
                min-height: 52px;
                transition: background .15s;
            }
            .gm-row:hover { background: #0A1A0E88; }
            .gm-row:last-child { border-bottom: none; }
            .gm-row-name {
                flex: 1;
                font-size: 0.8rem;
                color: #C4D4C8;
                font-weight: 500;
            }
            .gm-row-name span {
                font-size: 0.6rem;
                color: #374151;
                margin-left: 6px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }
            /* ── Slots de nível (visual) — o radio real fica invisível em cima ── */
            .gm-slots { display:flex; gap:4px; }
            .gm-slot {
                width: 96px;
                height: 30px;
                border-radius: 3px;
                border: 1px solid #1A3020;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.62rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                color: #374151;
                cursor: pointer;
                transition: all .15s;
            }
            /* Radio nativo sobreposto — invisível mas clicável */
            div[data-testid="stRadio"] { margin: 0 !important; }
            div[data-testid="stRadio"] > div[role="radiogroup"] {
                display: flex !important;
                gap: 4px !important;
                flex-direction: row !important;
            }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label {
                width: 96px !important;
                height: 30px !important;
                border-radius: 3px !important;
                border: 1px solid #1A3020 !important;
                background: transparent !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                font-size: 0.62rem !important;
                font-weight: 700 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.8px !important;
                color: #374151 !important;
                cursor: pointer !important;
                transition: all .15s !important;
                padding: 0 !important;
            }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
                border-color: #22C55E66 !important;
                color: #9CA3AF !important;
                background: #0A1A0E !important;
            }
            /* Slots ativos por posição no grupo */
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:nth-child(1):has(input:checked) {
                background: #7F1D1D !important;
                border-color: #EF4444 !important;
                color: #FCA5A5 !important;
                box-shadow: 0 0 8px #EF444433 !important;
            }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:nth-child(2):has(input:checked) {
                background: #713F12 !important;
                border-color: #EAB308 !important;
                color: #FDE68A !important;
                box-shadow: 0 0 8px #EAB30833 !important;
            }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:nth-child(3):has(input:checked) {
                background: #1F2937 !important;
                border-color: #6B7280 !important;
                color: #D1D5DB !important;
            }
            /* Slot Ignorar — 4º slot */
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:nth-child(4) {
                border-color: #1A1A1A !important;
                color: #292929 !important;
            }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:nth-child(4):hover {
                border-color: #EF444466 !important;
                color: #EF4444 !important;
                background: #1A0808 !important;
            }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label:nth-child(4):has(input:checked) {
                background: #0D0000 !important;
                border-color: #7F1D1D !important;
                color: #EF4444 !important;
                text-decoration: line-through !important;
                opacity: 0.7 !important;
            }
            /* Esconde o círculo do radio e o label de texto padrão */
            div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child { display:none !important; }
            div[data-testid="stRadio"] > label { display:none !important; }
            </style>
            """, unsafe_allow_html=True)

            # Topbar HUD
            st.markdown(f"""
            <div class="gm-panel">
              <div class="gm-topbar">
                <span class="gm-topbar-title">◈ Configuração de critérios AHP</span>
                <span class="gm-topbar-pos">{posicao}</span>
                <span class="gm-topbar-hint">Selecione a importância de cada atributo</span>
              </div>
              <div class="gm-legend">
                <div class="gm-legend-item">
                  <div class="gm-legend-dot" style="background:#EF4444"></div>
                  <div class="gm-legend-label"><b>Muito importante</b> · Peso máximo</div>
                </div>
                <div class="gm-legend-item">
                  <div class="gm-legend-dot" style="background:#EAB308"></div>
                  <div class="gm-legend-label"><b>Importante</b> · Peso médio</div>
                </div>
                <div class="gm-legend-item">
                  <div class="gm-legend-dot" style="background:#4B5563"></div>
                  <div class="gm-legend-label"><b>Menos importante</b> · Peso mínimo</div>
                </div>
                <div class="gm-legend-item">
                  <div class="gm-legend-dot" style="background:#1A1A1A; border:1px solid #374151"></div>
                  <div class="gm-legend-label"><b>Ignorar</b> · Fora do cálculo</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            GRUPOS = [
                ("PRIMÁRIOS — padrão: muito importante", [c for c in colunas_cfg if nivel_padrao(c) == 1]),
                ("SECUNDÁRIOS — padrão: importante",     [c for c in colunas_cfg if nivel_padrao(c) == 2]),
                ("AUXILIARES — padrão: menos importante",[c for c in colunas_cfg if nivel_padrao(c) == 3]),
            ]
            opcoes_nivel = {1: "▲  Máximo", 2: "◆  Médio", 3: "▼  Mínimo", 0: "✕  Ignorar"}

            with st.form(key=f"form_criterios_{posicao}"):
                selecoes = {}
                for grupo_titulo, grupo_crit in GRUPOS:
                    if not grupo_crit:
                        continue
                    st.markdown(f'<div class="gm-group-sep">{grupo_titulo}</div>', unsafe_allow_html=True)
                    for criterio in grupo_crit:
                        nome_exib = NOMES_AMIGAVEIS.get(criterio, criterio)
                        _opcoes = [1, 2, 3, 0]
                        _val = niveis_atuais.get(criterio, nivel_padrao(criterio))
                        default_idx = _opcoes.index(_val) if _val in _opcoes else 0
                        col_nome, col_radio = st.columns([2, 3])
                        with col_nome:
                            st.markdown(
                                f'<div class="gm-row"><span class="gm-row-name">{nome_exib}</span></div>',
                                unsafe_allow_html=True
                            )
                        with col_radio:
                            selecoes[criterio] = st.radio(
                                nome_exib,
                                options=[1, 2, 3, 0],
                                format_func=lambda x: opcoes_nivel[x],
                                index=default_idx,
                                horizontal=True,
                                key=f"radio_{posicao}_{criterio}",
                                label_visibility="collapsed"
                            )

                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button(
                    "✅  Salvar configuração desta posição",
                    use_container_width=True,
                    type="primary"
                )
                if submitted:
                    ativos = [c for c, v in selecoes.items() if v != 0]
                    if len(ativos) < 2:
                        st.error("⚠️ Selecione pelo menos 2 critérios ativos (não Ignorar) para continuar.")
                    else:
                        st.session_state['niveis_usuario'][posicao] = dict(selecoes)
                        st.session_state['configurado'][posicao] = True
                        st.rerun()

            # Opção de pular — só aparece antes do cálculo, e não para Overall (configuração obrigatória)
            if not st.session_state['ja_calculou'] and posicao not in POSICOES_OVERALL:
                st.caption("💡 Você também pode clicar em **🚀 Calcular** direto na barra lateral — as posições não configuradas usarão os pesos padrão.")
            elif not st.session_state['ja_calculou'] and posicao in POSICOES_OVERALL:
                st.caption("⚠️ É necessário confirmar os critérios desta aba antes de calcular.")

            continue

        df_filtrado, df_da_posicao = montar_df(posicao)

        if secao_ativa == "planilha":
            st.subheader("📋 Planilha completa")
            st.caption("Todos os dados originais da planilha importada.")
            _, df_bruta = montar_df(posicao)
            if df_bruta is not None:
                col_config_pl = {}
                if 'Nota média' in df_bruta.columns:
                    col_config_pl['Nota média'] = st.column_config.ProgressColumn(
                        'Nota média FM', min_value=0, max_value=20, format='%.1f')
                st.dataframe(df_bruta, column_config=col_config_pl, hide_index=True)
        elif secao_ativa == "confiabilidade":
            render_confiabilidade(posicao, df_da_posicao)
        else:
            render_secao(posicao, df_filtrado, df_da_posicao, secao_ativa)