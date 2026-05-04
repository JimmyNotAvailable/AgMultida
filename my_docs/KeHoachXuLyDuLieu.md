Dưới đây là **kế hoạch tìm kiếm dữ liệu chi tiết** cho pipeline Multimodal AgTech, tập trung vào **dữ liệu thực tế công khai**, không dùng dữ liệu giả lập. Kế hoạch này mở rộng trực tiếp từ hướng đã chốt: Sentinel-2 RGB+NIR, SMAP/ERA5-Land, Open-Meteo/CHIRPS, proxy label FAO-56 + NDVI + soil moisture, alignment và DVC versioning .

# KẾ HOẠCH TÌM KIẾM DỮ LIỆU

## Multimodal AgTech — Water Stress Detection

## 1. Mục tiêu tìm kiếm dữ liệu

Mục tiêu là xây dựng bộ dữ liệu đa phương thức đủ để train model:

```text
Image RGB+NIR [4,224,224]
+ Sensor/Environmental Sequence [48,8]
+ Weather Context [2–6]
+ Stress Label [0,1]
+ Modality Mask
+ Metadata traceable
```

Bộ dữ liệu phải đạt 5 tiêu chí:

| Tiêu chí         | Yêu cầu                                               |
| ---------------- | ----------------------------------------------------- |
| Thực tế          | Dữ liệu đến từ nguồn public/reanalysis/satellite thật |
| Đồng bộ          | Có thể align theo `zone_id`, `timestamp`, `lat/lon`   |
| Research-grade   | Có nguồn rõ ràng, có dataset card, có checksum        |
| Production-ready | Có metadata, missing flag, audit trail                |
| Khả thi 14 ngày  | Ưu tiên nguồn dễ tải bằng API/GEE/Python              |

---

## 2. Phạm vi dữ liệu cần tìm

### 2.1. Nhóm dữ liệu ảnh vệ tinh

**Nguồn ưu tiên:** Sentinel-2 Level-2A Surface Reflectance qua Google Earth Engine hoặc Copernicus/AWS.

Sentinel-2 L2A trên Google Earth Engine có dữ liệu surface reflectance, revisit khoảng 5 ngày và phù hợp để lấy các band B2, B3, B4, B8 cho RGB+NIR. ([Google for Developers][1])

| Thành phần | Band | Vai trò              |
| ---------- | ---: | -------------------- |
| Blue       |   B2 | RGB input            |
| Green      |   B3 | RGB input            |
| Red        |   B4 | RGB input, tính NDVI |
| NIR        |   B8 | Kênh NIR, tính NDVI  |

**Từ khóa tìm kiếm / truy vấn:**

```text
Sentinel-2 L2A surface reflectance Mekong Delta rice field 2023 2024 2025
Sentinel-2 B2 B3 B4 B8 crop stress drought agriculture Vietnam
COPERNICUS/S2_SR_HARMONIZED rice paddy Vietnam cloud mask
```

**Tiêu chí chọn ảnh:**

| Tiêu chí               | Ngưỡng                                                 |
| ---------------------- | ------------------------------------------------------ |
| Cloud cover toàn scene | `< 20–30%`                                             |
| Cloud trong zone crop  | `< 20%` ưu tiên                                        |
| Resolution             | 10m                                                    |
| Band bắt buộc          | B2, B3, B4, B8                                         |
| Thời gian              | Ưu tiên mùa khô và chuyển mùa                          |
| Khu vực                | Đồng bằng sông Cửu Long hoặc vùng trồng lúa tương đồng |

**Khu vực tìm kiếm đề xuất:**

```text
An Giang, Đồng Tháp, Kiên Giang, Long An, Cần Thơ, Sóc Trăng
```

**Output cần thu được:**

```text
raw/sentinel2/
├── zone_id/
│   ├── YYYYMMDD_B2.tif
│   ├── YYYYMMDD_B3.tif
│   ├── YYYYMMDD_B4.tif
│   ├── YYYYMMDD_B8.tif
│   ├── YYYYMMDD_ndvi.tif
│   └── metadata.json
```

---

## 3. Nhóm dữ liệu độ ẩm đất / đất / bốc thoát hơi

### 3.1. SMAP Soil Moisture

**Nguồn ưu tiên:** NASA SMAP L3 Enhanced 9km Soil Moisture.

SMAP L3 cung cấp composite hằng ngày về điều kiện bề mặt đất, gồm soil moisture/water content; bản enhanced L3 có lưới 9km. ([NASA Open Data Portal][2])

| Trường dữ liệu         | Vai trò                       |
| ---------------------- | ----------------------------- |
| Soil moisture          | Proxy chính cho water stress  |
| Retrieval quality flag | Lọc điểm lỗi                  |
| Timestamp daily        | Align với ảnh Sentinel-2      |
| Lat/lon grid           | Spatial interpolation về zone |

**Từ khóa tìm kiếm:**

```text
NASA SMAP L3 9km soil moisture Vietnam Mekong Delta daily
SMAP SPL3SMP_E soil moisture agriculture drought stress
Google Earth Engine NASA SMAP soil moisture 9km
```

**Tiêu chí chọn:**

| Tiêu chí           | Ngưỡng                            |
| ------------------ | --------------------------------- |
| Spatial resolution | 9km                               |
| Temporal           | daily                             |
| Missing rate       | `< 20%` sau gap-fill              |
| Quality flag       | Chỉ giữ retrieval hợp lệ          |
| Phạm vi            | Trùng ngày với Sentinel-2 ±1 ngày |

**Output:**

```text
raw/smap/
├── smap_soil_moisture_daily.parquet
└── smap_quality_report.csv
```

---

### 3.2. ERA5-Land

ERA5-Land cung cấp dữ liệu hourly cho biến bề mặt đất; ECMWF mô tả ERA5-Land là replay của thành phần land trong ERA5 với độ phân giải khoảng 9km và dữ liệu công khai từ 1950 tới gần hiện tại. ([ECMWF][3])

| Biến cần lấy                                | Vai trò                |
| ------------------------------------------- | ---------------------- |
| `2m_temperature`                            | Heat stress            |
| `2m_dewpoint_temperature`                   | Tính humidity proxy    |
| `skin_temperature`                          | Surface heat           |
| `volumetric_soil_water_layer_1`             | Soil moisture tầng mặt |
| `surface_latent_heat_flux` hoặc evaporation | ET proxy               |
| `total_precipitation`                       | Rain relief            |
| `potential_evaporation`                     | ET₀ proxy              |

**Từ khóa tìm kiếm:**

```text
ERA5-Land hourly soil moisture evapotranspiration Vietnam agriculture
ERA5-Land reanalysis 2m temperature soil water precipitation Mekong Delta
ECMWF ERA5-Land hourly data Python CDS API
```

