import requests
from typing import Any
from platforms.base.connection import BaseConnection


class ProxmoxConnection(BaseConnection):
    """
    Zajišťuje autentizaci vůči Proxmox API a správu session/tokenů.
    """

    def __init__(self, host: str, port: str):
        """
        Inicializuje připojení k Proxmox API.

        Args:
            host: IP adresa.
            port: Port Proxmox API.

        Attributes:
            host (str): Kombinace host:port.
            ip (str): Původní IP adresa serveru.
            port (str): Port API.
            ticket (str | None): Autentizační ticket.
            csrf_token (str | None): CSRF token pro API.
            headers (dict | None): HTTP hlavičky pro requesty.
        """
        self.host = host + ":" + port
        self.ip = host
        self.port = port

        self.ticket = None
        self.csrf_token = None
        self.headers = None

    def session_connect(self, username: str, password: str) -> dict:
        """
        Přihlásí se do Proxmox API a uloží autentizační tokeny.

        Args:
            username: Uživatelské jméno (např. root@pam).
            password: Heslo uživatele.

        Returns:
            Odpověď z Proxmox API obsahující autentizační data.
        """
        url = f"https://{self.host}/api2/json/access/ticket"

        # Volání login endpointu
        res = self.request(
            method="POST",
            url=url,
            data={
                "username": username,
                "password": password
            }
        )

        data = res["data"]

        # Uložení session údajů
        self.ticket = data.get("ticket")
        self.csrf_token = data.get("CSRFPreventionToken")

        self.headers = {
            "CSRFPreventionToken": self.csrf_token,
            "Cookie": f"PVEAuthCookie={self.ticket}"
        }

        return res

    def request(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        params: dict | None = None,
        files: Any = None
    ) -> dict:
        """
        Provede HTTP request vůči Proxmox API.

        Args:
            method: HTTP metoda (GET, POST, PUT, DELETE).
            url: Cílová URL.
            data: Tělo requestu (form data).
            params: Query parametry.
            files: Soubory pro upload.

        Returns:
            JSON odpověď z Proxmox API.

        Raises:
            ConnectionError: Pokud selže HTTP spojení.
            ValueError: Pokud odpověď není validní JSON.
            RuntimeError: Pokud API vrátí chybový status.
        """

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                data=data,
                params=params,
                files=files,
                verify=False,
                timeout=None
            )

        except requests.exceptions.RequestException as e:
            raise ConnectionError("Connection to Proxmox failed") from e

        try:
            resp_json = response.json()

        except ValueError as e:
            raise ValueError("Invalid JSON response from Proxmox") from e

        if response.status_code != 200:
            raise RuntimeError(f"Proxmox API error: {response.text}")

        return resp_json
    
    def disconnect(self) -> None:
        """
        Ukončí session a smaže autentizační údaje.
        """
        self.ticket = None
        self.csrf_token = None
        self.headers = None
