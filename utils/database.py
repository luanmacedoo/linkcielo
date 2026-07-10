"""
utils/database.py — Persistência no Google Sheets via gspread, com cache.

Estrutura da planilha (primeira aba, header na linha 1):
    cielo_id | descricao | valor_centavos | valor_exibicao | parcelas_max |
    short_url | criado_em | status | ultima_verificacao | ultimo_status_raw |
    ultimo_status_label | criado_por | liberado_em | liberado_por

Cache:
- `_carregar_todos_com_cache()` é cacheado por 30s (@st.cache_data)
- Qualquer escrita (salvar, atualizar, liberar) invalida o cache automaticamente
- `forcar_atualizacao()` permite invalidação manual (ex: botão "Atualizar")
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Fuso horário de Brasília (UTC-3) — usa offset fixo para não depender de tzdata
FUSO_BRASILIA = timezone(timedelta(hours=-3))

# Tempo de vida do cache em segundos.
# 30s reduz drasticamente as chamadas à API do Sheets, mantendo o histórico
# razoavelmente atualizado. Depois de escrita, o cache é invalidado
# automaticamente, então dados novos aparecem imediatamente.
CACHE_TTL_SEGUNDOS = 30


def agora_brasilia() -> str:
    """Retorna o horário atual no fuso de Brasília, em formato ISO."""
    return datetime.now(FUSO_BRASILIA).isoformat(timespec="seconds")


CABECALHO = [
    "cielo_id",
    "descricao",
    "valor_centavos",
    "valor_exibicao",
    "parcelas_max",
    "short_url",
    "criado_em",
    "status",
    "ultima_verificacao",
    "ultimo_status_raw",
    "ultimo_status_label",
    "criado_por",
    "liberado_em",
    "liberado_por",
    "parcelas_efetivas",  # Coluna O — nº de vezes que cliente parcelou (vindo da Cielo)
]


@st.cache_resource
def _get_worksheet() -> gspread.Worksheet:
    """Retorna a primeira aba da planilha (cacheado pra não autenticar a cada interação)."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    cliente = gspread.authorize(creds)
    planilha = cliente.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
    aba = planilha.sheet1

    valores = aba.get_all_values()
    if not valores or valores[0] != CABECALHO:
        if not valores:
            aba.append_row(CABECALHO)
        elif valores[0] != CABECALHO:
            aba.update("A1", [CABECALHO])

    return aba


def _linha_para_dict(linha: list, valores_indices: dict) -> dict:
    """Converte uma linha (list) em dict usando os índices das colunas."""
    def get_col(nome: str, default=""):
        idx = valores_indices.get(nome)
        if idx is None or idx >= len(linha):
            return default
        return linha[idx]

    valor_str = get_col("valor_centavos", "0")
    try:
        valor_int = int(valor_str) if valor_str else 0
    except ValueError:
        valor_int = 0

    parcelas_str = get_col("parcelas_max", "1")
    try:
        parcelas_int = int(parcelas_str) if parcelas_str else 1
    except ValueError:
        parcelas_int = 1

    # Parcelas efetivas: pode ser vazio (link antigo ou não pago ainda)
    parcelas_efetivas_str = get_col("parcelas_efetivas", "")
    parcelas_efetivas: Optional[int]
    if parcelas_efetivas_str:
        try:
            parcelas_efetivas = int(parcelas_efetivas_str)
        except ValueError:
            parcelas_efetivas = None
    else:
        parcelas_efetivas = None

    return {
        "cielo_id": get_col("cielo_id"),
        "descricao": get_col("descricao"),
        "valor_centavos": valor_int,
        "valor_exibicao": get_col("valor_exibicao"),
        "parcelas_max": parcelas_int,
        "short_url": get_col("short_url"),
        "criado_em": get_col("criado_em"),
        "status": get_col("status", "nao_pago"),
        "ultima_verificacao": get_col("ultima_verificacao"),
        "ultimo_status_raw": get_col("ultimo_status_raw"),
        "ultimo_status_label": get_col("ultimo_status_label"),
        "criado_por": get_col("criado_por"),
        "liberado_em": get_col("liberado_em"),
        "liberado_por": get_col("liberado_por"),
        "parcelas_efetivas": parcelas_efetivas,
    }


# ─── LEITURA COM CACHE ───────────────────────────────────────────────────────
# @st.cache_data cacheia o resultado por CACHE_TTL_SEGUNDOS.
# Quando o cache expira ou é invalidado, faz nova leitura da planilha.

@st.cache_data(ttl=CACHE_TTL_SEGUNDOS, show_spinner=False)
def _carregar_todos_com_cache() -> list[dict]:
    """Lê toda a planilha e retorna lista de dicts, CACHEADO por 30s."""
    aba = _get_worksheet()
    valores = aba.get_all_values()

    if not valores or len(valores) < 1:
        return []

    cabecalho = valores[0]
    indices = {nome: i for i, nome in enumerate(cabecalho)}
    linhas = valores[1:]

    return [_linha_para_dict(linha, indices) for linha in linhas if any(linha)]


