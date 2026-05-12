# Hướng dẫn thu thập dữ liệu thô cho hệ thống giám sát cây trồng

Tài liệu này mô tả cách thu thập dữ liệu thô cho một sản phẩm AI nông nghiệp thực tế. Trọng tâm không phải là dùng sẵn dữ liệu đã gắn nhãn, mà là xây dựng bộ dữ liệu gần với điều kiện vận hành thật: camera quan sát cây trồng, cảm biến IoT tại vườn/ruộng/nhà kính, dữ liệu thời tiết và dữ liệu ngữ cảnh.

Ưu tiên dữ liệu:

1. Ảnh cây trồng thô, chưa gắn nhãn hoặc chỉ có nhãn rất nhẹ.
2. Dữ liệu cảm biến IoT dạng chuỗi thời gian.
3. Dữ liệu thời tiết, mưa, độ ẩm đất, vệ tinh chỉ dùng làm ngữ cảnh bổ sung.
4. Nhật ký vận hành như tưới nước, bón phân, phun thuốc, phát hiện sâu bệnh.

Mục tiêu của tài liệu là giúp nhóm triển khai một quy trình thu thập dữ liệu có thể bảo vệ được về mặt học thuật và thực tế sản phẩm.

## 1. Định hướng phạm vi sản phẩm

Không nên bắt đầu với phạm vi quá rộng như “giám sát mọi vùng nông nghiệp bằng vệ tinh”. Phạm vi đó khó chứng minh tính thực tế vì dữ liệu vệ tinh và thời tiết thường không phản ánh đầy đủ trạng thái cây ở cấp độ ruộng nhỏ, luống cây hoặc nhà kính.

Phạm vi phù hợp hơn:

- một nhà kính
- một ruộng nhỏ
- một khu vườn/cánh đồng cố định
- một nhóm luống canh tác
- một vùng trồng có đối tác vận hành thật

Với bối cảnh Việt Nam, có thể chọn một trong các hướng sau:

### 1.1. Hướng ruộng/cánh đồng

Phù hợp với:

- lúa ở Đồng bằng sông Cửu Long
- rau màu ngoài trời
- vườn cây ăn trái
- khu canh tác có hệ thống tưới

Vấn đề thực tế cần theo dõi:

- thiếu nước hoặc ngập úng
- stress nhiệt
- mưa kéo dài
- khô hạn
- xâm nhập mặn
- sâu bệnh xuất hiện theo mùa
- sinh trưởng chậm bất thường

Dữ liệu nên thu:

- ảnh cây/canopy từ camera cố định
- ảnh cận cảnh lá từ điện thoại hoặc camera kiểm tra định kỳ
- nhiệt độ, độ ẩm không khí
- độ ẩm đất
- nhiệt độ đất
- ánh sáng
- lượng mưa/ngữ cảnh mưa từ CHIRPS hoặc trạm địa phương
- lịch tưới/bón phân/phun thuốc

### 1.2. Hướng nhà kính

Phù hợp với:

- rau thủy canh
- cà chua
- dưa lưới
- dưa leo
- ớt
- hoa hoặc cây giá trị cao

Vấn đề thực tế cần theo dõi:

- nhiệt độ trong nhà kính quá cao
- độ ẩm không phù hợp
- CO2 thấp hoặc dao động bất thường
- ánh sáng thiếu hoặc dư
- tưới/fertigation sai lịch
- bệnh lá xuất hiện sớm
- cây sinh trưởng không đồng đều

Dữ liệu nên thu:

- camera cố định nhìn toàn luống
- camera cận cảnh lá/quả nếu có
- nhiệt độ, độ ẩm, CO2
- ánh sáng/PAR
- pH, EC nếu có hệ thủy canh hoặc fertigation
- lịch tưới, lượng tưới, công thức dinh dưỡng
- ghi chú kiểm tra của người vận hành

### 1.3. Khuyến nghị chọn phạm vi MVP

Nếu cần làm nhanh, nên chọn:

```text
1 địa điểm + 1 loại cây + 1 mùa vụ + 2 camera + 2-4 loại cảm biến
```

Ví dụ MVP tốt:

```text
Nhà kính trồng dưa lưới
- 1 camera nhìn tổng thể luống
- 1 camera nhìn cận cảnh tán/lá
- sensor nhiệt độ/độ ẩm
- sensor ánh sáng
- sensor độ ẩm giá thể
- log tưới/fertigation
```

Hoặc:

```text
Ruộng lúa nhỏ ở Đồng bằng sông Cửu Long
- 1 camera cố định nhìn mặt ruộng/canopy
- ảnh điện thoại kiểm tra 2-3 lần/tuần
- sensor nhiệt độ/độ ẩm không khí
- sensor độ ẩm đất/mực nước nếu có
- dữ liệu mưa CHIRPS/Open-Meteo
- log tưới/xả nước/bón phân
```

