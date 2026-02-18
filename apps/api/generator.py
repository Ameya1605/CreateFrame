from typing import Dict, Any

def generate_prisma_schema(spec: Dict[str, Any]) -> str:
    schema = """// This is your Prisma schema file,
// learn more about it in the docs: https://pris.ly/d/prisma-schema

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
"""
    
    # Simple mapping from SpecOS types to Prisma types
    type_mapping = {
        "string": "String",
        "integer": "Int",
        "boolean": "Boolean",
        "json": "Json",
        "uuid": "String @id @default(uuid())", # simplified
        "datetime": "DateTime",
        "float": "Float"
    }

    for table in spec.get("database", []):
        schema += f"\nmodel {table['table_name']} {{\n"
        
        # Ensure there is an ID field if not specified (though usually handled by user)
        # For MVP, we'll just map fields directly
        has_id = False
        for field in table.get("fields", []):
            field_name = field["name"]
            field_type = field["type"].lower()
            prisma_type = type_mapping.get(field_type, "String")
            
            # Basic modifiers
            modifiers = ""
            if field_name == "id" and "uuid" in prisma_type:
                has_id = True
            elif field_name == "id" and field_type == "integer":
                modifiers = " @id @default(autoincrement())"
                has_id = True

            schema += f"  {field_name} {prisma_type}{modifiers}\n"
        
        if not has_id:
             # Fallback ID if user didn't specify one suitable field as ID
             schema += "  id String @id @default(uuid())\n"

        schema += "}\n"

    return schema


def generate_fastapi_code(spec: Dict[str, Any]) -> str:
    code = """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any

app = FastAPI()

# Pydantic Models
"""
    
    # Generate Pydantic models from Request/Response Schemas
    # This is a bit complex for MVP, so we'll do a simplified version
    # mapping endpoint names to models
    
    for endpoint in spec.get("endpoints", []):
        method = endpoint["method"].lower()
        route = endpoint["route"]
        model_name = "".join([part.capitalize() for part in route.split("/") if part]) + method.capitalize()
        
        # Request Model
        req_schema = endpoint.get("request_schema")
        if req_schema:
            code += f"\nclass {model_name}Request(BaseModel):\n"
            for k, v in req_schema.items():
                # Assuming v is type string description or example, we default to Any for safety in MVP
                code += f"    {k}: Any\n"
        
        # Response Model
        res_schema = endpoint.get("response_schema")
        if res_schema:
            code += f"\nclass {model_name}Response(BaseModel):\n"
            for k, v in res_schema.items():
                code += f"    {k}: Any\n"

    code += "\n# API Routes\n"

    for endpoint in spec.get("endpoints", []):
        method = endpoint["method"].lower()
        route = endpoint["route"]
        model_name = "".join([part.capitalize() for part in route.split("/") if part]) + method.capitalize()
        
        req_arg = ""
        req_type = ""
        if endpoint.get("request_schema"):
            req_arg = f", body: {model_name}Request"
        
        res_type = ""
        if endpoint.get("response_schema"):
            res_type = f", response_model={model_name}Response"

        code += f"\n@app.{method}('{route}'{res_type})\n"
        code += f"async def {method}_{model_name.lower()}({req_arg.strip(', ')}):\n"
        code += f"    # TODO: Implement logic for {route}\n"
        code += f"    return {{}}\n"

    return code
