# Kế Hoạch Tổng Thể: Nghiệm Thu Hiện Tại Và Lộ Trình Phát Triển Module

## 1. Mục đích tài liệu

Tài liệu này dùng để:
- chốt trạng thái phát triển tới thời điểm hiện tại
- làm mốc tạm dừng để tiến hành test nghiệm thu
- tổng hợp những gì đã hoàn thành ở Backend, Frontend, AI/Model, Data
- liệt kê khoảng trống còn lại trước khi tiến tới production
- đề xuất lộ trình phát triển tất cả các module trong các vòng tiếp theo

Tại thời điểm viết tài liệu này, ưu tiên công việc không còn là mở rộng tính năng ngay, mà là **dừng để nghiệm thu kết quả đã có**, xác nhận chất lượng nền tảng, rồi mới tiếp tục các phase sau.

---

## 2. Tóm tắt trạng thái hiện tại

### 2.1. Kết luận ngắn

Hệ thống hiện tại đã đạt mức:
- **chạy được cho internal dev / internal QA / demo kỹ thuật**
- **đủ để kiểm tra nghiệp vụ lõi và luồng admin chính**
- **chưa nên coi là production-ready hoàn chỉnh**

### 2.2. Những gì đã đạt được

#### Backend
- API Gateway đã có các lane chính:
  - `/v1/healthz`
  - `/v1/readyz`
  - `/v1/predict`
  - `/v1/recommend`
  - `/v1/telemetry`
  - `/v1/commands`
  - `/v1/zones`
  - `/v1/zones/{zone_id}/status`
- `/v1/zones` đọc thật từ `metadata/zone_registry.csv`
- zone detail và zone list đã có contract rõ hơn
- admin/backend lane đã có bearer auth thật cho phần lớn route nhạy cảm
- gateway đã có rate limiting cơ bản và có đường nâng cấp `memory|redis`
- gateway đã có CORS allowlist và security headers cơ bản
- websocket `/ws/updates` không còn anonymous open như trước
- AI Serving internal predict đã có internal API key check
- AI Serving readiness cũng đã được khóa bằng internal API key
- readiness phía gateway đã được sanitize để giảm lộ detail nội bộ

#### Frontend
- route `/`, `/dashboard`, `/admin` đã có shape rõ
- admin page không còn là placeholder đơn thuần
- admin có:
  - health/readiness panel
  - zone detail panel
  - zone list/table nhiều zone
  - predict runner
  - recommend runner
  - command runner
- zone row selection đã seed được form thao tác
- frontend API client đã có cơ chế attach bearer token cho protected lanes
- build frontend đang pass
- unit/integration tests frontend đang pass

#### Dữ liệu và metadata
- `metadata/zone_registry.csv` đang là source of truth cho zone list
- `zones.geojson` và registry đã có test đồng bộ
- pipeline xử lý dữ liệu, metadata, synthetic validation zones đã có nền tương đối rõ

#### Kiểm thử hiện tại
- backend tests pass cho các khối chính
- frontend tests pass
- frontend build pass
- hardening tests cho auth / rate limit / websocket / CORS / header pass

---

## 3. Phạm vi nghiệm thu ở thời điểm hiện tại

## 3.1. Mục tiêu nghiệm thu

Mục tiêu nghiệm thu vòng này không phải là xác nhận toàn bộ hệ thống đã sẵn sàng production, mà là xác nhận:

1. nền tảng backend/frontend đã chạy ổn định
2. admin lane chính đã hoạt động end-to-end ở mức kỹ thuật
3. hardening tối thiểu đã có mặt ở các điểm nhạy cảm
4. zone-driven workflow đã hình thành rõ ràng
5. code hiện tại đủ tốt để bước tiếp sang Phase 3.6 và các module sâu hơn

## 3.2. Những gì cần nghiệm thu

### Backend nghiệm thu
- gateway boot ổn định
- healthz hoạt động
- readyz hoạt động đúng shape
- `/v1/zones` trả danh sách zone đúng registry
- `/v1/zones/{zone_id}/status` hoạt động đúng auth
- `/v1/predict`, `/v1/recommend`, `/v1/commands` hoạt động đúng auth
- rate limit hoạt động đúng ở các lane đã gắn
- websocket bị chặn nếu thiếu auth/origin sai
- AI Serving `/internal/predict` chặn sai key
- AI Serving `/readyz` chặn sai key

