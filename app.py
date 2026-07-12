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

    /* Inputs de texto */
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #1a1a1a !important;
        border: 1px solid #dde3ef !important;
    }
    .stTextInput label, .stSelectbox label, .stRadio label {
        color: #1a1a1a !important;
    }

    /* SELECTBOX (dropdown) - todos os estados */
    .stSelectbox > div > div {
        background-color: #FFFFFF !important;
        color: #1a1a1a !important;
        border: 1px solid #dde3ef !important;
    }
    .stSelectbox [data-baseweb="select"] {
        background-color: #FFFFFF !important;
    }
    .stSelectbox [data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #1a1a1a !important;
    }
    /* Lista de opções do dropdown (popup quando abre) */
    [data-baseweb="popover"] {
        background-color: #FFFFFF !important;
    }
    [data-baseweb="popover"] ul {
        background-color: #FFFFFF !important;
    }
    [data-baseweb="popover"] li {
        background-color: #FFFFFF !important;
        color: #1a1a1a !important;
    }
    [data-baseweb="popover"] li:hover {
        background-color: #f4f7fc !important;
    }
    [role="listbox"] {
        background-color: #FFFFFF !important;
    }
    [role="option"] {
        background-color: #FFFFFF !important;
        color: #1a1a1a !important;
    }
    [role="option"]:hover {
        background-color: #f4f7fc !important;
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

    /* TODOS os botões: fundo claro com texto escuro (default secundário) */
    .stButton button {
        background-color: #FFFFFF !important;
        color: #041747 !important;
        border: 1px solid #dde3ef !important;
    }
    .stButton button:hover {
        background-color: #f4f7fc !important;
        border-color: #041747 !important;
        color: #041747 !important;
    }
    /* Texto dentro do botão secundário */
    .stButton button p,
    .stButton button span,
    .stButton button div {
        color: #041747 !important;
    }

    /* Botão PRIMÁRIO: azul escuro com texto branco */
    .stButton button[kind="primary"] {
        background-color: #041747 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #007FE0 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    /* Texto dentro do botão primário deve ser branco */
    .stButton button[kind="primary"] p,
    .stButton button[kind="primary"] span,
    .stButton button[kind="primary"] div {
        color: #FFFFFF !important;
    }

    /* Botão de submit do form (Gerar Link) - tratado como primário */
    [data-testid="stFormSubmitButton"] button {
        background-color: #041747 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    [data-testid="stFormSubmitButton"] button:hover {
        background-color: #007FE0 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stFormSubmitButton"] button p,
    [data-testid="stFormSubmitButton"] button span,
    [data-testid="stFormSubmitButton"] button div {
        color: #FFFFFF !important;
    }

    /* Link buttons */
    .stLinkButton a {
        background-color: #041747 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stLinkButton a:hover {
        background-color: #007FE0 !important;
        color: #FFFFFF !important;
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

    /* Alertas (success, info, error, warning) - força fundo claro com texto legível */
    [data-testid="stAlert"] {
        background-color: #f4f7fc !important;
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
    """Formata string ISO em '18/05/2026' (só a data, sem hora)."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        # Fallback: pega só os primeiros 10 caracteres se for um ISO simples
        # (ex: '2026-05-18' do começo de '2026-05-18T17:50:00')
        clean = iso_str.replace("T", " ").strip()
        if len(clean) >= 10:
            try:
                ano, mes, dia = clean[:10].split("-")
                return f"{dia}/{mes}/{ano}"
            except ValueError:
                pass
        return clean


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
                f"· {formatar_data(link['criado_em'])}"
            )
            if link.get("short_url"):
                st.markdown(f"`{link['short_url']}`")

            # Linha de status conforme categoria
            parcelas_efetivas = link.get("parcelas_efetivas")
            sufixo_parcelas = f" · {parcelas_efetivas}x" if parcelas_efetivas else ""

            if categoria == "pago_liberado":
                texto = "✓ Pago · 🔓 Liberado"
                if link.get("liberado_por"):
                    texto += f" por {link['liberado_por']}"
                texto += sufixo_parcelas
                st.caption(texto)
            elif categoria == "pago":
                texto = "✓ Pagamento confirmado"
                if link.get("ultimo_status_label"):
                    texto = f"✓ {link['ultimo_status_label']}"
                texto += sufixo_parcelas
                st.caption(texto)
            elif link.get("ultima_verificacao"):
                texto_status = link.get("ultimo_status_label") or "Sem tentativas de pagamento"
                st.caption(texto_status)

            # ─── AVISO PERMANENTE de divergência de parcelas ─────────────
            # Aparece sempre no card (não só após clique) quando o link
            # está pago-não-liberado e há divergência entre configurado e
            # efetivo, ou quando não temos info do parcelamento.
            if categoria == "pago":
                parcelas_max_v = link.get("parcelas_max") or 1
                parcelas_ef_v = link.get("parcelas_efetivas")

                if parcelas_ef_v is None:
                    # Sem info do parcelamento efetivo (link antigo)
                    st.markdown(
                        f'<div style="background:#fff8e1;border:1px solid {AMARELO};'
                        f'border-radius:6px;padding:8px 10px;margin-top:8px;'
                        f'font-size:12px;color:#856404;">'
                        f'⚠️ <strong>Sem info do parcelamento efetivo.</strong> '
                        f'Clique em "Reconsultar" pra buscar essa informação antes de liberar.'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                elif parcelas_ef_v != parcelas_max_v:
                    # Divergência entre configurado e efetivo
                    if parcelas_ef_v == 1:
                        efetivo_txt = "à vista (1x)"
                    else:
                        efetivo_txt = f"em <strong>{parcelas_ef_v}x</strong>"
                    if parcelas_max_v == 1:
                        esperado_txt = "à vista (1x)"
                    else:
                        esperado_txt = f"até <strong>{parcelas_max_v}x</strong>"

                    st.markdown(
                        f'<div style="background:#fff3cd;border:1px solid #ff9800;'
                        f'border-radius:6px;padding:8px 10px;margin-top:8px;'
                        f'font-size:12px;color:#b45309;">'
                        f'⚠️ <strong>Parcelamento diferente do configurado.</strong> '
                        f'Você configurou {esperado_txt}, mas o cliente pagou {efetivo_txt}. '
                        f'Registre o parcelamento correto no ERP.'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        with col_acao:
            # NÃO PAGO: botões "Atualizar" e "Copiar URL"
            if categoria == "nao_pago":
                if st.button("Atualizar", key=f"btn_{link['cielo_id']}", use_container_width=True):
                    with st.spinner("Consultando..."):
                        try:
                            cielo = get_cielo()
                            orders = cielo.get_link_payments(link["cielo_id"])
                            status, raw, lbl, parcelas = classificar_pagamento(orders)
                            db.atualizar_status(link["cielo_id"], status, raw, lbl, parcelas)
                            if status == "pago":
                                msg = f"✓ PAGO ({lbl})"
                                if parcelas:
                                    msg += f" · {parcelas}x"
                                st.success(msg)
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
                # Chave de session_state pra rastrear se está aguardando confirmação
                confirmar_key = f"confirmar_lib_{link['cielo_id']}"
                aguardando_confirmacao = st.session_state.get(confirmar_key, False)

                # Determina se precisa de confirmação:
                # - Sem info de parcelas_efetivas → precisa confirmar (link antigo)
                # - parcelas_efetivas != parcelas_max → precisa confirmar (divergência)
                # - parcelas_efetivas == parcelas_max → NÃO precisa (deu como esperado)
                parcelas_max = link.get("parcelas_max") or 1
                parcelas_ef = link.get("parcelas_efetivas")
                precisa_confirmar = (
                    parcelas_ef is None or parcelas_ef != parcelas_max
                )

                if not aguardando_confirmacao:
                    # Primeiro clique
                    if st.button(
                        "🔓 Marcar como liberado",
                        key=f"lib_{link['cielo_id']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        if precisa_confirmar:
                            # Precisa de confirmação: entra em modo aguardando
                            st.session_state[confirmar_key] = True
                            st.rerun()
                        else:
                            # Parcelas batem: libera direto, sem confirmação
                            try:
                                db.marcar_liberado(link["cielo_id"])
                                st.success("✓ Marcado como liberado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")
                else:
                    # Aguardando confirmação: mostra dois botões
                    if st.button(
                        "✓ Confirmar",
                        key=f"conf_{link['cielo_id']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        try:
                            db.marcar_liberado(link["cielo_id"])
                            st.session_state[confirmar_key] = False
                            st.success("✓ Marcado como liberado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

                    if st.button(
                        "✕ Cancelar",
                        key=f"canc_{link['cielo_id']}",
                        use_container_width=True,
                    ):
                        st.session_state[confirmar_key] = False
                        st.rerun()

                if st.button("Reconsultar", key=f"btn_{link['cielo_id']}", use_container_width=True):
                    with st.spinner("Consultando..."):
                        try:
                            cielo = get_cielo()
                            orders = cielo.get_link_payments(link["cielo_id"])
                            status, raw, lbl, parcelas = classificar_pagamento(orders)
                            db.atualizar_status(link["cielo_id"], status, raw, lbl, parcelas)
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
    col_titulo, col_recarregar, col_acao = st.columns([3, 1, 1])
    with col_titulo:
        st.markdown("### Histórico de links")
    with col_recarregar:
        if st.button("♻️ Recarregar", use_container_width=True,
                     help="Atualiza a lista lendo a planilha novamente"):
            db.forcar_atualizacao()
            st.rerun()
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
                            status, raw, label, parcelas = classificar_pagamento(orders)
                            db.atualizar_status(link["cielo_id"], status, raw, label, parcelas)
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

    # Quantidade inicial mostrada de cada categoria (paginação)
    QTD_INICIAL = 5

    def _render_secao(titulo: str, badge_tipo: str, links: list, categoria: str,
                      msg_vazia: str, chave_paginacao: str):
        """Renderiza uma seção do histórico com paginação 'Ver mais'."""
        st.markdown(
            f'<h4 style="color:{AZUL_ESC};margin-top:24px;">'
            f'{titulo} {card_status(str(len(links)), badge_tipo)}</h4>',
            unsafe_allow_html=True
        )

        if not links:
            st.info(msg_vazia)
            return

        # Quantos mostrar nesta categoria (default = QTD_INICIAL)
        qtd_mostrar = st.session_state.get(chave_paginacao, QTD_INICIAL)
        visiveis = links[:qtd_mostrar]
        restantes = len(links) - qtd_mostrar

        for link in visiveis:
            _render_item_historico(link, categoria=categoria)

        # Botões "Ver mais" e "Mostrar menos"
        if restantes > 0 or qtd_mostrar > QTD_INICIAL:
            col_a, col_b, _ = st.columns([1, 1, 2])
            if restantes > 0:
                with col_a:
                    if st.button(
                        f"Ver mais ({restantes})",
                        key=f"more_{chave_paginacao}",
                        use_container_width=True,
                    ):
                        st.session_state[chave_paginacao] = qtd_mostrar + QTD_INICIAL
                        st.rerun()
            if qtd_mostrar > QTD_INICIAL:
                with col_b:
                    if st.button(
                        "Mostrar menos",
                        key=f"less_{chave_paginacao}",
                        use_container_width=True,
                    ):
                        st.session_state[chave_paginacao] = QTD_INICIAL
                        st.rerun()

    # ─── Seção: Pagos (aguardando liberação no ERP) ──────────────────────
    _render_secao(
        titulo="Pagos — aguardando liberação no ERP",
        badge_tipo="pago",
        links=pagos,
        categoria="pago",
        msg_vazia="Nenhum pagamento aguardando liberação.",
        chave_paginacao="qtd_pagos",
    )

    # ─── Seção: Pago e liberado no ERP ───────────────────────────────────
    _render_secao(
        titulo="Pago e liberado no ERP",
        badge_tipo="liberado",
        links=pagos_liberados,
        categoria="pago_liberado",
        msg_vazia="Nenhum link liberado ainda.",
        chave_paginacao="qtd_liberados",
    )

    # ─── Seção: Não pagos / Não autorizados ──────────────────────────────
    _render_secao(
        titulo="Não pagos / Não autorizados",
        badge_tipo="pendente",
        links=nao_pagos,
        categoria="nao_pago",
        msg_vazia="Nenhum link pendente.",
        chave_paginacao="qtd_nao_pagos",
    )