**Tiêu chí chọn:**

| Tiêu chí            | Ngưỡng                                    |
| ------------------- | ----------------------------------------- |
| Temporal resolution | 1 giờ                                     |
| Spatial resolution  | ~9km / 0.1°                               |
| Thời gian           | Trùng Sentinel-2 và SMAP                  |
| Biến bắt buộc       | temperature, precipitation, soil water    |
| Gap                 | Không gap hoặc gap rất thấp do reanalysis |

**Output:**

```text
raw/era5_land/
├── era5_hourly_zone.parquet
├── era5_variables.json
└── era5_download_log.json
```

---

## 4. Nhóm dữ liệu mưa / thời tiết bối cảnh

### 4.1. CHIRPS rainfall

CHIRPS là bộ dữ liệu mưa quasi-global, kéo dài từ 1981 tới gần hiện tại, độ phân giải 0.05°, kết hợp satellite imagery và station data, phù hợp cho drought monitoring. ([Climate Hazards Center][4])

| Biến                   | Vai trò                 |
| ---------------------- | ----------------------- |
| Daily precipitation    | Rain relief             |
| 3-day rainfall sum     | Giảm stress gần hạn     |
| 7-day rainfall anomaly | Bối cảnh hạn            |
| Dry spell length       | Chỉ báo stress tích lũy |

**Từ khóa tìm kiếm:**

```text
CHIRPS daily rainfall Vietnam Mekong Delta drought agriculture
CHIRPS precipitation Google Earth Engine rice drought stress
Climate Hazards Group CHIRPS daily rainfall 0.05 degree
```

**Output:**

```text
raw/chirps/
├── chirps_daily_precip.parquet
└── chirps_anomaly_features.parquet
```

---

### 4.2. Open-Meteo Historical Weather

Open-Meteo Historical Weather API hỗ trợ dữ liệu lịch sử từ 1940, có hourly variables như temperature, relative humidity, precipitation, wind; từ 2017 trở đi dùng weather models mới với độ phân giải 9km. ([Open Meteo][5])

**Dùng Open-Meteo khi cần tải nhanh theo tọa độ zone**, đặc biệt cho prototype.

| Biến cần lấy         | Vai trò           |
| -------------------- | ----------------- |
| temperature_2m       | Heat penalty      |
| relative_humidity_2m | Stress context    |
| precipitation        | Rain relief       |
| wind_speed_10m       | ET context        |
| shortwave_radiation  | Evaporation proxy |
| evapotranspiration   | ET proxy nếu có   |

**Từ khóa / API query:**

```text
Open-Meteo historical weather API hourly temperature humidity precipitation evapotranspiration
Open-Meteo ERA5-Land historical weather agriculture Python
```

**Output:**

```text
raw/open_meteo/
├── zone_weather_hourly.parquet
└── open_meteo_request_log.json
```

---

## 5. Nhóm dữ liệu vùng canh tác / zone polygon

Dữ liệu ảnh và thời tiết chỉ có ích nếu ta có **vùng quan sát rõ ràng**. Vì vậy cần tìm hoặc tự tạo zone polygon.

### 5.1. Nguồn tìm kiếm

| Nguồn                      | Vai trò                               |
| -------------------------- | ------------------------------------- |
| OpenStreetMap              | Tham khảo vùng ruộng, kênh, ranh giới |
| GADM / geoBoundaries       | Ranh giới hành chính                  |
| FAO GAUL                   | Administrative boundaries             |
| GEE crop mask / land cover | Lọc vùng nông nghiệp                  |
| Sentinel-2 manual polygon  | Tự vẽ zone thực nghiệm                |

**Từ khóa tìm kiếm:**

```text
Vietnam Mekong Delta rice field shapefile
Mekong Delta agriculture land cover GeoJSON
Vietnam administrative boundary GADM GeoJSON
Google Earth Engine rice paddy mask Vietnam
```

### 5.2. Tiêu chí chọn zone

| Tiêu chí                  | Ngưỡng                                                     |
| ------------------------- | ---------------------------------------------------------- |
| Số zone Phase 1           | 6–12 zone                                                  |
| Diện tích mỗi zone        | 0.1–5 ha nếu farm-level, hoặc 1–25 km² nếu satellite-level |
| Có Sentinel-2 clear scene | Có ít nhất 10–20 ảnh hợp lệ                                |
| Có chuỗi weather/soil     | Có dữ liệu SMAP/ERA5/CHIRPS đầy đủ                         |
| Không overlap split       | Train/Val/Test tách zone rõ                                |

**Output:**

```text
metadata/zones.geojson
metadata/zone_registry.csv
```

Schema gợi ý:

```csv
zone_id,province,crop_type,lat,lon,area_ha,geometry_path,start_date,end_date
A01,An Giang,rice,10.52,105.12,2.4,zones.geojson,2024-01-01,2024-06-30
```

---

## 6. Nhóm dữ liệu ground truth / proxy label

Vì public dataset thường không có nhãn trực tiếp “water stress”, kế hoạch hiện tại dùng **proxy label** từ NDVI anomaly + soil moisture deficit + ET deficit + rainfall relief. Đây cũng là hướng đã được nêu trong tài liệu: public data không có nhãn stress trực tiếp, nên cần công thức proxy vật lý-nông học để tạo regression target `[0,1]` .

### 6.1. Dữ liệu cần tìm để tạo nhãn

| Thành phần      | Nguồn                                 |
| --------------- | ------------------------------------- |
| NDVI hiện tại   | Sentinel-2 B8, B4                     |
| NDVI baseline   | Sentinel-2 cùng zone trong 30–90 ngày |
| Soil moisture   | SMAP hoặc ERA5-Land                   |
| ET / ET₀ proxy  | ERA5-Land                             |
| Rainfall recent | CHIRPS / Open-Meteo                   |
| Temperature     | ERA5-Land / Open-Meteo                |

### 6.2. Công thức label đề xuất

```python
stress = sigmoid(
    0.40 * soil_moisture_deficit
  + 0.35 * ndvi_anomaly
  + 0.25 * et_deficit
  - 0.15 * rain_relief
  + 0.15 * heat_penalty
)
```

### 6.3. Tiêu chí nghiệm thu label

| Tiêu chí         | Mục tiêu                                         |
| ---------------- | ------------------------------------------------ |
| Label range      | `[0,1]`                                          |
| Healthy/Stressed | Khoảng 55/45 hoặc 60/40                          |
| Smoothness       | Không spike bất thường giữa các ngày gần nhau    |
| Explainability   | Mỗi label trace được về NDVI, SM, ET, rain, temp |
| No look-ahead    | Không dùng dữ liệu sau `t0`                      |

