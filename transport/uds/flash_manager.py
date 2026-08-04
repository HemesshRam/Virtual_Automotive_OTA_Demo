class FlashManager:

    # CAN FD frames can carry 64 bytes total.
    # Our VCAN path wraps firmware data in a 2-byte OTA header
    # before handing it to the frame builder, so keep payloads
    # below that limit.
    CHUNK_SIZE = 62

    def __init__(self, transport):
        self.transport = transport

    def enter_programming(self):
        if not self.transport.diagnostic_session_control():
            raise RuntimeError("Failed to enter programming session")

        self.transport.tester_present()
        seed = self.transport.request_seed()
        if not seed:
            raise RuntimeError("SecurityAccess seed request failed")

        if not self.transport.send_key(seed):
            raise RuntimeError("SecurityAccess key exchange failed")
        return True

    def erase_memory(self, size):
        return self.transport.erase_memory(size)

    def request_download(self, size):

        return self.transport.request_download(size)

    def transfer_data(self, firmware):

        chunk_size = getattr(
            self.transport,
            "max_transfer_payload",
            self.CHUNK_SIZE,
        )

        total_size = len(firmware)
        total_chunks = (total_size + chunk_size - 1) // chunk_size
        large_transfer = total_chunks > 100

        if large_transfer:
            print(
                f"\n[FlashManager] Transferring {total_size:,} bytes "
                f"in {total_chunks:,} chunks ({chunk_size} B each)"
            )

        # UDS TransferData blockSequenceCounter is one byte and wraps after 0xFF.
        seq = 1
        last_progress = -1

        for i in range(0, total_size, chunk_size):

            chunk = firmware[i:i + chunk_size]

            self.transport.transfer_data(seq, chunk)

            seq = (seq + 1) & 0xFF

            if large_transfer:
                progress = ((i + len(chunk)) * 100) // total_size
                if progress // 5 > last_progress // 5:
                    last_progress = progress
                    bar_filled = progress // 5
                    bar = "█" * bar_filled + "░" * (20 - bar_filled)
                    transferred = i + len(chunk)
                    print(
                        f"\r  [{bar}] {progress:3d}%  "
                        f"({transferred:,} / {total_size:,} bytes)  "
                        f"chunk {seq - 1:,}/{total_chunks:,}",
                        end="", flush=True,
                    )

        if large_transfer:
            print()  # newline after progress bar

        return True

    def transfer_exit(self):
        if not self.transport.request_transfer_exit():
            return False

        if not self.transport.verify_programming():
            return False

        return self.transport.activate_image()

    def ecu_reset(self):

        return self.transport.ecu_reset()
