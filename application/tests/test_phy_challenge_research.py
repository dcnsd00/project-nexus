import math
import unittest

from modules.phy_challenge_research import (
    analyze_project_file,
    catalog,
    decode_meta_clue,
)


def make_project():
    boxes = []
    ids = [value for value in range(1, 258) if value != 23]
    cx, cy = 1023.5, 1024.5
    for index in range(128):
        angle = math.radians(index * 2.8)
        radius = 250.0 + (index * 2.0)
        west_codepoint = "1F468" if index % 2 == 0 else "1F600"
        east_codepoint = "1F600" if index % 2 == 0 else "1F468"
        for offset, cp in ((0.0, west_codepoint), (math.pi, east_codepoint)):
            x = cx + radius * math.cos(angle + offset)
            y = cy + radius * math.sin(angle + offset)
            boxes.append({
                "id": ids[index * 2 + (0 if offset == 0.0 else 1)],
                "x": x,
                "y": y,
                "w": 0,
                "h": 0,
                "char": "test",
                "name": "test emoji",
                "unified": cp,
            })
    boxes.append({
        "id": 258, "x": cx, "y": cy, "w": 0, "h": 0,
        "char": "b", "name": "BITCOIN LOGO CENTER", "unified": "0062",
    })
    return {"natW": 2048, "natH": 2048, "boxes": boxes}


class MetaClueTests(unittest.TestCase):
    def test_reverse_then_rot13(self):
        self.assertEqual(decode_meta_clue(), "flabit Zephyrus Mox")

    def test_rejects_oversized_input(self):
        with self.assertRaises(ValueError):
            decode_meta_clue("x" * 257)


class ProjectAnalysisTests(unittest.TestCase):
    def test_geometric_pair_count_and_centre(self):
        result = analyze_project_file(make_project())
        self.assertEqual(result["emoji_boxes"], 256)
        self.assertEqual(result["pair_count"], 128)
        self.assertEqual(result["centre"]["source"], "box_id_258")
        self.assertEqual(result["pairing"]["max_reflection_error_px"], 0.0)

    def test_missing_id_23_and_s_byte_selection(self):
        result = analyze_project_file(make_project())
        self.assertEqual(result["missing_box_ids_1_to_257"], [23])
        self.assertEqual(
            result["s_byte_position_candidates"]["position_values"],
            [91, 137, 11, 41, 43, 161, 171, 217, 177],
        )
        self.assertTrue(result["signature_s_byte_canvas_id_diagnostic"]["direct_canvas_id_lookup_complete"])

    def test_unicode_modifier_base_property(self):
        result = analyze_project_file(make_project())
        self.assertEqual(result["pairing"]["pairs_with_emoji_modifier_base"], 128)

    def test_valid_compressed_public_point(self):
        from modules.phy_challenge_research import validate_compressed_public_key
        candidate = "031dffd7ff0d400f0afcc3fdcefc0d400f0da10f3a390f77ff0d400f68fe0d080f"
        result = validate_compressed_public_key(candidate)
        self.assertTrue(result["valid_curve_point"])
        self.assertEqual(result["y_parity"], 1)
        self.assertFalse(result["private_scalar_derived"])
        self.assertFalse(result["signature_verified"])

    def test_invalid_compressed_public_point_rejected(self):
        from modules.phy_challenge_research import validate_compressed_public_key
        with self.assertRaises(ValueError):
            validate_compressed_public_key("04" + "00" * 32)
        with self.assertRaises(ValueError):
            validate_compressed_public_key("02" + "00" * 32)

    def test_invalid_project_rejected(self):
        with self.assertRaises(ValueError):
            analyze_project_file({"boxes": []})

    def test_radial_phase_fit_recovers_known_increment(self):
        result = analyze_project_file(make_project())
        fit = result["radial_phase_fit"]
        self.assertEqual(fit["sample_count"], 128)
        self.assertAlmostEqual(fit["candidate_angular_increment_degrees"], 2.8, delta=0.1)
        self.assertEqual(fit["classification"],
                         "geometric heuristic; not an author-confirmed spiral index")

    def test_low_byte_stream_is_reported_without_claiming_hx_match(self):
        result = analyze_project_file(make_project())
        stream = result["signature_s_byte_canvas_id_diagnostic"]
        self.assertEqual(stream["raw_codepoint_low_byte_stream_length"], 9)
        self.assertEqual(len(stream["raw_codepoint_low_byte_stream_hex"]), 18)
        self.assertIn("diagnostic only", stream["interpretation"])

    def test_position_candidates_are_not_mislabeled_as_canvas_ids(self):
        result = analyze_project_file(make_project())
        candidates = result["s_byte_position_candidates"]["candidate_orders"]
        self.assertIn("angle_zero_based", candidates)
        self.assertIn("radius_one_based", candidates)
        self.assertTrue(candidates["angle_zero_based"]["selection_complete"])
        self.assertEqual(len(candidates["angle_zero_based"]["selected"]), 9)
        self.assertIn("matches_forum_angle_order_observation", result["reference_observations"])
        self.assertIn("not established as the true spiral order",
                      candidates["angle_zero_based"]["interpretation"])

    def test_canvas_id_lookup_is_diagnostic_only(self):
        result = analyze_project_file(make_project())
        diagnostic = result["signature_s_byte_canvas_id_diagnostic"]
        self.assertIn("not established as spiral positions", diagnostic["interpretation"])
        self.assertEqual(diagnostic["raw_codepoint_low_byte_stream_length"], 9)

    def test_catalog_does_not_claim_final_solver(self):
        info = catalog()
        self.assertEqual(info["state"], "implemented_local_analysis")
        self.assertIn("confirmed final scalar derivation", info["not_implemented"])
        self.assertFalse(info["network_access"])


if __name__ == "__main__":
    unittest.main()