## 2. Mục tiêu dữ liệu

Bộ dữ liệu cần phục vụ các bài toán sau:

- phát hiện bất thường môi trường
- phát hiện cây có dấu hiệu stress
- học biểu diễn từ ảnh chưa gắn nhãn
- học chuỗi thời gian từ sensor
- kết hợp ảnh + sensor + thời tiết
- gắn nhãn thủ công một phần nhỏ sau khi đã có dữ liệu thô

Không nên cố tạo ngay bộ dữ liệu đã gắn nhãn hoàn chỉnh. Với sản phẩm thực tế, cách hợp lý hơn là:

```text
dữ liệu thô liên tục
→ kiểm tra chất lượng
→ đồng bộ thời gian
→ tự học/self-supervised
→ phát hiện bất thường
→ chọn mẫu quan trọng để gắn nhãn thủ công
```

## 3. Các loại dữ liệu cần thu thập

## 3.1. Ảnh cây trồng thô

Đây là loại dữ liệu quan trọng nhất nếu sản phẩm muốn chứng minh khả năng quan sát tình trạng cây trồng trực tiếp.

Nguồn ảnh:

- camera cố định trong nhà kính
- camera cố định ngoài ruộng
- camera top-view nhìn từ trên xuống
- camera side-view nhìn ngang tán cây
- ảnh điện thoại khi kỹ thuật viên đi kiểm tra
- ảnh drone nếu có điều kiện

Không nên chỉ thu ảnh đã cắt/sửa/sàng lọc. Cần giữ ảnh gốc.

Thông tin cần lưu cho mỗi ảnh:

| Trường | Ý nghĩa |
| --- | --- |
| `image_id` | mã duy nhất của ảnh |
| `timestamp_utc` | thời điểm chụp theo UTC |
| `local_time` | giờ địa phương Việt Nam |
| `timezone` | nên là `Asia/Ho_Chi_Minh` |
| `zone_id` | mã khu vực/luống/ruộng |
| `camera_id` | mã camera |
| `capture_mode` | fixed, handheld, drone |
| `crop_type` | loại cây |
| `growth_stage` | giai đoạn sinh trưởng nếu biết |
| `source` | nguồn dữ liệu |
| `file_path` | đường dẫn file ảnh |
| `width`, `height` | kích thước ảnh |
| `notes` | ghi chú nếu có |

Tần suất khuyến nghị:

| Bối cảnh | Tần suất ảnh |
| --- | --- |
| Nhà kính | 5-15 phút/lần ban ngày |
| Ruộng ngoài trời | 15-60 phút/lần ban ngày |
| Ảnh điện thoại kiểm tra | 1-3 buổi/tuần |
| Drone | 1-4 lần/tháng nếu có |

Lưu ý kỹ thuật:

- cố định góc camera càng lâu càng tốt
- không đổi vị trí camera nếu không ghi log
- tránh chụp ngược sáng quá mạnh
- ghi lại nếu camera bị lau, lệch, thay thiết bị
- không xóa ảnh mờ ngay; nên đánh dấu chất lượng thay vì xóa
- ảnh ban đêm chỉ hữu ích nếu có đèn ổn định

## 3.2. Dữ liệu sensor IoT

Dữ liệu sensor là trục chính để hệ thống hiểu điều kiện môi trường thật.

Các biến nên thu:

| Nhóm | Biến |
| --- | --- |
| Vi khí hậu | nhiệt độ không khí, độ ẩm không khí |
| Ánh sáng | lux, PAR, bức xạ nếu có |
| Đất/giá thể | độ ẩm đất, nhiệt độ đất |
| Dinh dưỡng | pH, EC |
| Nhà kính | CO2, trạng thái quạt, rèm, cửa thông gió |
| Tưới | thời điểm tưới, thời lượng, lượng nước |
| Ngoài trời | mưa, gió, bức xạ, ngập/khô nếu có |

Thông tin cần lưu cho mỗi dòng sensor:

| Trường | Ý nghĩa |
| --- | --- |
| `sensor_id` | mã sensor |
| `timestamp_utc` | thời điểm đo theo UTC |
| `local_time` | giờ Việt Nam |
| `zone_id` | khu vực/luống/ruộng |
| `device_type` | loại thiết bị |
| `variable_name` | tên biến đo |
| `unit` | đơn vị |
| `raw_value` | giá trị thô |
| `quality_flag` | OK/MISSING/OUTLIER/CALIBRATION |
| `sampling_interval` | chu kỳ đo |
| `source` | nguồn dữ liệu |

Tần suất khuyến nghị:

