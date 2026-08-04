import unittest

from transport.uds.client import UDSClient


class FakeTransport:

    def __init__(self):
        self.calls = []
        self.max_transfer_payload = 4
        self.current_package = {"target_version": "2.0.0"}

    def diagnostic_session_control(self):
        self.calls.append("diagnostic_session_control")
        return True

    def tester_present(self):
        self.calls.append("tester_present")
        return True

    def request_seed(self):
        self.calls.append("request_seed")
        return bytes.fromhex("12345678")

    def send_key(self, seed):
        self.calls.append(("send_key", seed.hex()))
        return True

    def erase_memory(self, size):
        self.calls.append(("erase_memory", size))
        return True

    def request_download(self, size):
        self.calls.append(("request_download", size))
        return True

    def transfer_data(self, sequence, payload):
        self.calls.append(("transfer_data", sequence, payload))
        return True

    def request_transfer_exit(self):
        self.calls.append("request_transfer_exit")
        return True

    def verify_programming(self):
        self.calls.append("verify_programming")
        return True

    def activate_image(self):
        self.calls.append("activate_image")
        return True

    def ecu_reset(self):
        self.calls.append("ecu_reset")
        return True

    def wait_for_boot(self):
        self.calls.append("wait_for_boot")
        return True

    def read_software_version(self, timeout=5.0):
        self.calls.append(("read_software_version", timeout))
        return "2.0.0"


class UDSClientFlowTest(unittest.TestCase):

    def test_programming_sequence_includes_security_and_routines(self):
        transport = FakeTransport()
        client = UDSClient(transport)

        client.flash_firmware(b"abcdefgh")

        self.assertEqual(
            transport.calls,
            [
                "diagnostic_session_control",
                "tester_present",
                "request_seed",
                ("send_key", "12345678"),
                ("erase_memory", 8),
                ("request_download", 8),
                ("transfer_data", 1, b"abcd"),
                ("transfer_data", 2, b"efgh"),
                "request_transfer_exit",
                "verify_programming",
                "activate_image",
                "ecu_reset",
                "wait_for_boot",
                ("read_software_version", 5.0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
