from datetime import datetime
from pydantic import BaseModel, Field


class FederatedUpdateRequest(BaseModel):
    round_id: str
    model_version: str
    encrypted_gradients: str = Field(description="Base64-encoded AES-GCM encrypted gradient update")
    dp_noise_applied: bool
    epsilon_used: float = Field(ge=0.0)
    num_samples: int = Field(ge=1)


class FederatedUpdateResponse(BaseModel):
    accepted: bool
    rejection_reason: str | None = None
    next_round_at: datetime | None = None
    global_model_url: str | None = None
    remaining_epsilon: float
