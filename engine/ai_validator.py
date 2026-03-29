import os
import json
import re

class AIValidator:
    """
    Top-Grade AI Validation Layer.
    Connects to OpenAI GPT-4o to verify bank statements and extract metadata.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                print("Warning: openai package not installed. GPT-4o validation disabled.")

    def verify_document(self, filename, text):
        """Uses AI to confirm if a file is a bank statement."""
        if not self.client:
            return {"is_statement": None, "reason": "No API Key"}

        # Use first 3000 chars of text for tokens efficiency
        truncated_text = text[:3000]
        
        prompt = f"""
        Analyze the following text from a file named '{filename}'.
        Identify if it is a Bank Account Statement from an Indian Bank.
        
        Respond ONLY with a JSON object in this format:
        {{
            "is_statement": true/false,
            "bank_name": "Name of Bank" or "Unknown",
            "account_number": "Main Account Number" or "Unknown",
            "confidence_score": 0.0 to 1.0,
            "reason": "Short explanation"
        }}
        
        Text Content:
        {truncated_text}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a financial document analyzer."},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            return {"is_statement": None, "reason": f"AI Error: {str(e)}"}
