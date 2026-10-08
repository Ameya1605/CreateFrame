from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DatabaseField(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    nullable: bool = False
    unique: bool = False
    default: Optional[Any] = None
    index: bool = False

class RelationCreate(BaseModel):
    name: str
    type: str = "1:N"  # "1:N", "N:1", "1:1", "M:N"
    from_table: str
    from_field: str
    to_table: str
    to_field: str
    on_delete: str = "CASCADE"
    on_update: Optional[str] = "CASCADE"

class EnumCreate(BaseModel):
    name: str
    values: List[str]

class SchemaCreate(BaseModel):
    table_name: str
    fields: List[DatabaseField]
    relations: Optional[List[RelationCreate]] = []
    code: Optional[str] = None

class EndpointCreate(BaseModel):
    method: str
    route: str
    linked_table: Optional[str] = None
    auth_required: bool = True
    auth_type: Optional[str] = "bearer"
    roles: Optional[List[str]] = []
    request_schema: Optional[Dict[str, Any]] = {}
    response_schema: Optional[Dict[str, Any]] = {}
    code: Optional[str] = None

class FeatureCreate(BaseModel):
    name: str
    status: str = "mvp"
    description: Optional[str] = None

class UIComponentCreate(BaseModel):
    name: str
    type: str # page, layout, component
    route: Optional[str] = None
    code: Optional[str] = None

class PromptCreate(BaseModel):
    name: str
    template: str

class ProjectCreate(BaseModel):
    name: str
    repo_url: str

class ProjectBase(BaseModel):
    id: int
    name: str
    repo_url: str
    owner_id: int
    is_ai_enabled: bool = False

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    id: int
    username: str
    github_id: int

    class Config:
        from_attributes = True

class GenerateComponentRequest(BaseModel):
    project_id: int
    component_name: str
    component_type: str # page, component, layout
    description: Optional[str] = None

class GitHubAuthRequest(BaseModel):
    code: str

class SpecPushRequest(BaseModel):
    project_id: int

class BrainstormRequest(BaseModel):
    description: str

class RecommendationAction(BaseModel):
    type: str  # add_endpoint, add_schema, add_fields, add_feature, add_ui_component, navigate, info
    payload: Dict[str, Any]

class RecommendationItem(BaseModel):
    id: str
    rule_id: str
    layer: str
    type: str
    severity: str
    title: str
    description: str
    action: RecommendationAction
    confidence: float

class RecommendationsResponse(BaseModel):
    project_type: str
    completeness_scores: Dict[str, float]
    total_count: int
    critical_count: int
    recommendations: Dict[str, List[RecommendationItem]]
    all: List[RecommendationItem]

class FieldHintRequest(BaseModel):
    table_name: str

class LLMConfigUpdate(BaseModel):
    provider: str  # groq, openai, anthropic, ollama
    model: Optional[str] = None
    api_key: Optional[str] = None

class LLMConfigResponse(BaseModel):
    provider: str
    model: Optional[str] = None
    has_api_key: bool = False

class SyncResolutionItem(BaseModel):
    layer: str  # table, route, component
    key: str
    action: str  # accept_code, keep_spec, delete
    payload: Optional[Dict[str, Any]] = None

class SyncProjectRequest(BaseModel):
    resolutions: Optional[List[SyncResolutionItem]] = []

class ProjectSettingsUpdate(BaseModel):
    target_branch: Optional[str] = None
    governance_mode: Optional[str] = None # "direct" | "pr"

class ProjectSettingsResponse(BaseModel):
    target_branch: str
    governance_mode: str


# ─── Smarter AI Schemas ────────────────────────────────────────────────────────

class ImpactAnalysisRequest(BaseModel):
    query: str
    target_type: Optional[str] = None  # "field" | "table" | "route" | "component"
    table: Optional[str] = None
    field: Optional[str] = None
    action: Optional[str] = "rename"    # "rename" | "delete" | "modify"
    new_name: Optional[str] = None

class ImpactAffectedItem(BaseModel):
    type: str  # "route" | "component" | "feature" | "relation"
    identifier: str
    reason: str
    severity: str = "medium"  # "high" | "medium" | "low"
    detail: Optional[Dict[str, Any]] = None

class ImpactAnalysisResponse(BaseModel):
    query: str
    target: str
    action: str
    severity: str
    breaking_routes: List[ImpactAffectedItem]
    breaking_components: List[ImpactAffectedItem]
    breaking_features: List[ImpactAffectedItem]
    downstream_relations: List[ImpactAffectedItem]
    recommended_actions: List[str]
    ai_summary: Optional[str] = None

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str

class ChatReferenceItem(BaseModel):
    type: str  # "schema" | "endpoint" | "ui_component" | "feature" | "file"
    id: Optional[int] = None
    title: str
    detail: Optional[str] = None

class ArchitectureChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

class ArchitectureChatResponse(BaseModel):
    answer: str
    references: List[ChatReferenceItem]
    suggested_questions: Optional[List[str]] = []

class BuildPromptRequest(BaseModel):
    target: Optional[str] = "cursor"  # "cursor" | "claude_code" | "generic"
    save_as_template: Optional[bool] = False

class BuildPromptResponse(BaseModel):
    feature_id: int
    feature_name: str
    target: str
    prompt: str
    slice_summary: Dict[str, Any]
    template_id: Optional[int] = None

class CritiqueItem(BaseModel):
    id: str
    category: str  # "scalability" | "security" | "completeness" | "maintainability"
    severity: str  # "critical" | "warning" | "suggestion"
    title: str
    description: str
    remediation: str
    affected_items: Optional[List[str]] = []

class DesignCritiqueResponse(BaseModel):
    overall_score: int
    scalability_score: int
    security_score: int
    completeness_score: int
    maintainability_score: int
    executive_summary: str
    critiques: List[CritiqueItem]

class SpecFromDocRequest(BaseModel):
    content: str
    doc_type: Optional[str] = "prd"  # "prd" | "markdown" | "user_story" | "text"

class SpecFromWireframeRequest(BaseModel):
    image_base64: str
    screen_name: Optional[str] = "Screen"
    mime_type: Optional[str] = "image/png"

class ExtractedSpecItem(BaseModel):
    features: List[Dict[str, Any]]
    schemas: List[Dict[str, Any]]
    endpoints: List[Dict[str, Any]]
    ui_components: List[Dict[str, Any]]

class SpecFromDocResponse(BaseModel):
    extracted: ExtractedSpecItem
    summary: str

class ApplyExtractedSpecRequest(BaseModel):
    extracted: ExtractedSpecItem

class ADRGenerateRequest(BaseModel):
    title: Optional[str] = None
    context_note: Optional[str] = None

class ADRResponse(BaseModel):
    id: Optional[int] = None
    title: str
    status: str
    file_path: str
    content: str
    committed: bool = False
    created_at: Optional[str] = None

class ADRCommitRequest(BaseModel):
    adr_id: int


