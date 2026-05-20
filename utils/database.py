"""
utils/database.py — Persistência no Google Sheets via gspread.

Estrutura da planilha (primeira aba, header na linha 1):
    cielo_id | descricao | valor_centavos | valor_exibicao | parcelas_max |
    short_url | criado_em | status | ultima_verificacao | ultimo_status_raw |
    ultimo_status_label | criado_por | liberado_em | liberado_por
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
]


@st.cache_resource
def _get_worksheet() -> gspread.Worksheet:
    """Retorna a primeira aba da planilha (cacheado pra não autenticar a cada interação)."""
    # As credenciais são lidas como dict do st.secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    cliente = gspread.authorize(creds)
    planilha = cliente.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
    aba = planilha.sheet1

    # Garante que o cabeçalho exista (cria se planilha estiver vazia)
    valores = aba.get_all_values()
    if not valores or valores[0] != CABECALHO:
        if not valores:
            aba.append_row(CABECALHO)
        # Se tiver dados mas cabeçalho errado, sobrescreve só a linha 1
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
    }


def _carregar_todos_como_dicts() -> tuple[list[dict], dict]:
    """
    Lê toda a planilha e retorna (lista_de_dicts, indices_colunas).
    Útil pra evitar múltiplas chamadas à API do Sheets.
    """
    aba = _get_worksheet()
    valores = aba.get_all_values()

    if not valores or len(valores) < 1:
        return [], {}

    cabecalho = valores[0]
    indices = {nome: i for i, nome in enumerate(cabecalho)}
    linhas = valores[1:]

    dicts = [_linha_para_dict(linha, indices) for linha in linhas if any(linha)]
    return dicts, indices


def _encontrar_linha(cielo_id: str) -> Optional[int]:
    """
    Retorna o número da linha (1-indexed, considerando cabeçalho na linha 1)
    onde está o cielo_id, ou None se não achar.
    """
    aba = _get_worksheet()
    try:
        # gspread procura célula pelo valor; coluna 1 = cielo_id
        cell = aba.find(cielo_id, in_column=1)
        return cell.row if cell else None
    except gspread.exceptions.CellNotFound:
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
    ]

    # Se já existir, atualiza; caso contrário, adiciona no final
    linha_existente = _encontrar_linha(cielo_id)
    if linha_existente:
        aba.update(f"A{linha_existente}", [nova_linha])
    else:
        aba.append_row(nova_linha)


def atualizar_status(
    cielo_id: str,
    status: str,
    status_raw: Optional[str],
    status_label: Optional[str],
) -> None:
    """Atualiza colunas de status de um link específico."""
    aba = _get_worksheet()
    linha = _encontrar_linha(cielo_id)
    if not linha:
        return

    agora = agora_brasilia()
    # Colunas: H=status, I=ultima_verificacao, J=ultimo_status_raw, K=ultimo_status_label
    aba.update(
        f"H{linha}:K{linha}",
        [[status, agora, status_raw or "", status_label or ""]],
    )


def marcar_liberado(cielo_id: str, liberado_por: str = "") -> None:
    """Marca um link como liberado no ERP (muda status para 'pago_liberado')."""
    aba = _get_worksheet()
    linha = _encontrar_linha(cielo_id)
    if not linha:
        return

    agora = agora_brasilia()
    # Atualiza status (coluna H) para 'pago_liberado'
    aba.update(f"H{linha}", [["pago_liberado"]])
    # Atualiza liberado_em (M) e liberado_por (N)
    aba.update(f"M{linha}:N{linha}", [[agora, liberado_por]])


def desmarcar_liberado(cielo_id: str) -> None:
    """Reverte a liberação (volta status para 'pago')."""
    aba = _get_worksheet()
    linha = _encontrar_linha(cielo_id)
    if not linha:
        return

    aba.update(f"H{linha}", [["pago"]])
    aba.update(f"M{linha}:N{linha}", [["", ""]])


def listar_por_status(status: str) -> list[dict]:
    """Retorna links com determinado status, mais recentes primeiro."""
    todos, _ = _carregar_todos_como_dicts()
    filtrados = [d for d in todos if d.get("status") == status]
    # Ordena pelos mais recentes primeiro (criado_em em ISO ordena lexicograficamente)
    filtrados.sort(key=lambda d: d.get("criado_em", ""), reverse=True)
    return filtrados


def listar_todos() -> list[dict]:
    """Retorna todos os links, mais recentes primeiro."""
    todos, _ = _carregar_todos_como_dicts()
    todos.sort(key=lambda d: d.get("criado_em", ""), reverse=True)
    return todos


def buscar(cielo_id: str) -> Optional[dict]:
    """Busca um link pelo ID Cielo."""
    todos, _ = _carregar_todos_como_dicts()
    for d in todos:
        if d.get("cielo_id") == cielo_id:
            return d
    return None
