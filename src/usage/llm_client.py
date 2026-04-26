import json
import os
import re

import google.generativeai as genai
from dotenv import load_dotenv

# Load .env and configure Gemini client once.
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-flash")


def call_ai_for_json(system_prompt, user_prompt):
    try:
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
            ),
        )
        text = response.text.strip()

        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        return json.loads(text)

    except Exception as e:
        print(f"Error when call AI: {e}")
        return None
