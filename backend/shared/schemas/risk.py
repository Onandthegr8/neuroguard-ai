import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel


class SHAPContributor(BaseModel):
    feature: str
    contribution_pct: float
    direction: str  # 'increases_risk' | 'decreases_risk'


class RiskScoreResponse(BaseModel):
    prediction_id: uuid.UUID
    risk_score: float
    risk_tier: str
    confidence_interval: Tuple[float, float]
    model_version: str
    shap_explanations: Dict[str, float]
    top_contributors: List[SHAPContributor]
    keystroke_contribution: Optional[float]
    sleep_contribution: Optional[float]
    predicted_at: datetime


class RiskHistoryPoint(BaseModel):
    date: str
    risk_score: float
    risk_tier: str


class RiskHistoryResponse(BaseModel):
    user_id: uuid.UUID
    history: List[RiskHistoryPoint]
    days: int