| Loại sensor | Tần suất |
| --- | --- |
| Nhiệt độ/độ ẩm | 5-15 phút/lần |
| Ánh sáng | 5-15 phút/lần |
| CO2 | 5-15 phút/lần |
| Độ ẩm đất | 15-60 phút/lần |
| pH/EC | 15-60 phút/lần hoặc theo chu kỳ tưới |
| Sự kiện tưới | ghi theo sự kiện |

Lưu ý:

- không chỉ lưu giá trị đã trung bình theo ngày
- cần lưu dữ liệu càng thô càng tốt
- sensor mất kết nối phải được ghi là missing, không tự nội suy trong raw data
- khi thay pin/thay sensor/hiệu chuẩn phải ghi log
- không trộn dữ liệu raw và dữ liệu đã xử lý trong cùng một bảng

## 3.3. Dữ liệu thời tiết

Dữ liệu thời tiết chỉ nên dùng làm ngữ cảnh. Không nên xem nó là tín hiệu chính thay cho sensor tại vườn/ruộng.

Nguồn phù hợp:

- Open-Meteo
- ERA5-Land
- CHIRPS
- trạm thời tiết địa phương nếu có
- dữ liệu từ vendor sensor/farm platform

Biến nên thu:

- nhiệt độ không khí
- độ ẩm
- lượng mưa
- gió
- bức xạ mặt trời
- evapotranspiration
- chuỗi ngày khô hạn
- mưa 1 ngày, 3 ngày, 7 ngày, 30 ngày

## 3.4. Dữ liệu vệ tinh/remote sensing

Dữ liệu vệ tinh hữu ích cho ruộng/cánh đồng, nhưng không đủ để chứng minh sản phẩm quan sát cây ở cấp độ thực địa.

Nguồn:

- Sentinel-2 qua AWS Earth Search
- Microsoft Planetary Computer
- Copernicus Data Space
- Sentinel Hub
- Planet hoặc Airbus nếu có ngân sách

Nên thu:

- ảnh Sentinel-2 L2A
- band RGB/NIR
- cloud cover
- thời điểm chụp
- NDVI hoặc chỉ số thực vật khác ở lớp processed, không ghi đè raw

Vai trò:

- bổ sung bối cảnh vùng
- so sánh xu hướng sinh trưởng
- hỗ trợ ruộng ngoài trời
- không phù hợp làm nguồn chính cho nhà kính

## 3.5. Nhật ký vận hành

Nhật ký vận hành rất quan trọng vì nhiều bất thường không thể hiểu nếu chỉ nhìn ảnh/sensor.

Nên ghi:

- tưới nước lúc nào
- bón phân lúc nào
- phun thuốc lúc nào
- thay đổi công thức dinh dưỡng
- cắt tỉa
- phát hiện sâu bệnh
- mất điện
- thiết bị hỏng
- thay camera/sensor
- thu hoạch

Mẫu log tối thiểu:

| Trường | Ý nghĩa |
| --- | --- |
| `event_id` | mã sự kiện |
| `timestamp_utc` | thời điểm |
| `zone_id` | khu vực |
| `event_type` | irrigation, fertilizer, disease, maintenance |
| `description` | mô tả ngắn |
| `operator` | người ghi nếu được phép lưu |
| `confidence` | chắc chắn/tham khảo |

## 4. Nguồn dữ liệu mở/research

Các nguồn này dùng để bootstrap mô hình và pipeline. Không nên xem là thay thế hoàn toàn cho dữ liệu tự thu thập hoặc dữ liệu đối tác.

## 4.1. TERRA-REF

Loại nguồn:

- dataset nghiên cứu mở
- tập trung field phenotyping
- có nhiều loại sensor và ảnh thực địa

Phù hợp cho:

- tiền huấn luyện mô hình ảnh/cảm biến
- thử nghiệm hợp nhất nhiều modality
- mô phỏng bài toán field monitoring

Dữ liệu có thể có:

- ảnh RGB
- hyperspectral
- point cloud
- UAV imagery
- dữ liệu từ ground vehicle/scanner
- metadata theo plot/khu vực/thời gian

Cách thu thập:

1. Xác định crop và mùa vụ phù hợp nhất với bài toán.
2. Ưu tiên tải raw image assets trước.
3. Tải metadata đi kèm: thời gian, plot, sensor, modality.
4. Không chỉnh sửa file gốc.
5. Tạo manifest nội bộ gồm checksum, nguồn, ngày tải, loại dữ liệu.
6. Map plot ID của dataset sang `zone_id` nội bộ.
7. Đánh dấu rõ dữ liệu này không phải dữ liệu Việt Nam.

Ưu điểm:

- dữ liệu giàu modality
- phù hợp pretraining
- tốt hơn dataset chỉ có ảnh đã gắn nhãn

Hạn chế:

- không phản ánh đầy đủ khí hậu Việt Nam
- dung lượng lớn
- xử lý phức tạp
- không đại diện cho nhà kính nếu chọn hướng greenhouse

Khi nên dùng:

- muốn có dữ liệu raw field để thử pipeline
- cần dữ liệu đa cảm biến trước khi có partner
- cần chứng minh hướng multimodal hợp lý

## 4.2. Plant Phenotyping dataset portals

Loại nguồn:

- cổng tổng hợp dataset nghiên cứu về hình thái/sinh trưởng cây
- thường mạnh về ảnh cây

Phù hợp cho:

- ảnh cây chưa gắn nhãn hoặc ít gắn nhãn
- segmentation/counting/growth monitoring
- pretraining image encoder

Cách thu thập:

1. Lọc dataset có ảnh gốc, không chỉ có mask/annotation.
2. Ưu tiên dataset có chuỗi thời gian.
3. Ghi rõ dataset nào đã gắn nhãn, dataset nào raw.
4. Tải ảnh gốc và metadata.
5. Không trộn annotation vào raw folder.
6. Lưu license và điều kiện sử dụng.

Ưu điểm:

- nhiều ảnh cây chất lượng tốt
- dễ dùng cho phần thị giác máy tính
- có thể hỗ trợ mô hình nhận diện sinh trưởng

Hạn chế:

- thường thiếu sensor IoT
- nhiều dataset là benchmark đã gắn nhãn
- môi trường có thể là phòng thí nghiệm, không phải sản xuất thực tế

Khi nên dùng:

- cần dữ liệu ảnh để pretrain
- cần dữ liệu minh họa cho pipeline ảnh
- chưa có đủ ảnh tự thu thập

## 4.3. WUR / Autonomous Greenhouse Challenge

Loại nguồn:

- hệ sinh thái nghiên cứu/challenge về nhà kính tự động
- liên quan climate control, sensor, crop production

Phù hợp cho:

- định hình bài toán greenhouse
- học cách tổ chức dữ liệu sensor nhà kính
- tham khảo biến môi trường và control logs

Dữ liệu có thể có:

- nhiệt độ trong nhà kính
- độ ẩm
- CO2
- radiation
- setpoint điều khiển
- sản lượng hoặc tăng trưởng
- đôi khi có ảnh hoặc dữ liệu phụ trợ

Cách thu thập:

1. Tìm trang challenge, supplementary data, GitHub/repository nếu có.
2. Xác minh dữ liệu raw có public thật không.
3. Nếu chỉ có summary, không xem là nguồn raw chính.
4. Nếu có logs, tải nguyên bản.
5. Chuẩn hóa timezone và greenhouse compartment ID.
6. Tạo data dictionary cho từng biến.

Ưu điểm:

- rất sát hướng greenhouse
- biến sensor/control có ý nghĩa thực tế
- phù hợp làm tham chiếu thiết kế hệ thống

Hạn chế:

- public data có thể không đầy đủ
- ảnh raw không chắc có
- một số dữ liệu có thể nằm trong paper/supplement, không dễ dùng

Khi nên dùng:

- chọn MVP greenhouse
- cần tham khảo cách xây dựng control/sensor dataset
- cần nguồn bổ sung trước khi có dữ liệu đối tác

## 5. Nguồn thời tiết và khí hậu

## 5.1. Open-Meteo

Loại nguồn:

- API thời tiết công khai, dễ dùng
- không cần auth trong nhiều trường hợp

Phù hợp cho:

- lấy dữ liệu thời tiết lịch sử theo tọa độ
- đối chiếu với sensor tại site
- bổ sung feature thời tiết cho mô hình

Dữ liệu nên lấy:

- temperature_2m
- relative_humidity_2m
- dew_point_2m
- precipitation
- rain
- wind_speed_10m
- shortwave_radiation
- et0_fao_evapotranspiration

Cách thu thập:

1. Xác định tọa độ từng `zone_id`.
2. Gọi API theo khoảng ngày.
3. Lưu raw response hoặc CSV/Parquet gốc.
4. Ghi lại toàn bộ request parameters.
5. Đồng bộ về UTC nhưng giữ local date Việt Nam.

Vai trò:

- nguồn thời tiết nền
- fallback khi nguồn khác lỗi
- không thay thế sensor tại ruộng/nhà kính

## 5.2. CHIRPS

Loại nguồn:

- dữ liệu mưa lịch sử
- rất hữu ích với bài toán ruộng/lúa

Phù hợp cho:

- phân tích mưa mùa vụ
- dry spell
- stress nước ngoài đồng
- khu vực Đồng bằng sông Cửu Long

Dữ liệu nên lấy:

- mưa ngày
- tổng mưa 3 ngày
- tổng mưa 7 ngày
- tổng mưa 30 ngày
- số ngày không mưa liên tiếp

