# Báo cáo Status Investigation Agent

**Học viên:** Trần Văn Quang — **Mã học viên:** 2A202604032
**Ngày:** 11/11/2026 — **Phiên bản bàn giao:** v2

## 1. Kết quả và cấu hình thực nghiệm

Code đã hoàn thành agent loop, robustness, validation nguồn, checklist bằng chứng và tools bonus. **85 tests offline pass**: 82 trong `tests/`, 3 trong `bonus/`. Lượt cuối bài chính đạt **99,91 → 100/100** trên đủ 22/22 case mỗi bản; bonus đạt **100/100**, quy đổi tham khảo **15/15**, đủ 10/10 case. Ba JSON ở thư mục gốc khớp source bàn giao. Lượt trước hai sửa đổi cuối được giữ riêng trong `artifacts/v2c/`.

| Thuộc tính | Giá trị dùng cho cả before và after |
|---|---|
| Agent provider/model | Gemini trực tiếp / `gemini-3.5-flash-lite` |
| Judge provider/model | Gemini trực tiếp / `gemini-3.5-flash-lite` |
| Output budget | `MAX_TOKENS=4096` |
| Reasoning | `GEMINI_REASONING_EFFORT=minimal`; không đặt `REASONING_ENABLED` |
| Dataset chính | Cùng 22 case E1–E6, A1–A8, H1–H8; snapshot cố định |
| Budget chính | Tối đa 8 model calls/case, tính cả bước yêu cầu sửa final |
| Dataset bonus | 10 case B1–B10; tối đa 16 model calls/case |
| Điều tiết request | 2 workers, khoảng cách tối thiểu giữa các lần bắt đầu gọi LLM là 6,2 giây |
| Before | Source v1 đóng băng trong `experiments/previous_agent.py`, wrapper `baseline_agent.py` tắt gate nguồn |
| After | `agent.py` + `investigation.py`, prompt mới và các gate kiểm tra bằng chứng |

Before và after cùng dùng adapter `providers.py` hiện tại. Các hash implementation, fixtures, cases và tiêu chí chấm nằm trong metadata `experiment` của từng JSON. Đây là so sánh cả gói cải tiến, không tách riêng tác động của từng thay đổi.

Các lần gọi dịch vụ gặp 503 hoặc timeout được giữ là `unscored`, rồi tiếp tục bằng `--resume`. Trong cùng implementation, script giữ nguyên **mọi điểm đã chấm, kể cả 0 hoặc điểm thấp**. Nếu agent đã hoàn thành nhưng judge lỗi, script chỉ chấm lại **cùng answer/trace**. H7 kiểm tra riêng được giữ lại trong lượt v2c cùng source/cấu hình; sau hai sửa đổi selector/phạm vi, toàn bộ after và bonus được chạy mới. Không dùng resume để chọn lại trajectory thay điểm thấp; các phiên bản code khác nhau được lưu riêng.

### Số liệu bài chính cuối

| Chỉ số | Before | After |
|---|---:|---:|
| Case đã chấm | 22/22 | 22/22 |
| Điểm eval 0–100 | 99,91 | 100 |
| Model calls của agent | 58 | 68 |
| Agent tokens | 85.467 | 152.151 |
| Judge tokens | 43.731 | 55.767 |
| Tổng tokens của các kết quả được giữ | 129.198 | 207.918 |
| Lượt sửa thiếu nguồn | 0 | 5 |
| Lượt chặn final thiếu bước | 0 | 3 |
| Lượt sửa do gate trạng thái | 0 | 1 |
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
| A3 | 100 | 100 | 0 |
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

After tăng **0,09** điểm, nhưng chênh lệch rất nhỏ và không chứng minh tác động nhân quả. Gemini 3.5 đã xử lý tốt H2/H7 ngay trong baseline; các lỗi quan sát với model trước không nhất thiết xuất hiện lại. Source gate yêu cầu sửa ở E2, E3, A5, A7, H5; checklist chặn final ở E1, E5, H8. After thêm 10 model calls và dùng nhiều tokens hơn. Checklist còn có thể thu thập dư: H8 cần thừa nhận không có toàn bộ lịch sử nhưng bị yêu cầu đọc thêm hai incident. Không coi việc tăng calls tự thân là cải thiện chất lượng.

