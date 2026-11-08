# Vibicle 實作進度

MVP 採方案 A。E06 與 T31～T33／SR-T15～18 為 Deferred；八張業務表的規格與 71 項有效 AC 沿用 PRD。公網部署仍需正式網域、主機與管理權限。

## 基線重新驗證

- 2026-11-06 工作區有 `docs`、`web-app`、原作業文件與兩個既有 ZIP，無 `.git`。原始 Web3 專案未出現在本工作區。
- `docker compose ps` 顯示 PostgreSQL 18.6 健康。原開發 DB 和 Named Volume 保留。
- 由 `web-app` 執行 `./scripts/Test-Database.ps1`，在新驗證 DB `vibicle_3a_verify_9dff66edcd46` 重跑 0001 Migration、連線與 27 個整合測試，均通過。
- 初始前端 TypeScript 與 3 項 Vitest 通過。Windows Vite 預設 minify 在轉譯後退出 1，須排查。以新輸出目錄和 `--minify false` 建置成功，尚不計為預設 Build 通過。

## Slice 1 — Authentication

已實作 E01～E05。沿用 0001 三張表。新增 `errors.py`、`http_contract.py`、`repositories/auth.py`、`services/auth.py`，更新 `services/identity.py`、`routers/auth.py`、`main.py`、`schemas.py`、`config.py`、`database.py`。前端更新 `App.tsx`、`api.ts` 並新增 `auth.tsx`，加入 Web Locks、Auth Epoch、BroadcastChannel、非秘密 Pending marker 及 Uncertain UI。保留同 Context 登出重試；若無原 CSRF 或 Cookie 已換，結果仍未確認。

依賴變更為 pwdlib 0.3.1、argon2-cffi 25.1.0、email-validator 2.3.0、React Router 7.18.5 和 Node 型別。Lockfile 已更新。Argon2id 成本 m=19456 KiB、t=2、p=1，每 Process 只允許一個昂貴工作。Email 使用 normalized → PostgreSQL lower，允許合成 .test 網域，無 DNS 驗證。樣本已驗 Unicode 空白與大小寫；完整 Unicode Fixtures、併發與效能仍待驗證。開發設定範本與初始化腳本加入獨立限流 Secret，既有密碼保留。

| 驗證 | 狀態 | 命令及證據 |
| --- | --- | --- |
| E01～E05 正常流程、Cookie、重放、同帳號獨立 Session、來源／CSRF、閒置與限流 | Pass | 從 backend 設 `VIBICLE_TEST_DB=vibicle_3a_verify_9dff66edcd46` 後 `uv run pytest -q`，43 passed。包含 E05 真連線故障。 |
| Mypy | Pass | `uv run mypy`，17 個來源檔通過。 |
| HTTPS Chromium、跨分頁與 Login 回應中斷 | Pass（已測受控路徑） | `scripts/Browser-Auth.js`，實際 HTTPS Vite Proxy、兩 Tab、Server 成功 Login 後中斷回應、Reload 保留 marker。 |
| SR-T02／03／06／09／12／13 等競態、時間邊界、Restore | Not Run | 需要獨立 PostgreSQL 多連線與瀏覽器故障注入。CP-06 風險仍保留。 |

下一個依賴為 Slice 2 的 Vehicle／Mileage Ledger Migration 及 E07～E09。完成後重新檢查受保護車庫的 Auth AC。

## Slice 2 — 車庫與車輛建立

- E07～E09。新增 0002_vehicles，建立 vehicles 和 vehicle_mileage_changes。PK、VIN UQ、Owner FK、初始 Ledger partial UQ 與分頁索引。
- 修改 Backend models、Alembic、vehicle_schemas、routers/repositories/services/vehicles；前端新增 Garage、useRequest、useMutation、RequestState、types，App 按 Auth Epoch／User 隔離私人頁。
- Pass：`uv run pytest -q`（專用 DB head 0002）45 passed。包含兩連線 VIN、一位會員無法讀另一位的車、Mutation CSRF 和 Touch 失敗仍有業務成功結果。
- Pass：`scripts/Browser-Garage.js` 驗登入、新增、重新整理、手機寬度及車庫讀回。
- 未完整驗所有車庫分頁與 Fault 路徑，詳最終驗收。