### Frontend nghiệm thu
- app build được
- admin route bị gate khi không đủ điều kiện
- admin route vào được khi cấu hình hợp lệ
- zone table hiển thị đúng danh sách zone
- chọn zone cập nhật state đúng
- predict -> recommend -> command flow hiển thị đúng
- lỗi hiển thị dạng sanitized, không văng raw internals

### Dữ liệu nghiệm thu
- zone registry đúng shape
- zone IDs khớp dữ liệu metadata hiện có
- registry dùng được như source cho admin table

---

## 4. Checklist nghiệm thu đề xuất

## 4.1. Kiểm tra tự động

### Backend
Chạy:

```bash
pytest "E:/ProjectOnPC/MyProject/AgMultida/tests/backend/test_ai_serving.py" -v
pytest "E:/ProjectOnPC/MyProject/AgMultida/tests/backend/test_config_guardrails.py" -v
pytest "E:/ProjectOnPC/MyProject/AgMultida/tests/backend/test_admin_security.py" -v
pytest "E:/ProjectOnPC/MyProject/AgMultida/tests/backend/test_integration_wiring.py" -v
pytest "E:/ProjectOnPC/MyProject/AgMultida/tests/backend/test_predict_contract.py" -v
pytest "E:/ProjectOnPC/MyProject/AgMultida/tests/backend/test_zone_list_contract.py" -v
```

### Frontend
Chạy:

```bash
npm --prefix "E:/ProjectOnPC/MyProject/AgMultida/frontend" run test
npm --prefix "E:/ProjectOnPC/MyProject/AgMultida/frontend" run build
```

## 4.2. Kiểm tra thủ công

### Gateway / Admin flow
- mở admin route với internal flag + access token hợp lệ
- xác nhận health panel render
- xác nhận readiness panel render sanitized
- xác nhận zone table render đủ zone từ registry
- click từng row để xem active zone cập nhật đúng
- chạy predict
- chạy recommend
- chạy command
- thử sai auth để xem backend trả 401/403 đúng
- thử vượt rate limit để xem backend trả 429 đúng

### WebSocket
- thử connect thiếu auth -> bị chặn
- thử origin không hợp lệ -> bị chặn
- thử auth hợp lệ + origin hợp lệ -> connect được

---

## 5. Đánh giá readiness hiện tại

## 5.1. Backend readiness

### Đã đạt
- service boundaries rõ hơn
- auth đã đi vào lane quan trọng
- basic rate limit đã có
- config guardrails đã có
- zone registry-backed endpoint đã có
- websocket không còn mở public trần

### Chưa đạt mức production hoàn chỉnh
- Redis limiter mới ở mức chuẩn bị kiến trúc, chưa có bài test integration Redis thật
- một số phần vẫn còn tính chất stub
- chưa có battle-tested deploy proxy policy đầy đủ
- readiness/details giữa các service vẫn cần rà thêm cho public deployment
- vẫn còn warning kỹ thuật như `datetime.utcnow()` deprecation cần dọn sau

### Kết luận backend
- **Backend đủ cho internal QA / staging kỹ thuật**
- **Backend chưa nên coi là production-ready hoàn chỉnh**

## 5.2. Frontend readiness

### Đã đạt
- test pass
- build pass
- admin flow cốt lõi có thể thao tác
- zone table và panel đã usable
- protected lanes có token attach

### Chưa đạt mức production hoàn chỉnh
- auth UX hiện còn thiên về dev/internal hơn là user-facing production flow
- token/session model chưa phải mô hình production hoàn chỉnh
- realtime browser path chưa phải sản phẩm hoàn thiện
- chưa có E2E nghiệm thu đầy đủ theo góc nhìn end user / operator thực tế

### Kết luận frontend
- **Frontend đủ cho internal QA / demo kỹ thuật**
- **Frontend chưa đủ production-ready hoàn chỉnh**

## 5.3. Product readiness tổng thể

