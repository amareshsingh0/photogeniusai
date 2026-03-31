"""
Integration tests for the Refinement Lambda.

Run from repo root:
  python -m pytest aws/lambda/refinement/tests/test_refinement_integration.py -v

Or from aws/lambda/refinement:
  python -m pytest tests/test_refinement_integration.py -v
"""

import base64
import json
import os
import unittest
from unittest.mock import patch, MagicMock

# Add parent so handler can be imported
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import after env patch would require reload; we patch handler.S3_BUCKET in tests instead
from handler import lambda_handler


# 1x1 red pixel PNG (smallest valid PNG)
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _body(res: dict) -> dict:
    """Parse JSON body from Lambda response."""
    return json.loads(res.get("body", "{}"))


class TestRefinementIntegration(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(
            os.environ,
            {"S3_BUCKET": "test-bucket", "AWS_REGION": "us-east-1"},
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch("handler.S3_BUCKET", "test-bucket")
    @patch("handler.s3_client")
    def test_success_global_adjustment(self, mock_s3):
        mock_s3.put_object = MagicMock()
        event = {
            "body": json.dumps({
                "image_base64": TINY_PNG_B64,
                "instruction": "make it brighter",
                "strength": 0.7,
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 200, out.get("body"))
        body = _body(out)
        self.assertIn("refined_url", body)
        self.assertTrue(body["refined_url"].startswith("https://"), body["refined_url"])
        self.assertIn("refined/", body["refined_url"])
        self.assertIn("modification_applied", body)
        self.assertIn("metadata", body)
        self.assertEqual(body["metadata"].get("mod_type"), "global")
        mock_s3.put_object.assert_called_once()
        call_kw = mock_s3.put_object.call_args[1]
        self.assertEqual(call_kw["Bucket"], "test-bucket")
        self.assertEqual(call_kw["ContentType"], "image/png")
        self.assertTrue(call_kw["Key"].startswith("refined/"))
        self.assertTrue(call_kw["Key"].endswith(".png"))

    @patch("handler.s3_client")
    def test_success_style_fallback(self, mock_s3):
        mock_s3.put_object = MagicMock()
        event = {
            "body": json.dumps({
                "image_base64": TINY_PNG_B64,
                "instruction": "black and white",
                "strength": 0.5,
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 200, out.get("body"))
        body = _body(out)
        self.assertIn("refined_url", body)
        self.assertIn("modification_applied", body)
        self.assertEqual(body["metadata"].get("mod_type"), "style")

    @patch("handler.s3_client")
    def test_400_missing_instruction(self, mock_s3):
        event = {
            "body": json.dumps({
                "image_base64": TINY_PNG_B64,
                "instruction": "",
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 400)
        body = _body(out)
        self.assertIn("error", body)
        self.assertIn("instruction", body["error"].lower())
        mock_s3.put_object.assert_not_called()

    @patch("handler.s3_client")
    def test_400_missing_image(self, mock_s3):
        event = {
            "body": json.dumps({
                "instruction": "make it brighter",
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 400)
        body = _body(out)
        self.assertIn("error", body)
        mock_s3.put_object.assert_not_called()

    @patch("handler.s3_client")
    def test_400_unclear_instruction(self, mock_s3):
        event = {
            "body": json.dumps({
                "image_base64": TINY_PNG_B64,
                "instruction": "do something weird and random",
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 400)
        body = _body(out)
        self.assertIn("error", body)
        mock_s3.put_object.assert_not_called()

    @patch("handler.s3_client")
    def test_400_invalid_base64(self, mock_s3):
        event = {
            "body": json.dumps({
                "image_base64": "not-valid-base64!!!",
                "instruction": "make it brighter",
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 400)
        body = _body(out)
        self.assertIn("error", body)

    @patch("handler.s3_client")
    def test_500_s3_upload_failure(self, mock_s3):
        mock_s3.put_object = MagicMock(side_effect=Exception("S3 unavailable"))
        event = {
            "body": json.dumps({
                "image_base64": TINY_PNG_B64,
                "instruction": "make it brighter",
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 500)
        body = _body(out)
        self.assertIn("error", body)
        self.assertIn("S3", body["error"])

    @patch("handler.s3_client")
    def test_direct_invoke_body_dict(self, mock_s3):
        """Body as dict (direct invoke) instead of JSON string."""
        mock_s3.put_object = MagicMock()
        event = {
            "body": {
                "image_base64": TINY_PNG_B64,
                "instruction": "more contrast",
                "strength": 0.8,
            },
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 200)
        body = _body(out)
        self.assertIn("refined_url", body)
        self.assertEqual(body["metadata"].get("strength"), 0.8)

    @patch("handler.s3_client")
    def test_backward_compat_refinement_request(self, mock_s3):
        """Accept refinement_request as alias for instruction."""
        mock_s3.put_object = MagicMock()
        event = {
            "body": json.dumps({
                "image_base64": TINY_PNG_B64,
                "refinement_request": "make it darker",
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 200)
        body = _body(out)
        self.assertIn("refined_url", body)
        self.assertIn("modification_applied", body)

    @patch("handler.S3_BUCKET", "test-bucket")
    @patch("handler.s3_client")
    def test_success_image_url_s3_key(self, mock_s3):
        """Download image from S3 when image_url is an S3 key (no scheme)."""
        image_bytes = base64.b64decode(TINY_PNG_B64)
        mock_s3.get_object = MagicMock(return_value={"Body": MagicMock(read=MagicMock(return_value=image_bytes))})
        mock_s3.put_object = MagicMock()
        event = {
            "body": json.dumps({
                "image_url": "generations/abc123.png",
                "instruction": "increase saturation",
                "strength": 0.6,
            }),
        }
        out = lambda_handler(event, None)
        self.assertEqual(out["statusCode"], 200, _body(out))
        mock_s3.get_object.assert_called_once()
        call_kw = mock_s3.get_object.call_args[1]
        self.assertEqual(call_kw["Bucket"], "test-bucket")
        self.assertEqual(call_kw["Key"], "generations/abc123.png")
        mock_s3.put_object.assert_called_once()


if __name__ == "__main__":
    unittest.main()
