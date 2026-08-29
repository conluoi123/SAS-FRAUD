Báo cáo Tổng quan Hệ thống SAS Visual Investigator: Cẩm nang dành cho Thực tập sinh

Chào mừng các bạn thực tập sinh đến với hành trình chinh phục SAS Visual Investigator (SAS VI). Đây không chỉ là một công cụ phần mềm, mà là "vũ khí" chiến lược giúp các tổ chức tài chính như Orion Star Bank biến những dữ liệu thô (như giao dịch tiền mặt, chuyển khoản điện tử) thành những nhận định sắc bén để ngăn chặn tội phạm tài chính.

Bản báo cáo này được thiết kế như một lộ trình học tập trực quan, giúp các bạn không chỉ nắm bắt tính năng mà còn hiểu được tư duy vận hành của một điều tra viên chuyên nghiệp.

1. Giới thiệu Tổng quan về SAS Visual Investigator (SAS VI)

SAS VI cung cấp một giải pháp toàn diện để quản lý, tìm kiếm và điều tra dữ liệu. Các bạn hãy lưu ý rằng hệ thống vận hành qua ba giai đoạn cốt lõi:

1. Giai đoạn Cài đặt (Installation): Thiết lập nền tảng kỹ thuật và kết nối máy chủ (Linux, Postgres).
2. Giai đoạn Cấu hình (Configuration): Đây là công việc của Quản trị viên (viadmin). Họ định nghĩa các kho dữ liệu, tạo thực thể và thiết kế giao diện. Hiểu giai đoạn này sẽ giúp các bạn biết rõ nguồn gốc của dữ liệu mình đang xử lý.
3. Giai đoạn Điều tra (Investigation): Đây chính là trọng tâm công việc của các bạn. Với vai trò Điều tra viên (inv1) hoặc Quản lý (mgr1), các bạn sẽ trực tiếp rà soát cảnh báo và đưa ra quyết định xử lý.

Kỹ năng then chốt: Điều hướng giao diện Các bạn cần làm quen với Application Switcher (biểu đồ ô vuông ở góc trên bên trái) để chuyển đổi giữa các môi trường:

* Investigate and Search (Người dùng cuối): Nơi các bạn thực hiện tìm kiếm và điều tra hàng ngày.
* Manage Investigate and Search (Quản trị viên): Nơi cấu hình hệ thống (chỉ dành cho viadmin).

2. Các Khái niệm và Thuật ngữ Nền tảng: Thực thể và Mối quan hệ

Trong SAS VI, dữ liệu được mô hình hóa thành các Thực thể (Entities). Để hệ thống có thể "đọc" được dữ liệu từ bên ngoài, Quản trị viên phải định nghĩa một Kho dữ liệu (Data Store) làm cầu nối trước khi tạo thực thể.

So sánh Thực thể nội bộ và Thực thể bên ngoài

Tiêu chí	Thực thể nội bộ (Internal Entity)	Thực thể bên ngoài (External Entity)
Định nghĩa	Tạo ra và lưu trữ hoàn toàn trong SAS VI.	Ánh xạ từ các bảng có sẵn trong cơ sở dữ liệu ngoài.
Nguồn lưu trữ	Lược đồ (Schema) fdhdata bên trong cơ sở dữ liệu SharedServices.	Cơ sở dữ liệu bên ngoài (ví dụ: Postgres, schema insurance).
Bối cảnh (Context)	Có bối cảnh Tạo mới (Create), Chỉnh sửa, Chi tiết.	Chỉ có Chỉnh sửa, Chi tiết (không thể tạo mới từ đầu trong VI).
Ví dụ thực tế	Demo_Investigation (Thông tin vụ việc).	Home_Policy (Hợp đồng bảo hiểm), Customer.

Đối tượng con (Child Entities): Một thực thể có thể chứa các đối tượng con để thể hiện mối quan hệ phân cấp. Ví dụ: Một thực thể Home_Policy có thể có nhiều đối tượng con là Phone (Số điện thoại) gắn liền với nó.

💡 MẸO CHUYÊN GIA (PRO TIP): Bất cứ khi nào cấu trúc thực thể hoặc trang bị thay đổi, các bạn phải thực hiện Re-index (Tái lập chỉ mục) trong trang Jobs. Nếu không, những thay đổi đó sẽ không xuất hiện trong kết quả tìm kiếm. Đây là một "lỗi" thường gặp mà các thực tập sinh cần đặc biệt lưu ý!

3. Hệ thống Cảnh báo (Alerts) và Luồng hoạt động

Hệ thống cảnh báo giúp bạn sàng lọc hàng triệu giao dịch để tìm ra những "dấu vết" bất thường. Luồng logic diễn ra như sau: Scenarios (Kịch bản phân tích) -> Scenario-fired events -> Alerting events -> Alert Service.

Tại sao hệ thống cần Gộp cảnh báo (Alert Consolidation)?

* Giảm nhiễu: Thay vì hiển thị 100 giao dịch nghi vấn đơn lẻ của cùng một khách hàng, hệ thống gộp chúng thành một Alert duy nhất.
* Tập trung điều tra: Giúp các bạn có cái nhìn tổng thể về đối tượng (Actionable Entity) mà không bị phân tán.

Tính năng Reactivate (Kích hoạt lại): Hãy tưởng tượng bạn vừa đóng một vụ việc vì thiếu bằng chứng, nhưng ngay sau đó lại nhận được một hình ảnh quan trọng từ thực địa—đây chính là lúc tính năng Reactivate trở thành cứu cánh của bạn, giúp chuyển trạng thái từ "CLOSED" về lại "Active" để tiếp tục xử lý.

4. Quá trình Điều tra vụ việc (Investigations/Cases) và Workflow

