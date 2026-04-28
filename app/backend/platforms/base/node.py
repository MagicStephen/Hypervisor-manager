from abc import ABC, abstractmethod

class BaseNodeApi(ABC):

    @abstractmethod
    def get_node_status(self, node_id: str) -> dict:
        pass

    @abstractmethod
    def get_node_time_metrics(self, node_id: str, interval: str = "hour", cf: str = "AVERAGE", metrics: list | None = None) -> dict:
        pass

    @abstractmethod
    def get_node_storage(self, node_id: str) -> dict:
        pass
    
    @abstractmethod
    def get_node_networks(self, node: str):
        pass

    @abstractmethod
    def get_task_status(self, node: str, task_id: str) -> dict:
        pass

    @abstractmethod
    def get_node_storage_content(self, node_id: str, storage_id: str) -> dict:
        pass
    
    @abstractmethod
    def upload_node_storage_file(self, node_id: str, storage_id: str, content_type: str, file: str) -> dict:
        pass
    
    @abstractmethod
    def delete_node_storage_content(self, node_id: str, storage_id: str, vol_id: str) -> dict:
        pass
    
    @abstractmethod
    def get_node_logs(self, node_id: str, limit: int = 100) -> dict:
        pass