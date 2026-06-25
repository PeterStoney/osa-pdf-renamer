from dataclasses import dataclass

from .config import UNKNOWN


@dataclass
class DocumentDetails:
    patient_name: str = UNKNOWN
    sender: str = UNKNOWN
    document_type: str = UNKNOWN
    document_date: str = UNKNOWN
    raw_model_response: str = ""
    name_evidence: str = ""
    sender_evidence: str = ""
    type_evidence: str = ""
    date_evidence: str = ""
    confidence: float = 0.0


@dataclass
class VisionLine:
    text: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


@dataclass
class VisionOCR:
    text: str = ""
    lines: tuple = ()


@dataclass
class RenameResult:
    renamed: bool
    needs_review: bool


@dataclass
class BatchSummary:
    processed: int = 0
    renamed: int = 0
    unchanged: int = 0
    needs_review: int = 0
    errors: int = 0
