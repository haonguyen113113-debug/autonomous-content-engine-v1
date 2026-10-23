# Đánh giá repo & bước tiếp theo để hoàn thiện engine — 2026-10-23

Phạm vi: rà soát read-only trên checkout Linux của `main@94078f5`, có chạy test
suite và đọc contract/pack. **Không** render MP4, **không** chạy UI, **không**
gọi mạng (xem mục 6).

> **Cập nhật 2026-10-23 (sau bản review này):** M0, M1, M2 đã xong; M3 chạy
> hai lần và đã sửa 3 lỗi thật do lần đầu phát hiện — video đứng hình trong
> beat, contrast fail 3/3 beat, BP-16 thiếu dòng `support`. Gate hiện tại:
> 37 PASS, 1 FAIL (`Asset Library media` — không có media thật), clip QA
> NEEDS_REVIEW vì voice là WAV im lặng. Còn chặn PASS: review C-09 cho 12.2.0,
> media có rights, và mắt người trên contact sheet/MP4.
> Chi tiết: `docs/coordinator/reviews/R4-final-gate.md`. Số liệu test cũ
> (136 fail) đã lỗi thời — hiện **674 passed**.

---

## 1. Kết luận ngắn

Engine đã có **contract layer rất tốt** (rights scope fail-closed, card contract
90/90, Scene Graph tất định, QA ba trạng thái, tài liệu coordinator đầy đủ).
Nhưng nó **chưa "hoàn thiện"** ở ba tầng khác nhau, và tầng chặn đường ngay
lúc này không phải là tính năng:

| # | Vấn đề | Mức | Ảnh hưởng |
|---|---|---|---|
| 1 | Contract freeze hash theo CRLF → engine chết trên mọi máy không phải Windows | **P0** | 136/184 test fail trên Linux; không thể có CI; phá cam kết "portable" |
| 2 | 8/16 visual grammar không có card contract → R3/R4 không thể PASS | **P1** | Đây chính là blocker S3.1/S2.5 mà R4 ghi nhận |
| 3 | Scene Graph path mặc định **tắt** | **P1** | Mọi cải tiến planner không tới được file render |
| 4 | Worker chỉ chạy job `draft`, không có production job | P2 | Không có nền cho Hermes poll status |
| 5 | Chưa có API/schema Hermes, không auth | P2 | Chưa nối được outer agent (đúng như docs đã thừa nhận) |

**Bước tiếp theo tôi khuyên làm ngay (nửa ngày):** sửa P0.1 + dựng CI. Nó không
phải việc "cho đẹp" — hiện tại bất kỳ ai clone repo trên Linux/macOS, hoặc bất
kỳ CI nào, đều nhận một engine **fail-closed ở mọi bài toán** vì lý do không
liên quan gì đến nội dung.

---

## 2. Số liệu tôi đo được (không suy đoán)

Chạy `python -m pytest tests -q` trên checkout sạch, Python 3.11, không có
ffmpeg/ffprobe, không có key:

| Trạng thái | Passed | Failed | Skipped |
|---|---|---|---|
| Checkout nguyên trạng | 437 | **184** | 1 |
| Sau khi chuẩn hoá CRLF ở 2 chỗ hash | **618** | 3 | 1 |

Trong 3 fail còn lại:
- 1 do **môi trường**: `test_short_form_render_full_run_skips_opening` —
  `FFprobe was not found`.
- 2 do **test tự hard-code hash CRLF**:
  `test_12_1_0_reuses_12_0_0_resources_and_keeps_c09_starter_bytes`
  (mong `877543db…`, thực tế `5f2a0e6d…`) và
  `test_generator_output_matches_the_runtime_contract`.

Nghĩa là: **code đúng, artifact bị đóng băng theo line-ending của một máy
Windows duy nhất.** Không có bug logic nào ẩn sau 184 fail đó.

---

## 3. Phát hiện chi tiết

### P0.1 — Hash contract đóng băng theo CRLF (blocker thật sự)

Bằng chứng đo trực tiếp trên `apps/studio_templates/BP-01.short.json`:

```
kích thước : 2663 bytes, 131 dòng
sha256 LF  : a823c0a444a6afd5…   ← đây là thứ Git lưu và thứ Linux đọc
sha256 CRLF: 388e049b547e35b2…   ← đây là giá trị ghi trong card-contract.json
```

