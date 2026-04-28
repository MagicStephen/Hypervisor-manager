from abc import ABC, abstractmethod

class BaseClusterApi(ABC):

    @abstractmethod
    def get_cluster_topology(self) -> dict:
        pass
