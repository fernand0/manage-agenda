import unittest
from unittest.mock import patch, MagicMock

from manage_agenda.utils_llm import LLMClient


class TestLLMUtils(unittest.TestCase):
    def test_init(self):
        llm_client = LLMClient()
        self.assertIsInstance(llm_client, LLMClient)
