"""
components/ui.py — Tema Grupo LLE (mesmo padrão do CRM)
"""
import base64
from pathlib import Path

import streamlit as st

# Cores oficiais do components/ui.py do CRM
AMARELO  = "#FAC319"
VERDE    = "#0F8C3B"
AZUL     = "#007FE0"
AZUL_ESC = "#041747"


def get_logo_b64() -> str:
    """Retorna o logo do Grupo LLE em base64, ou string vazia se não achar."""
    for p in [Path(__file__).parent.parent / "assets" / "logo.png", Path("assets/logo.png")]:
        if p.exists():
            return base64.b64encode(p.read_bytes()).decode()
    return ""


def inject_css():
    """Injeta o tema visual do Grupo LLE."""
    st.markdown(f"""
    <style>
    /* Esconde menu automático e elementos do Streamlit que não queremos */
    [data-testid="stSidebarNav"] {{ display: none !important; }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}

    /* Botão primário com cor Grupo LLE */
    [data-testid="baseButton-primary"] {{
        background: {AZUL_ESC} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 7px !important;
        font-weight: 700 !important;
    }}
    [data-testid="baseButton-primary"]:hover {{
        background: {AZUL} !important;
    }}

    /* Headers em azul escuro */
    h1 {{ color: {AZUL_ESC} !important; font-weight: 700 !important; }}
    h2 {{ color: {AZUL_ESC} !important; font-weight: 600 !important; }}
    h3 {{ color: {AZUL_ESC} !important; }}

    /* Métricas com a borda lateral amarela do CRM */
    [data-testid="metric-container"] {{
        background: #f4f7fc;
        border-radius: 10px;
        padding: 14px 18px;
        border-left: 4px solid {AMARELO};
        box-shadow: 0 1px 4px rgba(4,23,71,0.07);
    }}

    /* Linha divisória amarela suave */
    hr {{ border-color: {AMARELO} !important; opacity: 0.25; }}

    /* Expander com borda padrão */
    [data-testid="stExpander"] {{
        border: 1px solid #dde3ef !important;
        border-radius: 9px !important;
    }}

    /* Tabs estilizados com amarelo no ativo */
    [data-baseweb="tab-list"] {{ gap: 4px; }}
    [data-baseweb="tab"][aria-selected="true"] {{
        color: {AZUL_ESC} !important;
        border-bottom-color: {AMARELO} !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def render_header():
    """Renderiza o cabeçalho com logo do Grupo LLE."""
    logo_b64 = get_logo_b64()

    if logo_b64:
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-width:210px;width:100%;" />'
    else:
        logo_html = f'<span style="color:{AMARELO};font-weight:800;font-size:26px;letter-spacing:2px;">GRUPO LLE</span>'

    st.markdown(
        f'<div style="background:{AZUL_ESC};padding:28px 24px;'
        f'border-radius:12px;text-align:center;margin-bottom:24px;">'
        f'{logo_html}'
        f'<div style="color:{AMARELO};font-size:11px;letter-spacing:.08em;'
        f'margin-top:8px;text-transform:uppercase;">Gerador de Link de Pagamento</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def card_status(texto: str, status: str = "pendente"):
    """Renderiza uma badge de status colorida."""
    cores = {
        "pago": VERDE,
        "pendente": "#666",
        "erro": "#b42318",
    }
    cor = cores.get(status, "#666")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        f'background:{cor};color:white;font-size:11px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.5px;">{texto}</span>'
    )
