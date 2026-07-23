from abc import ABC, abstractmethod

class INotification(ABC):
    """
    Base interface for all notifications in the application.
    """
    @abstractmethod
    def send(self, message: str = None, **kwargs) -> bool:
        pass