---

## 7. Chiến lược tìm kiếm theo giai đoạn

## Giai đoạn 1 — Chốt AOI và thời gian

**Mục tiêu:** chọn khu vực và khoảng thời gian có đủ dữ liệu sạch.

| Task               | Mô tả                                             | Output                |
| ------------------ | ------------------------------------------------- | --------------------- |
| Chọn AOI           | 6–12 zone ở Mekong Delta hoặc vùng lúa tương đồng | `zones.geojson`       |
| Chọn thời gian     | Ưu tiên 2023–2025, mùa khô/chuyển mùa             | `date_range.yaml`     |
| Check Sentinel-2   | Đếm số scene cloud thấp                           | `s2_availability.csv` |
| Check weather/soil | Kiểm tra SMAP/ERA5/CHIRPS coverage                | `coverage_report.csv` |

**Truy vấn GEE mẫu:**

```javascript
var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(aoi)
  .filterDate("2024-01-01", "2024-06-30")
  .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
  .select(["B2", "B3", "B4", "B8", "SCL"]);
```

---

## Giai đoạn 2 — Tìm và tải dữ liệu ảnh

| Task               | Mô tả                        | Output        |
| ------------------ | ---------------------------- | ------------- |
| Tải Sentinel-2 L2A | B2,B3,B4,B8,SCL              | GeoTIFF       |
| Tính NDVI          | `(B8-B4)/(B8+B4)`            | NDVI raster   |
| Cloud mask         | SCL/s2cloudless              | cloud mask    |
| Crop patch         | Theo zone polygon            | `[224,224,4]` |
| Lưu metadata       | cloud %, date, orbit, source | JSON          |

**Cấu trúc metadata ảnh:**

```json
{
  "sample_id": "A01_20240214_S2",
  "zone_id": "A01",
  "timestamp": "2024-02-14T03:21:00Z",
  "source": "COPERNICUS/S2_SR_HARMONIZED",
  "bands": ["B2", "B3", "B4", "B8"],
  "cloud_rate": 0.12,
  "ndvi_mean": 0.64,
  "patch_path": "raw/sentinel2/A01/20240214_patch.npy"
}
```

---

## Giai đoạn 3 — Tìm và tải dữ liệu soil/weather

| Nguồn      | Tần suất | Vai trò                    |
| ---------- | -------: | -------------------------- |
| SMAP L3    |    daily | soil moisture reference    |
| ERA5-Land  |   hourly | soil water, temp, ET proxy |
| CHIRPS     |    daily | rainfall                   |
| Open-Meteo |   hourly | quick weather context      |

**Feature cần tạo:**

```text
soil_moisture
soil_temp
air_temp
relative_humidity
rain_3h
rain_24h
et0_proxy
wind_speed
```

**Output chuẩn:**

```text
raw/environment/
├── zone_hourly_features.parquet
├── zone_daily_features.parquet
└── feature_quality_report.csv
```

Schema:

```csv
zone_id,timestamp,soil_moisture,soil_temp,air_temp,humidity,rain_3h,rain_24h,et0_proxy,wind_speed,source
A01,2024-02-14T03:00:00Z,0.22,29.4,34.2,61,0.0,1.2,4.8,2.1,ERA5+CHIRPS
```

---

## Giai đoạn 4 — Đồng bộ multimodal sample

Mỗi ảnh Sentinel-2 tại `t0` sẽ kéo theo một cửa sổ sensor/weather `[t0-48h, t0]`, đúng với kiến trúc model GRU 48 giờ.

| Thành phần              | Shape          |
| ----------------------- | -------------- |
| Image                   | `[4,224,224]`  |
| Sensor/weather sequence | `[48,8]`       |
| Weather context         | `[2–6]`        |
| Label                   | scalar `[0,1]` |
| Modality mask           | `[3]`          |

**Quy tắc alignment:**

| Trường hợp                 | Xử lý                              |
| -------------------------- | ---------------------------------- |
| Sentinel-2 có cloud >30%   | Loại hoặc đánh `image_quality=low` |
| Missing hourly weather <3h | Linear interpolation               |
| Missing 3–12h              | Kalman/forward-fill + `gap_flag=1` |
| Missing >12h               | Loại sample                        |
| SMAP daily lệch ngày       | Cho phép ±1 ngày                   |
| Weather sau `t0`           | Không dùng để tránh leakage        |

---

## 8. Bảng ưu tiên nguồn dữ liệu

| Priority | Nguồn                       | Dùng cho          | Lý do                                       |
| -------: | --------------------------- | ----------------- | ------------------------------------------- |
|       P0 | Sentinel-2 L2A              | RGB+NIR, NDVI     | Bắt buộc cho image branch                   |
|       P0 | ERA5-Land                   | hourly sequence   | Ổn định, đủ biến môi trường                 |
|       P0 | CHIRPS                      | rainfall          | Mạnh cho drought/rain relief                |
|       P1 | SMAP L3                     | soil moisture     | Ground truth proxy tốt nhưng resolution thô |
|       P1 | Open-Meteo                  | weather API nhanh | Tốt cho prototype và kiểm tra chéo          |
|       P2 | Local station / IoT sau này | validation        | Phase 2                                     |

---

## 9. Checklist chất lượng dữ liệu sau khi tìm kiếm

| Nhóm kiểm tra | Tiêu chí đạt                                      |
| ------------- | ------------------------------------------------- |
| Coverage      | Mỗi zone có ≥20 sample hợp lệ                     |
| Cloud         | Trung bình cloud trong patch `<20%`               |
| Temporal      | ≥90% sample có đủ 48h window                      |
| Spatial       | Tất cả sample nằm trong zone polygon hợp lệ       |
| Label         | Histogram không lệch cực đoan                     |
| Leakage       | Không dùng weather/ET sau timestamp ảnh           |
| Metadata      | Mỗi sample trace được source, timestamp, checksum |
| Split         | Train/Val/Test tách zone và thời gian             |

---

## 10. Deliverables của riêng phần tìm kiếm dữ liệu

```text
data_search/
├── README_DATA_SOURCES.md
├── sources_registry.yaml
├── zones.geojson
├── date_range.yaml
├── scripts/
│   ├── search_sentinel2_availability.py
│   ├── download_sentinel2_gee.py
│   ├── download_era5_land.py
│   ├── download_smap.py
│   ├── download_chirps.py
│   └── download_open_meteo.py
├── reports/
│   ├── coverage_report.csv
│   ├── cloud_report.csv
│   ├── missing_rate_report.csv
│   └── source_decision_log.md
└── metadata/
    ├── source_cards/
    ├── zone_registry.csv
    └── dataset_search_log.json
```

