from pydantic import BaseModel, Field
from typing import Optional
class IngestResponse(BaseModel):
    document_id: str
    version_id: int
    version_number: int
    nodes_created: int
    warnings: list[str]
class SelectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    node_ids: list[str] = Field(min_length=1)
class GenerateRequest(BaseModel):
    selection_id: str
    regenerate: bool = True
class TestCase(BaseModel):
    title: str = Field(min_length=3)
    requirement: str = Field(min_length=3)
    preconditions: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=3)
    priority: str = "medium"
class TestCaseBundle(BaseModel):
    test_cases: list[TestCase] = Field(min_length=3, max_length=5)
