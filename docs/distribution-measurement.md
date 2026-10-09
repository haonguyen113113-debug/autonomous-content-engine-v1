# Distribution + Measurement (mục 4 & 5)

Additive-only slice. Không sửa `template_foundation/*`, `apps/video_renderer.py`,
`apps/content_workflow.py`, `apps/web_ui/*`. Model song song có thể tiếp tục
ở template/renderer mà không xung đột file.

## Luồng

```
artifact (runtime/runs/<id>.json, read-only)
  -> quality_gate (script approved + evidence verified; publish cần voice audited)
  -> classify_theme (audience/thematic/format fit, giữ component + reasons)
  -> route_artifact (chọn 1 channel tốt nhất, không broadcast)
  -> plan_distribution (sidecar runtime/distribution/<id>.json)
  -> stage_plan / publish_plan (sidecar + runtime/publish/<id>/)
  -> measurement ledger (runtime/measurement/*.jsonl)
  -> classify_lifecycle (GENERATED != VERIFIED != STAGED != PUBLISHED != MEASURED != PAID)
```

## Dùng thử (stdlib only)

```python
from pathlib import Path
from apps.distribution import ChannelDestination, default_registry, plan_distribution, publish_plan
from apps.distribution.service import stage_plan
from apps.measurement import record_observation, record_payout, classify_lifecycle

root = Path(".")
run = {"run_id": "<12-hex>", "script_owner_approved": True,
       "evidence_verified_by_owner": True, "voice_preview": {...},
       "voice_preview_audited": True, "draft": {...}}

plan = plan_distribution(root, run, {"allen-knows-ball": [
    ChannelDestination(platform="local_file", account_ref="local"),
]})
stage_plan(root, plan)
result = publish_plan(root, run, plan, registry=default_registry())
```

- `youtube/tiktok/facebook` là stub: luôn trả `STAGED` + `adapter_not_configured`,
  không fake publish. Thay bằng adapter thật qua `AdapterRegistry.register`.
- `local_file` ghi manifest `runtime/publish/<id>/local_file.json`, không cần mạng.

## Economic truth

- `record_observation`: views/likes/conversions + `earnings_estimated_usd` (ước tính).
- `record_payout(verified_cash_received=True)`: tiền thật về tài khoản mới tính
  `profit_attributable_usd`. Estimate không bao giờ lên PAID.
- `summarize_by_run`: `contribution_margin_estimated = estimate - production`,
  `profit_attributable = verified_payout - production`.
- File ledger: `runtime/measurement/observations.jsonl`, `payouts.jsonl` (git-ignored).

## Server API (wired)

- `GET /api/distribution/<run_id>` — plan + publish records + lifecycle (read-only)
- `POST /api/distribution/plan` `{run_id, destinations[]}` — route + stage
- `POST /api/distribution/publish` `{run_id, dry_run?}` — publish via adapters
- `POST /api/measurement/observations` / `/api/measurement/payouts` — record (201)
- `GET /api/measurement/summary` — by-run + by-channel rollups

## Test

```powershell
python -m pytest tests/test_distribution_routing.py tests/test_measurement_ledger.py tests/test_distribution_api.py -q
```
