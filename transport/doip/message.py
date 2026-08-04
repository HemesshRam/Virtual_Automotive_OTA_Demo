import json

class OTAApplicationMessage:

    @staticmethod
    def encode(message):

        return json.dumps(message).encode()

    @staticmethod
    def decode(payload):

        return json.loads(payload.decode())