Cách thu thập:

1. Xác định AOI hoặc tọa độ zone.
2. Tải dữ liệu mưa ngày theo giai đoạn.
3. Lưu file raster gốc nếu có.
4. Tạo bảng processed riêng cho từng zone.
5. Không dùng trực tiếp CHIRPS làm nhãn stress; chỉ dùng làm feature/ngữ cảnh.

Vai trò:

- rất tốt cho field/rice pilot
- ít giá trị hơn với nhà kính kín

## 5.3. ERA5-Land

Loại nguồn:

- dữ liệu tái phân tích khí hậu
- cần tài khoản Copernicus/CDS

Phù hợp cho:

- backfill lịch sử dài
- biến môi trường cấp vùng
- soil moisture proxy khi chưa có sensor đất

Dữ liệu nên lấy:

- 2m temperature
- 2m dewpoint temperature
- soil water layer 1/2
- total precipitation
- potential evaporation
- wind components

Cách thu thập:

1. Đăng ký tài khoản CDS.
2. Chọn biến và khoảng thời gian.
3. Tải file gốc.
4. Lưu raw riêng.
5. Xử lý thành bảng theo zone ở bước processed.

Vai trò:

- nguồn thời tiết/ngữ cảnh tốt
- không thay thế sensor tại site

## 6. Nguồn vệ tinh và ảnh viễn thám

## 6.1. Sentinel-2 qua STAC providers

Nguồn:

- AWS Earth Search
- Microsoft Planetary Computer
- Copernicus Data Space
- Sentinel Hub

Phù hợp cho:

- field monitoring
- ruộng lúa
- vườn cây
- phân tích xu hướng sinh trưởng cấp vùng

Dữ liệu nên lấy:

- Sentinel-2 L2A
- B02, B03, B04, B08
- SCL/cloud mask
- cloud cover
- acquisition time
- STAC item metadata

Cách thu thập:

1. Xác định polygon AOI.
2. Query STAC theo date range và cloud threshold.
3. Tải asset raw hoặc lưu link asset nếu chưa tải.
4. Lưu STAC item JSON.
5. Tạo image index gồm scene ID, datetime, cloud cover, provider.
6. Tạo NDVI ở processed layer, không ghi đè raw.

Vai trò:

- bổ sung bối cảnh field
- không đủ cho giám sát nhà kính
- không nên là nguồn chính của sản phẩm thực tế

## 6.2. Planet / Airbus

Loại nguồn:

- ảnh vệ tinh thương mại độ phân giải cao

Phù hợp cho:

- field pilot có ngân sách
- cần ảnh tần suất cao hơn Sentinel-2
- vùng canh tác ngoài trời

Cách thu thập:

1. Xin trial/academic access nếu có.
2. Giới hạn AOI nhỏ.
3. Chỉ mua/tải giai đoạn quan trọng.
4. Ghi rõ license, quyền dùng thương mại, quyền train model.
5. Không public ảnh nếu license cấm redistribute.

Vai trò:

- hữu ích nếu có ngân sách
- không cần cho MVP greenhouse đầu tiên

## 7. Nguồn từ nền tảng sensor nông nghiệp

Nhóm này rất quan trọng nếu muốn có dữ liệu sensor gần thực tế.

Nguồn/vendor có thể xem xét:

- Arable
- Pessl / METOS
- CropX
- Teralytic
- Davis Instruments
- các nhà cung cấp sensor nội địa nếu có

Dữ liệu nên xin:

- raw sensor time-series
- metadata trạm/sensor
- vị trí hoặc zone mapping
- log mất kết nối
- log hiệu chuẩn
- lịch sử export
- dữ liệu API nếu có

Câu hỏi cần hỏi vendor:

1. Có API không hay chỉ export CSV?
2. Tần suất raw tối đa là bao nhiêu?
3. Có dữ liệu lịch sử không?
4. Có phân tách theo zone/trạm không?
5. Có ghi nhận missing data không?
6. Có log thay sensor/hiệu chuẩn không?
7. License có cho train model không?
8. Có được lưu trữ dài hạn không?

Cách thu thập:

1. Yêu cầu sample export schema.
2. Xác định biến nào là raw, biến nào đã xử lý.
3. Export dữ liệu tần suất cao nhất được phép.
4. Lưu file export gốc.
5. Tạo mapping từ tên biến vendor sang tên biến nội bộ.
6. Ghi rõ đơn vị đo.
7. Không tự động sửa outlier trong raw data.

Vai trò:

- rất tốt cho sensor stream
- thường thiếu ảnh cây đồng bộ
- cần kết hợp với camera tự lắp hoặc dữ liệu đối tác

## 8. Nguồn từ hệ thống điều khiển nhà kính

