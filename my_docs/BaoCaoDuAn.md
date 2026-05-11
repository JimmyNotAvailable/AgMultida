# BÁO CÁO TỔNG QUAN ĐỀ TÀI AGMULTIDA

## 1. Giới thiệu đề tài

AgMultida là hệ thống nông nghiệp thông minh đa phương thức, được xây dựng nhằm phát hiện sớm tình trạng stress thiếu nước của cây trồng và hỗ trợ đưa ra khuyến nghị tưới tiêu phù hợp cho từng vùng canh tác. Điểm cốt lõi của đề tài là không sử dụng một nguồn dữ liệu đơn lẻ, mà kết hợp đồng thời nhiều nguồn dữ liệu khác nhau gồm ảnh viễn thám, dữ liệu cảm biến môi trường, dữ liệu thời tiết và ngữ cảnh không gian - thời gian.

Trong thực tế sản xuất nông nghiệp, stress thiếu nước là một trong những nguyên nhân chính làm giảm năng suất, suy giảm chất lượng cây trồng và gây lãng phí tài nguyên nước nếu tưới không đúng thời điểm. Vì vậy, việc xây dựng một hệ thống có khả năng nhận biết sớm trạng thái thiếu nước và đưa ra khuyến nghị tưới dựa trên dữ liệu là cần thiết cả về mặt nghiên cứu lẫn ứng dụng.

Đề tài hướng đến hai mục tiêu chính:

- Về mặt nghiên cứu: xây dựng mô hình học sâu đa phương thức để ước lượng mức độ stress nước của cây trồng.
- Về mặt ứng dụng: chuyển đầu ra của mô hình thành khuyến nghị tưới tiêu có thể áp dụng trong vận hành thực tế.

---

## 2. Bài toán của đề tài

### 2.1. Bài toán đặt ra

Bài toán trung tâm của đề tài là: từ dữ liệu ảnh viễn thám, dữ liệu cảm biến đất - môi trường và dữ liệu thời tiết, hệ thống cần đánh giá được mức độ stress thiếu nước của cây trồng theo từng vùng canh tác tại từng thời điểm, sau đó chuyển kết quả này thành quyết định tưới tiêu phù hợp.

Xét về bản chất, đây không phải là bài toán phân loại nhị phân đơn giản kiểu “thiếu nước” hoặc “không thiếu nước”, mà là bài toán ước lượng mức độ stress nước theo thang liên tục trong khoảng từ 0 đến 1. Cách mô hình hóa này phù hợp hơn với thực tế vì trạng thái cây trồng thay đổi theo mức độ, không thay đổi đột ngột theo hai trạng thái tuyệt đối.

### 2.2. Các bài toán con được vận dụng

Để giải quyết bài toán tổng thể, đề tài vận dụng đồng thời nhiều bài toán học máy và xử lý dữ liệu:

1. **Bài toán hồi quy (Regression)**  
   Dùng để dự đoán giá trị liên tục biểu diễn xác suất hoặc mức độ stress nước trong khoảng [0,1].

2. **Bài toán học sâu đa phương thức (Multimodal Deep Learning)**  
   Dùng để học đồng thời từ nhiều nguồn dữ liệu khác bản chất như ảnh, chuỗi thời gian và vector thời tiết.

3. **Bài toán học biểu diễn theo thời gian (Temporal Modeling)**  
   Dùng để mô hình hóa diễn biến độ ẩm đất, nhiệt độ, mưa và các chỉ số môi trường trong một cửa sổ thời gian trước thời điểm dự đoán.

4. **Bài toán hợp nhất đặc trưng (Feature Fusion)**  
   Dùng để kết hợp thông tin giữa các modality nhằm tạo ra biểu diễn tổng hợp giàu thông tin hơn so với từng nguồn riêng lẻ.

5. **Bài toán ước lượng độ bất định (Uncertainty Estimation)**  
   Dùng để đánh giá mức độ tin cậy của mô hình khi đưa ra dự đoán, phục vụ quyết định tưới an toàn hơn.

6. **Bài toán ra quyết định (Decision Support)**  
   Dùng để chuyển đầu ra của mô hình AI thành khuyến nghị vận hành như không tưới, tưới nhẹ, tưới vừa, tưới mạnh hoặc tạm hoãn.

### 2.3. Tại sao lựa chọn các bài toán này

Việc lựa chọn các bài toán trên xuất phát từ đặc thù của bài toán nông nghiệp:

