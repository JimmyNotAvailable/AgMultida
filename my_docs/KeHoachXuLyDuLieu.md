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
