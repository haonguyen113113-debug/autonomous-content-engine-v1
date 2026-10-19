# Script Score — rule-based draft scoring (`apps/content_score.py`)

Bài học từ Visibly AI (NSS): tách **chấm điểm** (deterministic, free) khỏi
**generation** (LLM, tốn tiền). Cùng segments chuẩn hóa luôn cho cùng điểm,
nên filter, owner review và writer ngoài dùng chung một thang.

## Dùng

```python
from apps.content_score import score_script
result = score_script(run["draft"]["segments"])
# {"score": 78, "version": "1.0",
#  "components": {"grounding":..,"entity":..,"speech":..,"variety":..,"readability":..},
#  "findings": [{"component":..,"severity":..,"message":..}]}
```

`entity_aliases=None` tự load `data/entities` (read-only); truyền list
riêng để test deterministic không chạm FS.

## Thành phần (tổng 100)

| Component | Weight | Đo gì |
|---|---|---|
| grounding | 30 | hết `[CẦN NGUỒN]`; số liệu có `evidence_refs` |
| entity | 20 | beats nhắc alias club/player/competition đã biết |
| speech | 20 | narration vừa slot (`CHARS_PER_SECOND=14`, floor 55%, overrun 1.25) |
| variety | 15 | beats liền kề không lặp ý (5-gram overlap) |
| readability | 15 | câu ngắn, không filler broadcast |

## Quy ước (khóa bằng `tests/test_content_score.py`)

- Không bao giờ raise với input xấu; vấn đề thành findings + hạ điểm.
- Không I/O (trừ load seeds), không LLM, không clock → 0 cost.
- Target thực tế: sửa theo findings rồi chấm lại, aim ≥70 như NSS 70-80.
- Score không thay thế owner review; nó xếp hàng đợi review theo giá trị.