---

## 11. Lộ trình thực thi 5 ngày cho phần tìm kiếm dữ liệu

|  Ngày | Công việc                                                                        | Output                                          |
| ----: | -------------------------------------------------------------------------------- | ----------------------------------------------- |
| Day 1 | Chốt AOI, zone polygon, date range, kiểm tra Sentinel-2 coverage                 | `zones.geojson`, `s2_availability.csv`          |
| Day 2 | Tải Sentinel-2 B2/B3/B4/B8, tính NDVI, cloud mask                                | `raw/sentinel2/`, `cloud_report.csv`            |
| Day 3 | Tải ERA5-Land + CHIRPS + Open-Meteo theo zone                                    | `zone_hourly_features.parquet`                  |
| Day 4 | Tải SMAP, kiểm tra soil moisture coverage, merge daily/hourly                    | `soil_weather_merged.parquet`                   |
| Day 5 | Tạo search report, source registry, coverage QA, chốt dataset dùng cho alignment | `coverage_report.csv`, `README_DATA_SOURCES.md` |

---

## 12. Kết luận chốt hướng

Phần tìm kiếm dữ liệu nên đi theo chiến lược:

```text
Sentinel-2 làm trục chính
→ mỗi ảnh tại t0 kéo theo 48h ERA5/Open-Meteo/CHIRPS/SMAP
→ tạo proxy label từ NDVI + soil moisture + ET + rain + heat
→ chỉ giữ sample có metadata đầy đủ
→ DVC versioning ngay từ đầu
```

Đây là hướng phù hợp nhất với timeline 14 ngày vì vừa đủ **real-world**, vừa đủ **research-grade**, lại không phụ thuộc vào nhãn thực địa vốn rất khó có ngay trong Phase 1.

[1]: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED?utm_source=chatgpt.com "Harmonized Sentinel-2 MSI: MultiSpectral Instrument ..."
[2]: https://data.nasa.gov/dataset/smap-enhanced-l3-radiometer-global-and-polar-grid-daily-9-km-ease-grid-soil-moisture-v006?utm_source=chatgpt.com "SMAP Enhanced L3 Radiometer Global and Polar Grid ..."
[3]: https://www.ecmwf.int/en/era5-land?utm_source=chatgpt.com "ERA5-Land"
[4]: https://www.chc.ucsb.edu/data/chirps?utm_source=chatgpt.com "CHIRPS: Rainfall Estimates from Rain Gauge and Satellite ..."
[5]: https://open-meteo.com/en/docs/historical-weather-api?utm_source=chatgpt.com "️ Historical Weather API"
Dưới đây là phần **bổ sung “Cách thu thập dữ liệu”** theo dạng có thể đưa thẳng cho **Codex agent** thực thi. Nội dung gồm: **nguồn dữ liệu, cách tải, script cần tạo, input/output, lệnh chạy, tiêu chí kiểm tra**.

---

# BỔ SUNG KẾ HOẠCH THU THẬP DỮ LIỆU

## Multimodal AgTech — Real-World Public Dataset Pipeline

## 1. Mục tiêu của Codex agent

Codex agent cần tạo một pipeline tải dữ liệu thực tế công khai cho bài toán phát hiện stress nước cây trồng, gồm:

```text
1. Sentinel-2 L2A RGB+NIR imagery
2. ERA5-Land hourly weather/soil variables
3. CHIRPS daily rainfall
4. SMAP L3 soil moisture
5. Open-Meteo historical weather fallback
6. Zone polygons + metadata
7. Coverage report + quality report
```

Pipeline phải xuất dữ liệu về cấu trúc:

```text
data/
├── raw/
│   ├── sentinel2/
│   ├── era5_land/
│   ├── chirps/
│   ├── smap/
│   └── open_meteo/
├── metadata/
│   ├── zones.geojson
│   ├── zone_registry.csv
│   ├── source_registry.yaml
│   └── download_log.json
├── reports/
│   ├── coverage_report.csv
│   ├── cloud_report.csv
│   ├── missing_rate_report.csv
│   └── source_quality_report.md
└── interim/
    ├── image_index.parquet
    ├── environment_hourly.parquet
    └── environment_daily.parquet
```

---

# 2. Nguồn dữ liệu và cách tải

## 2.1. Sentinel-2 L2A — ảnh RGB+NIR

### Nguồn

Dùng **Google Earth Engine dataset**:

```text
COPERNICUS/S2_SR_HARMONIZED
```

Dataset này là Sentinel-2 Level-2A Surface Reflectance, có revisit khoảng 5 ngày, phù hợp để lấy B2, B3, B4, B8 cho RGB+NIR. ([Google for Developers][1])

### Band cần tải

| Band | Ý nghĩa                                       | Resolution |
| ---- | --------------------------------------------- | ---------: |
| B2   | Blue                                          |        10m |
| B3   | Green                                         |        10m |
| B4   | Red                                           |        10m |
| B8   | NIR                                           |        10m |
| SCL  | Scene Classification Layer, cloud/shadow mask |        20m |

### Cách tải

Dùng `earthengine-api` + `geemap`.

### Script cần tạo

```text
scripts/download_sentinel2_gee.py
```

### Input

```text
--zones metadata/zones.geojson
--start-date 2024-01-01
--end-date 2024-06-30
--cloud-threshold 30
--output-dir data/raw/sentinel2
```

### Output

```text
data/raw/sentinel2/
├── A01/
│   ├── 20240112_patch.npy
│   ├── 20240112_ndvi.npy
│   ├── 20240112_cloudmask.npy
│   └── 20240112_metadata.json
└── ...
```

### Logic tải

Codex agent cần implement:

```python
# scripts/download_sentinel2_gee.py

import ee
import geemap
import json
import argparse
import numpy as np
from pathlib import Path

def mask_s2_clouds(image):
    scl = image.select("SCL")
    # Keep vegetation, bare soil, water if needed; remove cloud/shadow/snow
    valid = (
        scl.neq(3)   # cloud shadow
        .And(scl.neq(8))   # medium probability cloud
        .And(scl.neq(9))   # high probability cloud
        .And(scl.neq(10))  # cirrus
        .And(scl.neq(11))  # snow/ice
    )
    return image.updateMask(valid)

def add_ndvi(image):
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return image.addBands(ndvi)

def download_sentinel2_for_zone(zone_geom, zone_id, start_date, end_date, cloud_threshold, output_dir):
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(zone_geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        .map(mask_s2_clouds)
        .map(add_ndvi)
        .select(["B2", "B3", "B4", "B8", "NDVI", "SCL"])
    )

    # TODO:
    # 1. Iterate image collection.
    # 2. Clip each image by zone_geom.
    # 3. Export bands as GeoTIFF or numpy array.
    # 4. Resize/crop later to [224,224,4].
    # 5. Save metadata JSON: source, date, cloud %, zone_id, bands.

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zones", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--cloud-threshold", type=float, default=30)
    parser.add_argument("--output-dir", default="data/raw/sentinel2")
    args = parser.parse_args()

    ee.Initialize()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # TODO: load GeoJSON zones and call download_sentinel2_for_zone()

if __name__ == "__main__":
    main()
```

