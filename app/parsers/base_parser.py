from abc import ABC, abstractmethod

class BaseParser(ABC):
    @abstractmethod
    def search(self, filters: dict):
        raise NotImplementedError

    def parse_card(self, card):
        raise NotImplementedError
