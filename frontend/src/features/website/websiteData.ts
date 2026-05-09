export const keyMetrics = [
  { label: 'Model', value: 'Water Stress AI v1.0' },
  { label: 'Freshness', value: 'Realtime zone refresh' },
  { label: 'Latency', value: '< 500 ms target' },
  { label: 'Mode', value: 'Predict + Recommend + Monitor' },
]

export const productFlows = [
  {
    title: 'Dự đoán stress nước theo vùng',
    input: 'Zone ID + timestamp + dữ liệu ảnh/cảm biến/thời tiết',
    output: 'Stress score, uncertainty, confidence, degraded mode',
    decision: 'Người vận hành thấy rõ mức độ rủi ro trước khi ra lệnh tưới.',
  },
  {
    title: 'Khuyến nghị tưới từ kết quả model',
    input: 'Kết quả prediction + độ ẩm đất + mưa gần hạn',
    output: 'Action, volume mm, reason, require acknowledgement',
    decision: 'Hệ thống giải thích tại sao nên tưới nhẹ, vừa, mạnh hoặc giữ lệnh.',
  },
  {
    title: 'Theo dõi trạng thái vùng trên bản đồ',
    input: 'Chọn polygon vùng trên dashboard',
    output: 'Latest prediction, latest decision, command state, updated time',
    decision: 'Click vào từng vùng là thấy tình trạng vận hành và kết quả model ngay.',
  },
]

export const designPillars = [
  {
    title: 'Visible model outputs',
    copy: 'Mọi thao tác liên quan model đều phải trả kết quả cụ thể trực tiếp trên giao diện thay vì chỉ mô tả chung chung.',
  },
  {
    title: 'Operator-safe decisions',
    copy: 'Khuyến nghị tưới luôn đi kèm lý do, độ tin cậy, và cờ xác nhận khi bất định cao hoặc thiếu nguồn dữ liệu.',
  },
  {
    title: 'Zone-first monitoring',
    copy: 'Bản đồ vùng là bề mặt vận hành chính để người dùng đi từ chọn vùng tới xem prediction, recommendation, và command state.',
  },
]

export const ablationRows = [
  ['Image only', '0.76', '0.12', 'Weak'],
  ['Sensor + Weather', '0.81', '0.09', 'Moderate'],
  ['Cross-attention fusion', '0.87', '0.05', 'Strong'],
]
