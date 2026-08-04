from ecus.base.config_manager import ConfigManager

gateway = ConfigManager("ecus/gateway")

print(gateway.ecu_name)
print(gateway.ecu_id)
print(gateway.current_version)
print(gateway.transport)
print(gateway.dependency)