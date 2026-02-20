import os
import json
import logging
from groq import Groq
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s:brain: %(message)s")
log = logging.getLogger("brain")

def get_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)

def analyze_spec_and_suggest(layer: str, current_items: List[Dict[str, Any]], project_context: str) -> List[str]:
    """
    Uses Groq to suggest improvements or missing items for a specific layer.
    """
    client = get_client()
    if not client:
        return ["AI suggestions unavailable (API key missing)"]

    prompt = f"""
    You are a Senior Technical Architect assisting a developer.
    Project Context: {project_context}
    Current layer being edited: {layer}
    Current items in this layer: {json.dumps(current_items)}

    Based on industry best practices for a modern full-stack application:
    1. Suggest 2-3 missing items for this layer.
    2. Give a brief (1 sentence) rationale for each.
    3. Keep it technical and "no-fluff".
    4. Format as a JSON list of strings.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional software architect. Respond only with a JSON list of strings."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
        )
        content = chat_completion.choices[0].message.content
        log.info("[suggest] raw response: %s", content)
        # Basic cleanup in case of markdown blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
             content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
    except Exception as e:
        log.error("[suggest] error: %s", e)
        return [f"Could not generate suggestions: {str(e)}"]

def generate_react_component(name: str, type: str, context: str) -> str:
    """
    Generates React code for a UI component using Groq.
    """
    client = get_client()
    if not client:
        return "// AI Code Generation unavailable (API key missing)"

    prompt = f"""
    You are an expert React/Next.js developer.
    Task: Generate a production-ready React component.
    Name: {name}
    Type: {type} (page/component/layout)
    Project Context (Schema/API): {context}

    Requirements:
    1. Use 'lucide-react' for icons.
    2. Use standard hooks (useState, useEffect) if needed.
    3. Use Tailwind CSS for all styling.
    4. If the context implies data fetching, use `fetch` to call the API endpoints defined in the context.
    5. PROVIDE ONLY THE CODE. No introduction, no markdown backticks, no explanation.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a React expert. Output raw code only. No markdown."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
        )
        content = chat_completion.choices[0].message.content
        log.info("[react-component] raw response:\n%s", content)
        if "```" in content:
             content = content.replace("```tsx", "").replace("```jsx", "").replace("```javascript", "").replace("```", "")
        
        return content.strip()
    except Exception as e:
        log.error("[react-component] error: %s", e)
        return f"// Error generating code: {str(e)}"

def suggest_initial_spec(description: str) -> Dict[str, Any]:
    """
    Takes a project description and suggests features and database tables.
    """
    client = get_client()
    if not client:
        return {"features": [], "schemas": []}

    prompt = f"""
    You are a Technical Architect. 
    A user wants to build: {description}

    Task:
    1. Identify 5 core MVP features (short names, e.g. "User Authentication", "Dashboard").
    2. Identify 3 core database tables needed.
    3. For each table, define 3-4 essential fields (name and type).

    Return ONLY a JSON object with this structure:
    {{
        "features": ["feature 1", "feature 2", ...],
        "schemas": [
            {{ "table_name": "name", "fields": [{{ "name": "field", "type": "string|integer|boolean|text" }}, ...] }},
            ...
        ]
    }}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a software architect. Respond only with JSON."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
        )
        content = chat_completion.choices[0].message.content
        log.info("[brainstorm] raw response:\n%s", content)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
    except Exception as e:
        log.error("[brainstorm] error: %s", e)
        return {"features": [], "schemas": []}

def summarize_project_progress(commits: List[str], features: List[str]) -> Dict[str, Any]:
    """
    Analyzes commit messages against features to suggest a 'completion' status.
    """
    client = get_client()
    if not client:
        return {"summary": "AI unavailable", "feature_status": {}}

    prompt = f"""
    Based on these recent GitHub commits:
    {json.dumps(commits)}

    And these planned features:
    {json.dumps(features)}

    Task:
    1. Write a 1-sentence summary of overall progress.
    2. For each feature, estimate a completion percentage (0-100) based ONLY on the commits.

    Respond with ONLY JSON:
    {{
        "summary": "...",
        "feature_status": {{ "Feature Name": 80, ... }}
    }}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        raw = chat_completion.choices[0].message.content
        log.info("[progress] raw response:\n%s", raw)
        return json.loads(raw)
    except Exception as e:
        log.error("[progress] error: %s", e)
        return {"summary": "Unable to synthesize commits.", "feature_status": {}}

def generate_code(item_type: str, item_name: str, spec: str) -> str:
    """
    Generates code (FastAPI, Prisma, or React) based on the item type.
    """
    client = get_client()
    if not client: return "// AI unavailable"

    prompts = {
        "schemas": f"You are a Senior Data Architect. Generate a clean, minimal Prisma model for '{item_name}' based on this spec: {spec}. Use PascalCase for model names. Do not add comments. Output raw prisma schema only.",
        "endpoints": f"You are a Senior Backend Engineer. Generate a performance-optimized FastAPI route for '{item_name}' based on: {spec}. Use Pydantic v2. Keep it minimal and clean. No docstrings or comments. Output raw python only.",
        "ui-components": f"You are a Senior Frontend Engineer. Generate a sleek React component using Tailwind and Lucide for '{item_name}' based on: {spec}. Focus on premium aesthetics and minimal code. Output raw tsx only."
    }

    try:
        res = client.chat.completions.create(
            messages=[{"role": "user", "content": prompts.get(item_type, "Generate code for " + item_name)}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        content = res.choices[0].message.content
        log.info("[generate-code: %s] raw response:\n%s", item_type, content)
        if "```" in content:
            content = content.split("```")[1].split("```", 1)[0].replace("tsx", "").replace("python", "").strip()
        return content
    except Exception as e:
        log.error("[generate-code] error: %s", e)
        return f"// Generation Error: {str(e)}"

def generate_commit_message(item_type: str, item_name: str) -> str:
    """Generates professional conventional commit messages."""
    prefixes = {
        "schemas": "feat(db)",
        "endpoints": "feat(api)",
        "ui-components": "feat(ui)"
    }
    prefix = prefixes.get(item_type, "chore")
    return f"{prefix}: implement {item_name.lower()}"

