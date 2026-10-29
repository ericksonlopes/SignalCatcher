import unittest

from src.modules.voice_identity.domain.selection import (
    selection_key,
    transcript_version,
    validate_selection,
)


class VoiceSelectionTests(unittest.TestCase):
    def test_free_selection_is_not_limited_to_thirty_seconds(self):
        validate_selection(0, 120, 120)

    def test_invalid_intervals(self):
        for start, end, duration in [(-1, 4, 5), (4, 4, 5), (0, 6, 5), (0, float("nan"), 5)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                validate_selection(start, end, duration)

    def test_transcript_version_ignores_names_but_tracks_text(self):
        result = {"segments": [{"text": "Hello"}], "speaker_mappings": {}}
        version = transcript_version(result)
        result["speaker_mappings"] = {"SPEAKER_00": "Alice"}
        self.assertEqual(version, transcript_version(result))
        result["segments"] = [{"text": "Changed"}]
        self.assertNotEqual(version, transcript_version(result))

    def test_repeated_explicit_request_has_stable_identity(self):
        self.assertEqual(
            selection_key("a", "b", "v", 1, 5),
            "9f13b25d7a594c5b9ad7987ff8e24ebcb40241364bbca8bbe52801af806b1e9b",
        )
        self.assertNotEqual(selection_key("a", "b", "v", 1, 5), selection_key("a", "b", "v", 1, 6))
