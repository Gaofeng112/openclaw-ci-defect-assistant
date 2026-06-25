from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.confirmation_store import token_suffix
from app.assistant import handle_chat
from app.schemas import BugCreateResponse


class BugPreviewReplyTest(TestCase):
    def test_one_sentence_bug_preview_contains_description(self):
        args = SimpleNamespace(
            user_id="17797610609074237",
            conversation_id="preview-with-description",
            text="企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷",
            fields_json="{}",
            fields_file=None,
            confirm_token=None,
            confirmed=False,
            no_wait_result=False,
            request_id=None,
        )

        with patch.dict("os.environ", {"TEAMBITION_MOCK": "0"}):
            payload = handle_chat(args)

        self.assertIn("描述", payload["reply"])
        self.assertIn("企业版正服中国上市检索生僻字会报错", payload["reply"])

    def test_bug_confirmation_requires_token(self):
        conversation_id = "preview-requires-token"
        preview_args = SimpleNamespace(
            user_id="17797610609074237",
            conversation_id=conversation_id,
            text="企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷",
            fields_json="{}",
            fields_file=None,
            confirm_token=None,
            confirmed=False,
            no_wait_result=False,
            request_id=None,
        )
        with patch.dict("os.environ", {"TEAMBITION_MOCK": "0"}):
            handle_chat(preview_args)
        confirm_args = SimpleNamespace(
            user_id="17797610609074237",
            conversation_id=conversation_id,
            text="确认",
            fields_json="{}",
            fields_file=None,
            confirm_token=None,
            confirmed=False,
            no_wait_result=False,
            request_id=None,
        )

        with patch.dict("os.environ", {"TEAMBITION_MOCK": "0"}):
            payload = handle_chat(confirm_args)

        self.assertFalse(payload["result"]["success"])
        self.assertEqual("confirm_token_required", payload["result"]["code"])

    def test_bug_confirmation_accepts_visible_token(self):
        conversation_id = "preview-with-token"
        preview_args = SimpleNamespace(
            user_id="17797610609074237",
            conversation_id=conversation_id,
            text="企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷",
            fields_json="{}",
            fields_file=None,
            confirm_token=None,
            confirmed=False,
            no_wait_result=False,
            request_id=None,
        )
        with patch.dict("os.environ", {"TEAMBITION_MOCK": "0"}):
            preview = handle_chat(preview_args)
        confirm_args = SimpleNamespace(
            user_id="17797610609074237",
            conversation_id=conversation_id,
            text=f"确认 {token_suffix(preview['result']['confirm_token'])}",
            fields_json="{}",
            fields_file=None,
            confirm_token=None,
            confirmed=False,
            no_wait_result=False,
            request_id=None,
        )

        def fake_submit(fields, payload):
            return BugCreateResponse(success=True, code="created", message="ok", task_id="mock-task", fields=fields)

        with patch.dict("os.environ", {"TEAMBITION_MOCK": "0"}), patch("app.tools.teambition_tool._submit_task", fake_submit):
            payload = handle_chat(confirm_args)

        self.assertTrue(payload["result"]["success"])
        self.assertEqual("created", payload["result"]["code"])
