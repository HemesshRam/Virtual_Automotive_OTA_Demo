import unittest

from common.automotive_realism import load_realism_profile


class RealismProfileTest(unittest.TestCase):

    def test_profile_covers_requested_production_simulation_areas(self):
        profile = load_realism_profile()

        self.assertIn("DCM", profile["autosar"]["simulated_modules"])
        self.assertIn("FBL", profile["autosar"]["simulated_modules"])
        self.assertIn("0x34", profile["uds"]["supported_services"])
        self.assertIn("0x78", profile["uds"]["simulated_nrc_matrix"])
        self.assertTrue(profile["flash"]["readback_verification"])
        self.assertTrue(profile["flash"]["ab_slots"])
        self.assertEqual(profile["ethernet"]["vehicle_identification"], "UDP/13400")
        self.assertIn("director", profile["uptane"]["simulated_roles"])


if __name__ == "__main__":
    unittest.main()
