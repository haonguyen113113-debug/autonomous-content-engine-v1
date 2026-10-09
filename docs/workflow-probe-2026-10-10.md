# Workflow probe — 2026-10-10 (run `1370343377aa`)

Headline: **Việt Nam tranh hạng Ba FIFA ASEAN Cup với Malaysia giữa bão chấn thương**
(Nguồn: VNExpress 07/10, VFF via TTV 08/10 — ĐTVN thiếu Đỗ Hoàng Hên/Tài Lộc/Xuân Son,
Kim Sang Sik trao cơ hội cho cựu QBV). Mở trong Workflows để duyệt.

## Stage results

| Stage | Time | Result |
|---|---|---|
| Script draft (Groq chain, 7 calls) | 18.2s | 6 beats, 0 fallback, $0.00, template **v0.9.0** |
| Asset library check (3 needs) | <1s | eligible 1/4/0 — xem nghẽn dưới |
| Distribution plan | 0.02s | `BLOCKED` — chờ owner duyệt (đúng thiết kế) |
| Publish attempt | <1s | `BLOCKED` — thiếu script approval + voice (đúng thiết kế) |

## What works

- Groq-first drafting: `qwen3.8-27b` → xoay `gpt-oss-120b/20b` khi limit, 18s xong 6 beats.
- Nova end-to-end ngay lần chạy đầu: beat-1 `hook_card`, hook 7 chữ
  "Việt Nam tranh hạng Ba, bão chấn thương" (đúng 5–8 chữ).
- Gates chặn đúng chỗ, không publish lọt.

## Bottlenecks & improvements

1. **Discovery trả 0 candidates cho cả 3 needs** (không lỗi, chỉ `NO_CANDIDATES`).
   2 needs shortfall → owner phải tìm tay hoặc chốt dùng authored boards.
   Cần cải thiện: log query/provider vào asset_checks, thử lại với query EN,
   kiểm tra Pexels key còn hạn không.
2. **Mode đơn điệu: 5/6 beats `source_card`.** Model chọn an toàn, video sẽ buồn.
   Cần cải thiện: prompt cân bằng mode (ép ≥1 tactical/chart khi có số liệu),
   hoặc post-check đa dạng mode trước owner review.
3. **Voice reference chưa có → full video tắc cứng.** `runtime/voice` trống nên
   voice preview/render-full đều fail cho đến khi owner thu mẫu 1 lần.
   Đây là việc owner duy nhất còn lại trước video hoàn chỉnh đầu tiên.
4. Draft status và evidence flow tốt; không phát sinh chi phí ($0.00/0.25 budget).

## Next owner actions

1. Duyệt script run `1370343377aa` trong Workflows.
2. Thu voice reference 1 lần (xem `docs/voice-baseline.md`).
3. Audit visual release Template Nova 0.9.0.