### Lệnh chạy

```bash
python scripts/download_sentinel2_gee.py \
  --zones metadata/zones.geojson \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --cloud-threshold 30 \
  --output-dir data/raw/sentinel2
```

### QA sau tải

Codex agent cần tạo thêm:

```text
scripts/qa_sentinel2.py
```

Kiểm tra:

```text
- Mỗi zone có ít nhất 20 scene hợp lệ
- Cloud rate trung bình < 20–30%
- Mỗi sample có đủ B2, B3, B4, B8
- NDVI nằm trong [-1,1]
- Metadata JSON tồn tại cho mọi patch
```

---

## 2.2. ERA5-Land — dữ liệu hourly soil/weather

### Nguồn

Dùng **Copernicus Climate Data Store — ERA5-Land hourly data**.

ERA5-Land cung cấp dữ liệu hourly từ 1950 tới hiện tại/gần hiện tại, gồm temperature, soil water, radiation, evaporation, runoff, wind, pressure và precipitation. ([Climate Data Store][2])

Có thể tải bằng:

```text
cdsapi
```

Hoặc dùng Google Earth Engine dataset:

```text
ECMWF/ERA5_LAND/HOURLY
```

GEE cũng có ERA5-Land hourly và ghi nhận dataset có các biến từ CDS. ([Google for Developers][3])

### Biến cần tải

| Variable CDS                                         | Tên dùng trong pipeline |
| ---------------------------------------------------- | ----------------------- |
| `2m_temperature`                                     | `air_temp`              |
| `2m_dewpoint_temperature`                            | `dewpoint`              |
| `skin_temperature`                                   | `surface_temp`          |
| `volumetric_soil_water_layer_1`                      | `soil_moisture_l1`      |
| `volumetric_soil_water_layer_2`                      | `soil_moisture_l2`      |
| `total_precipitation`                                | `precipitation`         |
| `potential_evaporation`                              | `et0_proxy`             |
| `10m_u_component_of_wind`, `10m_v_component_of_wind` | `wind_speed`            |

### Script cần tạo

```text
scripts/download_era5_land.py
```

### Input

```text
--zones metadata/zones.geojson
--start-date 2024-01-01
--end-date 2024-06-30
--output-dir data/raw/era5_land
--mode cdsapi
```

### Output

```text
data/raw/era5_land/
├── era5_land_2024_01.nc
├── era5_land_2024_02.nc
├── ...
└── era5_land_zone_hourly.parquet
```

### Logic tải bằng CDS API

Codex agent cần implement:

```python
# scripts/download_era5_land.py

import cdsapi
import argparse
from pathlib import Path

ERA5_VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "skin_temperature",
    "volumetric_soil_water_layer_1",
    "volumetric_soil_water_layer_2",
    "total_precipitation",
    "potential_evaporation",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
]

def download_month(year, month, bbox, output_path):
    """
    bbox format for CDS:
    [north, west, south, east]
    """
    client = cdsapi.Client()
    client.retrieve(
        "reanalysis-era5-land",
        {
            "variable": ERA5_VARIABLES,
            "year": str(year),
            "month": f"{month:02d}",
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": bbox,
        },
        str(output_path),
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zones", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output-dir", default="data/raw/era5_land")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # TODO:
    # 1. Load zones.geojson.
    # 2. Compute bounding box [north, west, south, east].
    # 3. Iterate months.
    # 4. Download NetCDF.
    # 5. Convert NetCDF to zone-level hourly parquet.

if __name__ == "__main__":
    main()
```

### Lệnh chạy

```bash
python scripts/download_era5_land.py \
  --zones metadata/zones.geojson \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --output-dir data/raw/era5_land
```

### Biến môi trường cần có

```bash
# ~/.cdsapirc
url: https://cds.climate.copernicus.eu/api
key: <CDS_API_KEY>
```

### Hậu xử lý ERA5

Codex agent cần tạo:

```text
scripts/process_era5_land.py
```

Output:

```text
data/interim/environment_hourly.parquet
```

Schema:

```csv
zone_id,timestamp,air_temp_c,dewpoint_c,relative_humidity,soil_moisture_l1,soil_moisture_l2,precipitation_mm,et0_proxy,wind_speed
A01,2024-01-01T00:00:00Z,28.4,23.2,73.1,0.31,0.34,0.0,3.2,1.8
```

---

## 2.3. CHIRPS — dữ liệu mưa daily

### Nguồn

Dùng **CHIRPS Daily** từ Climate Hazards Group hoặc GEE dataset:

```text
UCSB-CHG/CHIRPS/DAILY
```

CHIRPS là rainfall dataset quasi-global, từ 1981 tới gần hiện tại, độ phân giải 0.05°, dùng satellite và station data, phù hợp trend analysis và drought monitoring. ([Climate Hazards Center][4])

### Biến cần tải

| Band            | Đơn vị |
| --------------- | ------ |
| `precipitation` | mm/day |

### Script cần tạo

```text
scripts/download_chirps_gee.py
```

### Input

```text
--zones metadata/zones.geojson
--start-date 2024-01-01
--end-date 2024-06-30
--output-dir data/raw/chirps
```

### Output

```text
data/raw/chirps/
├── chirps_daily_zone.parquet
└── chirps_download_log.json
```

### Logic tải

```python
# scripts/download_chirps_gee.py

import ee
import argparse
import pandas as pd
from pathlib import Path

def get_chirps_daily(zone_geom, zone_id, start_date, end_date):
    collection = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterBounds(zone_geom)
        .filterDate(start_date, end_date)
        .select("precipitation")
    )

    # TODO:
    # 1. Reduce each daily image over zone geometry.
    # 2. Extract mean precipitation.
    # 3. Return DataFrame: zone_id, date, precipitation_mm.

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zones", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output-dir", default="data/raw/chirps")
    args = parser.parse_args()

    ee.Initialize()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # TODO: load zones, loop, save parquet.

if __name__ == "__main__":
    main()
```

### Lệnh chạy

```bash
python scripts/download_chirps_gee.py \
  --zones metadata/zones.geojson \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --output-dir data/raw/chirps
```

### Feature cần sinh thêm