- Stress nước là hiện tượng diễn ra liên tục theo thời gian, vì vậy cần bài toán hồi quy thay vì chỉ phân loại rời rạc.
- Tình trạng cây trồng chịu tác động đồng thời của nhiều yếu tố như trạng thái quang phổ lá, độ ẩm đất, nhiệt độ, lượng mưa và bối cảnh thời tiết; do đó cần mô hình đa phương thức.
- Dữ liệu cảm biến và thời tiết có tính chuỗi thời gian, nên cần thuật toán có khả năng học phụ thuộc theo thời gian.
- Quyết định tưới tiêu là quyết định có rủi ro, do đó không chỉ cần dự đoán mà còn cần biết khi nào mô hình không chắc chắn.
- Trong thực tế dữ liệu thường thiếu hoặc không đồng bộ hoàn toàn, nên mô hình cần có khả năng chịu lỗi và hoạt động trong điều kiện dữ liệu suy giảm.

Như vậy, việc lựa chọn các bài toán và thuật toán trong đề tài không mang tính ngẫu nhiên, mà được xây dựng trực tiếp từ yêu cầu thực tiễn của bài toán phát hiện stress nước và hỗ trợ tưới tiêu.

---

## 3. Bộ dữ liệu sử dụng

### 3.1. Tổng quan bộ dữ liệu

Đề tài sử dụng bộ dữ liệu đa nguồn, gồm bốn nhóm chính:

1. Dữ liệu ảnh viễn thám
2. Dữ liệu cảm biến và môi trường
3. Dữ liệu thời tiết
4. Dữ liệu không gian vùng canh tác

Mỗi nhóm dữ liệu đóng một vai trò khác nhau trong việc mô tả trạng thái cây trồng và điều kiện canh tác.

### 3.2. Dữ liệu ảnh viễn thám

Nguồn ảnh chính được sử dụng là **Sentinel-2 L2A**. Đây là loại ảnh vệ tinh quang học có độ phủ rộng, được hiệu chỉnh khí quyển, phù hợp cho các bài toán theo dõi thảm thực vật.

Các kênh phổ chính được sử dụng gồm:

- B2
- B3
- B4
- B8

Ý nghĩa của từng nhóm kênh:

- B2, B3, B4 phản ánh thông tin phổ trong vùng nhìn thấy, giúp mô tả bề mặt và hiện trạng quan sát trực quan.
- B8 là kênh cận hồng ngoại (NIR), đặc biệt quan trọng trong giám sát thực vật vì phản ánh mạnh trạng thái sinh lý của cây.

Việc lựa chọn ảnh 4 kênh thay vì RGB thông thường giúp mô hình học tốt hơn các dấu hiệu liên quan đến sức khỏe thực vật và stress nước.

### 3.3. Dữ liệu cảm biến và môi trường

Nhóm dữ liệu này phản ánh trực tiếp trạng thái đất và môi trường gần mặt đất. Các biến đầu vào chính gồm:

- soil_moisture
- soil_temp
- air_temp
- humidity
- ec
- ph
- rain_3h
- rain_24h

Vai trò của nhóm dữ liệu này là cung cấp thông tin động theo thời gian, đặc biệt là xu hướng suy giảm hoặc phục hồi độ ẩm đất, vốn là tín hiệu rất quan trọng để phát hiện stress nước.

### 3.4. Dữ liệu thời tiết

Các nguồn thời tiết được khai thác gồm:

- ERA5-Land
- CHIRPS
- Open-Meteo

Các đặc trưng thời tiết tổng hợp gồm:

- rain_forecast_3h
- rain_24h_cumulative
- temp_max_24h
- temp_min_24h
- humidity_avg_24h
- et0_daily

Nhóm dữ liệu này giúp cung cấp bối cảnh khí tượng, từ đó làm rõ nguyên nhân và xu hướng của stress nước. Ví dụ, cùng một mức độ ẩm đất nhưng nếu sắp có mưa lớn thì quyết định tưới có thể khác hoàn toàn so với trường hợp nắng nóng kéo dài.

### 3.5. Dữ liệu không gian vùng canh tác

Dữ liệu không gian gồm:

- zone polygons
- registry vùng canh tác
- metadata địa lý

Dữ liệu này đóng vai trò xác định đơn vị phân tích là từng vùng (zone), giúp gom dữ liệu theo không gian, đồng bộ mẫu học máy và hiển thị kết quả trên dashboard bản đồ.

---

## 4. Đặc trưng dữ liệu đầu vào

### 4.1. Đặc trưng ảnh

Đầu vào ảnh được biểu diễn dưới dạng tensor kích thước:

- `[B, 4, 224, 224]`

Trong đó:

