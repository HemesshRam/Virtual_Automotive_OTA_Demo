from tcu.firmware_manager import FirmwareManager

manager = FirmwareManager("firmware/releases/2.0.0")

print("\nCampaign :", manager.campaign_id())
print("Release  :", manager.release_version())
print("Primary  :", manager.transport_priority())
print("Fallback :", manager.transport_fallback())

print()

if manager.verify_repository():

    inventory = manager.build_inventory()

    print("Repository Verification : SUCCESS")

else:

    print("Repository Verification : FAILED")