Nguồn/vendor tham khảo:

- Priva
- Hoogendoorn
- Ridder
- hệ thống điều khiển nhà kính nội địa nếu có

Dữ liệu nên xin:

- nhiệt độ
- độ ẩm
- CO2
- radiation/light
- trạng thái quạt
- trạng thái rèm
- trạng thái cửa thông gió
- lịch tưới
- fertigation
- setpoints
- compartment ID

Câu hỏi cần hỏi đối tác/vendor:

1. Có export lịch sử theo compartment không?
2. Sensor và control action có cùng timeline không?
3. Có API không?
4. Có camera tích hợp không?
5. Có log tưới/fertigation chi tiết không?
6. Có ghi nhận lỗi thiết bị không?
7. Dữ liệu có được dùng để train model không?

Cách thu thập:

1. Xin raw export theo từng compartment.
2. Giữ nguyên tên biến gốc.
3. Tạo data dictionary.
4. Chuẩn hóa timestamp sang UTC.
5. Lưu thêm timezone/local date.
6. Liên kết với ảnh camera theo `zone_id` và thời gian.

Vai trò:

- nguồn tốt nhất nếu chọn hướng greenhouse
- có tính sản phẩm cao
- cần quyền truy cập từ operator hoặc vendor

## 9. Thu thập qua đối tác thực địa

Đây là nguồn quan trọng nhất nếu muốn chứng minh sản phẩm thực tế.

Đối tác có thể là:

- trường/viện nông nghiệp
- trang trại
- nhà kính thương mại
- hợp tác xã
- doanh nghiệp IoT nông nghiệp
- đơn vị tưới tiêu
- vườn canh tác có kỹ thuật viên ổn định

Nên xin gì từ đối tác:

- quyền lắp camera
- quyền lắp sensor
- quyền truy cập log sensor hiện có
- lịch mùa vụ
- lịch tưới/bón phân/phun thuốc
- ghi chú sâu bệnh
- thông tin thay đổi thiết bị
- thông tin thu hoạch

Pilot tối thiểu:

```text
1 site
1 crop
1 season
1-2 camera
2-4 sensor streams
weekly manual notes
```

Quy trình triển khai:

1. Chọn một site nhỏ, dễ kiểm soát.
2. Đặt `zone_id` cố định cho từng luống/khu vực.
3. Lắp camera ở vị trí không đổi.
4. Lắp sensor đúng độ cao/độ sâu.
5. Đồng bộ giờ thiết bị về UTC.
6. Chụp ảnh theo chu kỳ cố định.
7. Thu sensor theo chu kỳ cố định.
8. Ghi lại mọi can thiệp của con người.
9. Backup dữ liệu mỗi ngày.
10. Kiểm tra thiếu dữ liệu mỗi tuần.

Mẫu thiết bị tối thiểu:

| Thiết bị | Số lượng | Mục đích |
| --- | ---: | --- |
| Camera cố định | 1-2 | ảnh cây/canopy |
| Sensor nhiệt độ/độ ẩm | 1 | vi khí hậu |
| Sensor độ ẩm đất/giá thể | 1-2 | nước trong đất/giá thể |
| Sensor ánh sáng | 1 | ánh sáng/PAR proxy |
| Gateway/Raspberry Pi | 1 | lưu và gửi dữ liệu |

## 10. Tự thu thập dữ liệu pilot

Nếu chưa có đối tác, vẫn nên tự thu pilot nhỏ để chứng minh pipeline.

Cấu hình gợi ý:

- ESP32 hoặc thiết bị tương tự
- Raspberry Pi hoặc mini PC
- camera USB/IP camera
- DHT22/SHT31 cho nhiệt độ/độ ẩm
- capacitive soil moisture sensor
- BH1750 hoặc light sensor tương đương
- optional: CO2 sensor cho nhà kính

Quy trình:

1. Chọn một cây/luống nhỏ.
2. Cố định camera.
3. Đặt sensor ở vị trí ổn định.
4. Ghi ảnh mỗi 10-15 phút ban ngày.
5. Ghi sensor mỗi 5-15 phút.
6. Ghi log tưới/bón phân bằng file CSV hoặc form đơn giản.
7. Không chỉnh sửa ảnh gốc.
8. Mỗi ngày kiểm tra thiết bị có hoạt động không.
9. Mỗi tuần kiểm tra missing data.

Dữ liệu tự thu có giá trị vì:

- đúng bài toán thật
- có thể kiểm soát metadata
- có thể thiết kế đồng bộ ảnh/sensor từ đầu
- dễ giải thích trong báo cáo sản phẩm

Hạn chế:

- cần thời gian
- dữ liệu ít trong giai đoạn đầu
- cần bảo trì thiết bị
- cần kiểm soát privacy nếu camera có thể chụp người

