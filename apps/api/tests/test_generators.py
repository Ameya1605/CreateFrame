import pytest
import generator

def test_prisma_schema_single_primary_key_with_uuid():
    spec = {
        "database": [
            {
                "table_name": "Profile",
                "fields": [
                    {"name": "id", "type": "uuid"},
                    {"name": "user_id", "type": "uuid"},
                    {"name": "team_id", "type": "uuid"},
                    {"name": "bio", "type": "string"},
                ]
            }
        ]
    }
    schema = generator.generate_prisma_schema(spec)
    assert "id String @id @default(uuid())" in schema
    # Crucial fix: user_id and team_id must NOT be marked with @id @default(uuid())
    assert "user_id String\n" in schema
    assert "team_id String\n" in schema
    # Exactly one @id per model
    assert schema.count("@id") == 1

def test_fastapi_generator_path_parameters_syntax():
    spec = {
        "endpoints": [
            {
                "method": "get",
                "route": "/users/{id}",
                "response_schema": {"id": "string", "name": "string"}
            },
            {
                "method": "get",
                "route": "/orgs/{org_id}/members/{user_id}",
                "response_schema": {"status": "string"}
            },
            {
                "method": "post",
                "route": "/users/{id}/avatar",
                "request_schema": {"image_url": "string"},
                "response_schema": {"success": "bool"}
            }
        ]
    }
    code = generator.generate_fastapi_code(spec)
    
    # Must compile without Python syntax errors
    compiled = compile(code, "<generated_fastapi_code>", "exec")
    assert compiled is not None
    
    # Check that curly braces are NOT present in function or class names
    assert "async def get_users{id}get" not in code
    assert "get_users_id(id: str)" in code or "get_users_id" in code
    assert "id: str" in code
    assert "org_id: str" in code
    assert "user_id: str" in code

def test_fastapi_generator_includes_request_and_response_schemas():
    spec = {
        "endpoints": [
            {
                "method": "post",
                "route": "/items",
                "request_schema": {"title": "string", "count": "integer"},
                "response_schema": {"id": "string", "title": "string"}
            }
        ]
    }
    code = generator.generate_fastapi_code(spec)
    
    # Verify request and response models are generated
    assert "class ItemsPostRequest(BaseModel):" in code
    assert "title: str" in code
    assert "count: int" in code
    assert "class ItemsPostResponse(BaseModel):" in code
    assert "response_model=ItemsPostResponse" in code
    assert "body: ItemsPostRequest" in code
    
    # Verify code executes
    compiled = compile(code, "<generated_items>", "exec")
    assert compiled is not None
