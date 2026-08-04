from common.logical_addresses import *

class RoutingTable:

    def __init__(self):

        self.routes = {
            GATEWAY_ADDRESS: "gateway",
            BCM_ADDRESS: "bcm",
            CLUSTER_ADDRESS: "cluster"
        }

    def resolve(self, logical_address):

        return self.routes.get(logical_address)