## Slice 3 — 車輛編輯及目前里程

- E10／E21。共用 Vehicle Row Lock，驗 expected revision 與有效 H，同交易寫目前 C／Ledger；No-op 保留版本。VehicleEdit 表單明確確認下修。
- 0003_maintenance 提前建立有效 H 所需的 Event／Version 表，與 0002 連續；在既有驗證 DB 線上套用，`alembic check` Pass。
- Pass：`test_revision_lock_and_mileage_ledger` 兩連線同版本 200／409、非 Owner 404、無理由拒絕與初始／下修 Ledger。端到端 Browser 覆蓋另見 Slice 8。

## Slice 4／5 — 維修補登與更正

- E14、E16、E18、E19。新增 history_schemas、routers/repositories/services/history 與 VehicleHistory UI。0003 含 Deferred Composite FK、同事件 previous FK、唯一 previous／version_no。
- Pass：`tests/test_history.py` 真 PG 合理補登、衝突補登、競爭更正、舊值保留、H 重算後可降 C、版本分頁防混；全套到此 48 passed。
- 兩個 API 併發測試用真實多連線；瀏覽器雙分頁故障、跨車 FK 的完整負面測試仍需分開標記。

## Slice 6 — 私有主照片

- E22／E23。0004_vehicle_images 增加 Image Metadata 與同車 FK。新增 upload、image_worker、repositories/services/routers/images、clean_images、VehiclePhoto。
- Pillow 13.0.0、python-multipart 0.0.33 已鎖版；Linux 子程序 5 秒與 128 MiB 預算。Windows 本機子程序有 5 秒、尺寸與像素限制，OS 記憶體上限在 Linux runtime 生效。
- Pass：`tests/test_images.py` 真 PNG、Metadata、內容宣告不符、替換失敗保留舊圖、替換後舊 URL 404。完整格式及尺寸負面案例見最終驗收。

## Slice 7 — 公開 Marketplace

- E11～E13、E15、E17、E20。固定 Public DTO、不露 Owner Email、完整 VIN 或申報者 ID。新增 Marketplace、Listing；接回 Public Timeline、版本與 C 下修摘要。Public Detail／Market 在焦點恢復時重查。
- Pass：`tests/test_marketplace.py` 驗合法上架、literal 搜尋、no-op、公開投影及下架後詳情／照片／履歷不可讀。
- 公開路徑永不延長 Session，圖片由受控 E23 讀取。

## Slice 8 — Docker 與整合

- 新增兩個 Dockerfile、Caddyfile、compose.deploy.yaml、deploy env 範本、provision 與備份還原腳本。專用 Docker project／Volume，保留原本 dev DB／Volume。
- Pass：Compose Images 建置，Linux Vite 預設 minify 正常。Compose 初次有 API IP 衝突，固定 API／Gateway IP 後已修復。
- Pass：本機 Caddy `https://localhost:8443`，E05 和 `/garage/new` 回 200，Migration job 正常退出。API 與 PostgreSQL 不映射到 Host；Caddy 僅 loopback。
- 正式公網域名／ACME：Blocked by External Prerequisite。須使用者指定已持有的主機／域名及 DNS 權限。

## 交付狀態

