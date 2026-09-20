import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class LLMService:
    """
    Central service for all GPT interactions.

    Every future AI capability in RestaurantAI
    will go through this class.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found in .env"
            )

        self.client = OpenAI(
            api_key=api_key
        )

    def test_connection(self) -> str:
        """
        Make the simplest possible GPT call.
        Used only to verify connectivity.
        """

        response = self.client.responses.create(
            model="gpt-5-mini",
            input="Reply with exactly these three words: Hello RestaurantAI Brain",
        )

        return response.output_text.strip()


llm_service = LLMService()