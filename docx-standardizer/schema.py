"""Canonical document schema. Used both as a Pydantic model for validation and as the JSON schema fed to OpenAI in strict structured-output mode."""

from typing import List

from pydantic import BaseModel, Field


class Definition(BaseModel):
    term: str
    meaning: str


class Responsibility(BaseModel):
    role: str
    duties: str


class ProcedureStep(BaseModel):
    step_number: int
    action: str


class RevisionEntry(BaseModel):
    version: str
    date: str
    author: str
    summary: str


class DocumentControl(BaseModel):
    doc_id: str
    owner: str
    approval: str
    effective_date: str


class StandardizedDocument(BaseModel):
    """Ten canonical sections derived from the client's Upwork JD."""

    title: str
    document_control: DocumentControl
    purpose: str
    scope: str
    definitions: List[Definition] = Field(default_factory=list)
    responsibilities: List[Responsibility] = Field(default_factory=list)
    procedure: List[ProcedureStep]
    records: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    revision_history: List[RevisionEntry]
