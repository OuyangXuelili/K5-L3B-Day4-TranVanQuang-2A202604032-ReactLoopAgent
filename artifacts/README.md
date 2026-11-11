# Bằng chứng thực nghiệm

Code bàn giao là **v2**, với **85 tests pass**. Báo cáo chính nằm ở [BAO_CAO.md](../BAO_CAO.md). Lượt cuối dùng Gemini trực tiếp, `gemini-3.5-flash-lite`, cùng model/budget/dataset cho before và after. Mỗi báo cáo có hash implementation và dữ liệu được bảo vệ để phân biệt các phiên bản.

Kết quả cuối đã chấm đủ: chính **99,91 → 100/100** (22/22 mỗi bản), bonus **100/100 → 15/15** (10/10). Ba JSON ở gốc và bản sao trong `v2/` là kết quả của source hiện tại; các thư mục lịch sử giữ kết quả phiên bản cũ.

| File | Nội dung |
|---|---|
| `../eval_before.json` | 22 case bài chính với implementation v1 đóng băng, tắt gate nguồn |
| `../eval_after.json` | 22 case bài chính với source v2 bàn giao |
| `../eval_bonus.json` | 10 case bonus với source v2 bàn giao |
| `v2/eval_*.json` | Bản thực nghiệm mới; chỉ công bố ra gốc khi cả ba bộ đã chấm đủ |
| `eval_comparison.json` | Điểm từng case, calls, tokens, chi phí và vi phạm cơ học before/after |
| `experiment_manifest.json` | Cấu hình, Git base, hash source/dữ liệu/báo cáo và metrics |
| `verification.json` | Kiểm tra source khớp report, 10 file được bảo vệ, key, syntax và số case |
| `test_results.txt` | Log 82 tests chính và 3 tests bonus, tất cả pass |
| `demo_trace.json` | Trace LLM thật H1 của after: hai incident ban đầu và incident GitHub được dẫn |
| `error_demo.json` | Trace LLM thật H7 của after: timeout Cloudflare và câu trả lời có giới hạn |
| `offline_demo.json` | Scripted provider minh họa thiếu URL và sửa nguồn; không phải điểm LLM |
| `v2/offline_investigation.json` | Sáu scripted replay cố ý final sớm để kiểm tra checklist; không phải điểm LLM |

Lịch sử được giữ riêng:

- `v1/`: kết quả OpenRouter Gemini 2.5 Flash và bonus NVIDIA, báo cáo, log và bằng chứng ban đầu.
- `v2a/`: lượt Gemini 3.1 Flash Lite đầu, phát hiện H7 gán Operational khi timeout và B10 bỏ retry.
- `v2b/`: lượt Gemini 3.1 sau guard trạng thái/retry, trước sửa parser gán ID/provider; có source `agent.py` và `investigation.py` của lượt đó.
- `v2c/`: lượt Gemini 3.5 trước sửa chọn incident mới nhất và giới hạn provider của checklist; có source cùng kết quả đầy đủ 99,77 chính và 14,92/15 bonus.
- `gemini31_partial/`: lượt chạy lại chưa đủ điểm do 503/timeout, không phải điểm toàn bộ dataset.
- `*_partial_*.json`: kết quả lưu trước resume. Các case đã chấm được giữ nguyên, kể cả điểm thấp; agent hoàn thành nhưng judge lỗi chỉ được rejudge cùng answer/trace.
- Các file `*_probe.json`, `*_check.json`, `gemini35_h7.json`, `smoke.json` và `model_check_e2.json` là kiểm tra riêng. Case H7 Gemini 3.5 được tái sử dụng trong bộ after cùng source/cấu hình, không thay thế bằng trajectory mới.
- `eval_*_402.json`, `eval_*_budget_*.json`, `eval_before_flash_*.json`, `eval_after_markdown_bug.json` và các lượt thử cũ lưu lỗi cấu hình, tài khoản hoặc code trước khi sửa; không dùng thay kết quả cuối.

Usage chỉ tính các kết quả cuối được giữ, không tính toàn bộ các lần lỗi/probe. API Gemini không trả trường chi phí ở các kết quả này, nên chi phí là `null`/N/A. Không dùng chênh lệch điểm giữa hai model như bằng chứng tác động của code. Điểm eval khác điểm rubric bài chính 85; bonus quy đổi tối đa 15 chỉ là tham khảo cho giảng viên.

Không có API key trong file nộp; `.env` chỉ tồn tại cục bộ và được Git bỏ qua. Chạy `python -X utf8 scripts/verify_delivery.py` sau khi có đủ kết quả cuối để tái tạo manifest và kiểm tra bàn giao.
