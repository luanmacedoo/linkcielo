"""
utils/cielo_client.py — Cliente da API Cielo para Link de Pagamento.
Gerencia OAuth2, criação de link e consulta de status de pagamentos.
"""
import base64
import time

import requests

CIELO_API_BASE = "https://cieloecommerce.cielo.com.br/api/public"
TOKEN_ENDPOINT = f"{CIELO_API_BASE}/v2/token"
PRODUCTS_ENDPOINT = f"{CIELO_API_BASE}/v1/products/"

TOKEN_SAFETY_MARGIN_SECONDS = 60

# Status da Cielo retornados como string na API /payments
CIELO_STATUS_PAGO = {"Authorized", "PaymentConfirmed"}
CIELO_STATUS_LABEL_PT = {
    "NotFinished": "Não finalizada",
    "Authorized": "Autorizada",
    "PaymentConfirmed": "Pagamento confirmado",
    "Denied": "Negada",
    "Voided": "Cancelada",
    "Refunded": "Estornada",
    "Pending": "Pendente",
    "Aborted": "Abortada",
    "Scheduled": "Agendada",
}


class CieloError(Exception):
    """Erro genérico ao chamar a API Cielo."""
    pass


class CieloClient:
    def __init__(self, client_id: str, client_secret: str):
        if not client_id or not client_secret:
            raise ValueError(
                "ClientID e ClientSecret são obrigatórios. "
                "Configure-os em st.secrets ou variáveis de ambiente."
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def _build_basic_auth_header(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        return f"Basic {encoded}"

    def _token_is_valid(self) -> bool:
        return (
            self._access_token is not None
            and time.time() < self._token_expires_at - TOKEN_SAFETY_MARGIN_SECONDS
        )

    def _fetch_new_token(self) -> None:
        headers = {
            "Authorization": self._build_basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        try:
            response = requests.post(TOKEN_ENDPOINT, headers=headers, timeout=30)
        except requests.RequestException as e:
            raise CieloError(f"Falha de conexão ao gerar token: {e}")

        if response.status_code not in (200, 201):
            raise CieloError(
                f"Falha ao gerar token (HTTP {response.status_code}): {response.text}"
            )

        data = response.json()
        self._access_token = data.get("access_token")
        try:
            expires_in = int(data.get("expires_in", 1200))
        except (ValueError, TypeError):
            expires_in = 1200
        self._token_expires_at = time.time() + expires_in

        if not self._access_token:
            raise CieloError("Resposta de token sem campo access_token.")

    def get_access_token(self) -> str:
        if not self._token_is_valid():
            self._fetch_new_token()
        return self._access_token  # type: ignore[return-value]

    def create_payment_link(
        self,
        name: str,
        price_cents: int,
        product_type: str = "Payment",
        max_installments: int | None = None,
    ) -> dict:
        """Cria um link de pagamento na Cielo."""
        if not name or not name.strip():
            raise ValueError("Descrição do pedido é obrigatória.")
        if len(name) > 128:
            raise ValueError("Descrição não pode passar de 128 caracteres.")
        if price_cents <= 0:
            raise ValueError("Valor deve ser maior que zero.")
        if max_installments is not None and not 1 <= max_installments <= 18:
            raise ValueError("Número de parcelas deve ser entre 1 e 18.")

        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {
            "type": product_type,
            "name": name.strip(),
            "price": price_cents,
            # Alguns ECs exigem 'shipping' mesmo em links sem entrega física
            "shipping": {"type": "WithoutShipping"},
        }
        if max_installments is not None:
            body["maxNumberOfInstallments"] = max_installments

        try:
            response = requests.post(
                PRODUCTS_ENDPOINT, headers=headers, json=body, timeout=30
            )
        except requests.RequestException as e:
            raise CieloError(f"Falha de conexão ao criar link: {e}")

        if response.status_code not in (200, 201):
            raise CieloError(
                f"Falha ao criar link (HTTP {response.status_code}): {response.text}"
            )

        return response.json()

    def get_link_payments(self, link_id: str) -> list[dict]:
        """Consulta as transações de um link de pagamento."""
        if not link_id:
            raise ValueError("ID do link é obrigatório.")

        token = self.get_access_token()
        url = f"{PRODUCTS_ENDPOINT}{link_id}/payments"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as e:
            raise CieloError(f"Falha de conexão ao consultar transações: {e}")

        if response.status_code == 404 or not response.text.strip():
            return []
        if response.status_code not in (200, 201):
            raise CieloError(
                f"Falha ao consultar transações (HTTP {response.status_code}): {response.text}"
            )

        try:
            data = response.json()
        except ValueError:
            return []

        if isinstance(data, dict):
            orders = data.get("orders") or data.get("Orders") or []
            if isinstance(orders, list):
                return orders
        return []


def classificar_pagamento(
    orders: list[dict],
) -> tuple[str, str | None, str | None, int | None]:
    """
    Analisa lista de orders e retorna:
        (status_simples, status_raw, label_pt, parcelas_efetivas)

    parcelas_efetivas: número de vezes que o cliente escolheu parcelar
                       (retorno da Cielo no campo `installments`).
                       Retorna None se não houver info ou se não foi pago.
    """
    if not orders:
        return ("nao_pago", None, None, None)

    melhor_status: str | None = None
    foi_pago = False
    parcelas_efetivas: int | None = None

    for order in orders:
        payment = order.get("payment") or order.get("Payment") or {}
        status_str = payment.get("status") or payment.get("Status")
        if not status_str:
            continue

        if status_str in CIELO_STATUS_PAGO:
            foi_pago = True
            melhor_status = status_str
            # Extrai o número de parcelas efetivo. A Cielo retorna como
            # 'installments' (camelCase) ou 'Installments' (PascalCase).
            raw_installments = payment.get("installments") or payment.get("Installments")
            if raw_installments is not None:
                try:
                    parcelas_efetivas = int(raw_installments)
                except (ValueError, TypeError):
                    parcelas_efetivas = None
            break

        if melhor_status is None:
            melhor_status = status_str

    label = CIELO_STATUS_LABEL_PT.get(melhor_status) if melhor_status else None
    return (
        "pago" if foi_pago else "nao_pago",
        melhor_status,
        label,
        parcelas_efetivas,
    )