Chuỗi `388e049b…` xuất hiện trong **cả** `12.0.0/card-contract.json` và
`12.1.0/card-contract.json` ở trường `starter_sha256`. Repo **không có**
`.gitattributes`, blob lưu LF.

Chuỗi thất bại:

```
load_contract()                       apps/studio_templates/card_media.py:797
  └ _load_cached → validate_contract   :785 / :767
      └ _validate_against_starter     :548
          └ _sha256_file              :160   hashlib.sha256(path.read_bytes())
              → "starter_sha256 drifted; regenerate the contract"
```

Đường thứ hai, độc lập, cùng lỗi: `apps/scene_graph/schema.py:702`
(`_starter_children` → "contract starter drifted from the frozen hash").

Hệ quả không chỉ là test đỏ: `build_scene_graph()` gọi `load_contract()` ngay
đầu, nên trên máy LF **toàn bộ planner/selector/renderer/QA dừng**, kể cả khi
chạy thật. Đây là lý do 46 test `card_selector`, 32 `card_media_contract`,
27 `card_contract`, 25 `renderer_scenegraph` cùng đỏ.

**Cách sửa (4 việc, ~2–3 giờ):**

1. Gom về **một** helper duy nhất, hash nội dung đã chuẩn hoá:

   ```python
   def file_digest(path: Path) -> str:
       data = path.read_bytes().replace(b"\r\n", b"\n")
       return hashlib.sha256(data).hexdigest()
   ```

   Dùng nó ở `card_media.py:160` và `schema.py:702` (xoá bản sao thứ hai).
2. Regenerate contract: `python tools/build_card_contract.py --write --version 12.1.0`
   (và `12.0.0`). Việc này **đổi `contract_hash`** — phải cập nhật `docs/ENGINE_STATE.md`
   + `docs/coordinator/*` và chấp nhận invalidate frozen graphs cũ, đúng như quy
   ước "regenerating it invalidates frozen graphs by design".
3. Thêm `.gitattributes`:

   ```
   * text=auto eol=lf
   *.json text eol=lf
   *.py   text eol=lf
   *.png  binary
   *.jpg  binary
   *.ttf  binary
   ```
4. Sửa 2 test hard-code hash để tính hash chuẩn hoá thay vì so literal.

Sau bước này: 618 → **620 passed**, và **622 passed** trên CI có ffmpeg
(test render thật chỉ còn phụ thuộc ffprobe).

### P0.2 — Smoke test render tự skip, nên "same-beat motion" không bao giờ đóng được

`tests/test_scene_graph_render_smoke.py:117` skip khi thiếu ffmpeg. README đang
yêu cầu: *"Treat same-beat motion as unresolved until the smoke test passes"* —
nhưng trên máy không có ffmpeg, suite vẫn "xanh" mà chưa chứng minh gì. Đây là
false-green đúng loại mà triết lý QA của repo muốn tránh.

Sửa: CI cài ffmpeg; và cho phép `ACE_REQUIRE_RENDER_TESTS=1` biến skip thành
fail để môi trường release không thể lặng lẽ bỏ qua.

### P1.1 — 8/16 visual grammar không có card contract (gốc của R3/R4)

Đối chiếu `visual-modes.json` (16 mode) với `12.1.0/card-contract.json`:

| Có card contract (short) — **8/16** | Không có card contract (short) — **8/16** |
|---|---|
| hook_card, duel_columns, stat_leader, score_card, source_card, player_poster_side, player_poster_top, potm_card | **tactical_explainer**, conclusion, goal_card, fixture_card, fixture_list, quote_card, discipline_card, welcome_card |

Phân bố execution trên 90 card: **21 `contract`, 7 `partial`, 62 `legacy_non_ready`**.
Toàn bộ `TA-*` là long-form và bị defer, nên beat `tactical_explainer` chỉ còn
đường "legacy pitch plate" — khớp đúng R3 blocker #1 (5 beat cùng một mode) và
#4 (không có hierarchy hook → evidence → attribution). Đây là **thiếu card ở
template layer**, không phải lỗi renderer, và R3 packet đã đúng khi cấm vá
renderer.

