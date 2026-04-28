from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import ssl


class EsxiConnection:
    """
    Zajišťuje připojení k VMware ESXi / vSphere API pomocí pyVmomi.

    Třída spravuje session (ServiceInstance) a poskytuje pomocné metody
    pro vyhledávání objektů v inventory.
    """

    def __init__(self, host: str):
        """
        Inicializuje připojení k ESXi/vSphere.

        Args:
            host: IP adresa nebo hostname ESXi/vCenter serveru.

        Attributes:
            host (str): Adresa serveru.
            si: ServiceInstance objekt (hlavní session).
            content: vSphere content tree (inventory root).
        """
        self.host = host
        self.si = None
        self.content = None

    def session_connect(self, username: str, password: str) -> dict:
        """
        Naváže session k vSphere API.

        Používá `SmartConnect` z pyVmomi a vytvoří `ServiceInstance`,
        přes který se následně přistupuje k celé infrastruktuře.

        Args:
            username: Uživatelské jméno (např. root nebo administrator@vsphere.local).
            password: Heslo uživatele.

        Returns:
            None (session je uložena do atributů instance).

        Raises:
            PermissionError: Pokud jsou přihlašovací údaje neplatné.
            ConnectionError: Pokud se nepodaří navázat spojení.
        """
        try:
            context = ssl._create_unverified_context()
            self.si = SmartConnect(
                host=self.host,
                user=username,
                pwd=password,
                sslContext=context
            )
            self.content = self.si.RetrieveContent()

        except vim.fault.InvalidLogin as e:
            raise PermissionError("Invalid vSphere login credentials") from e
        except Exception as e:
            raise ConnectionError("Failed to connect to vSphere") from e

    def get_container_view(self, vim_types, recursive: bool = True):
        """
        Vytvoří container view pro iteraci přes objekty daného typu.

        Args:
            vim_types: Seznam typů (např. [vim.VirtualMachine]).
            recursive: Zda procházet i podstromy.

        Yields:
            Objekty odpovídající zadaným typům.
        """
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            vim_types,
            recursive
        )

        try:
            for obj in container.view:
                yield obj
        finally:
            container.Destroy()

    def get_entity_by_moid(self, moid: str, entity_type):
        """
        Vyhledá objekt podle Managed Object ID (moid).

        Args:
            moid: Interní identifikátor objektu (např. vm-123).
            entity_type: Typ objektu (např. vim.VirtualMachine).

        Returns:
            Nalezený objekt nebo None.
        """
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            [entity_type],
            True
        )

        try:
            for obj in container.view:
                if getattr(obj, "_moId", None) == moid:
                    return obj
        finally:
            container.Destroy()

        return None

    def get_entity_by_name(self, name: str, entity_type):
        """
        Vyhledá objekt podle názvu.

        Args:
            name: Název objektu.
            entity_type: Typ objektu (např. vim.VirtualMachine).

        Returns:
            Nalezený objekt nebo None.
        """
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            [entity_type],
            True
        )

        try:
            for obj in container.view:
                if getattr(obj, "name", None) == name:
                    return obj
        finally:
            container.Destroy()

        return None

    def disconnect(self):
        """
        Ukončí session k vSphere API.

        Odpojí ServiceInstance a vyčistí interní stav.
        """
        if self.si:
            Disconnect(self.si)
            self.si = None
            self.content = None