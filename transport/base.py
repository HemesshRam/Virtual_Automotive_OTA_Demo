from abc import ABC, abstractmethod


class Transport(ABC):

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def discover_ecus(self):
        pass

    @abstractmethod
    def diagnostic_session_control(self):
        pass

    @abstractmethod
    def tester_present(self):
        pass

    @abstractmethod
    def request_seed(self):
        pass

    @abstractmethod
    def send_key(self, seed):
        pass

    @abstractmethod
    def erase_memory(self, size):
        pass

    @abstractmethod
    def request_download(self, size):
        pass

    @abstractmethod
    def transfer_data(self, sequence, payload):
        pass

    @abstractmethod
    def request_transfer_exit(self):
        pass

    @abstractmethod
    def verify_programming(self):
        pass

    @abstractmethod
    def activate_image(self):
        pass

    @abstractmethod
    def ecu_reset(self):
        pass

    @abstractmethod
    def wait_for_boot(self):
        pass

    @abstractmethod
    def send_start(self, ecu):
        pass

    @abstractmethod
    def send_chunk(self, ecu, sequence, data):
        pass

    @abstractmethod
    def send_end(self, ecu):
        pass

    @abstractmethod
    def health_check(self, ecu):
        pass

    @abstractmethod
    def get_version(self, ecu):
        pass

    @abstractmethod
    def shutdown(self):
        pass
