"""
utils/auth.py — Login com senha compartilhada simples.
"""
import hmac

import streamlit as st

from components.ui import AZUL_ESC, AMARELO, get_logo_b64


def verificar_senha() -> bool:
    """
    Retorna True se o usuário está autenticado.
    Mostra a tela de login se não estiver.
    """
    if st.session_state.get("autenticado"):
        return True

    _mostrar_tela_login()
    return False


def _verificar_senha_callback():
    """Callback chamado quando o usuário envia o formulário de login."""
    senha_digitada = st.session_state.get("senha_input", "")
    senha_correta = st.secrets["APP_PASSWORD"]

    # hmac.compare_digest evita ataques de tempo
    if hmac.compare_digest(senha_digitada, senha_correta):
        st.session_state["autenticado"] = True
        st.session_state["erro_login"] = False
    else:
        st.session_state["autenticado"] = False
        st.session_state["erro_login"] = True


def _mostrar_tela_login():
    """Renderiza a tela de login centralizada."""
    logo_b64 = get_logo_b64()

    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown("<br>", unsafe_allow_html=True)

        # Cabeçalho com logo
        if logo_b64:
            logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-width:200px;width:100%;" />'
        else:
            logo_html = f'<span style="color:{AMARELO};font-weight:800;font-size:26px;letter-spacing:2px;">GRUPO LLE</span>'

        st.markdown(
            f'<div style="background:{AZUL_ESC};padding:24px;'
            f'border-radius:12px 12px 0 0;text-align:center;">{logo_html}'
            f'<div style="color:{AMARELO};font-size:11px;letter-spacing:.08em;'
            f'margin-top:6px;text-transform:uppercase;">Gerador de Link de Pagamento</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Container do formulário (sem div wrapper, deixa o Streamlit cuidar)
        with st.form("login_form"):
            st.text_input(
                "Senha de acesso",
                type="password",
                key="senha_input",
                placeholder="Digite a senha",
            )
            submitted = st.form_submit_button(
                "Entrar", type="primary", use_container_width=True
            )

            if submitted:
                _verificar_senha_callback()
                if st.session_state.get("autenticado"):
                    st.rerun()

        if st.session_state.get("erro_login"):
            st.error("❌ Senha incorreta.")

        st.markdown(
            '<p style="text-align:center;color:#94a3b8;font-size:12px;margin-top:16px;">'
            'Acesso restrito — Grupo LLE</p>',
            unsafe_allow_html=True
        )


def fazer_logout():
    """Limpa a sessão e força a tela de login."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