- `B` là kích thước batch
- `4` là số kênh phổ sử dụng
- `224 x 224` là kích thước ảnh sau chuẩn hóa

Các giá trị ảnh được đưa về dạng `float32` và chuẩn hóa về khoảng phù hợp để mô hình học ổn định.

### 4.2. Đặc trưng chuỗi thời gian

Dữ liệu cảm biến được biểu diễn dưới dạng tensor:

- `[B, 48, 8]`

Ý nghĩa:

- 48 mốc thời gian liên tiếp
- 8 đặc trưng tại mỗi mốc
- tương ứng cửa sổ quan sát 48 giờ trước thời điểm dự đoán

Biểu diễn này cho phép mô hình học xu hướng biến đổi theo thời gian, thay vì chỉ nhìn vào một thời điểm tĩnh.

### 4.3. Đặc trưng thời tiết

Dữ liệu thời tiết được biểu diễn dưới dạng vector 6 chiều. Đây là dạng đặc trưng tổng hợp, phản ánh bối cảnh khí tượng ngắn hạn và trung hạn trước hoặc gần thời điểm dự đoán.

### 4.4. Đặc trưng phụ trợ

Ngoài ba nhóm chính, mỗi mẫu còn có thêm:

- modality mask
- zone_id
- timestamp
- metadata truy vết

Trong đó, `modality mask` có vai trò đánh dấu modality nào đang có hoặc thiếu dữ liệu tại thời điểm suy luận.

---

## 5. Tiền xử lý dữ liệu

### 5.1. Tiền xử lý ảnh viễn thám

Dữ liệu ảnh được xử lý qua các bước:

1. Cắt ảnh theo vùng canh tác tương ứng.
2. Lấy đúng 4 kênh phổ cần thiết: B2, B3, B4, B8.
3. Resize hoặc crop về kích thước chuẩn 224x224.
4. Chuyển dữ liệu về dạng số thực.
5. Chuẩn hóa giá trị ảnh để đưa về cùng thang đo.

Mục tiêu của bước này là làm đồng nhất đầu vào, giảm nhiễu do khác biệt kích thước và đảm bảo mô hình học ổn định.

### 5.2. Tiền xử lý dữ liệu chuỗi thời gian

Dữ liệu cảm biến và môi trường được xử lý qua các bước:

1. Resample theo đơn vị giờ.
2. Xây dựng cửa sổ lookback 48 giờ.
3. Chuẩn hóa từng đặc trưng bằng Min-Max Scaling hoặc chuẩn hóa tương đương.
4. Cắt ngưỡng ngoại lai nhằm giảm ảnh hưởng của dữ liệu bất thường.
5. Sắp xếp dữ liệu theo đúng thứ tự thời gian.

Bước này giúp thuật toán GRU học được xu hướng biến đổi theo thời gian mà không bị lệch bởi khác biệt thang đo giữa các biến.

### 5.3. Tiền xử lý dữ liệu thời tiết

Dữ liệu thời tiết được tổng hợp theo khoảng thời gian phù hợp và biến đổi thành các đặc trưng thống kê như lượng mưa tích lũy, nhiệt độ cực đại, nhiệt độ cực tiểu, độ ẩm trung bình và ET0 hằng ngày. Điều này giúp giảm nhiễu và tăng tính khái quát cho nhánh thời tiết của mô hình.

### 5.4. Đồng bộ dữ liệu đa nguồn

Đây là bước rất quan trọng của đề tài. Các nguồn dữ liệu khác nhau được đồng bộ theo:

- `zone_id`
- `timestamp`

Ảnh Sentinel-2 được sử dụng làm mốc chính theo thời điểm quan sát. Các nguồn khác như cảm biến và thời tiết được căn chỉnh về cùng trục không gian - thời gian để tạo mẫu học máy thống nhất.

### 5.5. Xử lý thiếu dữ liệu

Trong thực tế, hệ thống đa nguồn thường gặp tình trạng thiếu dữ liệu do ảnh bị mây che, cảm biến lỗi hoặc nguồn thời tiết cập nhật chậm. Đề tài xử lý bằng các cách:

- zero-fill ở mức đầu vào
- sử dụng `modality mask`
- huấn luyện với `modality dropout`

Nhờ đó, mô hình không phụ thuộc tuyệt đối vào việc tất cả các nguồn dữ liệu đều đầy đủ.

### 5.6. Chống rò rỉ dữ liệu

Dữ liệu được chia theo nguyên tắc không gian - thời gian, nhằm:

- tránh rò rỉ thông tin giữa train/validation/test
- phản ánh sát hơn điều kiện vận hành thực tế

