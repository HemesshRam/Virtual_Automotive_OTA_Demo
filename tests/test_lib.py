from doipclient import DoIPClient
import inspect

print(inspect.getsource(DoIPClient.send_diagnostic_to_address))
print(inspect.getsource(DoIPClient.receive_diagnostic))