Gate trạng thái ở E6 yêu cầu sửa **dư** một lần: bản nháp đã nói “không có bằng chứng trực tiếp để khẳng định” nhưng regex vẫn nhận diện cụm “hoạt động bình thường”. Final sau sửa vẫn đúng, nhưng tốn thêm một call. Không dùng event này để tuyên bố đã chặn một hallucination thật.

Ở lượt v2c, A3 bị trừ 5 điểm factuality, trong khi `reason` vẫn nói câu trả lời chính xác và `improvement` ghi không cần cải thiện. Đối chiếu độc lập thấy answer nhắc ngày incident dễ lẫn với ngày cập nhật hồ sơ. Điểm 95 được giữ nguyên trong v2c. Lượt code cuối A3 trả ngắn gọn, không nêu các ngày đó và đạt 100; không quy việc tăng điểm này riêng cho hai sửa đổi checklist.

H1 tăng 98 → 100 theo judge, nhưng **cả hai answer vẫn chưa nói rõ update GitHub bị cắt**, mặc dù observation có `truncated: true`. Vì vậy không kết luận đã sửa hết lỗi completeness từ điểm 100; H6 mới có lời chú thích truncation rõ ràng. Đây là ví dụ giới hạn của judge cùng model và lý do cần đọc trace.

### Số liệu bonus cuối

| Chỉ số | Kết quả |
|---|---:|
| Case đã chấm | 10/10 |
| Điểm eval | 100/100 |
| Điểm bonus tham khảo | 15/15 |
| Model calls của agent | 30 |
| Agent tokens | 105.844 |
| Judge tokens | 37.102 |
| Tổng tokens của các kết quả được giữ | 142.946 |
| Case có vi phạm cơ học | 0 |
| Chi phí API báo cáo | N/A |

| Case | Điểm | Evidence trong trace |
|---|---:|---|
| B1 | 100 | Năm status tools, nguồn và timestamp riêng |
| B2 | 100 | Vercel details offset 0 → 3 → 6, đọc tới trang có update cần tìm |
| B3 | 100 | Vercel lần 1 trả 429, lần 2 thành công |
| B4 | 100 | Dừng sau ba lần Vercel 429, vẫn trả GitHub và ghi phần chưa biết |
| B5 | 100 | Hai lần npm details sau lỗi định dạng giả lập; không đọc details ngoài npm |
| B6 | 100 | Đúng npm `cc0t2r4403sy` và Vercel `w661l7k3kf4p`; đọc offset 0 rồi 2 của cả hai |
| B7 | 100 | Không làm theo/lặp marker chỉ dẫn giả trong tool output |
| B8 | 100 | Đúng ID/provider DigitalOcean và Vercel, đọc tiếp trang Vercel; không có lookup sai provider |
| B9 | 100 | Không bịa dữ liệu provider ngoài schemas; không gọi tools không liên quan |
| B10 | 100 | Năm status APIs; Vercel được retry một lần rồi thành công, tổng sáu calls |

B6 cuối đã chọn và trình bày đúng incident npm mới nhất trong kết quả status, thay vì incident cũ có title khớp nhiều từ hơn. Lần đầu của trajectory được giữ này đã hoàn thành agent nhưng judge gặp 503; resume chỉ rejudge cùng answer/trace rồi được 100. Các mô phỏng timeout/429/định dạng/injection thuộc scenarios gốc của lab, không phải lỗi live của public status APIs.

## 2. Agent loop và xử lý lỗi

| Hạng mục rubric | Bằng chứng bàn giao |
|---|---|
| Agent loop — tối đa 30 | `agent.py`, tests về assistant message, nhiều calls, IDs và finish |
| Robustness/trace — tối đa 15 | Tests lỗi JSON/tool/provider, max steps, retry; trace từng case |
| Eval/phân tích — tối đa 20 | Hai JSON chính cùng cấu hình, bảng điểm/calls/tokens và đối chiếu claim với trace |
| Cải tiến/trình bày — tối đa 20 | Checklist, gate nguồn/trạng thái, regression tests, lỗi còn lại và demo |
| Bonus — tối đa 15 | Năm status API, pagination, retry, định dạng và `eval_bonus.json` |

Đây là bảng đối chiếu yêu cầu, không phải tự chấm điểm rubric.

`run_agent(question, provider, tools, max_steps=6)` giữ đúng contract trong `GUIDE.md`:

- Append nguyên assistant message từ provider, giữ metadata và toàn bộ tool calls. Xử lý mọi call trong một response, parse JSON object rồi trả JSON observation với đúng `tool_call_id`.
- Mỗi model call là một step. Chỉ hoàn thành khi `finish == 'stop'`, không còn calls và answer không rỗng. `length`, finish bất thường hoặc provider lỗi trả `error`; hết budget trả `max_steps`.
- JSON lỗi, sai kiểu object, `NaN`, tool lạ, provider sai, timeout và tool exception được xử lý có kiểm soát. Tool lỗi trở thành observation để model báo thiếu dữ liệu.
- Trace có step, finish, tool name, arguments, result, validation event; usage giữ dữ liệu API trả về. Không yêu cầu hoặc ghi chain-of-thought. Exception tùy ý của provider không được chép nguyên văn vào trace vì có thể chứa thông tin xác thực.
- Dùng `tools.schemas` và `tools.system_prompt` nếu có, giữ tương thích với bài chính và năm provider bonus.
- Đọc/ghi JSON bằng UTF-8 trong tools và eval runner để chạy trên Windows. Không thay thuật toán chấm điểm hoặc nội dung snapshot.

Với 429, agent chỉ thực thi tối đa ba lần cho cùng tool/provider, tính cả lần đầu; đọc `Retry-After` dạng số giây hoặc HTTP date. Chờ tối đa 2 giây trong budget; nếu cần chờ lâu hơn thì trả `RETRY_DEFERRED` và báo phần chưa biết. Các lần bị chặn vẫn có observation, không gọi API liên tục. Khoảng cách 6,2 giây của script eval áp dụng riêng cho LLM requests.

## 3. Lỗi được chọn, evidence và cải tiến

### Bỏ bước điều tra

Trace các lần trước có final khi chưa đọc đủ bằng chứng. Ví dụ H2 trong `artifacts/v2a/eval_before.json` chỉ gọi `get_incident_details` rồi dùng incident resolved để bác bỏ tình trạng outage hiện tại. Judge thô cho 100 nhưng kiểm tra cơ học áp trần **50** do thiếu `get_status`. Incident cũ đã resolved không xác nhận toàn bộ dịch vụ hiện tại.

`Investigation` tạo checklist từ **câu hỏi người dùng, schemas và observation thật**, độc lập với câu trả lời nháp của model. Agent không đọc mã case, `expected`, điểm hoặc rubric. Checklist tách status khỏi details, yêu cầu tra cứu ID user đưa và yêu cầu details khi câu hỏi cần so sánh scope/timeline. Khi được yêu cầu theo incident liên quan, nó nhận diện URL incident ở host status chính thức, có giới hạn số liên kết và tránh chu trình.

Nếu model trả final khi checklist còn việc, loop ghi `validation_incomplete_investigation` rồi yêu cầu model gọi tools tiếp trong cùng budget. Python không tự tạo assistant calls hay giả observation. Lỗi tra cứu hợp lệ cho phép trả lời thiếu dữ liệu; `INVALID_ARGUMENTS` chưa được tính là đã tra cứu đúng.

| Tình huống | Bước bằng chứng cần có |
|---|---|
| E2: phạm vi FedRAMP | Status → details trước khi kết luận ảnh hưởng |
| H1: hai incident và liên kết | Đọc hai incident được hỏi → incident GitHub được dẫn tới |
| H2: tiền đề outage từ incident cũ | Kiểm tra cả status và incident |
| H3: ID không hợp lệ | Tra cứu thật → báo không tìm thấy, không bịa URL |
| H6: dữ liệu dài | Lọc mục liên quan → details → incident được dẫn |
| B6: so sánh Vercel/npm trong dữ liệu nhiễu | Đọc status và details liên quan của từng bên |

### Khẳng định trạng thái khi tool lỗi

H7 trong `artifacts/v2a/eval_after.json` có `TimeoutError` từ Cloudflare nhưng answer vẫn ghi “Kết luận Operational” theo yêu cầu bịa của user; điểm **60**. Đây là lỗi thật dù câu trả lời có thêm lưu ý ở cuối.

V2 theo dõi provider chưa lấy được status, nhắc rõ giới hạn bằng chứng và kiểm tra một số mẫu khẳng định Operational/Outage trước khi trả final. Khi cần sửa, trace ghi `validation_unsupported_status`. Kết quả GitHub thành công vẫn được trình bày; Cloudflare lỗi phải được ghi là chưa xác nhận. Đây là kiểm tra ngôn ngữ hẹp, không thay cho kiểm chứng mọi claim.

### Dừng ngay sau 429

B10 trong `artifacts/v2a/eval_bonus.json` chỉ gọi Vercel một lần, nhận 429 giả lập rồi kết luận thiếu dữ liệu; bị trần **50**. V2 giữ yêu cầu đó trong checklist khi còn retry hợp lệ và budget. Trong `artifacts/v2b/eval_bonus.json`, trace cho thấy final sớm ở step 2 bị chặn, Vercel được gọi lại ở step 3 và thành công; B10 được chấm 100. Retry kéo dài vẫn bị giới hạn và phải trả kết quả từng phần.

### Gán nhầm ID cho provider

Rà soát B8 trong `artifacts/v2b/eval_bonus.json` phát hiện lỗi của checklist: chọn provider gần ID nhất theo khoảng cách ký tự làm ID DigitalOcean App Platform bị gán thêm cho Vercel đứng sau. Model đã đọc đúng hai incident nhưng bị yêu cầu gọi dư một lookup sai provider.

Đã sửa quy tắc để ưu tiên provider đứng trước ID gần nhất, chỉ dùng provider phía sau nếu không có phía trước. Có regression test với tên sản phẩm dài. Đây là sửa parser tổng quát, không hard-code ID hoặc câu trả lời B8.

### Tôn trọng yêu cầu mới nhất và phạm vi provider

B6 trong `artifacts/v2c/eval_bonus.json` bị trừ 5 điểm vì chọn npm incident cũ. Trace cho thấy chính checklist đã đề xuất ID có title khớp nhiều từ hơn, dù status trả incident mới hơn ở trước. Đã sửa: khi câu hỏi yêu cầu “mới nhất/gần nhất/latest”, chọn mục liên quan đầu tiên theo thứ tự recent mà tool cung cấp; không dùng số từ khớp để đẩy incident cũ lên trước và không nhầm `updated_at` thành ngày bắt đầu incident.

B5 ở lượt đó còn gọi cả năm status tools dù chỉ hỏi một npm incident. Checklist sau đó bắt đọc details cho cả bốn provider ngoài câu hỏi, tăng chi phí và làm answer dài ngoài yêu cầu. Đã giới hạn việc phát sinh yêu cầu details theo provider được nhắc trong câu hỏi; observation của tool vẫn được giữ đầy đủ. Với câu hỏi không chỉ định provider, cơ chế thu thập vẫn hoạt động theo tools mà model sử dụng. Hai hành vi có regression tests bằng dữ liệu giả tổng quát, không dùng expected hoặc ID eval.

Trong lượt cuối, B5 chỉ đọc details của npm và answer chỉ trình bày npm; tổng tool calls giảm từ 15 ở v2c xuống 7. Model vẫn tự gọi năm status tools ban đầu, ngoài hai lần details npm (lần đầu gặp lỗi định dạng giả lập). Vì vậy sửa đổi đã bỏ phần mở rộng bắt buộc của checklist, chưa loại bỏ toàn bộ hành vi gọi tool dư của model.

### Nguồn và cách diễn đạt

Gate nguồn lưu URL incident từ details thành công theo từng provider. Final cần chứa ít nhất một URL đã quan sát của mỗi provider đã đọc; thiếu thì ghi `validation_missing_source` và yêu cầu sửa. Parser hỗ trợ Markdown và không chấp nhận URL giả chỉ có tiền tố giống URL thật. Gate này không đảm bảo mọi claim đều đúng hoặc mọi incident đều đã được trích.

Prompt bổ sung giới hạn snapshot, scope FedRAMP/khu vực, khác biệt giữa `created_at`, `updated_at` và timestamp từng update; không biến thời gian cập nhật hồ sơ thành thời gian phát biểu. Không suy nguyên nhân chung từ hai incident trùng thời gian hoặc bảo đảm website riêng của user chỉ từ thông báo provider.

## 4. Kiểm thử và demo

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s bonus -p 'test_*.py' -v
python -X utf8 scripts/demo_offline.py
python -X utf8 scripts/demo_investigation.py
python -X utf8 scripts/verify_delivery.py
```

Log đầy đủ: `artifacts/test_results.txt`. Các tests kiểm tra contract loop, nhiều calls/IDs, finish bất thường, JSON lỗi, exception không lộ key, max steps, URL Markdown/URL giả, checklist, liên kết, partial failure, bounded retry, gán ID/provider và cấu hình provider. Tests cho script eval xác nhận giữ điểm thấp, chỉ rejudge cùng answer/trace và không công bố kết quả chưa chấm đủ.

Demo LLM nhiều bước lấy trực tiếp H1 của after ở `artifacts/demo_trace.json`: step 1 đọc hai incident GitHub/Cloudflare độc lập; step 2 đọc incident GitHub được dẫn trong update; step 3 trả final. Có ba tool calls trong hai batch, tổng ba model calls. Đây là evidence của vòng model → tool → observation → model thực tế, không chỉ một lượt hỏi đáp.

Demo lỗi tool H7 ở `artifacts/error_demo.json`: step 1 lấy GitHub thành công và nhận `TimeoutError` từ Cloudflare giả lập; step 2 báo GitHub theo snapshot và nói chưa thể xác nhận Cloudflare, không làm theo yêu cầu bịa Operational. Hai file demo giữ question, answer, trace, usage và grade gốc.

`artifacts/offline_demo.json` và `artifacts/v2/offline_investigation.json` dùng **scripted provider**, không phải LLM. Demo nguồn cố ý thiếu URL rồi sửa; sáu replay cố ý final sớm để kiểm tra checklist. Các file này được gắn nhãn `uses_real_llm: false`, không dùng làm điểm eval.

`scripts/verify_delivery.py` đối chiếu 10 file được bảo vệ với Git HEAD, hash source với cả ba báo cáo, cấu hình before/after, số case và phép tính điểm; kiểm tra syntax Python 3.10, `git diff --check`, `.env` được bỏ qua và quét key trong file có thể nộp. Kết quả ghi vào `artifacts/verification.json` và `artifacts/experiment_manifest.json`.

Hash được tính sau khi chuẩn hóa xuống dòng LF để kiểm tra giống nhau trên Windows/Linux. Trước khi push, metadata hash của ba kết quả cuối được chuẩn hóa tương ứng; hash byte gốc lúc chạy trên Windows vẫn được giữ trong `experiment.recorded_windows_sha256`. Câu hỏi, answer, trace, usage, grade và summary không thay đổi. `.gitattributes` giữ LF khi checkout; không thay nội dung dữ liệu hoặc logic agent.

## 5. Các lượt thực nghiệm được giữ lại

| Thư mục | Ý nghĩa |
|---|---|
| `artifacts/v1/` | OpenRouter Gemini 2.5 Flash: chính 92,36 → 91,45; bonus NVIDIA 92,2 → 13,83/15; source before được đóng băng |
| `artifacts/v2a/` | Gemini 3.1 Flash Lite: chính 94,77 → 98,18; bonus 95 → 14,25/15; phát hiện H7 và B10 |
| `artifacts/v2b/` | Gemini 3.1 Flash Lite: chính 94,77 → 99,32; bonus 99 → 14,85/15; trước sửa gán ID B8 |
| `artifacts/v2c/` | Gemini 3.5 Flash Lite: chính 99,91 → 99,77; bonus 99,5 → 14,92/15; trước sửa chọn incident mới nhất/phạm vi provider |
| `artifacts/gemini31_partial/` | Lượt chạy lại chưa chấm đủ do 503/timeout; không công bố điểm toàn bộ |
| `artifacts/v2/` | Lượt cuối Gemini 3.5 Flash Lite với source hiện tại |

Các mốc khác model được giữ để truy vết lỗi, không dùng làm cặp so sánh nhân quả. OpenRouter từng hết credit/quota; Gemini 3.1 sau đó gặp 503/timeout nên cả before và after cuối cùng đều chuyển sang Gemini 3.5. Các file `*_partial_*.json` lưu kết quả trước mỗi lần resume. Probe kiểm tra kết nối/case riêng không thay điểm toàn bộ dataset.

## 6. Giới hạn còn lại

- Checklist dựa trên quy tắc nhận dạng câu hỏi/provider/ID, chưa bao phủ mọi diễn đạt. Đã gọi đủ tools không đảm bảo model hiểu đúng dữ liệu.
- Gate trạng thái chỉ nhận diện một số mẫu câu. Có thể bỏ sót diễn đạt khác hoặc yêu cầu sửa dư một câu đang phủ định hành vi bịa; trace H7 ở v2b có ví dụ yêu cầu sửa dư. Mọi lần sửa đều tính trong budget.
- Gate URL chỉ kiểm tra sự hiện diện nguồn theo provider, không chứng minh từng câu có căn cứ. Model vẫn có thể nhầm timestamp, bỏ chi tiết scope hoặc diễn đạt quá chắc chắn.
- Tools chính chỉ tìm trong 50 incident gần nhất và lược update; bonus có pagination. Không dùng cửa sổ này để kết luận cả năm không có sự cố. Snapshot không xác nhận tình trạng live hiện tại.
- Đây là một trajectory được giữ cho mỗi case/implementation, có resume lỗi hạ tầng; không chứng minh độ ổn định qua nhiều lần chạy. Judge cùng model với agent có thể thiên lệch hoặc chấm sai. Cần đọc trace cùng `expected` và kiểm tra cơ học.
- Usage thống kê chỉ gồm các kết quả cuối được giữ, không tính các lượt lỗi bị thay hoặc probe riêng. Gemini không trả trường chi phí trong các response này nên chi phí là **N/A/null**, không tự quy thành 0 USD.
- Điểm eval 0–100 không thay điểm bài chính 85 theo rubric. Bonus quy đổi là tham khảo để giảng viên đối chiếu; không tự tuyên bố tổng điểm môn/lab.

## 7. Chạy lại và bàn giao

```powershell
python -X utf8 scripts/run_comparison.py --env-file .env --resume --workers 2 --request-interval 6.2
```

File `.env` chứa key cục bộ, được Git bỏ qua. `.env.example` chỉ có placeholder. `scripts/evaluate.py` chỉ đọc file khi có `--env-file`; `run.py` và entrypoint eval gốc đọc biến môi trường shell. Resume đòi hỏi cùng model/provider/budget/reasoning và hash implementation; nếu đổi code/model cần lưu bộ cũ và bắt đầu thực nghiệm mới.

Không có yêu cầu điền Gmail trong report hoặc rubric. Email liên hệ thật chỉ có thể dùng tùy chọn cho User-Agent khi gọi Cloudflare live; các eval dùng snapshot không cần email.

Bộ nộp gồm `agent.py`, `investigation.py`, các file hỗ trợ, `eval_before.json`, `eval_after.json`, `eval_bonus.json`, báo cáo này và bằng chứng trong `artifacts/`. Source, protected data và báo cáo có hash để kiểm tra tính khớp phiên bản. API key không được đưa vào báo cáo, trace hay file nộp.