Đây là bước cần thiết để việc đánh giá mô hình có ý nghĩa hơn so với chia ngẫu nhiên đơn giản.

---

## 6. Xây dựng nhãn (Label)

### 6.1. Đặc điểm của nhãn

Trong giai đoạn hiện tại, nhãn của đề tài được xây dựng theo dạng **proxy label**, chưa phải nhãn thực địa đo trực tiếp đầy đủ trên quy mô lớn. Đây là cách tiếp cận hợp lý trong bối cảnh bài toán nông nghiệp thường thiếu ground-truth chuẩn hóa và tốn chi phí thu thập.

### 6.2. Công thức xây dựng nhãn stress

Nhãn stress được tổng hợp từ các thành phần:

- soil_moisture_deficit
- ndvi_anomaly
- et_deficit
- rain_relief
- heat_penalty

Các thành phần này được kết hợp theo trọng số:

- soil_moisture_deficit: 0.40
- ndvi_anomaly: 0.35
- et_deficit: 0.25
- rain_relief: -0.15
- heat_penalty: 0.15

Sau đó, tổng hợp được đưa qua hàm sigmoid để thu được giá trị trong khoảng [0,1].

### 6.3. Ý nghĩa và hạn chế

Cách xây dựng proxy label có ý nghĩa ở chỗ:

- tận dụng tri thức miền nông nghiệp để xây dựng nhãn khi chưa có nhãn đầy đủ
- cho phép triển khai nghiên cứu và huấn luyện mô hình ở giai đoạn đầu
- phản ánh phần nào mức độ stress nước theo logic vật lý - sinh lý cây trồng

Tuy nhiên, hạn chế là:

- nhãn không hoàn toàn tương đương ground-truth ngoài thực địa
- có thể mang sai số tích lũy từ các chỉ số thành phần
- cần được cải thiện bằng dữ liệu đo thực địa trong các giai đoạn tiếp theo

---

## 7. Mô hình Deep Learning sử dụng trong đề tài

### 7.1. Mô hình tổng thể

Mô hình chính được sử dụng trong đề tài là **MultimodalStressNet**. Đây là mô hình học sâu đa nhánh, được thiết kế để tiếp nhận đồng thời ba loại dữ liệu:

1. Ảnh viễn thám
2. Chuỗi thời gian cảm biến - môi trường
3. Vector thời tiết

Kiến trúc tổng thể gồm các khối:

- Image Encoder
- Temporal Encoder
- Weather Encoder
- Cross-Attention Fusion
- Output Head
- Uncertainty Estimation

Đầu ra cuối cùng của mô hình gồm:

- `stress_prob`: xác suất hoặc mức độ stress nước
- `uncertainty`: độ bất định của dự đoán
- các thông tin giải thích như attention weights hoặc confidence flag

---

## 8. Lý thuyết và thuật toán sử dụng trong mô hình

### 8.1. CNN và EfficientNet-B3 cho nhánh ảnh

#### a) Lý thuyết CNN

Mạng tích chập (Convolutional Neural Network - CNN) là loại mạng nơ-ron đặc biệt hiệu quả trong xử lý ảnh. CNN hoạt động dựa trên các lớp tích chập để học đặc trưng không gian từ dữ liệu ảnh, từ các đặc trưng mức thấp như biên, góc, texture đến các đặc trưng mức cao hơn như cấu trúc bề mặt, vùng thực vật và kiểu phản xạ phổ.

Ưu điểm của CNN:

- khai thác tốt cấu trúc không gian cục bộ
- giảm số lượng tham số nhờ chia sẻ kernel
- học đặc trưng ảnh tốt hơn so với các mô hình truyền thống thủ công

#### b) Lý thuyết EfficientNet

EfficientNet là họ mô hình CNN tối ưu bằng cơ chế **compound scaling**, tức là mở rộng đồng thời chiều sâu, chiều rộng và độ phân giải đầu vào theo cách cân bằng. So với nhiều backbone CNN truyền thống, EfficientNet cho hiệu quả tốt với chi phí tính toán hợp lý.

Trong đề tài, **EfficientNet-B3** được chọn vì:

- đủ mạnh để trích xuất đặc trưng ảnh đa phổ
- chi phí tính toán vừa phải
- phù hợp triển khai thực nghiệm và suy luận
- đạt cân bằng tốt giữa độ chính xác và tốc độ

#### c) Cách vận dụng trong đề tài

Trong đề tài, EfficientNet-B3 được dùng làm **image encoder** cho ảnh Sentinel-2 4 kênh. Nhiệm vụ của nhánh này là học các mẫu không gian và phổ liên quan đến sức khỏe cây trồng, chẳng hạn:

