# Template v2.0.0 "Signature" — rework brief

## Audit thực tế trên plates 1.0.0 (xem ảnh render)

1. Source card: nội dung dồn top 25%, void giấy khổng lồ giữa claim và URL.
2. Chart column: nhãn giá trị đè lên tick trục ("6" đè line); bars một màu phẳng;
   giấy trống xung quanh, không điểm nhấn takeaway.
3. Statline: khoảng chết giữa rows, rails mỏng, số nhỏ so với canvas.
4. Hero: numeral trôi trong void đen, không spotlight/glow/reflection.
5. Chung: phẳng 2D, không depth/lighting/texture — thua kênh top về lực thị giác.

## Quyết định 3D

- **Không dùng Blender/3D thật:** phá portability (cài đặt GBs), render CPU
  chậm hàng chục phút/video, trái cost target local-first của spec.
- **Faux-3D trong PIL:** extruded type, spotlight radial, glassy pills,
  gradient+glow bars, reflection, vignette — đạt ~80% cảm quan broadcast
  với 1% chi phí, giữ pipeline CPU hiện tại. Blender là optional tương lai.

## Có mới trong v2.0.0

1. `spotlight`: quầng sáng radial sau focal mọi plate tối.
2. `extrude`: chữ display/hero/headline nổi 3–4px + glow.
3. Source card dựng lại: claim lớn giữa, seal nguồn tròn, quote watermark khổ lớn.
4. Chart: nhãn giá trị né tick trục; bars gradient + glow cap.
5. Statline: rows khít, số lớn hơn, rails phát sáng, edge gradient thay bars mỏng.
6. Hero: spotlight + extrude + reflection mờ + glow ring.
7. Vignette mọi plate. Giữ nguyên layout ids, fonts, palette family, motion 1.0.0.

## Acceptance

- Plates render không void/tràn/chồng lấn ở cả 2 aspect (xem ảnh).
- 18s preview + 24s overlay proof trên 2.0.0 PASS; draft mới resolve 2.0.0.
