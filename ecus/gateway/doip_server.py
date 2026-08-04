import socket

from transport.doip.constants import DOIP_TCP_PORT

class DoIPServer:

    def __init__(self,
                 dispatcher):

        self.dispatcher = dispatcher

    def start(self):

        server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        server.bind(("0.0.0.0", DOIP_TCP_PORT))

        server.listen()

        print("Gateway DoIP Server Started")

        while True:

            conn, addr = server.accept()

            print(
                f"Tester Connected: {addr}"
            )

            conn.close()