- sự thay đổi phản xạ của thảm thực vật
- dấu hiệu suy giảm sinh trưởng
- trạng thái khô hạn trên bề mặt vùng canh tác

Nhờ đó, nhánh ảnh đóng vai trò cung cấp thông tin trực quan và quang phổ về hiện trạng cây trồng.

### 8.2. GRU cho nhánh chuỗi thời gian

#### a) Lý thuyết RNN và GRU

RNN (Recurrent Neural Network) là mô hình dành cho dữ liệu tuần tự, có khả năng ghi nhớ thông tin từ các bước thời gian trước. Tuy nhiên, RNN cơ bản dễ gặp hiện tượng mất gradient khi chuỗi dài.

GRU (Gated Recurrent Unit) là biến thể cải tiến của RNN, sử dụng các cổng để kiểm soát việc cập nhật và ghi nhớ trạng thái ẩn. So với LSTM, GRU có cấu trúc đơn giản hơn, ít tham số hơn nhưng vẫn học tốt quan hệ theo thời gian.

Ưu điểm của GRU:

- học phụ thuộc thời gian hiệu quả
- nhẹ hơn LSTM
- phù hợp với chuỗi thời gian ngắn và trung bình
- dễ huấn luyện hơn trong nhiều bài toán thực tế

#### b) Cách vận dụng trong đề tài

Trong đề tài, dữ liệu cảm biến được tổ chức thành chuỗi 48 giờ gần nhất trước thời điểm dự đoán. GRU 2 lớp được sử dụng để học:

- xu hướng giảm hoặc tăng độ ẩm đất
- mối liên hệ giữa mưa, nhiệt độ, độ ẩm không khí và trạng thái cây trồng
- động thái thay đổi của môi trường gần thời điểm đánh giá

Lý do chọn GRU thay vì chỉ dùng MLP hoặc thống kê thủ công là vì stress nước không chỉ phụ thuộc giá trị tức thời mà còn phụ thuộc xu hướng biến đổi theo thời gian.

### 8.3. Attention cho chuỗi thời gian

#### a) Lý thuyết Attention

Cơ chế attention cho phép mô hình học cách “chú ý” nhiều hơn vào những thành phần quan trọng trong đầu vào, thay vì xem mọi thời điểm đều có tầm quan trọng như nhau.

Trong bài toán chuỗi thời gian, attention giúp mô hình xác định:

- mốc thời gian nào ảnh hưởng mạnh nhất đến dự đoán hiện tại
- biến động nào trong quá khứ gần cần được ưu tiên

#### b) Cách vận dụng trong đề tài

Attention được đặt lên trên đầu ra của GRU để giúp mô hình tập trung nhiều hơn vào các thời điểm quan trọng, ví dụ:

- độ ẩm đất giảm mạnh gần thời điểm hiện tại
- mưa vừa xảy ra nhưng chưa đủ để phục hồi độ ẩm
- nhiệt độ tăng cao trong khoảng ngắn trước thời điểm dự đoán

Nhờ attention, mô hình không bị phụ thuộc cứng nhắc vào việc gộp toàn bộ chuỗi theo cách đồng đều.

### 8.4. MLP cho nhánh thời tiết

#### a) Lý thuyết MLP

MLP (Multilayer Perceptron) là mạng nơ-ron truyền thẳng nhiều lớp, phù hợp với dữ liệu vector có số chiều cố định. MLP học các quan hệ phi tuyến giữa các biến đầu vào và đầu ra thông qua nhiều lớp fully connected kết hợp hàm kích hoạt phi tuyến.

#### b) Cách vận dụng trong đề tài

Nhánh thời tiết nhận vào vector 6 chiều gồm các chỉ số khí tượng tổng hợp. MLP được dùng để mã hóa các đặc trưng này thành embedding thời tiết. Lý do dùng MLP là vì dữ liệu thời tiết ở đây đã ở dạng đặc trưng tổng hợp, không cần xử lý không gian như ảnh, cũng không cần phụ thuộc dài theo chuỗi như GRU.

### 8.5. Cross-Attention Fusion

#### a) Lý thuyết cross-attention

Cross-attention là cơ chế cho phép một nguồn dữ liệu này học cách tham chiếu sang nguồn dữ liệu khác. Không giống phép nối vector đơn thuần (concatenation), cross-attention có khả năng học mối quan hệ phụ thuộc giữa các modality.

Về nguyên lý:

- Query lấy từ một nguồn đặc trưng
- Key và Value lấy từ nguồn đặc trưng khác
- Attention score xác định mức độ liên quan giữa các nguồn

Nhờ đó, mô hình không chỉ gộp thông tin mà còn học cách liên hệ thông tin giữa các nguồn với nhau.

#### b) Cách vận dụng trong đề tài

Trong đề tài:

- embedding ảnh đóng vai trò query
- chuỗi cảm biến và token thời tiết đóng vai trò context

Cách thiết kế này cho phép mô hình học các mối liên hệ kiểu:

- cùng một ảnh hiện tại nhưng nếu 48 giờ qua độ ẩm đất giảm liên tục thì khả năng stress cao hơn
- cùng một biểu hiện thực vật trên ảnh nhưng nếu sắp có mưa lớn thì mức độ ưu tiên tưới có thể giảm

Đây là điểm then chốt giúp mô hình mang đúng bản chất đa phương thức, thay vì chỉ ghép nhiều đầu vào một cách cơ học.

### 8.6. Modality Dropout

#### a) Lý thuyết

Modality dropout là kỹ thuật ngẫu nhiên làm thiếu một hoặc nhiều nguồn dữ liệu trong quá trình huấn luyện. Mục đích là buộc mô hình học cách dự đoán bền vững ngay cả khi một số modality bị thiếu.

#### b) Cách vận dụng trong đề tài

Trong thực tế, ảnh có thể bị mây che, cảm biến có thể mất tín hiệu, hoặc nguồn thời tiết có thể cập nhật chậm. Vì vậy, đề tài sử dụng modality dropout trong quá trình huấn luyện để tăng tính robust cho hệ thống.

Lý do chọn kỹ thuật này là vì hệ thống nông nghiệp thực tế hiếm khi có dữ liệu hoàn hảo ở mọi thời điểm.

### 8.7. MC Dropout để ước lượng độ bất định

#### a) Lý thuyết

MC Dropout (Monte Carlo Dropout) là kỹ thuật giữ dropout hoạt động cả ở pha suy luận, sau đó chạy nhiều lần forward pass trên cùng một mẫu. Trung bình các kết quả dự đoán cho ta giá trị dự đoán kỳ vọng, còn phương sai phản ánh độ bất định.

Ưu điểm:

- đơn giản, dễ tích hợp
- không cần thay đổi kiến trúc quá nhiều
- phù hợp cho các bài toán cần nhận biết độ tin cậy của dự đoán

#### b) Cách vận dụng trong đề tài

Đề tài sử dụng MC Dropout để tính:

- giá trị stress trung bình
- mức dao động giữa các lần suy luận
- confidence flag cho quyết định vận hành

Lý do chọn MC Dropout là vì quyết định tưới có liên quan trực tiếp đến tài nguyên và năng suất. Khi mô hình không chắc chắn, hệ thống cần biết điều đó để tránh quyết định quá mạnh.

---

## 9. Chúng ta vận dụng mô hình này để giải quyết bài toán như thế nào?

Quy trình giải quyết của đề tài gồm các bước sau:

### Bước 1. Thu thập dữ liệu đa nguồn

Hệ thống thu thập dữ liệu ảnh, cảm biến, thời tiết và dữ liệu không gian vùng canh tác.

### Bước 2. Đồng bộ dữ liệu theo vùng và thời gian

Tất cả dữ liệu được căn chỉnh theo `zone_id` và `timestamp` để tạo ra các mẫu thống nhất.

### Bước 3. Tạo mẫu học máy

Mỗi mẫu học máy gồm:

- ảnh Sentinel-2 4 kênh
- chuỗi cảm biến 48 giờ
- vector thời tiết 6 chiều
- modality mask
- stress label dạng proxy

### Bước 4. Huấn luyện mô hình đa phương thức

Mô hình học:

- đặc trưng không gian từ ảnh qua EfficientNet-B3
- đặc trưng thời gian từ cảm biến qua GRU + attention
- đặc trưng ngữ cảnh từ thời tiết qua MLP
- quan hệ giữa các nguồn qua cross-attention fusion

### Bước 5. Sinh đầu ra stress

Mô hình xuất ra:

- xác suất stress nước
- độ bất định
- thông tin giải thích và mức độ tin cậy

### Bước 6. Hậu xử lý và hiệu chỉnh

Đầu ra được đưa qua các bước như calibration, smoothing, confidence flag và degraded mode để tăng độ ổn định trước khi phục vụ quyết định.

### Bước 7. Decision engine ra khuyến nghị tưới

Dựa trên:

- stress probability
- uncertainty
- soil moisture
- rain forecast
- degraded mode

