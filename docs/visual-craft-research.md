# Visual craft research — thứ gì làm nên visual đẹp cho video

Nguồn: Disney 12 principles (via Adobe/Wikipedia/NYFA), School of Motion
(sports lower thirds), KeepTheScore/NewBlue (broadcast), kinetic-type guides
(TodayMade/Upskillist/SVGator/AICoursify), "Why Your Motion Design Looks Cheap"
(Stephan Zammit), "Why Your Motion Graphics Never Look Quite Like Vox"
(FlatPackFX), Videobolt glossary (2.5D/parallax/glow/grain), thumbnails thực tế
(Tifo 3.9–5.1M-view Shorts, FMS, Aperture, Copa90).

## 10 nguyên lý rút ra (khả thi với pipeline PIL + FFmpeg local)

1. **Staging — 1 frame, 1 ý.** Ánh sáng/bóng đổ chỉ mắt vào focal duy nhất;
   bỏ mọi chi tiết không phục vụ ý đó. (Plates cũ: rainbow chi tiết nhỏ tranh
   nhau — tab, slashes, số chương, rail mỏng.)
2. **Easing, không linear.** Zoom tuyến tính (`zoom+0.0004`) là cảm giác "máy
   móc" lớn nhất. Dùng ease-out cubic: nhanh đầu, settle cuối.
3. **Parallax 2.5D.** Nền chậm, chủ thể vừa, chữ nhanh — 3 tốc độ khác nhau
   tạo chiều sâu không cần 3D thật. Plates cũ: 1 lớp zoom đồng nhất.
4. **Ánh sáng có hướng.** Một nguồn sáng chủ đạo (trên-trái), glow/bloom/shadow
   nhất quán theo hướng đó. Glow đối xứng đều = giả.
5. **Texture.** Grain, vignette, light leaks là khác biệt "film/premium" vs
   "vector rẻ tiền". Plates cũ chỉ backdrop có grain.
6. **Exaggeration.** Đẩy quá thực tế một chút: chữ to hơn, rails dày hơn,
   glow mạnh hơn. Thiết kế cũ nhút nhát (số nhỏ, rails 5px).
7. **Kinetic type: vào nhanh, giữ để đọc.** 1–2s/cụm từ trên mobile; animate
   xong phải đứng yên cho đọc; không animate chữ trong lúc đang bay vào.
   Ít phần tử chuyển động cùng lúc — nền động thì chữ tĩnh và ngược lại.
8. **Broadcast grammar.** Hộp góc cạnh, glass 3D, duel screens, đọc được trong
   2 giây, motion theo genre (thể thao = năng lượng nhanh, không fade nghệ).
9. **Màu có vai trò.** Mỗi màu một nhiệm vụ cố định (chủ thể/áp lực/số/quan
   trọng), nền subdued để chữ nổi; contrast text/bg ≥ 4.5:1.
10. **Mọi chi tiết là quyết định (Vox).** Hệ thống: vai trò màu, vai trò type,
    nhịp spacing lặp lại mọi frame — không trang trí ngẫu hứng.

## Self-diagnosis: plates cũ fail ở đâu

| Lỗi | Nguyên lý vi phạm |
|---|---|
| Zoom đều tuyến tính mọi beat | #2 Easing |
| 1 plate tĩnh + zoom chung | #3 Parallax |
| Không grain, sáng đều | #4, #5 Light/Texture |
| Rails 5px, số nhỏ, glow đối xứng | #6 Exaggeration |
| Kicker/tab/số chương/slashes cùng hét | #1 Staging |
| Chữ bay + nền trôi cùng lúc | #7 Kinetic type |

## Build rules cho template tiếp theo

- Mọi zoom dùng ease-out cubic; text vào ≤0.3s rồi đứng yên đủ thời gian đọc.
- Mỗi scene 3 lớp tốc độ (bg 0.3x, subject 1x, type pop-in).
- Grain + vignette + 1 hướng sáng trên mọi plate tối.
- Focal duy nhất/frame; audit list furniture trước khi ship.
- Type ≥ 1/4 chiều cao khung cho claim; rails ≥ 8px; glow có hướng.
- Màu: nền subdued, 1 màu/một vai trò, contrast check ở 350px.