```text
rain_1d
rain_3d_sum
rain_7d_sum
dry_spell_days
rain_anomaly_30d
```

---

## 2.4. SMAP L3 — soil moisture daily

### Nguồn

Dùng **NASA SMAP Enhanced L3 Radiometer Global Daily 9 km EASE-Grid Soil Moisture**.

Sản phẩm SMAP Enhanced L3 cung cấp daily estimates về điều kiện bề mặt đất và soil moisture toàn cầu, derived từ SMAP radiometer. ([National Snow and Ice Data Center][5])

Có 2 cách tải:

```text
Option A: NASA Earthdata / NSIDC download
Option B: Google Earth Engine nếu dùng collection có sẵn
```

GEE có collection SMAP `NASA/SMAP/SPL3SMP_E/005`, tuy nhiên bản này trong tài liệu GEE cũ có coverage đến 2023-12-03; nếu cần 2024–2025 nên ưu tiên NSIDC/NASA Earthdata hoặc kiểm tra collection mới. ([Google for Developers][6])

### Biến cần tải

| Variable            | Vai trò                           |
| ------------------- | --------------------------------- |
| soil moisture AM/PM | soil moisture proxy               |
| quality flag        | lọc retrieval lỗi                 |
| surface flag        | loại điểm băng/tuyết/water nếu có |

### Script cần tạo

```text
scripts/download_smap.py
```

### Input

```text
--zones metadata/zones.geojson
--start-date 2024-01-01
--end-date 2024-06-30
--output-dir data/raw/smap
--provider nsidc
```

### Output

```text
data/raw/smap/
├── smap_daily_zone.parquet
├── smap_raw_files/
└── smap_quality_report.csv
```

### Logic khuyến nghị

Vì SMAP tải qua NASA Earthdata thường cần authentication, Codex agent nên hỗ trợ 2 mode:

```text
--provider gee
--provider nsidc
```

### Pseudocode

```python
# scripts/download_smap.py

import argparse
from pathlib import Path

def download_smap_from_gee(zones_path, start_date, end_date, output_dir):
    """
    Use GEE collection if date range is supported.
    Dataset candidate:
    NASA/SMAP/SPL3SMP_E/005
    """
    # TODO:
    # 1. Initialize ee.
    # 2. Load ImageCollection.
    # 3. Filter date/bounds.
    # 4. Reduce over each zone.
    # 5. Save daily soil moisture parquet.

def download_smap_from_nsidc(zones_path, start_date, end_date, output_dir):
    """
    Use NASA Earthdata/NSIDC.
    Requires Earthdata credentials.
    """
    # TODO:
    # 1. Read EARTHDATA_USERNAME and EARTHDATA_PASSWORD from env.
    # 2. Query NSIDC granules by date/bbox.
    # 3. Download HDF5 files.
    # 4. Extract soil moisture and quality flags.
    # 5. Spatially aggregate to zone centroid/bbox.
    # 6. Save daily parquet.

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zones", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output-dir", default="data/raw/smap")
    parser.add_argument("--provider", choices=["gee", "nsidc"], default="nsidc")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    if args.provider == "gee":
        download_smap_from_gee(args.zones, args.start_date, args.end_date, args.output_dir)
    else:
        download_smap_from_nsidc(args.zones, args.start_date, args.end_date, args.output_dir)

if __name__ == "__main__":
    main()
```

### Biến môi trường

```bash
export EARTHDATA_USERNAME="<your_username>"
export EARTHDATA_PASSWORD="<your_password>"
```

### QA

```text
- Có soil_moisture theo ngày cho từng zone
- Missing daily rate < 25%
- Quality flag hợp lệ
- Soil moisture nằm trong range vật lý hợp lý: 0–0.6 m3/m3
```

---

## 2.5. Open-Meteo — historical weather fallback

### Nguồn

Dùng **Open-Meteo Historical Weather API**.

Open-Meteo Historical API cung cấp historical weather từ 1940, có hourly variables như temperature, relative humidity, precipitation, wind; từ 2017 trở đi dùng weather models độ phân giải 9km. ([Open Meteo][7])

### Khi nào dùng?

Dùng khi:

```text
- Cần tải nhanh weather theo lat/lon zone
- ERA5-Land CDS API bị chậm
- Cần fallback để kiểm tra chéo air_temp, rain, humidity
```

### Script cần tạo

```text
scripts/download_open_meteo.py
```

### Input

```text
--zone-registry metadata/zone_registry.csv
--start-date 2024-01-01
--end-date 2024-06-30
--output-dir data/raw/open_meteo
```

### API URL mẫu

```text
https://archive-api.open-meteo.com/v1/archive
```

### Variables

```text
temperature_2m
relative_humidity_2m
dew_point_2m
precipitation
rain
wind_speed_10m
shortwave_radiation
et0_fao_evapotranspiration
```

### Code skeleton

```python
# scripts/download_open_meteo.py

import argparse
import requests
import pandas as pd
from pathlib import Path

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
    "rain",
    "wind_speed_10m",
    "shortwave_radiation",
    "et0_fao_evapotranspiration",
]

def fetch_open_meteo(lat, lon, start_date, end_date):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "UTC",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data["hourly"])
    df = df.rename(columns={"time": "timestamp"})
    return df

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone-registry", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output-dir", default="data/raw/open_meteo")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    zones = pd.read_csv(args.zone_registry)

    frames = []
    for _, row in zones.iterrows():
        df = fetch_open_meteo(row["lat"], row["lon"], args.start_date, args.end_date)
        df["zone_id"] = row["zone_id"]
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(Path(args.output_dir) / "open_meteo_hourly.parquet", index=False)

if __name__ == "__main__":
    main()
```

### Lệnh chạy

```bash
python scripts/download_open_meteo.py \
  --zone-registry metadata/zone_registry.csv \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --output-dir data/raw/open_meteo
```

---

# 3. Zone polygon và zone registry

## 3.1. File bắt buộc

Codex agent cần tạo template:

```text
metadata/zones.geojson
metadata/zone_registry.csv
```

### `zone_registry.csv`

```csv
zone_id,province,crop_type,lat,lon,area_ha,start_date,end_date
A01,An Giang,rice,10.521,105.125,2.4,2024-01-01,2024-06-30
A02,Dong Thap,rice,10.643,105.638,3.1,2024-01-01,2024-06-30
A03,Can Tho,rice,10.034,105.782,2.8,2024-01-01,2024-06-30
```

### `zones.geojson`

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "zone_id": "A01",
        "crop_type": "rice",
        "province": "An Giang"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [105.120, 10.520],
            [105.130, 10.520],
            [105.130, 10.530],
            [105.120, 10.530],
            [105.120, 10.520]
          ]
        ]
      }
    }
  ]
}
```

---

# 4. File cấu hình nguồn dữ liệu

Codex agent cần tạo:

```text
metadata/source_registry.yaml
```

Nội dung:

```yaml
project:
  name: multimodal-agtech-water-stress
  version: v0.1-real-public-data

