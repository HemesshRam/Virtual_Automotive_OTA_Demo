import unittest

from common.logical_addresses import TESTER_ADDRESS
from transport.doip.library_client import LibraryDoIPClient


class DiagnosticMessage:
    source_address = 0x1001
    target_address = TESTER_ADDRESS
    user_data = bytes.fromhex("5002")


class FakePythonDoIPClient:
    class TransportType:
        TRANSPORT_TCP = object()

    def __init__(self):
        self.timeouts = []
        self._client_logical_address = TESTER_ADDRESS

    def read_doip(self, timeout=None, transport=None):
        self.timeouts.append(timeout)
        return DiagnosticMessage()


class DoIPLibraryClientTimeoutTest(unittest.TestCase):

    def test_default_receive_uses_numeric_timeout_for_python_doipclient(self):
        client = LibraryDoIPClient()
        client.using_library = True
        client.client = FakePythonDoIPClient()
        client._active_target_address = 0x1001

        payload = client._receive_raw_diagnostic()

        self.assertEqual(payload, bytes.fromhex("5002"))
        self.assertIsInstance(client.client.timeouts[0], float)
        self.assertGreater(client.client.timeouts[0], 0)


if __name__ == "__main__":
    unittest.main()
