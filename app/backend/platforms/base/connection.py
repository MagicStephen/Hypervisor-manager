from abc import ABC, abstractmethod

class BaseConnection(ABC):

    @abstractmethod
    def session_connect(self, username: str, password: str):
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass