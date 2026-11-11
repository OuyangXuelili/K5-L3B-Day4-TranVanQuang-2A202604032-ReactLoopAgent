# Báo cáo thực hành: Status Investigation Agent

**Học viên:** Trần Văn Quang — **Mã:** 2A202604032
**Ngày thực hiện:** 11/11/2026
**Repo:** K5-L3B-Day4-TranVanQuang-2A202604032-ReactLoopAgent

## 1. Phạm vi hoàn thành

Tôi đã đọc README, GUIDE, RUBRIC, contract provider/tools, bộ tests và hai bộ eval trước khi hoàn thiện bài. Agent dùng Python standard library, không có framework agent và không hard-code câu trả lời hoặc mã incident trong `agent.py`.

- Khởi tạo system/user messages; gọi model theo giới hạn bước.
- Giữ nguyên assistant message và trả đủ mọi tool result với đúng `tool_call_id` trước lượt model tiếp theo.
- Chỉ hoàn thành khi `finish == stop`, không có calls và có câu trả lời hợp lệ. Các tình huống `length`, lỗi provider, response sai contract không được báo hoàn thành.
- JSON lỗi hoặc không phải object được gửi lại dưới dạng `INVALID_ARGUMENTS`. Tool lỗi là observation; các tool khác vẫn được xử lý.
- Ghi trace gồm model step/finish, tool name, arguments, result, validation và retry; lưu usage riêng. Không ghi exception body có thể chứa header/key.
- Kiểm tra URL nguồn trước khi hoàn thành; yêu cầu model sửa trong chính `max_steps`, không tăng budget ngầm.
- Dùng `tools.schemas` và `tools.system_prompt` khi có để hỗ trợ GitHub, Cloudflare, Vercel, npm và DigitalOcean trong bonus.
- Giới hạn retry sau 429 ở tối đa ba lần thực thi thật cho cùng tool/provider; đọc `Retry-After` dạng giây hoặc HTTP date. Chờ tối đa hai giây mỗi lần, hoặc dừng và báo thiếu dữ liệu nếu vượt budget chờ.
- Hỗ trợ pagination thông qua model và `next_offset`; prompt yêu cầu không tuyên bố đọc đủ nếu còn trang hoặc nội dung bị cắt.

Tôi sửa việc đọc/ghi JSON sang UTF-8 trong hai bộ tools và eval runner để chạy được trên Windows. Dữ liệu fixtures, cases, scenarios, grading và rubric không bị thay đổi. Hash của các file này được lưu trong `artifacts/experiment_manifest.json`.

## 2. Cấu hình và cách so sánh

| Thuộc tính | Cấu hình bài chính |
|---|---|
| Provider | OpenRouter |
| Agent model | `google/gemini-2.5-flash` |
| Judge model | `google/gemini-2.5-flash` |
| Dữ liệu | Snapshot, đủ 22 case E1–E6, A1–A8, H1–H8 |
| Giới hạn | 8 model calls/case, 4096 output tokens/response |
| Before | Cùng loop và prompt, tắt validation URL |
| After | Bật validation URL theo từng provider |

`experiments/baseline_agent.py` cung cấp baseline có kiểm soát. Cả hai phiên bản dùng cùng provider/model/judge, snapshot, dataset và giới hạn. Before chạy ba case đồng thời; after chạy tuần tự để giảm lỗi tài khoản. Đây là khác biệt vận hành cần lưu ý khi so sánh.

Một số lần thử trước đó gặp response rỗng, judge JSON lỗi hoặc HTTP 402. Tôi giữ kết quả thô trong `artifacts/`, không tính các lần đó thành điểm 0 hay trình bày trung bình phần đã chấm như điểm tổng. After được resume chỉ với case `unscored`; mọi điểm đã chấm, kể cả điểm thấp, được giữ nguyên. Thông tin resume và bản trước mỗi lần nằm trong `experiment.previous_attempt`.

## 3. Lỗi được chọn và cải tiến

Tôi chọn **E4**, vì trace cho thấy agent đọc thành công chi tiết incident nhưng final thiếu nguồn:

- Before, step 1: `get_incident_details` trả `ok: true`, components Webhooks, Actions, Pages và URL `https://stspg.io/pjgptg3cfc6n`.
- Before, step 2: final mô tả ảnh hưởng nhưng không chứa URL. Agent vẫn `completed`; judge còn cho 100 điểm. Vì vậy chỉ đọc điểm judge không phát hiện được lỗi dẫn nguồn.
- Nguyên nhân: prompt yêu cầu nguồn nhưng loop chưa kiểm tra điều kiện này trước khi chấp nhận final.
- Thay đổi: lưu URL từ `get_incident_details` thành công theo provider; final phải có ít nhất một URL đã quan sát của mỗi provider đã đọc incident. Nếu thiếu, ghi `validation_missing_source` và yêu cầu model sửa trong budget.
- After, step 2: validator phát hiện thiếu nguồn; step 3 trả final có URL và hoàn thành. E4 vẫn được judge chấm 100, nhưng trace chứng minh điều kiện nguồn đã được thực thi.

Trong quá trình xác minh, tôi phát hiện parser URL nhận nhầm Markdown `[URL](URL)` là thiếu nguồn. Tôi sửa ranh giới token URL và thêm regression test cho link Markdown, URL in đậm, dấu ngoặc nhọn và bảng. Kết quả chạy có lỗi parser được lưu riêng trong `artifacts/eval_after_markdown_bug.json`; không dùng làm bản after cuối.

Validator chỉ kiểm tra sự hiện diện nguồn đã quan sát, chưa chứng minh từng claim được nguồn hỗ trợ. Nó cũng chưa buộc agent phải gọi chi tiết incident: nếu model dừng ngay sau status, không có URL incident để gate kiểm tra.

## 4. Kết quả bài chính

| Chỉ số | Before | After |
|---|---:|---:|
| Case được chấm | 22/22 | 22/22 |
| Điểm eval | 92,36/100 | 91,45/100 |
| Model calls của agent | 43 | 45 |
| Agent tokens | 53.834 | 57.132 |
| Judge tokens | 32.644 | 32.733 |
| Event sửa nguồn | 0 | 2 |
| Chi phí agent (USD) | 0,02234774 | 0,02366156 |
| Chi phí judge (USD) | 0,01644600 | 0,01602170 |
| Tổng chi phí báo trong hai file (USD) | 0,03879374 | 0,03968326 |

Điểm after giảm **0,91**. Chi phí tăng khoảng **0,00088952 USD**. Hai event sửa nguồn thuộc E4 và H6. Tôi không kết luận cải tiến làm tăng điểm tổng; bằng chứng rõ nhất là bắt và sửa được final thiếu URL trong giới hạn bước. Chi phí trên lấy từ `usage.cost`, chỉ tính các kết quả cuối cùng, chưa bao gồm các lần thử lỗi, smoke test và các case chạy lại bị thay thế. Không coi đây là tổng hóa đơn tài khoản.

So sánh từng case, vi phạm cơ học và tổng usage có thể tái tạo bằng `python -X utf8 scripts/compare_evals.py`; kết quả ở `artifacts/eval_comparison.json`.

| Case | Before | After | Chênh lệch |
|---|---:|---:|---:|
| E1 | 100 | 95 | -5 |
| E2 | 100 | 80 | -20 |
| E3 | 100 | 100 | 0 |
| E4 | 100 | 100 | 0 |
| E5 | 100 | 100 | 0 |
| E6 | 100 | 100 | 0 |
| A1 | 98 | 98 | 0 |
| A2 | 100 | 100 | 0 |
| A3 | 100 | 98 | -2 |
| A4 | 90 | 98 | +8 |
| A5 | 90 | 100 | +10 |
| A6 | 98 | 98 | 0 |
| A7 | 100 | 87 | -13 |
| A8 | 100 | 100 | 0 |
| H1 | 60 | 60 | 0 |
| H2 | 50 | 50 | 0 |
| H3 | 50 | 50 | 0 |
| H4 | 100 | 100 | 0 |
| H5 | 98 | 100 | +2 |
| H6 | 100 | 100 | 0 |
| H7 | 98 | 98 | 0 |
| H8 | 100 | 100 | 0 |

### Lỗi còn lại và giới hạn judge

- **H1: 60 điểm ở cả hai bản.** Agent đọc GitHub và Cloudflare trong cùng step nhưng không đọc tiếp incident GitHub được dẫn. Kiểm tra cơ học giới hạn 60 vì chưa có tool calls ở hai model steps khác nhau.
- **H2: 50 điểm ở cả hai bản.** Agent đọc incident resolved nhưng bỏ `get_status`; chưa đủ kiểm tra tiền đề về tình trạng snapshot hiện tại.
- **H3: 50 điểm ở cả hai bản.** Agent trả lời ID không hợp lệ mà không thực sự gọi `get_incident_details`. Không bịa incident là tốt, nhưng thiếu thao tác tra cứu được yêu cầu.
- **E2 after: 80 điểm.** Agent mới xem status rồi nói cần đọc chi tiết để xác nhận FedRAMP, thay vì đọc luôn. Gate nguồn không giải quyết được lỗi dừng điều tra sớm này.
- **A5:** before gọi năm 2025 là tương lai dù snapshot thuộc 2026, nhưng judge vẫn cho 90. After trả lời giới hạn khá chung chung mà judge cho 100. Đây là ví dụ judge có thể bỏ sót sai sót hoặc đánh giá quá cao.
- **H6 after:** judge cho 100 nhưng trace mới có status và incident đầu, chưa đọc incident được dẫn. Cần kiểm tra trace thay vì suy từ điểm cao ra hoàn thành mọi yêu cầu.

Agent và judge dùng cùng model nên có thể cùng bỏ qua một lỗi. Mỗi bản chỉ có một bộ kết quả cuối cùng; một số case sau lỗi hạ tầng được chạy lại. Thực nghiệm này không chứng minh độ ổn định, quan hệ nhân quả của chênh lệch điểm hoặc tính đúng đắn trong live.

## 5. Bonus

Agent kết nối sáu schemas của BonusTools, sử dụng prompt riêng, trả lỗi 429/định dạng cho model, giới hạn retry thật và giữ metadata pagination trong observation. Bonus không dùng để thay điểm bài chính.

Lượt Gemini ban đầu gặp HTTP 402 ở budget 4096. Tôi thử budget 2048, chấm được B2/B3 nhưng B1 bị `length`, các case sau tiếp tục lỗi tài khoản. Kết quả đó được lưu ở `artifacts/eval_bonus_gemini_2048.json`, không trộn vào kết quả model khác.

Tôi chuyển riêng bộ bonus sang `nvidia/nemotron-3.5-lightning:free` qua OpenRouter, agent và judge cùng model, `max_steps=16`, `MAX_TOKENS=4096`, khoảng cách tối thiểu 3,2 giây giữa các lần bắt đầu gọi LLM. Case B1 thử trước được giữ nguyên khi resume chạy đủ bộ; mọi case cuối cùng đều dùng cùng cấu hình bonus này. Đây là bộ eval riêng, không phải so sánh chất lượng giữa hai model.

Kết quả cuối trong `eval_bonus.json`: **10/10 case được chấm, 92,2/100, quy đổi tham khảo 13,83/15**. Chi phí trả về từ API cho các model calls được ghi trong file là **0 USD**. Không tự cộng điểm này vào điểm eval bài chính hay suy ra điểm rubric do giảng viên chấm.

| Case | Điểm |
|---|---:|
| B1 | 100 |
| B2 | 89 |
| B3 | 100 |
| B4 | 100 |
| B5 | 90 |
| B6 | 50 |
| B7 | 100 |
| B8 | 100 |
| B9 | 100 |
| B10 | 93 |

B3/B4 cho thấy agent xử lý được cả rate limit tạm thời và kéo dài; B7 không lặp injection marker. **B6 còn lỗi bỏ bước đọc chi tiết incident**: đã gọi hai status tools nhưng chưa gọi `get_incident_details`, nên kiểm tra cơ học áp trần 50. Lần judge đầu không trả JSON hoàn chỉnh; tôi chỉ chấm lại **cùng answer và trace**, không chạy lại agent để lấy câu trả lời tốt hơn. Chín điểm đã có được giữ nguyên khi resume.

## 6. Kiểm thử và demo

Các lệnh kiểm tra:

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s bonus -p 'test_*.py' -v
python -X utf8 scripts/demo_offline.py
python -X utf8 scripts/compare_evals.py
```

Các test bổ sung kiểm tra tool-call IDs, usage, lỗi provider không lộ exception text, JSON không phải object/NaN, timeout nhiều calls, finish bất thường, budget không hợp lệ, Retry-After, giới hạn ba lần 429, nguồn nhiều provider, URL bịa với tiền tố hợp lệ và pagination lấy offset thật từ tool. Chúng kiểm tra cơ chế, không thay thế đánh giá năng lực LLM.

Kết quả kiểm thử hiện tại: **56 tests chính + 3 tests bonus = 59 tests pass**. Log đầy đủ ở `artifacts/test_results.txt`. Có thêm test xác nhận resume giữ nguyên điểm 0 và chỉ chấm lại judge trên answer đã hoàn thành. Kiểm tra cú pháp theo Python 3.10 cũng pass; môi trường thực thi là Python 3.13 trên Windows.

**Demo thật:** `artifacts/demo_trace.json`, trích case A6 từ after. Step 1 đọc incident đầu, step 2 đọc incident được liên kết, step 3 trả final. Có thể trình bày sự khác nhau giữa ảnh hưởng, nguyên nhân được nguồn xác nhận và dữ liệu bị cắt.

**Demo offline:** `artifacts/offline_demo.json` cố ý dùng scripted provider để tạo final thiếu URL. Before hoàn thành sau ba lượt; after yêu cầu sửa và hoàn thành sau bốn lượt. File ghi rõ không gọi LLM thật, không có điểm judge.

## 7. Chạy lại và bảo quản cấu hình

Xem lệnh PowerShell trong README. `scripts/evaluate.py --env-file .env` đọc cấu hình như dữ liệu, không thực thi nội dung shell; biến đã có trong shell được ưu tiên. `run.py` và `evals/run_evals.py` không tự đọc `.env`.

API key chỉ nằm trong `.env` được Git bỏ qua. Không đưa file này vào bài nộp. Kết quả nộp gồm `agent.py`, `eval_before.json`, `eval_after.json`, `eval_bonus.json`, báo cáo này và các scripts/tests/bằng chứng liên quan.