Đề xuất: pack **12.2.0** author tối thiểu 2 card 1080×1920 có contract:
`tactical_explainer` và `conclusion`. Definition of done:
`execution.status == contract`; planner chọn được; `check_card_contract`
trả `PASS` (không `NEEDS_REVIEW`); `build_card_contract.py --check` xanh;
có snapshot test khoá box/font như các card khác.

### P1.2 — Scene Graph path mặc định tắt

`apps/video_renderer.py:3001`: nếu `ACE_SCENE_GRAPH_RENDER != "1"` thì đi path
legacy; biến này **không có** trong `.env.example` và không có trong README.
Nghĩa là mặc định (và trong R3 report) render vẫn chạy legacy, còn planner
chỉ được test bằng test. Nên đảo cờ: graph là mặc định, legacy sau
`ACE_RENDER_LEGACY=1`, rồi ghi vào `.env.example` + `docs/transferable-runtime.md`.
Làm việc này **sau** P1.1, nếu không sẽ chỉ đổi cái gì được render sai.

### P2.1 — Worker chưa phải production pipeline

`apps/worker/queue_store.py:27` → `SUPPORTED_TYPES = ("draft",)`;
`apps/worker/runner.py` chỉ dispatch `draft`. Voice/render/QA hiện chạy đồng bộ
trong HTTP handler của `apps/web_ui/server.py`, nên: request dài, không retry
theo bước, restart giữa render là mất, không resume, không có trạng thái để
poll. Queue file-backed và atomic đã tốt — thiếu **loại job** và **state machine**.

Đề xuất: thêm type `production` với payload `run_id` + contract version;
stage `validate → resolve_assets → plan → voice → render → qa`; mỗi stage ghi
artifact + trạng thái + lỗi; retry chỉ stage lỗi; idempotent theo `run_id`.
Đây là điều kiện tiên quyết cho mục 4.2.

### P2.2 — Boundary Hermes chưa tồn tại (đúng như tài liệu nói)

`docs/hermes-engine-integration.md` mô tả đúng nhưng chưa có gì được build:
không JSON Schema versioned, không submit/status có auth, không idempotency,
không vocabulary trạng thái. `POST /api/content/batch-runs` là hàng đợi draft,
không phải production API.

Kèm theo, nếu mở server ra ngoài localhost:
- `apps/web_ui/server.py:1443` mặc định `--host 127.0.0.1` nhưng cho phép
  `0.0.0.0`, **không có auth cho bất kỳ route `/api` nào**.
- `apps/web_ui/server.py:273`: `/api/studio/config` trả **nguyên văn**
  `POLOTNO_API_KEY` cho client. Chấp nhận được khi chỉ localhost; phải chặn
  hoặc bỏ field `key` trước khi bind mạng.

### P3 — Vệ sinh repo (không chặn, nhưng nên dọn)

- **Kích thước:** 572.5 MB tracked trong 1 commit, `.git` pack 402.65 MB.
  `assets/originals/plates/*.png` có file 5–7 MB (254 PNG + 178 JPG).
  Clone chậm, GitHub sẽ cảnh báo. Cân nhắc Git LFS cho `assets/originals/plates/`
  hoặc downsample bản lưu kho (bản render vẫn 1080×1920).
- **Script one-off:** `build_starters_v10/v11/v12.py`, `fix_*.py`, `proof_*.py`
  (~3k dòng) đang nằm trong `apps/studio_templates/` như code runtime. Nên
  chuyển `tools/archive/` để người mới không nhầm là entrypoint.
- **README lệch thực tế:** đang ghi "103 passed, 1 failed", "same-beat motion
  unresolved", "chưa verify sau merge" — trong khi suite hiện 618 pass (sau P0.1)
  và smoke test ít nhất không còn fail. `ENGINE_STATE.md` ghi "554 passed" cũng
  đã cũ.
- **`docs/coordinator/STATE.json`:** chứa `repo_root` tuyệt đối
  `C:/Users/...`, commit `4755cd9` trong khi HEAD là `94078f5`, và task
  `PACKET_READY` cho việc đã xong. Nên coi đây là file generated, không commit,
  hoặc thêm cảnh báo "snapshot, có thể cũ".
- **Thiếu dev requirements:** không có `pytest` trong bất kỳ `requirements*.txt`
  nào. Thêm `requirements-dev.txt` (`pytest==8.*`) để CI tái lập được.
