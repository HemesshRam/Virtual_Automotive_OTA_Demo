import can


class FrameBuilder:

    @staticmethod
    def build(arbitration_id, payload):

        if len(payload) > 64:
            raise ValueError("CAN FD payload exceeds 64 bytes")

        return can.Message(
            arbitration_id=arbitration_id,
            data=payload,
            is_extended_id=False,
            is_fd=True,
            bitrate_switch=True,
        )
