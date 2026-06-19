"""ParkinsonsDataset — loads and preprocesses UCI + PhysioNet data for supervised pre-training."""

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import Dataset


class ParkinsonsDataset(Dataset):
    """
    Wraps keystroke + sleep feature vectors with Parkinson's labels.

    For pre-training we use public datasets:
    - UCI Parkinson's Telemonitoring (voice/motor): converted to synthetic keystroke proxies
    - PhysioNet Parkinson's mPower: real accelerometer + sleep data

    In production federated training, this class is instantiated on each device
    with the user's local data only.
    """

    KEYSTROKE_COLS = [
        "mean_dwell_ms", "std_dwell_ms", "mean_iki_ms", "std_iki_ms",
        "p25_iki", "p75_iki", "iki_entropy", "typing_speed_wpm",
        "correction_freq", "autocorrect_rate", "rhythm_score",
        "velocity_decay_coeff", "diurnal_var", "session_count_7d",
        "typing_consistency_7d", "bigram_transition_mean", "bigram_transition_std",
        "pause_frequency", "burst_typing_rate", "fatigue_index",
    ]
    SLEEP_COLS = [
        "rem_duration_min", "rem_fragmentation_idx", "sleep_efficiency",
        "stage_transition_count", "nocturnal_movement_idx", "hrv_rmssd",
        "resting_hr", "deep_sleep_pct", "awakenings", "sleep_onset_min",
        "rem_7d_trend", "hrv_14d_trend", "sleep_eff_30d_trend",
        "rem_behavior_score", "circadian_regularity_score",
    ]

    def __init__(self, dataframe: pd.DataFrame, label_col: str = "parkinson_label", fit_scaler: bool = True):
        self.df = dataframe.reset_index(drop=True)
        self.label_col = label_col

        self.ks_scaler = StandardScaler()
        self.sl_scaler = StandardScaler()

        ks_data = self.df[self.KEYSTROKE_COLS].fillna(0).values.astype(np.float32)
        sl_data = self.df[self.SLEEP_COLS].fillna(0).values.astype(np.float32)

        if fit_scaler:
            self.ks_data = self.ks_scaler.fit_transform(ks_data).astype(np.float32)
            self.sl_data = self.sl_scaler.fit_transform(sl_data).astype(np.float32)
        else:
            self.ks_data = ks_data
            self.sl_data = sl_data

        self.labels = self.df[label_col].values.astype(np.float32)

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        return (
            torch.tensor(self.ks_data[idx]),
            torch.tensor(self.sl_data[idx]),
            torch.tensor(self.labels[idx]).unsqueeze(0),
        )

    @classmethod
    def random_split(cls, df: pd.DataFrame, train_frac: float = 0.7, val_frac: float = 0.15):
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        n = len(df)
        n_train = int(n * train_frac)
        n_val = int(n * val_frac)
        train_ds = cls(df.iloc[:n_train])
        val_ds = cls(df.iloc[n_train:n_train + n_val], fit_scaler=False)
        test_ds = cls(df.iloc[n_train + n_val:], fit_scaler=False)
        # Apply train scaler to val/test
        val_ds.ks_scaler = train_ds.ks_scaler
        val_ds.sl_scaler = train_ds.sl_scaler
        val_ds.ks_data = train_ds.ks_scaler.transform(val_ds.ks_data).astype(np.float32)
        val_ds.sl_data = train_ds.sl_scaler.transform(val_ds.sl_data).astype(np.float32)
        test_ds.ks_scaler = train_ds.ks_scaler
        test_ds.sl_scaler = train_ds.sl_scaler
        test_ds.ks_data = train_ds.ks_scaler.transform(test_ds.ks_data).astype(np.float32)
        test_ds.sl_data = train_ds.sl_scaler.transform(test_ds.sl_data).astype(np.float32)
        return train_ds, val_ds, test_ds
