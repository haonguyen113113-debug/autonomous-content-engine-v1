# PROTOTYPE LOCK: MR-02 san-trang (white #FFFFFF / coral split)

**Status:** APPROVED AS PROTOTYPE — rebuild toàn bộ template pack theo card này.
**Files:** `docs/design/mr02-san-trang-proof.png` (1080×1920, render kèm
lite depth + detailing) · script `apps/studio_templates/redesign_mr02_skill.py`
(palette `SAN_TRANG`) · colorway proof trong `mr02-colorways-compare.png`.

## Audit chốt (ngày lock)

| Check | Kết quả |
|---|---|
| Contrast body (ink/white) | PASS ≥7 (test khóa) |
| Contrast secondary (slate/white) | PASS ≥4.5 (test khóa) |
| Contrast loser zone (paper/slate trên ink) | PASS theo thiết kế gốc |
| Palette | PASS — chỉ white/ink/coral/slate/mist |
| Vietnamese diacritics | PASS mắt thường (HÀ NỘI, NAM ĐỊNH, Hàng Đẫy, Nguồn + ngày) |
| Slot contract | PASS — comp/when/home/away/score/source, không data bịa |
| No-overlap text | PASS mắt thường |
| Safe areas | PASS text (margins 76, top ≥195, credit 1820 như bản gốc duyệt); crop-marks decor bleed có chủ đích |
| Winner encoding | PASS — coral field→white field + ink monumental + coral bar (không cần chữ "thắng") |
| Grain mask band sau context line | NOTE — vệt sạch sau dòng context là mask bảo vệ microcopy, đọc như highlight, chấp nhận |

## Spec rebuild toàn pack từ prototype này

1. Nền trắng `#FFFFFF` dominant; khối đối lập Coral đặc (không tint nhạt).
2. Winner = ink monumental + coral bar + coral glow; loser = ink numeral/name
   trên coral, credit ink (ink/coral ≥4.5 đã khóa bằng test).
3. Context 1 dòng sentence-case slate; provenance mist y1820.
4. Circle motif + corner marks + notched trim + perforation + ticks + pinstripes
   (detailing.py, non-data only) — liều lượng như proof.
5. Lite depth (top-light + glow + grain nửa, bỏ haze trên nền trắng).
6. Numerals BigShoulders (latin only); tiếng Việt Barlow/BeVietnam.
7. Mỗi card rebuild phải pass: contrast pairs, palette audit, slot contract,
   eyeball owner — như checklist trên.
