import os
import unittest

from transport.doip.library_client import LibraryDoIPClient
from transport.uds.codec import (
    build_transfer_data,
    parse_request_download_max_block_length,
)


class DoIPTransferChunkLimitTest(unittest.TestCase):

    def test_default_transfer_chunk_uses_stable_gateway_programming_size(self):
        client = LibraryDoIPClient()

        self.assertEqual(client.max_transfer_payload, 8192)

        payload = build_transfer_data(1, b"A" * client.max_transfer_payload)
        self.assertEqual(len(payload), 8194)

    def test_env_override_is_capped_to_gateway_isotp_limit(self):
        original = os.environ.get("OTA_DOIP_TRANSFER_CHUNK_SIZE")
        os.environ["OTA_DOIP_TRANSFER_CHUNK_SIZE"] = "65535"
        try:
            client = LibraryDoIPClient()
            self.assertEqual(client.max_transfer_payload, 16384)
        finally:
            if original is None:
                os.environ.pop("OTA_DOIP_TRANSFER_CHUNK_SIZE", None)
            else:
                os.environ["OTA_DOIP_TRANSFER_CHUNK_SIZE"] = original

    def test_request_download_response_parser_reads_demo_block_length(self):
        payload = bytes([0x74, 0x00, 0x44, 0x20, 0x00])
        self.assertEqual(parse_request_download_max_block_length(payload), 8192)


if __name__ == "__main__":
    unittest.main()
