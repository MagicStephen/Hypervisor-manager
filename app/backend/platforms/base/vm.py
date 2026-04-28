from abc import ABC, abstractmethod
from config import LOG_ROOT, BACKUP_ROOT

class BaseVmApi(ABC):

    @abstractmethod
    def create_vm(self, node_id: str, opt_params: dict) -> dict:
        pass

    @abstractmethod
    def destroy_vm(self, node_id: str, vm_id: str):
        pass
    
    @abstractmethod
    def get_vm_status(self, node_id: str, vm_id: str, params: list) -> dict:
        pass

    @abstractmethod
    def set_vm_status(self, node_id: str, vm_id: str, status: str):
        pass

    @abstractmethod
    def manage_vm_snapshots(self, node_id: str, vm_id: str, snap_parameters: dict | None = None):
        pass

    @abstractmethod
    def drop_vm_snapshot(self, node_id: str, vm_id: str, snap_name: str):
        pass

    @abstractmethod
    def rollback_vm_snapshot(self, node_id: str, vm_id: str, snap_name: str):
        pass

    @abstractmethod
    def get_vm_config(self, node_id: str, vm_id: str) -> dict:
        pass

    @abstractmethod
    def set_vm_config(self, node_id: str, vm_id: str, config_params: dict):
        pass
    
    @abstractmethod
    def get_vm_backups(self, node_id: str, vm_id: str):
        pass

    @abstractmethod
    def create_vm_backup(self, node_id: str, vm_id: str, backup_params: dict):
        pass

    @abstractmethod
    def get_vm_logs(self, node_id: str, vm_id: str, line_limit: int):
        pass

    @abstractmethod
    def open_console(self, node_id: str, vm_id: str, protocol: str = "vnc"):
        pass
    
    
    def _get_fs_vm_backups(self, vm_id: str, platform_name: str):
        from pathlib import Path

        backup_dir = Path(BACKUP_ROOT) / platform_name / str(vm_id)

        if not backup_dir.exists() or not backup_dir.is_dir():
            return []

        backups = []

        for file in backup_dir.iterdir():
            if not file.is_file():
                continue

            stat = file.stat()

            backups.append({
                "id": file.name,
                "name": file.name,
                "filename": file.name,
                "size": stat.st_size,
                "ctime": int(stat.st_mtime),
                "storage": "nfs-backups",
                "content": "backup",
                "subtype": "vm",
                "platform": platform_name,
                "source": "nfs",
            })

        backups.sort(key=lambda x: x["ctime"], reverse=True)
        return backups