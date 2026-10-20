# Worker batch queue — draft qua đêm, duyệt buổi sáng

Worker cũ dùng `queue` trong RAM: server và worker là 2 process
riêng nên không bao giờ thấy job của nhau, restart là mất job. Giờ queue
nằm file trong `runtime/queue/{queued,claimed,done,failed}/<job_id>.json`
(`apps/worker/queue_store.py`) — producer và worker nào cũng thấy nhau.

## Luồng qua đêm

```
Tối: POST /api/content/batch-runs {jobs:[{topic, story_form, evidence, ...}]} (tối đa 20)
  → validate hết trước (topic 4-500 ký tự), sai 1 job là 400 cả batch, không enqueue gì
  → 201 {job_ids}
Đêm: worker local (`python -m apps.worker.main` trong terminal riêng)
  claim từng job → run_content_agent → draft xong dừng ở WAITING_FOR_OWNER_REVIEW
  → done (kèm run_id) / failed (kèm error). Retry trong-run giữ nguyên (3 lần, backoff).
  Restart giữa chừng: claim quá 30 phút tự về queued (hết attempts → failed, có lý do).
Sáng: GET /api/jobs xem queued/claimed/done/failed → vào UI duyệt từng run như cũ.
```

## Quy ước

- Job types: chỉ `draft`. Worker crash không mất job, không kẹt job (stale recovery).
- Gate của owner giữ nguyên: worker chỉ sản xuất draft, không duyệt, không publish.
- `GET /api/jobs` read-only; `POST /api/content/batch-runs` là producer duy nhất.
- Khóa bằng `tests/test_worker_queue.py` (roundtrip, reject input xấu,
  stale recover/requeue/exhaust, overview).
