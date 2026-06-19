"""NeuroGuard AI Model — TCN + BiLSTM + Multi-Head Attention hybrid.

Input:
  keystroke_features: (B, 20) float tensor
  sleep_features:     (B, 15) float tensor

Output:
  risk_score: (B, 1) float in [0, 1]
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple


# ---------------------------------------------------------------------------
# Temporal Convolutional Network block
# ---------------------------------------------------------------------------

class _TCNBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float = 0.2):
        super().__init__()
        padding = (kernel_size - 1) * dilation
        self.conv1 = nn.utils.weight_norm(nn.Conv1d(in_channels, out_channels, kernel_size, dilation=dilation, padding=padding))
        self.conv2 = nn.utils.weight_norm(nn.Conv1d(out_channels, out_channels, kernel_size, dilation=dilation, padding=padding))
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        self.init_weights()

    def init_weights(self) -> None:
        nn.init.normal_(self.conv1.weight, 0, 0.01)
        nn.init.normal_(self.conv2.weight, 0, 0.01)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x if self.downsample is None else self.downsample(x)
        out = self.relu(self.conv1(x)[..., :x.size(-1)])
        out = self.dropout(out)
        out = self.relu(self.conv2(out)[..., :x.size(-1)])
        out = self.dropout(out)
        return self.relu(out + residual)


class KeystrokeTCN(nn.Module):
    """TCN backbone for the keystroke feature branch."""

    def __init__(self, input_size: int = 20, channels: Tuple[int, ...] = (64, 128, 128), kernel_size: int = 3, dropout: float = 0.2):
        super().__init__()
        layers = []
        in_c = 1
        for i, out_c in enumerate(channels):
            dilation = 2 ** i
            layers.append(_TCNBlock(in_c, out_c, kernel_size, dilation, dropout))
            in_c = out_c
        self.net = nn.Sequential(*layers)
        self.fc = nn.Linear(channels[-1], 128)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 20) → (B, 1, 20) for Conv1d
        x = x.unsqueeze(1)
        out = self.net(x)                           # (B, 128, 20)
        out = out.mean(dim=-1)                      # global average pooling → (B, 128)
        return F.relu(self.fc(out))                 # (B, 128)


# ---------------------------------------------------------------------------
# BiLSTM backbone for sleep features
# ---------------------------------------------------------------------------

class SleepBiLSTM(nn.Module):
    """Bidirectional LSTM for sleep feature branch."""

    def __init__(self, input_size: int = 15, hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_size * 2, 128)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 15) → (B, 15, 1)
        x = x.unsqueeze(-1)
        out, _ = self.lstm(x)                       # (B, 15, 128)
        out = out[:, -1, :]                         # last timestep → (B, 128)
        return F.relu(self.fc(out))                 # (B, 128)


# ---------------------------------------------------------------------------
# Full NeuroGuard model
# ---------------------------------------------------------------------------

class NeuroGuardModel(nn.Module):
    """
    Hybrid TCN + BiLSTM + Multi-Head Attention risk classifier.

    keystroke_features (B, 20) ──→ KeystrokeTCN  ──→ (B, 128) ─┐
                                                                  ├─ concat (B, 256)
    sleep_features     (B, 15) ──→ SleepBiLSTM   ──→ (B, 128) ─┘
                                                                  │
                                         MultiHeadAttention(8, 256)
                                                                  │
                                         LayerNorm + Dropout(0.4)
                                                                  │
                                      FC(256→128) → ReLU
                                      FC(128→64)  → ReLU
                                      FC(64→1)    → Sigmoid
                                                                  │
                                              risk_score ∈ [0, 1]
    """

    KEYSTROKE_FEATURES = 20
    SLEEP_FEATURES = 15
    FEATURE_NAMES = [
        # Keystroke (20)
        "mean_dwell_ms", "std_dwell_ms", "mean_iki_ms", "std_iki_ms",
        "p25_iki", "p75_iki", "iki_entropy", "typing_speed_wpm",
        "correction_freq", "autocorrect_rate", "rhythm_score",
        "velocity_decay_coeff", "diurnal_var", "session_count_7d",
        "typing_consistency_7d", "bigram_transition_mean", "bigram_transition_std",
        "pause_frequency", "burst_typing_rate", "fatigue_index",
        # Sleep (15)
        "rem_duration_min", "rem_fragmentation_idx", "sleep_efficiency",
        "stage_transition_count", "nocturnal_movement_idx", "hrv_rmssd",
        "resting_hr", "deep_sleep_pct", "awakenings", "sleep_onset_min",
        "rem_7d_trend", "hrv_14d_trend", "sleep_eff_30d_trend",
        "rem_behavior_score", "circadian_regularity_score",
    ]

    def __init__(self, dropout: float = 0.4):
        super().__init__()
        self.keystroke_branch = KeystrokeTCN(input_size=self.KEYSTROKE_FEATURES)
        self.sleep_branch = SleepBiLSTM(input_size=self.SLEEP_FEATURES)

        d_model = 256
        self.attention = nn.MultiheadAttention(embed_dim=d_model, num_heads=8, dropout=0.1, batch_first=True)
        self.layer_norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

        self.classifier = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        keystroke_features: torch.Tensor,
        sleep_features: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            keystroke_features: (B, 20)
            sleep_features:     (B, 15)
        Returns:
            risk_score: (B, 1) ∈ [0, 1]
        """
        ks_out = self.keystroke_branch(keystroke_features)   # (B, 128)
        sl_out = self.sleep_branch(sleep_features)           # (B, 128)

        fused = torch.cat([ks_out, sl_out], dim=-1)          # (B, 256)
        fused_seq = fused.unsqueeze(1)                       # (B, 1, 256) for attention

        attn_out, _ = self.attention(fused_seq, fused_seq, fused_seq)
        attn_out = attn_out.squeeze(1)                       # (B, 256)
        fused = self.layer_norm(fused + attn_out)
        fused = self.dropout(fused)

        return self.classifier(fused)

    def predict_with_uncertainty(
        self,
        keystroke_features: torch.Tensor,
        sleep_features: torch.Tensor,
        n_samples: int = 20,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """MC Dropout uncertainty estimation. Returns (mean, lower_ci, upper_ci)."""
        self.train()  # enable dropout
        with torch.no_grad():
            samples = torch.stack([self(keystroke_features, sleep_features) for _ in range(n_samples)], dim=0)
        self.eval()
        mean = samples.mean(0)
        std = samples.std(0)
        return mean, mean - 1.96 * std, mean + 1.96 * std

    @property
    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