- 22 個 MVP Endpoint 實作完成。E06／CP-API-01 保持 Deferred。13 項 Must Have／71 項有效 AC 的本機驗收對照見 [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md)。
- 兩套 Compose project 分離。原 `vibicle-foundation_postgres_data`、原開發 DB 和既有 ZIP／文件已保留。原 DB 只做增量 Migration，測試資料寫入驗證 DB 和本機 Docker 測試 project。
- 本機 `https://localhost:8443` 保持運行，公開車市有一台合成展示車。Caddy 對本機 HTTP 8080 回 HTTPS 8443，API 有啟動 Socket Healthcheck，避免首次啟動時暫時 502。
- Browser 腳本位於 `web-app/scripts`，已走過兩頁籤、重新登入／換帳號、凍結恢復、故障處理、失去 Register／Logout／Login／Mutation 回應、下架與圖片授權。Linux worker 6000×2000、超界、128 MiB 與 5 秒限制已驗。
- 備份／還原與容器重建均實測。還原目標 `vibicle-restore-e382e6dc` 為隔離的 9443 環境，舊 SID 失效且照片 bytes 一致。
- 公網網域／DNS／受信任 ACME Certificate 為 Blocked by External Prerequisite。Windows Native Vite Build 曾失敗，Docker Linux Production Build 已通過。
- CP-06 保持開放。故意繞過 Coordinator 時，另一個已提交 Session 的晚到 Cookie 仍可能被 Browser 套用，已以負面控制重現。完整 T／SR 壓力、BFCache、Commit Transport 與容器停機故障等未完成項目見驗收文件。自動審查阻擋隔離 PG 容器停止故障注入，獨立 API 對不可達 DB 已驗 503。

### 最終執行

| 項目 | 結果 | 重現方式 |
| --- | --- | --- |
| PostgreSQL 18.6／四個 Migration／八張業務表 | Pass | `Test-Database.ps1` 建新 DB，`uv run python -m alembic current` 及 `alembic check` |
| 後端全套 | 94 passed，0 skipped | 設 `VIBICLE_TEST_DB=vibicle_3a_verify_de65d4eb4bc1` 後 `uv run --locked python -m pytest -q` |
| 靜態與前端測試 | Pass | `uv run ruff check --no-cache`、`uv run mypy`、`npm.cmd run typecheck`、`npm.cmd test` 5 passed |
| Compose Gateway／TLS／SPA | Pass | `docker compose --env-file .env.deploy.local -f compose.deploy.yaml up -d --build --wait` 與 curl Local CA |
| 瀏覽器與備份／還原 | Pass | Browser 腳本、Backup-Vibicle.ps1、Restore-Vibicle.ps1；詳 [驗收表](FINAL_VERIFICATION.md) |
| 公網自訂網域／DNS／ACME | Blocked by External Prerequisite | 待正式主機與 DNS 管理資源 |

後端測試仍有 1 項上游 TestClient 棄用警告。沒有變更 PRD／API Contract 的規格，也沒有 Commit 或 Push。

### 新版應用來源檔案清單

可重現來源與測試腳本如下。實際秘密、DB、備份與本機 Build 產物使用忽略路徑。

