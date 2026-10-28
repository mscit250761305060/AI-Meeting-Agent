import re
import json
import ast
import yaml

def clean_json_response(response):
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"RAW LLM RESPONSE BEFORE CLEANING:\n{response}\n---")
    
    response = response.strip()

    # If the response contains a markdown block, extract it
    match = re.search(r"```(?:json)?(.*?)```", response, flags=re.IGNORECASE | re.DOTALL)
    if match:
        response = match.group(1).strip()
    else:
        # Otherwise, try to find the first { and last }
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            response = response[start_idx:end_idx+1]

    def try_parse_and_dump(text):
        try:
            return json.dumps(json.loads(text))
        except Exception:
            pass
        
        try:
            parsed = yaml.safe_load(text)
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed)
        except Exception:
            pass
            
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed)
        except Exception:
            pass
            
        return None

    result = try_parse_and_dump(response)
    if result:
        return result

    # If all parsing fails, return a safe fallback to prevent JSONDecodeError crashes
    return "{}"