### Có thể kết luận hiện tại
- **Product hiện tại đã có thể chạy kiểm tra được**
- **Có thể nghiệm thu nội bộ theo từng luồng chính**
- **Chưa nên xem là bản production/public để mở rộng người dùng thực**

---

## 6. Kế hoạch dừng hiện tại để nghiệm thu

## 6.1. Quyết định tạm dừng phát triển

Tại thời điểm này, hợp lý nhất là:
- dừng mở rộng tính năng mới ngay lập tức
- thực hiện nghiệm thu kỹ thuật + nghiệp vụ với trạng thái hiện tại
- ghi nhận bug / gap / UX pain / security note
- chỉ sau đó mới vào Phase tiếp theo

## 6.2. Đầu ra mong muốn từ vòng nghiệm thu

Sau nghiệm thu cần thu được:
- danh sách bug thực tế
- danh sách blocker nếu có
- danh sách việc còn thiếu trước Phase 3.6
- quyết định rõ:
  - tiếp tục làm feature
  - hoặc quay lại hardening / stabilization thêm

---

## 7. Lộ trình phát triển tất cả các module trong tương lai

## 7.1. Module A — API Gateway / Backend Control Plane

### Mục tiêu
Biến gateway thành entry point ổn định, có auth, rate-limit, observability, policy rõ ràng.

### Hướng phát triển tiếp
- hoàn thiện Redis-backed limiter thật
- chuẩn hóa route classification: public/internal/admin/device
- thêm audit trail tốt hơn cho command lane
- thêm structured headers cho rate limit
- chuẩn hóa websocket handshake + policy
- chuẩn hóa DB readiness nếu database lane được bật sâu hơn
- rà lại telemetry lane tách biệt admin/device

### Kết quả mong muốn
- backend đủ ổn định cho staging/prod pilot

---

## 7.2. Module B — Admin Frontend / Ops Console

### Mục tiêu
Biến admin thành công cụ vận hành thực sự cho operator/admin.

### Phase kế tiếp gần nhất
**Phase 3.6**
- bulk selection
- filter
- sort
- table extraction thành component rõ ràng
- action staging tốt hơn

### Phase sau đó
- pagination/virtualization nếu zone count tăng
- command history
- per-zone timeline
- auth/session UX tốt hơn
- error and retry UX tốt hơn
- operator confirmations, audit visualizations

### Kết quả mong muốn
- admin usable cho daily operations nội bộ

---

## 7.3. Module C — Telemetry / Ingestion

### Mục tiêu
Biến telemetry từ stub thành ingestion lane thật.

### Hướng phát triển
- xác định rõ auth model cho device
- ingest path riêng cho sensor/device
- validation/mapping measurements đầy đủ
- persistence layer cho telemetry
- replay / retry / dead-letter strategy
- quality flags cho dữ liệu đầu vào

### Kết quả mong muốn
- data vào hệ thống ổn định, truy vết được, chịu lỗi tốt

---

## 7.4. Module D — AI Serving / Inference

### Mục tiêu
Biến inference lane từ internal service ổn định thành model serving đủ tin cậy cho môi trường gần production.

### Hướng phát triển
- readiness policy rõ hơn
- strict model/manifest guards
- latency budget measurement
- fallback/degraded mode chiến lược rõ
- artifact/version governance
- warmup / load / cache policy
- observability cho inference cost và latency

### Kết quả mong muốn
- AI serving tin cậy, traceable, predictable

---

## 7.5. Module E — Decision Engine / Recommendation Logic

### Mục tiêu
Đảm bảo recommend/action lane minh bạch, kiểm thử tốt, và an toàn.

### Hướng phát triển
- rule transparency tốt hơn
- command safety checks sâu hơn
- bulk command semantics
- audit detail cho từng recommendation/action
- explainability cho operator

### Kết quả mong muốn
- operator hiểu được tại sao hệ thống đề xuất hành động

---

## 7.6. Module F — Command Execution / Actuation

### Mục tiêu
Từ mock command runner đi tới command orchestration thật.

### Hướng phát triển
- command queue thật
- ACK lifecycle thật
- retry/timeout/override handling
- command history storage
- per-device/per-zone execution state
- bulk commands có guardrails

