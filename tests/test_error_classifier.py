import unittest
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import classify_youtube_error, is_bot_block


class TestErrorClassifier(unittest.TestCase):
    def test_classify_court_order(self):
        error_msg = "ERROR: [youtube] W2Uo2oqS2NA: This content is not available on this country domain due to a court order."
        self.assertEqual(classify_youtube_error(error_msg), ContentStep.COURT_ORDER)

    def test_classify_court_order_case_insensitive(self):
        error_msg = "this content is not available due to a COURT ORDER."
        self.assertEqual(classify_youtube_error(error_msg), ContentStep.COURT_ORDER)

    def test_classify_other_errors(self):
        self.assertEqual(classify_youtube_error("this video has been removed"), ContentStep.VIDEO_REMOVED)
        self.assertEqual(classify_youtube_error("sign in to confirm your age"), ContentStep.AGE_RESTRICTED)
        self.assertEqual(classify_youtube_error("members-only content like this video"), ContentStep.MEMBERS_ONLY)
        self.assertEqual(classify_youtube_error("removed following a copyright"), ContentStep.COPYRIGHT_REMOVED)
        self.assertEqual(classify_youtube_error("account associated with this video has been terminated"), ContentStep.ACCOUNT_TERMINATED)
        self.assertEqual(classify_youtube_error("some generic network timeout"), ContentStep.ERROR)

    def test_is_bot_block(self):
        self.assertTrue(is_bot_block("Sign in to confirm you're not a bot"))
        self.assertFalse(is_bot_block("ERROR: [youtube] W2Uo2oqS2NA: This content is not available on this country domain due to a court order."))


if __name__ == "__main__":
    unittest.main()
