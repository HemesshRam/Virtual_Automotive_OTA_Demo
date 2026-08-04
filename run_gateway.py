import threading

from ecus.gateway.can_receiver import GatewayReceiver
from transport.doip.server import DoIPServer

doip = DoIPServer("Gateway ECU", port=13400)

threading.Thread(
    target=doip.start,
    daemon=True
).start()

GatewayReceiver().start()