## 11. Quy định privacy, security và license

Trước khi đặt camera:

- phải có sự đồng ý của chủ site
- tránh chụp mặt người, đường công cộng, nhà dân, biển số xe
- nếu không tránh được người trong ảnh, phải hạn chế quyền truy cập
- không public tọa độ chính xác nếu đối tác chưa đồng ý
- không commit ảnh raw nhạy cảm lên repo public
- credential API/vendor phải để ngoài repo
- cần có chính sách lưu trữ và xóa dữ liệu

Trước khi dùng dữ liệu bên thứ ba:

- kiểm tra license có cho research không
- kiểm tra có cho commercial use không
- kiểm tra có cho train model không
- kiểm tra có cho redistribute không
- ghi attribution nếu yêu cầu
- lưu lại điều khoản sử dụng tại thời điểm tải

Nguyên tắc:

```text
Không rõ quyền sử dụng → không dùng cho sản phẩm thương mại.
Không rõ quyền public → không đưa vào demo public.
Không rõ quyền train model → chỉ dùng để nghiên cứu nội bộ.
```

## 12. Cấu trúc lưu trữ dữ liệu

Raw data phải được giữ nguyên. Không ghi đè, không chỉnh sửa trực tiếp.

Cấu trúc khuyến nghị:

```text
data/
  raw/
    images/
      <source>/
        <zone_id>/
          <camera_id>/
            YYYY/
              MM/
                DD/
    sensors/
      <source>/
        <zone_id>/
          <sensor_id>/
            YYYY/
              MM/
    weather/
      <source>/
        <zone_id>/
    satellite/
      <source>/
        <zone_id>/
    operations/
      <source>/
        <zone_id>/
    manifests/
      source_download_log.csv
      checksums.csv
      device_registry.csv
      zone_registry.csv
  processed/
    aligned_samples/
    image_index/
    sensor_features/
    weather_features/
```

Quy tắc:

- `data/raw` chỉ chứa dữ liệu gốc
- `data/processed` chứa dữ liệu đã xử lý
- mọi file raw phải có checksum
- mọi source phải có manifest
- mọi camera/sensor phải có registry

## 13. Metadata tối thiểu

Mỗi source cần ghi:

| Trường | Ý nghĩa |
| --- | --- |
| `source_name` | tên nguồn |
| `source_type` | image, sensor, weather, satellite, operations |
| `provider` | nhà cung cấp |
| `collection_method` | API, export, manual, device |
| `license_or_permission` | quyền sử dụng |
| `downloaded_at_utc` | thời điểm tải |
| `time_range_start_utc` | bắt đầu |
| `time_range_end_utc` | kết thúc |
| `zone_id` | khu vực |
| `device_id` | camera/sensor/scene ID |
| `file_format` | jpg, csv, parquet, tif... |
| `checksum` | mã kiểm tra file |
| `notes` | ghi chú |

## 14. Kiểm tra chất lượng dữ liệu

Trước khi dùng dữ liệu, cần kiểm tra:

- có timestamp không
- timezone có rõ không
- có bị thiếu dữ liệu không
- missing data có được đánh dấu không
- ảnh có bị lỗi file không
- ảnh có metadata camera không
- sensor có đơn vị đo không
- sensor có outlier bất thường không
- thiết bị có bị thay đổi không
- source có license rõ không
- raw data có bị chỉnh sửa không

Không nên loại bỏ dữ liệu lỗi ngay. Nên đánh dấu bằng quality flag:

| Flag | Ý nghĩa |
| --- | --- |
| `OK` | dữ liệu bình thường |
| `MISSING` | thiếu dữ liệu |
| `OUTLIER` | giá trị bất thường |
| `DEVICE_ERROR` | lỗi thiết bị |
| `CALIBRATION` | giai đoạn hiệu chuẩn |
| `LOW_LIGHT` | ảnh thiếu sáng |
| `BLURRY` | ảnh mờ |
| `OCCLUDED` | ảnh bị che |

## 15. Thứ tự ưu tiên theo hướng sản phẩm

## 15.1. Nếu chọn hướng nhà kính

Ưu tiên:

1. dữ liệu đối tác nhà kính
2. camera + sensor tự lắp trong nhà kính
3. dữ liệu từ Priva/Hoogendoorn/Ridder nếu tiếp cận được
4. WUR/Autonomous Greenhouse Challenge để tham khảo
5. Plant Phenotyping datasets cho ảnh cây
6. Open-Meteo/ERA5-Land làm ngữ cảnh bên ngoài

MVP đề xuất:

```text
Smart Greenhouse Crop Monitoring
Input: camera + nhiệt độ + độ ẩm + ánh sáng + CO2/soil moisture
Output: cảnh báo bất thường môi trường và dấu hiệu stress cây
```

