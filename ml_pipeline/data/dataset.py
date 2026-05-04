"""AgMultidaDataset: torch Dataset wrapping validated AlignedSample instances.

Validates all samples at init time (fail-fast). Each __getitem__ returns
a dict matching MultimodalStressNet.forward() signature plus label tensor.
Collation by default DataLoader produces correct batch shapes.

Synced with: contracts/data_contract.yaml, contracts/onnx_io_contract.yaml
"""
from __future__ import annotations

import torch
from torch.utils.data import Dataset

from ml_pipeline.data.sample import AlignedSample


class AgMultidaDataset(Dataset):
    """Dataset of validated AlignedSamples for DataLoader consumption.

    All samples are validated at construction time. If any sample
    violates the data contract, ValueError propagates immediately.

    __getitem__ returns:
        {
            "image":         [4, 224, 224] float32,
            "sensor_seq":    [48, 8]       float32,
            "weather_ctx":   [6]           float32,
            "modality_mask": [3]           float32,
            "label":         [1]           float32,
        }
    """

    def __init__(self, samples: list[AlignedSample]) -> None:
        if not samples:
            raise ValueError(
                "AgMultidaDataset requires at least one sample. "
                "Got empty list."
            )
        self._samples = samples

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        sample = self._samples[idx]
        result = sample.to_model_dict()
        result["label"] = torch.tensor([sample.label], dtype=torch.float32)
        return result
