from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNCERTAIN_CLASSIFICATION = "UNCERTAIN_CLASSIFICATION"
    MISSING_PRODUCT_INFORMATION = "MISSING_PRODUCT_INFORMATION"
    PREFERENCE_NOT_IN_CORPUS = "PREFERENCE_NOT_IN_CORPUS"
    PREFERENCE_CONDITIONAL = "PREFERENCE_CONDITIONAL"
    REGULATORY_COST_NOT_QUANTIFIABLE = (
        "REGULATORY_COST_NOT_QUANTIFIABLE"
    )
    NO_RELEVANT_CANDIDATE = "NO_RELEVANT_CANDIDATE"


@dataclass
class InputContext:
    product: str
    export_country: str
    import_country: str
    goods_value_eur: float


@dataclass
class ClassificationResult:
    status: Status
    nc_code: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None
    missing_information: list[str] = field(
        default_factory=list
    )


@dataclass
class TariffResult:
    status: Status
    standard_rate_pct: Optional[float] = None
    duty_text: Optional[str] = None
    standard_duty_eur: Optional[float] = None
    calculation_basis: Optional[str] = None
    missing_information: list[str] = field(
        default_factory=list
    )


@dataclass
class PreferenceResult:
    status: Status
    agreement: Optional[str] = None
    preferential_rate_pct: Optional[float] = None
    preferential_duty_eur: Optional[float] = None
    conditions: list[str] = field(
        default_factory=list
    )


@dataclass
class RegulatoryResult:
    framework: str
    finding: str
    cost_quantifiable: bool
    status: Status = Status.SUPPORTED


@dataclass
class CostSummary:
    standard_customs_duty_eur: Optional[float] = None
    potential_customs_duty_eur: Optional[float] = None
    other_regulatory_cost_eur: Optional[float] = None


@dataclass
class SourceReference:
    document: str
    section: Optional[str] = None
    page: Optional[int] = None
    excerpt: Optional[str] = None


@dataclass
class AnalysisResult:
    input: InputContext
    classification: ClassificationResult

    tariff: TariffResult = field(
        default_factory=TariffResult
    )

    preference: Optional[PreferenceResult] = None

    regulatory: list[RegulatoryResult] = field(
        default_factory=list
    )

    cost_summary: CostSummary = field(
        default_factory=CostSummary
    )

    warnings: list[str] = field(
        default_factory=list
    )

    sources: list[SourceReference] = field(
        default_factory=list
    )

    def to_dict(self):
        return asdict(self)