Khi một cảnh báo có đủ cơ sở nghi ngờ, nó sẽ trở thành một cuộc điều tra chính thức thông qua các Quy trình nghiệp vụ (Workflows).

* Thành phần hỗ trợ: Attachments (Tài liệu đính kèm như ảnh .jpg), Comments (Bình luận có định dạng văn bản), và Workspaces (Không gian làm việc trực quan).

Luồng công việc (Workflow) giữa Điều tra viên và Quản lý

Vai trò	Tác vụ (Task)	Ý nghĩa nghiệp vụ
Investigator (inv1)	Claim task	Nhận quyền sở hữu và khóa tác vụ để xử lý.
Investigator (inv1)	Send to Manager	Hoàn thành báo cáo và trình cấp trên phê duyệt.
Manager (mgr1)	Return for rework	Trả lại yêu cầu điều tra viên bổ sung chứng cứ.
Manager (mgr1)	Close	Quyết định đóng vụ việc sau khi đã xử lý triệt để.

Quyết định xử lý (Disposition): Đây là kết luận cuối cùng cho một cảnh báo, ví dụ: "Add to Investigation" (Đưa vào điều tra) hoặc "Close Immediately" (Đóng ngay lập tức nếu không có rủi ro).

5. Công cụ Hỗ trợ Phân tích: Insights và Workspaces

Trên giao diện điều tra, các bạn sẽ thường xuyên làm việc với hai không gian quan trọng. Hãy tìm biểu tượng Bóng đèn (Light bulb icon) để truy cập Insights.

Đặc điểm	Workspaces (Không gian làm việc)	Insights (Thông tin chuyên sâu)
Tính chất	Động: Có thể chỉnh sửa, thêm bớt đối tượng.	Tĩnh: Là "ảnh chụp" bằng chứng tại một thời điểm.
Mục đích	Phân tích, khám phá các mối liên kết mới.	Lưu giữ bằng chứng không đổi để đưa vào báo cáo.

Các Góc nhìn dữ liệu (Data views):

* Detail view: Cung cấp thông tin chi tiết từng trường dữ liệu.
* Map view: Định vị thực thể trên bản đồ để phát hiện các cụm hoạt động theo địa lý.
* Table: Lọc và so sánh dữ liệu hàng loạt một cách nhanh chóng.
* Timeline: Tái hiện trình tự các sự kiện theo thời gian.
* Network view: Trực quan hóa các mối quan hệ ẩn giữa các đối tượng.

6. Tính năng Tìm kiếm và Khám phá thông tin (Searching)

Hệ thống cung cấp những công cụ truy vấn cực kỳ linh hoạt:

* Tìm kiếm toàn cầu (Global Search): Sử dụng ký tự đại diện * để xem toàn bộ danh mục thực thể được phép truy cập.
* Tìm kiếm nâng cao (Advanced Search): Sử dụng Query Builder để lọc theo loại đối tượng và thuộc tính.
* Bộ lọc đặc trưng (Filter Facets): Một công cụ cực kỳ hữu ích giúp thu hẹp phạm vi tìm kiếm theo các trường quan trọng như Incident Date (Ngày xảy ra sự việc) hoặc Claim Value (Giá trị khiếu nại).
* Tìm kiếm ngữ âm (Phonetic Search): Tìm được cả những tên viết sai nhưng đọc giống nhau (ví dụ: gõ Hoppor vẫn tìm ra Hopper và Hooper).
* Tìm kiếm theo vị trí (Map search): Vẽ một hình chữ nhật trên bản đồ để tìm tất cả thực thể trong khu vực đó.

Ngoài ra, đừng quên tính năng Find text in page (biểu tượng kính lúp trên thư mục) để truy tìm từ khóa cụ thể ngay trong hồ sơ đang mở.

7. Giao diện Báo cáo Quản lý (Management Reports)

Cấp quản lý sử dụng các báo cáo này để đo lường hiệu quả vận hành, các bạn có thể lọc báo cáo theo các chiến lược cụ thể như Domestic Alert Strategy:

* Assignment Reports: Theo dõi số lượng cảnh báo đang hoạt động hoặc bị tạm dừng (Suppressed).
* Disposition Reports: Phân tích tỷ lệ đóng hồ sơ và hiệu suất xử lý của từng nhóm.
* Task Reports: Thống kê thời gian trung bình hoàn thành mỗi bước trong Workflow.
* Audit Report: Truy vết mọi hành động của người dùng (ví dụ: kiểm tra xem inv1 đã xem những hồ sơ nào) để đảm bảo tính minh bạch.

8. SAS Mobile Investigator: Hỗ trợ Điều tra thực địa

SAS VI không chỉ bó hẹp trong văn phòng. Ứng dụng di động mang lại khả năng phản ứng nhanh:

* Tính linh động: Kiểm tra danh sách tác vụ (Tasks) và thực hiện tìm kiếm ngay khi đang di chuyển.
* Bằng chứng thực địa (Evidence): Các bạn có thể dùng điện thoại chụp ảnh trực tiếp và tải lên hệ thống. Hình ảnh này sẽ được đồng bộ ngay lập tức với cơ sở dữ liệu trung tâm, giúp đội ngũ ở văn phòng có bằng chứng tức thì.

Kết luận: Việc làm chủ SAS Visual Investigator là sự kết hợp giữa kỹ năng sử dụng công cụ trực quan và tư duy logic trong phân tích dữ liệu. Hãy luôn nhớ: "Dữ liệu chỉ là những con số vô hồn cho đến khi bạn kết nối chúng lại thành một câu chuyện có ý nghĩa". Chúc các bạn có một kỳ thực tập thành công!