hệ thống đưa ra các mức khuyến nghị:

- no_irrigation
- light
- moderate
- heavy
- hold

Như vậy, bài toán nghiên cứu không dừng ở mức dự đoán AI, mà được khép kín thành chuỗi xử lý từ dữ liệu đến hành động hỗ trợ tưới tiêu.

---

## 10. Quy trình xây dựng và huấn luyện mô hình

Quy trình xây dựng mô hình gồm:

1. Xác định đầu vào và đầu ra của từng mẫu.
2. Xây dựng dataloader đa phương thức.
3. Thiết kế ba encoder riêng cho ảnh, chuỗi thời gian và thời tiết.
4. Thiết kế khối fusion bằng cross-attention.
5. Xây dựng output head cho stress prediction.
6. Bổ sung ước lượng bất định bằng MC Dropout.
7. Bổ sung hậu xử lý và cơ chế giải thích đầu ra.

Các thông số huấn luyện chính:

- Optimizer: AdamW
- Learning rate: 3e-4
- Weight decay: 1e-4
- Scheduler: OneCycleLR
- Batch size: 32
- Max epoch: 50
- Early stopping patience: 7
- AMP: bật

Hàm mất mát chính:

- MSE trên đầu ra sigmoid
- có hỗ trợ label smoothing

Việc chọn AdamW và OneCycleLR giúp quá trình học ổn định hơn, tối ưu tốt với mạng sâu hiện đại và giảm nguy cơ overfitting.

---

## 11. Kết quả đạt được

### 11.1. Kết quả về dữ liệu và hệ thống

Đến thời điểm hiện tại, đề tài đã đạt được các kết quả rõ ràng về mặt hạ tầng dữ liệu và mô hình:

- Xây dựng được pipeline dữ liệu đa nguồn.
- Thu thập được dữ liệu Sentinel-2, thời tiết và dữ liệu môi trường phục vụ bài toán.
- Xây dựng được contract dữ liệu cho học máy và suy luận.
- Xây dựng được kiến trúc mô hình học sâu đa phương thức hoàn chỉnh.
- Có pipeline training, inference và export ONNX.
- Có post-processing, uncertainty estimation và decision engine.
- Có tích hợp backend/frontend phục vụ khai thác kết quả.

Ngoài ra, trạng thái dữ liệu trong repo cho thấy:

- Sentinel-2 thu được 13 scene
- 6/6 zone đạt pass
- Open-Meteo pass
- CHIRPS pass ở mức nguồn dữ liệu

### 11.2. Kết quả về mặt mô hình

Về mặt mô hình, đề tài đã đạt được các kết quả quan trọng sau:

1. Xây dựng được mô hình Deep Learning đa phương thức phù hợp với bài toán stress nước.
2. Mô hình có khả năng kết hợp thông tin từ ảnh, chuỗi thời gian và thời tiết thay vì phụ thuộc vào một nguồn đơn lẻ.
3. Mô hình có khả năng vận hành trong bối cảnh dữ liệu thiếu nhờ modality dropout và modality mask.
4. Mô hình có khả năng ước lượng độ bất định, giúp hệ thống an toàn hơn khi hỗ trợ quyết định tưới.
5. Kết quả đầu ra không chỉ là giá trị dự đoán mà còn kèm thông tin giải thích và độ tin cậy.

### 11.3. Kết quả định lượng

Tại thời điểm tổng hợp báo cáo, repo hiện có đã thể hiện rõ:

- kiến trúc mô hình
- pipeline huấn luyện
- pipeline suy luận
- đường dẫn triển khai mô hình

Tuy nhiên, repo chưa chốt đầy đủ một bảng metric huấn luyện cuối cùng ở mức báo cáo chính thức như:

- MAE
- RMSE
- R²
- AUROC hoặc F1 nếu quy đổi sang ngưỡng phân lớp
- checkpoint production cuối cùng đã xác thực

Vì vậy, cách trình bày phù hợp và trung thực là:

> Đề tài đã xây dựng hoàn chỉnh pipeline dữ liệu, kiến trúc mô hình học sâu đa phương thức, cơ chế suy luận và hỗ trợ quyết định. Kết quả hiện tại cho thấy hệ thống đã giải quyết tốt bài toán ở mức mô hình hóa và kiến trúc triển khai. Tuy nhiên, các chỉ số định lượng cuối cùng của mô hình vẫn cần được tổng hợp đầy đủ từ các lần huấn luyện thực nghiệm cuối trước khi có thể kết luận chính thức về hiệu năng tối ưu.

---