- **Không có CI:** không có `.github/workflows`. Đây là lý do P0.1 sống được
  đến hôm nay.

---

## 4. Thứ tự thực hiện đề xuất

| Mốc | Việc | Done khi | Ước lượng |
|---|---|---|---|
| **M0** | P0.1 + P0.2 + CI | `pytest` xanh trên ubuntu-latest có ffmpeg; `build_card_contract.py --check` xanh; không còn hash literal CRLF | 0.5 ngày |
| **M1** | Pack 12.2.0: card `tactical_explainer` + `conclusion` | planner chọn được, QA `PASS`, R3 blocker #1/#4 đóng | 1–2 ngày |
| **M2** | Đảo mặc định `ACE_SCENE_GRAPH_RENDER`, ghi env/docs | render mặc định đi graph; legacy chỉ khi opt-in | 0.5 ngày |
| **M3** | **R4 gate thật**: 1 render short 12.2.0, contact sheet + MP4, người duyệt S1–S5 | verdict package có Tier-2 human PASS | 1 ngày |
| **M4** | Production job type + state machine trong worker | job `production` chạy được, resume sau restart, có status | 1–2 ngày |
| **M5** | Hermes API v1: JSON Schema + auth + idempotency + status | Hermes submit → poll → `ready_for_owner_review` | 2–3 ngày |
| **M6** | Dọn P3 | repo < 100 MB hoặc có LFS; README/STATE đúng | 1 ngày |

Điểm cần nhấn: **M3 mới là "hoàn thiện engine" theo định nghĩa của chính repo**
(`GOAL_AND_THRESHOLDS.md`: PASS = human eyes trên contact sheet + MP4). M4/M5
là để engine trở thành *dịch vụ* cho Hermes; đừng làm M4/M5 trước M0–M3, vì
chúng chỉ tự động hoá một pipeline chưa qua gate.

Nếu chỉ chọn **một** việc cho tuần này: **M0**. Nếu chọn hai: **M0 + M1**.

---

## 5. Điểm mạnh nên giữ (đừng "cải tiến" mất)

- `rights_scope.is_usable_for()` deny-by-default, tách rights khỏi suitability,
  `verified` không phải giấy phép chung — đúng và hiếm.
- `graph_hash` + validate fail-closed + từ chối graph bị sửa kể cả khi hash
  được tính lại — mức kỷ luật contract này rất tốt.
- QA ba trạng thái có `NEEDS_REVIEW`, `check_text_fit` đo theo box đã freeze,
  `check_media_placement` so pixel với baseline pack-only — đúng hướng "không
  PASS nếu chỉ dựa vào asset ID".
- Tách "legacy/partial/contract" theo từng card là cách đúng để không âm thầm
  render thiếu.
- Bộ tài liệu `docs/coordinator/` (contracts, task packet, report, rubric)
  tốt hơn phần lớn repo cùng loại; giữ nguyên kỷ luật đó.

---

## 6. Những gì tôi **chưa** kiểm chứng

- **Không render MP4**: sandbox không có ffprobe (chỉ có ffmpeg qua PyPI), nên
  `test_scene_graph_render_smoke` bị skip. Mọi nhận xét về thẩm mỹ/hình ảnh
  trong tài liệu này là kế thừa từ R1/R3, **không** phải tôi đã xem.
- **Không chạy UI** (`apps/web_ui/server.py`) và không đánh giá trải nghiệm.
- **Không gọi provider** (Openverse/Wikimedia/Pexels) nên không đánh giá chất
  lượng discovery/ranking thực tế.
- Không có key LLM/TTS nên nhánh voice và nhánh draft-cloud không được chạy.

---

## 7. Lệnh tái lập

```bash
python -m venv .venv && . .venv/bin/activate
pip install pytest pillow
python -m pytest tests -q                    # 437 passed, 184 failed (LF checkout)

# chứng minh nguyên nhân
python - <<'PY'
import hashlib, pathlib
b = pathlib.Path("apps/studio_templates/BP-01.short.json").read_bytes()
print("LF  ", hashlib.sha256(b).hexdigest())
print("CRLF", hashlib.sha256(b.replace(b"\n", b"\r\n")).hexdigest())
PY
# LF   a823c0a444a6afd5…  (thực tế)
# CRLF 388e049b547e35b2…  (giá trị trong card-contract.json)
```