def _invalidar_cache() -> None:
    """
    Invalida o cache de leitura. Chamado automaticamente após qualquer escrita
    pra garantir que a próxima leitura pegue dados atualizados.
    """
    _carregar_todos_com_cache.clear()


def forcar_atualizacao() -> None:
    """
    Função pública pra forçar atualização do histórico (usar em botão 'Atualizar').
    """
    _invalidar_cache()


# ─── OPERAÇÕES ────────────────────────────────────────────────────────────────

def _encontrar_linha_via_cache(cielo_id: str) -> Optional[int]:
    """
    Retorna o número da linha (1-indexed) do cielo_id, usando o cache.

    Vantagem: não faz chamada extra ao Sheets (aba.find()). Aproveita os
    dados já cacheados.
    """
    todos = _carregar_todos_com_cache()
    for i, item in enumerate(todos, start=2):  # start=2 porque linha 1 = header
        if item.get("cielo_id") == cielo_id:
            return i
    return None


def salvar_link(
    cielo_id: str,
    descricao: str,
    valor_centavos: int,
    valor_exibicao: str,
    parcelas_max: int,
    short_url: Optional[str],
    criado_por: str = "",
) -> None:
    """Insere um novo link no histórico (ou atualiza se cielo_id já existir)."""
    aba = _get_worksheet()
    agora = agora_brasilia()

    nova_linha = [
        cielo_id,
        descricao,
        str(valor_centavos),
        valor_exibicao,
        str(parcelas_max),
        short_url or "",
        agora,
        "nao_pago",
        "",  # ultima_verificacao
        "",  # ultimo_status_raw
        "",  # ultimo_status_label
        criado_por,
        "",  # liberado_em
        "",  # liberado_por
        "",  # parcelas_efetivas (só preenchido quando pago)
    ]

    linha_existente = _encontrar_linha_via_cache(cielo_id)
    if linha_existente:
        aba.update(f"A{linha_existente}", [nova_linha])
    else:
        aba.append_row(nova_linha)

    _invalidar_cache()


def atualizar_status(
    cielo_id: str,
    status: str,
    status_raw: Optional[str],
    status_label: Optional[str],
    parcelas_efetivas: Optional[int] = None,
) -> None:
    """
    Atualiza colunas de status de um link específico.

    Se `parcelas_efetivas` for informado, também grava esse valor na coluna O
    (número de vezes que o cliente escolheu parcelar no ato do pagamento).
    """
    aba = _get_worksheet()
    linha = _encontrar_linha_via_cache(cielo_id)
    if not linha:
        return

    agora = agora_brasilia()
    # Colunas: H=status, I=ultima_verificacao, J=ultimo_status_raw, K=ultimo_status_label
    aba.update(
        f"H{linha}:K{linha}",
        [[status, agora, status_raw or "", status_label or ""]],
    )

    # Coluna O = parcelas_efetivas (só sobrescreve se veio valor novo)
    if parcelas_efetivas is not None:
        aba.update(f"O{linha}", [[str(parcelas_efetivas)]])

    _invalidar_cache()


def marcar_liberado(cielo_id: str, liberado_por: str = "") -> None:
    """Marca um link como liberado no ERP (muda status para 'pago_liberado')."""
    aba = _get_worksheet()
    linha = _encontrar_linha_via_cache(cielo_id)
    if not linha:
        return

    agora = agora_brasilia()
    aba.update(f"H{linha}", [["pago_liberado"]])
    aba.update(f"M{linha}:N{linha}", [[agora, liberado_por]])

    _invalidar_cache()


def desmarcar_liberado(cielo_id: str) -> None:
    """Reverte a liberação (volta status para 'pago')."""
    aba = _get_worksheet()
    linha = _encontrar_linha_via_cache(cielo_id)
    if not linha:
        return

    aba.update(f"H{linha}", [["pago"]])
    aba.update(f"M{linha}:N{linha}", [["", ""]])

    _invalidar_cache()


# ─── FUNÇÕES DE CONSULTA ─────────────────────────────────────────────────────
# Todas usam o cache. Múltiplas chamadas na mesma execução do app compartilham
# a mesma leitura, evitando estouro de cota do Sheets.

def listar_por_status(status: str) -> list[dict]:
    """Retorna links com determinado status, mais recentes primeiro."""
    todos = _carregar_todos_com_cache()
    filtrados = [d for d in todos if d.get("status") == status]
    filtrados.sort(key=lambda d: d.get("criado_em", ""), reverse=True)
    return filtrados


def listar_todos() -> list[dict]:
    """Retorna todos os links, mais recentes primeiro."""
    todos = list(_carregar_todos_com_cache())  # copia pra não mexer no cache
    todos.sort(key=lambda d: d.get("criado_em", ""), reverse=True)
    return todos


def buscar(cielo_id: str) -> Optional[dict]:
    """Busca um link pelo ID Cielo."""
    todos = _carregar_todos_com_cache()
    for d in todos:
        if d.get("cielo_id") == cielo_id:
            return d
    return None
