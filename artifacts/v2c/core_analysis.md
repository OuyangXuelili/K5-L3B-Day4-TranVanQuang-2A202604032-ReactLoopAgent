### Số liệu bài chính trước hai sửa đổi cuối (v2c)

| Chỉ số | Before | After |
|---|---:|---:|
| Case đã chấm | 22/22 | 22/22 |
| Điểm eval 0–100 | 99,91 | 99,77 |
| Model calls của agent | 58 | 69 |
| Agent tokens | 85.467 | 158.039 |
| Judge tokens | 43.731 | 58.515 |
| Tổng tokens của các kết quả được giữ | 129.198 | 216.554 |
| Lượt sửa thiếu nguồn | 0 | 7 |
| Lượt chặn final thiếu bước | 0 | 1 |
| Case có vi phạm cơ học | 0 | 0 |
| Chi phí API báo cáo | N/A | N/A |

| Case | Before | After | Chênh lệch |
|---|---:|---:|---:|
| E1 | 100 | 100 | 0 |
| E2 | 100 | 100 | 0 |
| E3 | 100 | 100 | 0 |
| E4 | 100 | 100 | 0 |
| E5 | 100 | 100 | 0 |
| E6 | 100 | 100 | 0 |
| A1 | 100 | 100 | 0 |
| A2 | 100 | 100 | 0 |
| A3 | 100 | 95 | -5 |
| A4 | 100 | 100 | 0 |
| A5 | 100 | 100 | 0 |
| A6 | 100 | 100 | 0 |
| A7 | 100 | 100 | 0 |
| A8 | 100 | 100 | 0 |
| H1 | 98 | 100 | +2 |
| H2 | 100 | 100 | 0 |
| H3 | 100 | 100 | 0 |
| H4 | 100 | 100 | 0 |
| H5 | 100 | 100 | 0 |
| H6 | 100 | 100 | 0 |
| H7 | 100 | 100 | 0 |
| H8 | 100 | 100 | 0 |

After không tăng điểm tổng ở lượt này. Gemini 3.5 đã xử lý tốt H2/H7 ngay trong baseline; các lỗi quan sát với model trước không nhất thiết xuất hiện lại. Source gate thực sự yêu cầu sửa ở E2, E3, E5, A5, A7, H6, H7; checklist chặn final ở H8. Đổi lại, after thêm 11 model calls và dùng nhiều tokens hơn. Checklist còn có thể thu thập dư: H8 cần thừa nhận không có toàn bộ lịch sử nhưng bị yêu cầu đọc thêm hai incident. Không coi việc tăng calls tự thân là cải thiện chất lượng.

A3 bị trừ 5 điểm factuality, trong khi `reason` vẫn nói câu trả lời chính xác và `improvement` ghi không cần cải thiện. Đối chiếu độc lập thấy answer nêu các incident “ngày 05/11 và 07/11” nhưng incident `h02n9572mx9y` bắt đầu ngày 04/11, hồ sơ cập nhật ngày 07/11; cách viết dễ gây nhầm. Phần Cloudflare timeout được xử lý đúng và không có vi phạm cơ học. Giữ nguyên điểm 95, không rejudge để đổi điểm.

H1 tăng 98 → 100 theo judge, nhưng **cả hai answer vẫn chưa nói rõ update GitHub bị cắt**, mặc dù observation có `truncated: true`. Vì vậy không kết luận đã sửa hết lỗi completeness từ điểm 100; H6 mới có lời chú thích truncation rõ ràng. Đây là ví dụ giới hạn của judge cùng model và lý do cần đọc trace.