aoi:
  country: Vietnam
  region: Mekong Delta
  crop_type: rice
  zone_file: metadata/zones.geojson
  zone_registry: metadata/zone_registry.csv

date_range:
  start_date: "2024-01-01"
  end_date: "2024-06-30"

sources:
  sentinel2:
    provider: google_earth_engine
    collection: COPERNICUS/S2_SR_HARMONIZED
    bands: [B2, B3, B4, B8, SCL]
    derived: [NDVI]
    cloud_threshold: 30
    output: data/raw/sentinel2

  era5_land:
    provider: copernicus_cds
    dataset: reanalysis-era5-land
    temporal_resolution: hourly
    variables:
      - 2m_temperature
      - 2m_dewpoint_temperature
      - skin_temperature
      - volumetric_soil_water_layer_1
      - volumetric_soil_water_layer_2
      - total_precipitation
      - potential_evaporation
      - 10m_u_component_of_wind
      - 10m_v_component_of_wind
    output: data/raw/era5_land

  chirps:
    provider: google_earth_engine
    collection: UCSB-CHG/CHIRPS/DAILY
    variable: precipitation
    temporal_resolution: daily
    output: data/raw/chirps

  smap:
    provider: nsidc
    dataset: SPL3SMP_E
    temporal_resolution: daily
    spatial_resolution: 9km
    variables:
      - soil_moisture
      - quality_flag
    output: data/raw/smap

  open_meteo:
    provider: open_meteo_archive_api
    endpoint: https://archive-api.open-meteo.com/v1/archive
    fallback_for: [era5_land]
    variables:
      - temperature_2m
      - relative_humidity_2m
      - dew_point_2m
      - precipitation
      - rain
      - wind_speed_10m
      - shortwave_radiation
      - et0_fao_evapotranspiration
    output: data/raw/open_meteo
```

---

# 5. Master script điều phối tải dữ liệu

Codex agent cần tạo:

```text
scripts/run_data_collection.py
```

Mục tiêu: chạy toàn bộ pipeline theo `source_registry.yaml`.

```python
# scripts/run_data_collection.py

import subprocess
from pathlib import Path

def run(cmd):
    print(f"[RUN] {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/interim").mkdir(parents=True, exist_ok=True)
    Path("data/reports").mkdir(parents=True, exist_ok=True)

    run("""
    python scripts/download_sentinel2_gee.py \
      --zones metadata/zones.geojson \
      --start-date 2024-01-01 \
      --end-date 2024-06-30 \
      --cloud-threshold 30 \
      --output-dir data/raw/sentinel2
    """)

    run("""
    python scripts/download_era5_land.py \
      --zones metadata/zones.geojson \
      --start-date 2024-01-01 \
      --end-date 2024-06-30 \
      --output-dir data/raw/era5_land
    """)

    run("""
    python scripts/download_chirps_gee.py \
      --zones metadata/zones.geojson \
      --start-date 2024-01-01 \
      --end-date 2024-06-30 \
      --output-dir data/raw/chirps
    """)

    run("""
    python scripts/download_smap.py \
      --zones metadata/zones.geojson \
      --start-date 2024-01-01 \
      --end-date 2024-06-30 \
      --output-dir data/raw/smap \
      --provider nsidc
    """)

    run("""
    python scripts/download_open_meteo.py \
      --zone-registry metadata/zone_registry.csv \
      --start-date 2024-01-01 \
      --end-date 2024-06-30 \
      --output-dir data/raw/open_meteo
    """)

    run("python scripts/build_data_coverage_report.py")

if __name__ == "__main__":
    main()
```

Lệnh chạy:

```bash
python scripts/run_data_collection.py
```

---

# 6. Script kiểm tra coverage sau tải

Codex agent cần tạo:

```text
scripts/build_data_coverage_report.py
```

Nhiệm vụ:

```text
1. Đếm số Sentinel-2 scene hợp lệ / zone.
2. Tính cloud rate trung bình / zone.
3. Kiểm tra hourly weather coverage.
4. Kiểm tra daily rainfall coverage.
5. Kiểm tra SMAP missing rate.
6. Xuất coverage_report.csv và source_quality_report.md.
```

Schema output:

```csv
zone_id,s2_scene_count,s2_mean_cloud,era5_hourly_coverage,chirps_daily_coverage,smap_daily_coverage,open_meteo_hourly_coverage,status
A01,24,0.18,0.99,1.00,0.86,1.00,PASS
A02,19,0.23,0.99,1.00,0.82,1.00,WARN
```

Tiêu chí:

```text
PASS nếu:
- s2_scene_count >= 20
- s2_mean_cloud <= 0.30
- era5_hourly_coverage >= 0.95
- chirps_daily_coverage >= 0.95
- smap_daily_coverage >= 0.75
```

---

# 7. Requirements cho Codex agent tạo

Codex agent cần tạo:

```text
requirements-data.txt
```

Nội dung:

```txt
earthengine-api
geemap
geopandas
shapely
rasterio
rioxarray
xarray
netCDF4
h5py
cdsapi
numpy
pandas
pyarrow
requests
tqdm
pyyaml
scikit-learn
```

Setup:

```bash
pip install -r requirements-data.txt
```

Auth cần chuẩn bị:

```bash
# Google Earth Engine
earthengine authenticate

# Copernicus CDS
# Tạo ~/.cdsapirc

# NASA Earthdata
export EARTHDATA_USERNAME="<username>"
export EARTHDATA_PASSWORD="<password>"
```

---

# 8. Prompt hoàn chỉnh để ra lệnh cho Codex agent

Bạn có thể copy nguyên khối này:

```text
Bạn là Senior Data Engineer cho dự án Multimodal AgTech Water Stress Detection.

Hãy tạo pipeline Python thu thập dữ liệu public real-world cho model multimodal gồm Sentinel-2 RGB+NIR, ERA5-Land hourly, CHIRPS rainfall, SMAP soil moisture và Open-Meteo fallback.

Yêu cầu triển khai:

1. Tạo cấu trúc thư mục:
data/raw/sentinel2
data/raw/era5_land
data/raw/chirps
data/raw/smap
data/raw/open_meteo
data/interim
metadata
reports
scripts

