"""
app.py — Gerador de Link de Pagamento Cielo — Grupo LLE
Streamlit App com Supabase e autenticação por senha.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime

import streamlit as st

from components.ui import inject_css, render_header, card_status, AZUL_ESC, AMARELO, VERDE, AZUL
from utils.auth import verificar_senha, fazer_logout
from utils.cielo_client import CieloClient, CieloError, classificar_pagamento
from utils import database as db


# ─── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Grupo LLE — Link de Pagamento",
    page_icon="💳",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Força tema claro independente da preferência do navegador
st.markdown("""
<style>
    /* Fundo geral claro */
    .stApp {
        background-color: #FFFFFF !important;
        color: #1a1a1a !important;
    }
    [data-testid="stHeader"] {
        background-color: #FFFFFF !important;
    }
    [data-testid="stAppViewContainer"] {
        background-color: #FFFFFF !important;
    }

    /* Inputs */
    .stTextInput input, .stSelectbox > div > div {
        background-color: #FFFFFF !important;
        color: #1a1a1a !important;
        border: 1px solid #dde3ef !important;
    }
    .stTextInput label, .stSelectbox label, .stRadio label {
        color: #1a1a1a !important;
    }

    /* Textos */
    p, span, div, label {
        color: #1a1a1a;
    }
    h1, h2, h3, h4 { color: #041747 !important; }

    /* Códigos */
    code, pre {
        background-color: #f4f7fc !important;
        color: #041747 !important;
    }

    /* TODOS os botões: fundo claro com texto escuro (default) */
    .stButton button {
        background-color: #FFFFFF !important;
        color: #041747 !important;
        border: 1px solid #dde3ef !important;
    }
    .stButton button:hover {
        background-color: #f4f7fc !important;
        border-color: #041747 !important;
    }

    /* Botão PRIMÁRIO: azul escuro com texto branco */
    .stButton button[kind="primary"] {
        background-color: #041747 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #007FE0 !important;
    }

    /* Link buttons */
    .stLinkButton a {
        background-color: #041747 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stLinkButton a:hover {
        background-color: #007FE0 !important;
    }

    /* Tabs */
    [data-baseweb="tab-list"] {
        background-color: transparent !important;
    }
    [data-baseweb="tab"] {
        color: #666 !important;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        color: #041747 !important;
    }

    /* Expander */
    [data-testid="stExpander"] {
        background-color: #FFFFFF !important;
    }
    [data-testid="stExpander"] summary {
        color: #1a1a1a !important;
    }

    /* Forms */
    [data-testid="stForm"] {
        background-color: #FFFFFF !important;
        border: 1px solid #dde3ef !important;
    }
</style>
""", unsafe_allow_html=True)

inject_css()

# ─── Verificação de senha (bloqueia o resto da app se não logado) ────────────
if not verificar_senha():
    st.stop()


# ─── Utilitários ─────────────────────────────────────────────────────────────

@st.cache_resource
def get_cielo() -> CieloClient:
    """Instancia o cliente Cielo (cacheado pra reaproveitar o token entre interações)."""
    return CieloClient(
        client_id=st.secrets["CIELO_CLIENT_ID"],
        client_secret=st.secrets["CIELO_CLIENT_SECRET"],
    )


def parse_valor_brl(valor_str: str) -> int:
    """Converte texto em reais para centavos. Aceita '89,90', '1.234,56', 'R$ 89,90'."""
    if not valor_str:
        raise ValueError("Valor é obrigatório.")

    cleaned = valor_str.strip().replace("R$", "").replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")

    try:
        valor_decimal = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Valor inválido: '{valor_str}'.")
    if valor_decimal <= 0:
        raise ValueError("O valor deve ser maior que zero.")

    return int((valor_decimal * 100).quantize(Decimal("1")))


def formatar_brl(centavos: int) -> str:
    """Converte centavos em string 'R$ X.XXX,XX'."""
    valor = Decimal(centavos) / 100
    inteiro, _, decimal = f"{valor:.2f}".partition(".")
    inteiro_fmt = ""
    for i, c in enumerate(reversed(inteiro)):
        if i > 0 and i % 3 == 0:
            inteiro_fmt = "." + inteiro_fmt
        inteiro_fmt = c + inteiro_fmt
    return f"R$ {inteiro_fmt},{decimal}"


def formatar_data(iso_str: str) -> str:
    """Formata string ISO em '2026-05-18 14:32'."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return iso_str.replace("T", " ")


def _render_item_historico(link: dict, categoria: str):
    """
    Renderiza um card de item do histórico.

    Args:
        link: dict com os dados do link.
        categoria: 'nao_pago', 'pago' ou 'pago_liberado'.
    """
    cores_borda = {
        "nao_pago": AMARELO,
        "pago": VERDE,
        "pago_liberado": AZUL,
    }
    cor_borda = cores_borda.get(categoria, AMARELO)

    with st.container():
        st.markdown(
            f'<div style="background:white;border:1px solid #dde3ef;'
            f'border-left:4px solid {cor_borda};border-radius:8px;'
            f'padding:14px 16px;margin-bottom:8px;">',
            unsafe_allow_html=True,
        )

        col_info, col_acao = st.columns([3, 1])

        with col_info:
            st.markdown(f"**{link['descricao']}**")
            st.caption(
                f"{formatar_brl(link['valor_centavos'])} "
                f"· até {link['parcelas_max']}x "
                f"· criado em {formatar_data(link['criado_em'])}"
            )
            if link.get("short_url"):
                st.markdown(f"`{link['short_url']}`")

            # Linha de status conforme categoria
            if categoria == "pago_liberado":
                st.caption(
                    f"✓ Pago em {formatar_data(link.get('ultima_verificacao', ''))} "
                    f"· 🔓 Liberado no ERP em {formatar_data(link.get('liberado_em', ''))}"
                    + (f" por {link['liberado_por']}" if link.get("liberado_por") else "")
                )
            elif categoria == "pago":
                st.caption(
                    f"✓ Confirmado em {formatar_data(link.get('ultima_verificacao', ''))}"
                    + (f" — {link['ultimo_status_label']}" if link.get("ultimo_status_label") else "")
                )
            elif link.get("ultima_verificacao"):
                texto_status = link.get("ultimo_status_label") or "sem tentativas de pagamento"
                st.caption(
                    f"Última verificação: {formatar_data(link['ultima_verificacao'])} — {texto_status}"
                )

        with col_acao:
            # NÃO PAGO: botões "Atualizar" e "Copiar URL"
            if categoria == "nao_pago":
                if st.button("Atualizar", key=f"btn_{link['cielo_id']}", use_container_width=True):
                    with st.spinner("Consultando..."):
                        try:
                            cielo = get_cielo()
                            orders = cielo.get_link_payments(link["cielo_id"])
                            status, raw, lbl = classificar_pagamento(orders)
                            db.atualizar_status(link["cielo_id"], status, raw, lbl)
                            if status == "pago":
                                st.success(f"✓ PAGO ({lbl})")
                            else:
                                st.info(lbl or "Sem tentativas")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

                if link.get("short_url"):
                    if st.button("Copiar URL", key=f"cp_{link['cielo_id']}", use_container_width=True):
                        st.code(link["short_url"], language=None)

            # PAGO (não liberado): botão "Liberar no ERP" + "Reconsultar"
            elif categoria == "pago":
                if st.button(
                    "🔓 Liberar no ERP",
                    key=f"lib_{link['cielo_id']}",
                    use_container_width=True,
                    type="primary",
                ):
                    try:
                        db.marcar_liberado(link["cielo_id"])
                        st.success("✓ Marcado como liberado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

                if st.button("Reconsultar", key=f"btn_{link['cielo_id']}", use_container_width=True):
                    with st.spinner("Consultando..."):
                        try:
                            cielo = get_cielo()
                            orders = cielo.get_link_payments(link["cielo_id"])
                            status, raw, lbl = classificar_pagamento(orders)
                            db.atualizar_status(link["cielo_id"], status, raw, lbl)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

            # PAGO E LIBERADO: botão "Reverter liberação" (caso de erro)
            elif categoria == "pago_liberado":
                if st.button(
                    "↩ Reverter liberação",
                    key=f"rev_{link['cielo_id']}",
                    use_container_width=True,
                ):
                    try:
                        db.desmarcar_liberado(link["cielo_id"])
                        st.success("Liberação revertida.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

        st.markdown('</div>', unsafe_allow_html=True)


# ─── Cabeçalho com logo ──────────────────────────────────────────────────────
render_header()

# Botão de logout discreto no topo direito
col_meta, col_logout = st.columns([4, 1])
with col_logout:
    if st.button("Sair", key="btn_logout", use_container_width=True):
        fazer_logout()


# ─── Abas: Novo Link e Histórico ─────────────────────────────────────────────
tab_novo, tab_historico = st.tabs(["➕ Novo Link", "📋 Histórico"])


# ─── ABA: NOVO LINK ──────────────────────────────────────────────────────────
with tab_novo:
    st.markdown("### Criar novo link de pagamento")

    with st.form("form_novo_link", clear_on_submit=False):
        descricao = st.text_input(
            "Descrição do pedido",
            max_chars=128,
            placeholder="Ex: Consultoria — 1 hora",
        )

        col1, col2 = st.columns([2, 1])
        with col1:
            valor_str = st.text_input(
                "Valor (R$)",
                placeholder="Ex: 89,90",
            )
        with col2:
            parcelas = st.selectbox(
                "Parcelas (máx.)",
                options=[1, 2, 3, 4, 5, 6],
                format_func=lambda n: f"{n}x{' (à vista)' if n == 1 else ''}",
                index=0,
            )

        submitted = st.form_submit_button(
            "Gerar Link", type="primary", use_container_width=True
        )

        if submitted:
            try:
                if not descricao or not descricao.strip():
                    raise ValueError("Descrição é obrigatória.")

                centavos = parse_valor_brl(valor_str)

                with st.spinner("Gerando link na Cielo..."):
                    cielo = get_cielo()
                    resposta = cielo.create_payment_link(
                        name=descricao.strip(),
                        price_cents=centavos,
                        product_type="Payment",
                        max_installments=int(parcelas),
                    )

                link = (
                    resposta.get("shortUrl")
                    or resposta.get("ShortUrl")
                    or resposta.get("link")
                )
                link_id = resposta.get("id") or resposta.get("Id")

                if link_id:
                    try:
                        db.salvar_link(
                            cielo_id=link_id,
                            descricao=descricao.strip(),
                            valor_centavos=centavos,
                            valor_exibicao=valor_str,
                            parcelas_max=int(parcelas),
                            short_url=link,
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Link criado, mas falhou ao salvar no histórico: {e}")

                # Guarda o resultado pra mostrar fora do form (Streamlit limpa logs do form)
                st.session_state["ultimo_link"] = {
                    "descricao": descricao.strip(),
                    "valor": valor_str,
                    "parcelas": int(parcelas),
                    "link": link,
                    "id": link_id,
                    "resposta": resposta,
                }
                st.session_state["ultimo_erro"] = None

            except ValueError as e:
                st.session_state["ultimo_erro"] = str(e)
                st.session_state["ultimo_link"] = None
            except CieloError as e:
                st.session_state["ultimo_erro"] = f"Erro na Cielo: {e}"
                st.session_state["ultimo_link"] = None
            except Exception as e:
                st.session_state["ultimo_erro"] = f"Erro inesperado: {e}"
                st.session_state["ultimo_link"] = None

    # Mostra o resultado fora do form
    if st.session_state.get("ultimo_erro"):
        st.error(f"❌ {st.session_state['ultimo_erro']}")

    if st.session_state.get("ultimo_link"):
        r = st.session_state["ultimo_link"]
        st.success("✓ Link gerado com sucesso!")

        if r["link"]:
            st.code(r["link"], language=None)

            col_a, col_b = st.columns(2)
            with col_a:
                st.link_button(
                    "🔗 Abrir link", r["link"],
                    type="primary", use_container_width=True,
                )

        st.caption(
            f"**{r['descricao']}** · {formatar_brl(parse_valor_brl(r['valor']))} "
            f"· até {r['parcelas']}x"
            + (f" · ID: `{r['id']}`" if r["id"] else "")
        )

        with st.expander("Ver resposta completa da API"):
            st.json(r["resposta"])


# ─── ABA: HISTÓRICO ──────────────────────────────────────────────────────────
with tab_historico:
    col_titulo, col_acao = st.columns([3, 1])
    with col_titulo:
        st.markdown("### Histórico de links")
    with col_acao:
        if st.button("🔄 Atualizar pendentes", use_container_width=True):
            with st.spinner("Consultando status na Cielo..."):
                try:
                    nao_pagos = db.listar_por_status("nao_pago")
                    cielo = get_cielo()
                    novos_pagos = 0
                    erros = 0

                    for link in nao_pagos:
                        try:
                            orders = cielo.get_link_payments(link["cielo_id"])
                            status, raw, label = classificar_pagamento(orders)
                            db.atualizar_status(link["cielo_id"], status, raw, label)
                            if status == "pago":
                                novos_pagos += 1
                        except Exception:
                            erros += 1

                    if novos_pagos:
                        st.success(f"✓ {novos_pagos} novo(s) pagamento(s) confirmado(s)!")
                    else:
                        st.info(f"Verificados {len(nao_pagos)} links — nenhum pago ainda.")
                    if erros:
                        st.warning(f"⚠️ {erros} link(s) falharam na consulta.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    try:
        pagos = db.listar_por_status("pago")
        pagos_liberados = db.listar_por_status("pago_liberado")
        nao_pagos = db.listar_por_status("nao_pago")
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        st.info(
            "Verifique se a planilha do Google Sheets está configurada. "
            "Veja o README.md para instruções."
        )
        st.stop()

    # ─── Seção: Pagos (aguardando liberação no ERP) ──────────────────────
    st.markdown(
        f'<h4 style="color:{AZUL_ESC};margin-top:16px;">'
        f'Pagos — aguardando liberação no ERP {card_status(str(len(pagos)), "pago")}</h4>',
        unsafe_allow_html=True
    )

    if pagos:
        for link in pagos:
            _render_item_historico(link, categoria="pago")
    else:
        st.info("Nenhum pagamento aguardando liberação.")

    # ─── Seção: Pago e liberado no ERP ───────────────────────────────────
    st.markdown(
        f'<h4 style="color:{AZUL_ESC};margin-top:24px;">'
        f'Pago e liberado no ERP {card_status(str(len(pagos_liberados)), "liberado")}</h4>',
        unsafe_allow_html=True
    )

    if pagos_liberados:
        for link in pagos_liberados:
            _render_item_historico(link, categoria="pago_liberado")
    else:
        st.info("Nenhum link liberado ainda.")

    # ─── Seção: Não pagos / Não autorizados ──────────────────────────────
    st.markdown(
        f'<h4 style="color:{AZUL_ESC};margin-top:24px;">'
        f'Não pagos / Não autorizados {card_status(str(len(nao_pagos)), "pendente")}</h4>',
        unsafe_allow_html=True
    )

    if nao_pagos:
        for link in nao_pagos:
            _render_item_historico(link, categoria="nao_pago")
    else:
        st.info("Nenhum link pendente.")