## 12. Đánh giá mô hình

### 12.1. Ưu điểm của mô hình

Mô hình đề xuất có nhiều ưu điểm phù hợp với bài toán:

- Tận dụng được dữ liệu đa nguồn, phản ánh bài toán toàn diện hơn.
- Kết hợp tốt thông tin không gian, thời gian và ngữ cảnh khí tượng.
- Có khả năng hoạt động bền vững hơn khi thiếu một phần dữ liệu.
- Có cơ chế đánh giá độ bất định, giúp giảm rủi ro khi ra quyết định tưới.
- Có khả năng mở rộng và tích hợp vào hệ thống backend/frontend.

### 12.2. Hạn chế của mô hình

Bên cạnh ưu điểm, mô hình vẫn còn một số hạn chế:

- Nhãn hiện tại là proxy label, chưa phải ground-truth thực địa hoàn chỉnh.
- Chưa có bảng đánh giá định lượng cuối cùng được chốt rõ ràng trong repo hiện tại.
- Một số thành phần phục vụ suy luận và AI serving vẫn còn thiên về scaffold triển khai.
- Hiệu năng ngoài thực địa cần được kiểm chứng thêm bằng dữ liệu thực nghiệm thực tế.

### 12.3. Đánh giá mức độ phù hợp với bài toán

Xét về mặt lựa chọn kiến trúc, mô hình là phù hợp với bài toán vì:

- ảnh viễn thám phù hợp cho nhận biết dấu hiệu sinh lý cây trồng trên không gian
- GRU phù hợp cho mô hình hóa xu hướng môi trường theo thời gian
- MLP phù hợp cho dữ liệu thời tiết tổng hợp
- cross-attention phù hợp cho việc liên hệ giữa các modality
- MC Dropout phù hợp cho bài toán hỗ trợ quyết định cần độ an toàn

Nói cách khác, mỗi thuật toán được chọn đều có lý do rõ ràng và gắn trực tiếp với đặc thù dữ liệu của đề tài.

### 12.4. Hướng đánh giá định lượng nên bổ sung

Để đánh giá mô hình đầy đủ hơn trong giai đoạn tiếp theo, cần bổ sung các chỉ số:

- MAE
- RMSE
- R²
- Calibration error
- độ ổn định khi thiếu modality
- so sánh với baseline đơn nguồn hoặc mô hình concat đơn giản

Ngoài ra nên thực hiện:

- ablation study cho từng nhánh dữ liệu
- so sánh GRU với LSTM hoặc Transformer temporal encoder
- so sánh cross-attention với concat fusion
- đánh giá ngoài thực địa với nhãn đo thực

---

## 13. Kết luận

Đề tài AgMultida đã xây dựng được một hướng tiếp cận phù hợp cho bài toán phát hiện stress thiếu nước và hỗ trợ tưới tiêu trong nông nghiệp thông minh. Điểm nổi bật của đề tài là sử dụng mô hình học sâu đa phương thức, kết hợp dữ liệu ảnh viễn thám, chuỗi cảm biến môi trường và dữ liệu thời tiết để ước lượng mức độ stress nước theo từng vùng canh tác.

Về mặt thuật toán, đề tài vận dụng hợp lý nhiều phương pháp như EfficientNet-B3 cho ảnh, GRU kết hợp attention cho chuỗi thời gian, MLP cho dữ liệu thời tiết, cross-attention cho hợp nhất đặc trưng, modality dropout để tăng độ bền và MC Dropout để ước lượng độ bất định. Việc lựa chọn các thuật toán này xuất phát trực tiếp từ đặc thù dữ liệu và yêu cầu thực tiễn của bài toán.

Kết quả hiện tại cho thấy đề tài đã đạt được khung kỹ thuật khá đầy đủ từ thu thập dữ liệu, tiền xử lý, xây dựng nhãn, huấn luyện mô hình, suy luận, đánh giá độ tin cậy, đến tích hợp khuyến nghị tưới. Tuy nhiên, để khẳng định mạnh hơn hiệu quả thực nghiệm của mô hình, đề tài vẫn cần bổ sung bảng kết quả huấn luyện cuối cùng, đánh giá định lượng đầy đủ và kiểm chứng bằng dữ liệu thực địa trong các giai đoạn tiếp theo.

Nhìn chung, đề tài đã giải quyết đúng hướng bài toán cả ở mức nghiên cứu lẫn mức xây dựng hệ thống, đồng thời tạo nền tảng tốt để tiếp tục mở rộng thành hệ thống hỗ trợ tưới tiêu thông minh có khả năng ứng dụng thực tế cao.