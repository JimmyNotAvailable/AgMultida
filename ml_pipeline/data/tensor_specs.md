# Tensor Shape Specifications
## MultimodalAgTech Phase 1 -- BE/ML/FE Sync Document

> **Source of truth:** `contracts/data_contract.yaml` + `contracts/onnx_io_contract.yaml`
> **Synced with:** `ml_pipeline/configs/model.yaml` Section 3.2 of `KeHoachModelDL.md`

---

## Model Inputs

| Name | dtype | Shape | Source | Notes |
|------|-------|-------|--------|-------|
| `image` | float32 | `[B, 4, 224, 224]` | Sentinel-2 B2/B3/B4/B8 | Normalized [0,1]. Channels: Blue, Green, Red, NIR |
| `sensor_seq` | float32 | `[B, 48, 8]` | ERA5-Land + SMAP + CHIRPS | 48h lookback, 1h resolution. Features: soil_moisture, soil_temp, air_temp, humidity, ec, ph, rain_3h, rain_24h |
| `weather_ctx` | float32 | `[B, 6]` | Open-Meteo / ERA5 | Padded to 6 dims. Features: rain_forecast_3h, rain_24h_cum, temp_max, temp_min, humidity_avg, et0_daily |
| `modality_mask` | float32 | `[B, 3]` | Alignment pipeline | [image, sensor, weather]. 1.0=present, 0.0=missing |

## Model Outputs

| Name | dtype | Shape | Post-processing |
|------|-------|-------|-----------------|
| `logits` | float32 | `[B, 1]` | sigmoid -> stress_prob [0,1] |
| `attention_weights` | float32 | `[B, 49]` | 48 sensor timesteps + 1 weather token. Used for XAI payload |

## Internal Embeddings

| Stage | Shape | Description |
|-------|-------|-------------|
| Image embedding | `[B, 256]` | EfficientNet-B3 -> GlobalAvgPool -> Linear(1536, 256) |
| Sensor embedding | `[B, 48, 256]` | GRU(8, 128, 2 layers) -> Linear(128, 256) |
| Weather embedding | `[B, 1, 256]` | MLP(6 -> 64 -> 256) with LayerNorm + GELU |
| Cross-Attention Q | `[B, 1, 256]` | Image embedding unsqueezed |
| Cross-Attention KV | `[B, 49, 256]` | Concat(sensor[B,48,256], weather[B,1,256]) |
| Fusion concat | `[B, 768]` | Concat(img_256, attn_sensor_256, attn_weather_256) |

## Missing Modality Handling

When `modality_mask[i] = 0.0`:
- Zero-fill the corresponding input tensor
- ModalityDropout(p=0.3) during training simulates this
- At inference: `degraded_mode=true`, `uncertainty *= 1.3`

## ONNX Export

- Opset: 17
- Dynamic axes: batch dimension only
- Size budget: <55MB FP32
- MC Dropout: 10 forward passes (dropout kept ON), mean/var computed in Python wrapper