2. Tạo file metadata/source_registry.yaml mô tả đầy đủ source:
- Sentinel-2: Google Earth Engine collection COPERNICUS/S2_SR_HARMONIZED, bands B2,B3,B4,B8,SCL, derived NDVI, cloud_threshold=30.
- ERA5-Land: Copernicus CDS dataset reanalysis-era5-land, hourly variables: 2m_temperature, 2m_dewpoint_temperature, skin_temperature, volumetric_soil_water_layer_1, volumetric_soil_water_layer_2, total_precipitation, potential_evaporation, 10m_u_component_of_wind, 10m_v_component_of_wind.
- CHIRPS: GEE collection UCSB-CHG/CHIRPS/DAILY, band precipitation.
- SMAP: NSIDC/NASA Earthdata SPL3SMP_E daily 9km soil moisture. Hỗ trợ mode provider=gee và provider=nsidc.
- Open-Meteo: archive API endpoint https://archive-api.open-meteo.com/v1/archive với variables temperature_2m, relative_humidity_2m, dew_point_2m, precipitation, rain, wind_speed_10m, shortwave_radiation, et0_fao_evapotranspiration.

3. Tạo template:
metadata/zones.geojson
metadata/zone_registry.csv

4. Tạo các script:
scripts/download_sentinel2_gee.py
scripts/download_era5_land.py
scripts/process_era5_land.py
scripts/download_chirps_gee.py
scripts/download_smap.py
scripts/download_open_meteo.py
scripts/build_data_coverage_report.py
scripts/run_data_collection.py

5. Mỗi script phải có argparse đầy đủ, logging rõ ràng, tạo output folder nếu chưa có, và lưu download_log.json.

6. Sentinel-2:
- Dùng earthengine-api.
- Lọc theo zones.geojson, start_date, end_date.
- Lọc CLOUDY_PIXEL_PERCENTAGE < 30.
- Lấy B2,B3,B4,B8,SCL.
- Tính NDVI = (B8-B4)/(B8+B4).
- Cloud mask bằng SCL, loại cloud shadow, cloud medium/high probability, cirrus, snow.
- Export mỗi scene theo zone thành patch .npy hoặc GeoTIFF.
- Lưu metadata JSON gồm sample_id, zone_id, timestamp, source, cloud_rate, bands, ndvi_mean, patch_path.

7. ERA5-Land:
- Dùng cdsapi.
- Tải NetCDF theo tháng cho bbox bao phủ zones.
- Convert NetCDF sang zone-level hourly parquet.
- Tính thêm relative_humidity từ temperature/dewpoint nếu cần.
- Tính wind_speed từ u/v wind.
- Output data/interim/environment_hourly.parquet.

8. CHIRPS:
- Dùng GEE collection UCSB-CHG/CHIRPS/DAILY.
- Reduce precipitation mean theo từng zone mỗi ngày.
- Tạo features rain_1d, rain_3d_sum, rain_7d_sum, dry_spell_days.
- Output data/raw/chirps/chirps_daily_zone.parquet.

9. SMAP:
- Tạo 2 provider:
  a) gee: dùng NASA/SMAP/SPL3SMP_E/005 nếu date range hỗ trợ.
  b) nsidc: dùng Earthdata credentials từ env EARTHDATA_USERNAME và EARTHDATA_PASSWORD.
- Extract soil_moisture và quality flags.
- Aggregate theo zone.
- Output data/raw/smap/smap_daily_zone.parquet và smap_quality_report.csv.

10. Open-Meteo:
- Dùng requests gọi archive API theo lat/lon trong zone_registry.csv.
- Lưu hourly parquet.
- Output data/raw/open_meteo/open_meteo_hourly.parquet.

11. Coverage report:
- Tạo reports/coverage_report.csv gồm:
zone_id, s2_scene_count, s2_mean_cloud, era5_hourly_coverage, chirps_daily_coverage, smap_daily_coverage, open_meteo_hourly_coverage, status.
- PASS nếu:
s2_scene_count >= 20,
s2_mean_cloud <= 0.30,
era5_hourly_coverage >= 0.95,
chirps_daily_coverage >= 0.95,
smap_daily_coverage >= 0.75.
- Tạo reports/source_quality_report.md tóm tắt nguồn nào đạt, nguồn nào fail, lý do.

12. Tạo requirements-data.txt gồm:
earthengine-api, geemap, geopandas, shapely, rasterio, rioxarray, xarray, netCDF4, h5py, cdsapi, numpy, pandas, pyarrow, requests, tqdm, pyyaml, scikit-learn.

13. Tạo README_DATA_COLLECTION.md hướng dẫn:
- Cài dependencies
- Authenticate Google Earth Engine
- Cấu hình ~/.cdsapirc cho CDS
- Cấu hình EARTHDATA_USERNAME/EARTHDATA_PASSWORD
- Chạy python scripts/run_data_collection.py
- Đọc reports/coverage_report.csv

Ưu tiên code chạy được, có error handling, có retry cơ bản cho API/network, và không hard-code absolute path.
```

---

# 9. Gợi ý lệnh chạy cuối cùng

Sau khi Codex agent tạo xong code:

```bash
pip install -r requirements-data.txt

earthengine authenticate

export EARTHDATA_USERNAME="<your_username>"
export EARTHDATA_PASSWORD="<your_password>"

python scripts/run_data_collection.py
```

Sau đó kiểm tra:

```bash
ls data/raw/sentinel2
ls data/raw/era5_land
ls data/raw/chirps
ls data/raw/smap
ls data/raw/open_meteo

cat reports/source_quality_report.md
python -c "import pandas as pd; print(pd.read_csv('reports/coverage_report.csv'))"
```

---

Phần quan trọng nhất để Codex agent không làm lệch hướng là: **Sentinel-2 làm trục sample chính**, mọi nguồn khác phải được tải để align về `zone_id + timestamp`, sau đó mới tạo `[t0-48h, t0]` cho model.

[1]: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED?utm_source=chatgpt.com "Harmonized Sentinel-2 MSI: MultiSpectral Instrument ..."
[2]: https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?utm_source=chatgpt.com "ERA5-Land hourly data from 1950 to present"
[3]: https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY?utm_source=chatgpt.com "ERA5-Land Hourly - ECMWF Climate Reanalysis"
[4]: https://www.chc.ucsb.edu/data/chirps?utm_source=chatgpt.com "CHIRPS: Rainfall Estimates from Rain Gauge and Satellite ..."
[5]: https://nsidc.org/data/spl3smp_e/versions/3?utm_source=chatgpt.com "SMAP Enhanced L3 Radiometer Global Daily 9 km EASE ..."
[6]: https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL3SMP_E_005?utm_source=chatgpt.com "SPL3SMP_E.005 SMAP L3 Radiometer Global Daily 9 km ..."
[7]: https://open-meteo.com/en/docs/historical-weather-api?utm_source=chatgpt.com "️ Historical Weather API"
