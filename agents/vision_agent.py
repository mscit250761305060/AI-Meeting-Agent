import os
import json
from PIL import Image
from google import genai
from dotenv import load_dotenv

load_dotenv()

def analyze_ui_screenshot(image_path: str) -> dict:
    """
    Analyzes a UI screenshot or wireframe image and returns structured UI requirements.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"error": "GEMINI_API_KEY not found in environment."}
            
        client = genai.Client(api_key=api_key)
        
        try:
            image = Image.open(image_path)
        except Exception as e:
            return {"error": f"Failed to load image: {e}"}
        
        prompt = """
        Analyze this UI screenshot or wireframe reference.
        Extract the layout structure, navigation elements, UX patterns, and design style.
        
        Return ONLY a valid JSON object matching this schema exactly:
        {
          "page": "Suggested Page Name",
          "components": ["list of structural components like 'left sidebar', 'top navbar', 'data table'"],
          "style": "description of the visual style (e.g. 'clean modern admin dashboard with dark mode')"
        }
        
        Ensure your response is raw JSON, with no markdown code blocks.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )
        
        text = response.text.strip()
        
        # Clean json formatting blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        return json.loads(text.strip())
        
    except Exception as e:
        print(f"Error in Vision Agent: {e}")
        return {"error": str(e)}