~~~text
.gitignore
docs/FINAL_VERIFICATION.md
docs/IMPLEMENTATION_PROGRESS.md
web-app/.env.deploy.example
web-app/.env.example
web-app/backend/.dockerignore
web-app/backend/.python-version
web-app/backend/alembic.ini
web-app/backend/alembic/env.py
web-app/backend/alembic/script.py.mako
web-app/backend/alembic/versions/0001_auth_foundation.py
web-app/backend/alembic/versions/0002_vehicles_vehicles_and_mileage_ledger.py
web-app/backend/alembic/versions/0003_maintenance_maintenance_events_and_versions.py
web-app/backend/alembic/versions/0004_vehicle_images_private_vehicle_images.py
web-app/backend/Dockerfile
web-app/backend/pyproject.toml
web-app/backend/src/vibicle_api/__init__.py
web-app/backend/src/vibicle_api/bundle_images.py
web-app/backend/src/vibicle_api/check_db.py
web-app/backend/src/vibicle_api/clean_images.py
web-app/backend/src/vibicle_api/config.py
web-app/backend/src/vibicle_api/database.py
web-app/backend/src/vibicle_api/errors.py
web-app/backend/src/vibicle_api/history_schemas.py
web-app/backend/src/vibicle_api/http_contract.py
web-app/backend/src/vibicle_api/image_worker.py
web-app/backend/src/vibicle_api/main.py
web-app/backend/src/vibicle_api/models.py
web-app/backend/src/vibicle_api/provision.py
web-app/backend/src/vibicle_api/repositories/__init__.py
web-app/backend/src/vibicle_api/repositories/auth.py
web-app/backend/src/vibicle_api/repositories/database.py
web-app/backend/src/vibicle_api/repositories/history.py
web-app/backend/src/vibicle_api/repositories/images.py
web-app/backend/src/vibicle_api/repositories/vehicles.py
web-app/backend/src/vibicle_api/routers/__init__.py
web-app/backend/src/vibicle_api/routers/auth.py
web-app/backend/src/vibicle_api/routers/history.py
web-app/backend/src/vibicle_api/routers/images.py
web-app/backend/src/vibicle_api/routers/vehicles.py
web-app/backend/src/vibicle_api/schemas.py
web-app/backend/src/vibicle_api/services/__init__.py
web-app/backend/src/vibicle_api/services/auth.py
web-app/backend/src/vibicle_api/services/history.py
web-app/backend/src/vibicle_api/services/identity.py
web-app/backend/src/vibicle_api/services/images.py
web-app/backend/src/vibicle_api/services/vehicles.py
web-app/backend/src/vibicle_api/upload.py
web-app/backend/src/vibicle_api/vehicle_schemas.py
web-app/backend/tests/conftest.py
web-app/backend/tests/test_auth.py
web-app/backend/tests/test_contract_validation.py
web-app/backend/tests/test_database.py
web-app/backend/tests/test_history.py
web-app/backend/tests/test_identity.py
web-app/backend/tests/test_images.py
web-app/backend/tests/test_marketplace.py
web-app/backend/tests/test_vehicles.py
web-app/backend/uv.lock
web-app/Caddyfile
web-app/compose.deploy.yaml
web-app/compose.yaml
web-app/frontend/.dockerignore
web-app/frontend/Dockerfile
web-app/frontend/index.html
web-app/frontend/package-lock.json
web-app/frontend/package.json
web-app/frontend/src/api.test.ts
web-app/frontend/src/api.ts
web-app/frontend/src/App.tsx
web-app/frontend/src/auth.tsx
web-app/frontend/src/components/Listing.tsx
web-app/frontend/src/components/RequestState.tsx
web-app/frontend/src/components/VehicleHistory.tsx
web-app/frontend/src/components/VehiclePhoto.tsx
web-app/frontend/src/hooks/useMutation.ts
web-app/frontend/src/hooks/useRequest.ts
web-app/frontend/src/main.tsx
web-app/frontend/src/pages/Garage.tsx
web-app/frontend/src/pages/Marketplace.tsx
web-app/frontend/src/pages/VehicleEdit.tsx
web-app/frontend/src/style.css
web-app/frontend/src/types.ts
web-app/frontend/tsconfig.json
web-app/frontend/vite.config.ts
web-app/README.md
web-app/scripts/Backup-Vibicle.ps1
web-app/scripts/Browser-Account-Switch.js
web-app/scripts/Browser-Auth.js
web-app/scripts/Browser-Cookie-Reorder.js
web-app/scripts/Browser-Cross-Origin-Auth.js
web-app/scripts/Browser-Garage.js
web-app/scripts/Browser-Logout-Recovery.js
web-app/scripts/Browser-MVP.js
web-app/scripts/Browser-Persistence.js
web-app/scripts/Browser-Public-Errors.js
web-app/scripts/Browser-Registration-Unknown.js
web-app/scripts/Browser-Tab-Recovery.js
web-app/scripts/Browser-Unknown-Business.js
web-app/scripts/check-image-budget.py
web-app/scripts/Initialize-Deploy.ps1
web-app/scripts/Initialize-Dev.ps1
web-app/scripts/Restore-Vibicle.ps1
web-app/scripts/Test-Database.ps1
~~~