## 15.2. Nếu chọn hướng ruộng/cánh đồng

Ưu tiên:

1. dữ liệu đối tác thực địa
2. camera + sensor tự lắp ngoài ruộng
3. TERRA-REF để pretrain/thử nghiệm
4. Sentinel-2 làm ngữ cảnh vùng
5. CHIRPS/Open-Meteo/ERA5-Land làm ngữ cảnh thời tiết

MVP đề xuất:

```text
Field Crop Stress Monitoring
Input: camera cố định + soil moisture + nhiệt độ/độ ẩm + mưa + Sentinel-2
Output: phát hiện bất thường nước/stress/sinh trưởng chậm
```

## 16. Lộ trình triển khai 30-60-90 ngày

### 30 ngày đầu

Mục tiêu: có pipeline dữ liệu chạy được.

Việc cần làm:

1. Chọn scope: greenhouse hoặc field.
2. Chọn crop và site giả định.
3. Tải open datasets: TERRA-REF hoặc Plant Phenotyping.
4. Tải weather context: Open-Meteo, CHIRPS, ERA5-Land nếu có.
5. Thiết kế metadata schema.
6. Tạo raw folder + manifest.
7. Viết script index ảnh và sensor.

Kết quả mong muốn:

- có dữ liệu ảnh thô mẫu
- có dữ liệu weather/satellite ngữ cảnh
- có manifest và metadata
- có pipeline đồng bộ thời gian cơ bản

### 60 ngày đầu

Mục tiêu: có dữ liệu pilot thật hoặc gần thật.

Việc cần làm:

1. Liên hệ ít nhất 1 đối tác.
2. Nếu chưa có đối tác, tự lắp pilot nhỏ.
3. Thu ảnh định kỳ.
4. Thu sensor định kỳ.
5. Ghi nhật ký tưới/bón phân.
6. Kiểm tra missing data hằng tuần.
7. Bắt đầu xây dựng aligned samples.

Kết quả mong muốn:

- có 2-4 tuần dữ liệu ảnh/sensor thật
- có log vận hành tối thiểu
- có dữ liệu đủ để demo phát hiện bất thường đơn giản

### 90 ngày đầu

Mục tiêu: có bộ dữ liệu đủ bảo vệ hướng sản phẩm.

Việc cần làm:

1. Tiếp tục thu dữ liệu đều.
2. Gắn nhãn thủ công một phần nhỏ các ngày/sự kiện quan trọng.
3. Tạo quality report.
4. Tạo dataset card.
5. Huấn luyện baseline self-supervised/anomaly detection.
6. So sánh mô hình chỉ dùng weather/satellite với mô hình dùng camera/sensor.

Kết quả mong muốn:

- chứng minh camera + sensor thực tế hơn weather/satellite-only
- có báo cáo chất lượng dữ liệu
- có cơ sở để phát triển sản phẩm thật

## 17. Những gì không nên xem là đủ

Không nên xem các nguồn sau là đủ cho sản phẩm thực tế:

- chỉ dùng Sentinel-2
- chỉ dùng weather API
- chỉ dùng dataset đã gắn nhãn bệnh cây
- chỉ dùng ảnh benchmark trong phòng lab
- chỉ dùng dữ liệu tổng hợp theo ngày
- chỉ dùng dashboard screenshot thay vì raw export

Lý do:

- sản phẩm cần quan sát trực tiếp cây và môi trường tại site
- dữ liệu đã gắn nhãn sẵn không phản ánh quy trình vận hành thật
- weather/satellite không đủ độ chi tiết cho nhà kính hoặc ruộng nhỏ

## 18. Kết luận khuyến nghị

Hướng dữ liệu tốt nhất cho dự án:

```text
Open datasets để bootstrap
+ weather/satellite làm context
+ partner hoặc self-collected camera/sensor làm dữ liệu lõi
```

Nếu cần chọn một hướng duy nhất, nên chọn:

```text
Nhà kính hoặc ruộng nhỏ có camera + sensor IoT
```

Đây là hướng có tính sản phẩm cao hơn so với chỉ dựa vào Sentinel và dữ liệu thời tiết đã có nhãn.

Chiến lược hợp lý:

1. Dùng TERRA-REF/Plant Phenotyping để có dữ liệu ảnh ban đầu.
2. Dùng Open-Meteo/CHIRPS/ERA5-Land/Sentinel-2 làm context.
3. Tự thu hoặc xin đối tác dữ liệu camera + sensor.
4. Chỉ gắn nhãn một phần nhỏ sau khi đã có dữ liệu raw.
5. Chứng minh mô hình học từ dữ liệu vận hành thực tế, không phụ thuộc vào bộ nhãn có sẵn.