### Kết quả mong muốn
- command lane an toàn, kiểm soát được, audit được

---

## 7.7. Module G — Data Processing / Dataset Pipeline

### Mục tiêu
Chuẩn hóa dữ liệu huấn luyện, metadata, validation set, traceability.

### Hướng phát triển
- hoàn thiện pipeline xử lý dữ liệu
- data lineage rõ
- manifest generation ổn định
- registry/geojson consistency checks mở rộng
- split governance train/val/test tốt hơn
- dữ liệu mới tích hợp mà không phá contract cũ

### Kết quả mong muốn
- data pipeline ổn định cho huấn luyện và serving

---

## 7.8. Module H — Model Training / Experimentation

### Mục tiêu
Tăng chất lượng mô hình và khả năng lặp lại thí nghiệm.

### Hướng phát triển
- training workflow chuẩn hóa
- experiment tracking
- artifact promotion policy
- calibration/uncertainty evaluation tốt hơn
- export path ổn định ONNX / serving compatibility

### Kết quả mong muốn
- model lifecycle bài bản hơn

---

## 7.9. Module I — Database / Persistence

### Mục tiêu
Tạo nền bền vững cho trạng thái hệ thống, audit, history, telemetry, command execution.

### Hướng phát triển
- persistence cho zone state
- persistence cho command history
- persistence cho telemetry
- pool/readiness/integration tests database
- migration strategy

### Kết quả mong muốn
- product không còn phụ thuộc quá nhiều vào stub/in-memory state

---

## 7.10. Module J — Security / Compliance / Production Hardening

### Mục tiêu
Khóa dần các lỗ hổng trước khi mở rộng sử dụng.

### Hướng phát triển
- finalize prod auth/session model
- Redis limiter integration thật
- deploy proxy + HTTPS + HSTS policy hoàn chỉnh
- log redaction review
- secret strength/policy audit
- service-to-service auth review
- threat modeling lại command/telemetry lanes

### Kết quả mong muốn
- sẵn sàng pilot thực tế hoặc production rollout kiểm soát

---

## 7.11. Module K — Testing / QA / Acceptance

### Mục tiêu
Biến việc kiểm tra từ thủ công rời rạc thành quy trình nghiệm thu ổn định.

### Hướng phát triển
- E2E admin flow
- integration tests cho auth/rate limit/websocket
- browser-based operator journey
- regression matrix theo module
- acceptance checklist per milestone

### Kết quả mong muốn
- mỗi phase đều có quality gate rõ ràng

---

## 8. Thứ tự ưu tiên đề xuất sau nghiệm thu

### Ưu tiên 1
- tổng hợp kết quả nghiệm thu hiện tại
- sửa bug/blocker phát hiện trong nghiệm thu

### Ưu tiên 2
- vào **Phase 3.6 Admin UX**:
  - bulk actions
  - filter
  - sort

### Ưu tiên 3
- ổn định telemetry / persistence / queue nền tảng

### Ưu tiên 4
- nâng production hardening thêm một nấc

### Ưu tiên 5
- mở rộng E2E / acceptance framework

---

## 9. Đề xuất cách làm ở phiên tiếp theo

Khi quay lại làm việc sau vòng nghiệm thu, nên đi theo trình tự:

1. đọc lại tài liệu này
2. tổng hợp kết quả nghiệm thu thực tế
3. phân loại:
   - blocker
   - bug
   - UX issue
   - security note
   - deferred improvement
4. chốt có tiếp tục sang Phase 3.6 ngay không
5. nếu không có blocker lớn, bắt đầu Phase 3.6

---

## 10. Kết luận cuối tài liệu

Tính tới thời điểm tạm dừng hiện tại:
- nền tảng backend/frontend đã tiến rất xa so với mức scaffold ban đầu
- hệ thống **đủ để kiểm tra nghiệm thu nội bộ**
- chưa nên coi là production-ready hoàn chỉnh
- bước hợp lý nhất là **dừng phát triển tính năng mới để nghiệm thu**, ghi nhận kết quả, rồi mới mở phase tiếp theo

Tài liệu này là mốc chốt để giữ ngữ cảnh kỹ thuật và định hướng phát triển trong các phiên sau.
