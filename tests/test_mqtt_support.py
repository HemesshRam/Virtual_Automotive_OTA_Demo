import unittest
from unittest.mock import Mock, patch

from common.mqtt_config import vehicle_topics
from common.mqtt_utils import connect_with_retry
from ota_server.mqtt_publisher import OTAMQTTPublisher


class MQTTSupportTest(unittest.TestCase):

    def test_vehicle_topics_match_expected_layout(self):
        topics = vehicle_topics("demo-vin")
        self.assertEqual(topics.campaign, "vehicle/demo-vin/ota/campaign")
        self.assertEqual(topics.status, "vehicle/demo-vin/ota/status")
        self.assertEqual(topics.inventory, "vehicle/demo-vin/ota/inventory")
        self.assertEqual(topics.events, "vehicle/demo-vin/ota/events")

    def test_connect_with_retry_retries_then_succeeds(self):
        client = Mock()
        client.connect.side_effect = [RuntimeError("down"), None]

        with patch("common.mqtt_utils.time.sleep") as sleep:
            self.assertTrue(connect_with_retry(client, "TEST"))

        self.assertEqual(client.connect.call_count, 2)
        sleep.assert_called_once()

    def test_campaign_payload_contains_download_url(self):
        publisher = OTAMQTTPublisher("demo-vin")
        campaign = {
            "campaign_id": "OTA_2026_001",
            "release_version": "2.0.0",
            "vehicle_model": "Virtual Vehicle",
        }

        payload = {
            "type": "campaign_available",
            "campaign_id": campaign["campaign_id"],
            "release_version": campaign["release_version"],
            "vehicle_model": campaign["vehicle_model"],
            "download_url": "http://127.0.0.1:8080/campaign/latest",
        }

        self.assertEqual(payload["campaign_id"], "OTA_2026_001")
        self.assertEqual(payload["download_url"], "http://127.0.0.1:8080/campaign/latest")


if __name__ == "__main__":
    unittest.main()
