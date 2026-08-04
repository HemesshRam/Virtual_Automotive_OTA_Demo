import unittest

from transport.uds import codec


class UDSCodecTest(unittest.TestCase):

    def test_udsoncan_is_available_for_request_encoding(self):
        self.assertIs(codec.UDSCAN_AVAILABLE, True)

    def test_udsoncan_payloads_match_demo_protocol_expectations(self):
        self.assertEqual(codec.build_diagnostic_session_control().hex(), "1002")
        self.assertEqual(codec.build_tester_present().hex(), "3e00")
        self.assertEqual(codec.build_read_data_by_identifier().hex(), "22f188")
        self.assertEqual(codec.build_security_access_request_seed().hex(), "2701")
        self.assertEqual(
            codec.build_security_access_send_key(key=b"\x01\x02\x03\x04").hex(),
            "270201020304",
        )
        self.assertEqual(
            codec.build_routine_control_start(codec.ROUTINE_ERASE_MEMORY, b"\x00\x00\x00\x20").hex(),
            "3101ff0000000020",
        )
        self.assertEqual(
            codec.build_request_download(0x1234).hex(),
            "3400440000000000001234",
        )
        self.assertEqual(codec.build_transfer_data(1, b"abc").hex(), "3601616263")
        self.assertEqual(codec.build_request_transfer_exit().hex(), "37")
        self.assertEqual(codec.build_ecu_reset().hex(), "1101")

    def test_demo_security_key_derivation(self):
        self.assertEqual(
            codec.derive_demo_security_key(bytes.fromhex("12345678")).hex(),
            "b76e6abb",
        )


if __name__ == "__main__":
    unittest.main()
