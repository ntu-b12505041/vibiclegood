# Vibicle

Vibicle 是二手車履歷與出售資訊展示平台。使用合成車輛資料，維修紀錄為車主自行申報，網站僅供作業展示。

在 Windows PowerShell 可用 Docker Compose 執行完整網站。實作與測試狀態見 [實作進度](../docs/IMPLEMENTATION_PROGRESS.md) 和 [逐項驗收](../docs/FINAL_VERIFICATION.md)。Step 3A 基線另有 [驗證紀錄](../docs/STEP_3A_VERIFICATION.md)。

公網部署與測試結果見 [正式部署與驗證](../docs/DEPLOYMENT_REPORT.md)。

## 1. 本機 Production-like 啟動

需要 Docker Desktop 的 Linux Engine 與 Compose v2 以上。從工作區的 `web-app` 執行下列指令。初始化腳本會產生三個各自獨立的亂數秘密，已有設定檔時會保留。此 Compose project 有自己的資料庫及圖片 Volume。

~~~powershell
docker version
.\scripts\Initialize-Deploy.ps1
docker compose --env-file .env.deploy.local -f compose.deploy.yaml config --quiet
docker compose --env-file .env.deploy.local -f compose.deploy.yaml up -d --build --wait --wait-timeout 90
docker compose --env-file .env.deploy.local -f compose.deploy.yaml ps --all
~~~

開啟 `https://localhost:8443`，使用自行建立的合成帳號，例如 `demo1@example.test`，及長度 12～128 Unicode Code Points 的密碼。註冊後手動登入。在車庫新增 17 碼合成 VIN、填售價並上傳照片後即可上架。合成 VIN 示例 `TEST1234567890123`，排除 I、O、Q。

Caddy 用自己的 Local CA。以下指令取得該測試環境的 CA 憑證並驗證 TLS。要在一般瀏覽器驗證，先核對檔案來自本機容器，再用測試專用瀏覽器 Profile 信任該 CA。Playwright 可在隔離的測試 Context 對本機憑證例外，正式公網驗收必須使用受信任憑證並開啟驗證。

~~~powershell
New-Item -ItemType Directory -Force output\tls | Out-Null
docker compose --env-file .env.deploy.local -f compose.deploy.yaml cp caddy:/data/caddy/pki/authorities/local/root.crt output/tls/caddy-local-root.crt
curl.exe --fail --show-error --ssl-revoke-best-effort --cacert output/tls/caddy-local-root.crt https://localhost:8443/api/auth/me
~~~

停止用 `docker compose --env-file .env.deploy.local -f compose.deploy.yaml stop`。要重建容器並保留資料，用 `up -d --build --force-recreate --wait` 搭配相同 env、Compose 和 project。日常操作保留 Named Volume。Migration job 正常結束時 `ps --all` 會列 `migrate Exited (0)`。

## 2. Windows 開發模式

Node 24、uv、Python 3.13 和 Docker Desktop。開發用 PostgreSQL 在另一個 project，Host port 55432。開發 HTTPS 憑證可用 Git for Windows 的 OpenSSL 產生，範例使用 PowerShell 7。

~~~powershell
# 終端 A，web-app
.\scripts\Initialize-Dev.ps1
docker compose up -d --wait db
New-Item -ItemType Directory -Force output\tls | Out-Null
$openssl = 'C:\Program Files\Git\usr\bin\openssl.exe'
& $openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 7 -keyout output/tls/local-key.pem -out output/tls/local-cert.pem -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
~~~

~~~powershell
# 終端 B，web-app/backend
$env:PUBLIC_ORIGIN = 'https://127.0.0.1:5173'
uv sync --locked
uv run python -m alembic upgrade head
uv run python -m vibicle_api.check_db
uv run python -m uvicorn vibicle_api.main:app --host 127.0.0.1 --port 8000 --no-access-log --reload
~~~

~~~powershell
# 終端 C，web-app/frontend
npm.cmd ci
$env:VIBICLE_DEV_TLS_CERT = (Resolve-Path ..\output\tls\local-cert.pem).Path
$env:VIBICLE_DEV_TLS_KEY = (Resolve-Path ..\output\tls\local-key.pem).Path
npm.cmd run dev
~~~

開啟 `https://127.0.0.1:5173`。前端的相對 URL 由 Vite Dev Proxy 轉送至 Uvicorn `127.0.0.1:8000`。Production 的 Caddy 提供編譯好的靜態資產、SPA fallback、TLS 與同 Origin Proxy。兩種模式 API 都透過 PostgreSQL 存狀態。停止開發程序用 Ctrl+C，在 web-app 執行 `docker compose stop db`。本機圖片預設在被忽略的 `output/private`。

## 3. 程式結構與資料流

| 路徑 | 用途 |
| --- | --- |
| `frontend/src/App.tsx`、`pages/`、`components/` | React 路由、帳號表單、車庫、維修履歷、主照片與公開車市 |
| `frontend/src/auth.tsx`、`api.ts`、`hooks/` | Web Locks、Epoch、跨分頁通知、Request/Response、錯誤與 Unknown |
| `backend/src/vibicle_api/main.py`、`http_contract.py`、`routers/` | API 入口、Request ID、安全錯誤、Request 驗證與各 Endpoint |
| `backend/src/vibicle_api/services/` | Auth、車輛版本、里程、維修更正、上架及照片的交易規則 |
| `backend/src/vibicle_api/repositories/`、`models.py`、`database.py` | SQLAlchemy、查詢、資料約束與 Private File Storage |
| `backend/alembic/` | 四個線上 Migration。部署由獨立 migrator 執行 |
| `backend/src/vibicle_api/image_worker.py`、`clean_images.py` | 有界子程序處理照片與停止 Writer 後的維護清理 |
| `backend/tests/`、`frontend/src/api.test.ts`、`scripts/Browser-*.js` | API、真 PostgreSQL、並行、前端及 Chromium E2E |
| `compose.yaml`、`compose.deploy.yaml`、`Caddyfile`、兩個 Dockerfile | 分開的開發與 Production-like 環境 |
| `scripts/*-Vibicle.ps1`、`bundle_images.py` | 協調 DB 與 Private Image 的備份、隔離還原與校驗 |

Browser 從同 Origin 送 Cookie 和 Mutation 的 CSRF Token。Auth Router 查 Session Hash、核對來源與 Token。車輛 Service 用登入身分驗 Owner，以共同 Vehicle Row Lock 保護聚合寫入，Repository 向 PostgreSQL 查資料。提交後只對白名單成功請求另開短交易 Touch。若 Touch 失敗，API 保留業務成功並要求重新確認身分。圖片也經 API 授權，再由 Private Volume 讀出處理後 bytes。

E01～E05 為 Authentication。E07～E10 為車庫與車輛新增、編輯，E11～E13 為上下架與公開車市，E14～E21 為履歷、版本鏈與里程，E22～E23 為主照片。E06 Deferred。

## 4. 最終資料模型

~~~mermaid
erDiagram
    app_users o|--o{ auth_sessions : "authenticated"
    app_users ||--o{ vehicles : "owns"
    app_users ||--o{ vehicle_mileage_changes : "records C"
    app_users ||--o{ maintenance_record_versions : "submits"
    vehicles ||--|{ vehicle_mileage_changes : "starts with C"
    vehicles ||--o{ maintenance_events : "has"
    maintenance_events ||--|{ maintenance_record_versions : "contains"
    maintenance_record_versions ||--o| maintenance_events : "current"
    maintenance_record_versions o|--o| maintenance_record_versions : "previous"
    vehicles ||--o{ vehicle_images : "contains"
    vehicle_images o|--o| vehicles : "current"
    auth_rate_limit_buckets {
      text scope PK
      bytea subject_hash PK
      timestamptz window_start PK
    }
~~~

0001 是三張 Auth 表；0002 新增 Vehicle 與 Mileage Ledger；0003 新增 Event 與 Version Chain，current 版本的同事件 FK 為 Deferred；0004 新增 Image Metadata 與同車主圖 FK。Alembic 的技術表另記 revision。以 `uv run python -m alembic current` 核對 `0004_vehicle_images`。部署 Runtime 使用 `vibicle_runtime`，無修改原履歷、里程 Ledger 或 Session Secret 的權限。測試的開發 DB 使用 migrator 以檢查原生約束。

## 5. 測試與操作證據

~~~powershell
# web-app，建立隔離的驗證 DB，保留既有開發資料
.\scripts\Test-Database.ps1
# backend
uv run ruff check --no-cache
uv run mypy
# 設 VIBICLE_TEST_DB 為腳本輸出的專用 DB 名稱後可重跑完整 pytest
uv run pytest -q
# frontend
npm.cmd run typecheck
npm.cmd test
~~~

Production build 在 Linux Docker build 內執行 `npm run build`。本機 Windows 若 Vite 的 native 寫出階段失敗，可用 Docker Build 重現。Browser 由 web-app 開獨立 Chromium session，依驗證文件執行 `scripts/Browser-MVP.js`；其測試帳號、VIN 與圖片都是合成資料，留在所使用的本機環境。

## 6. 正式部署

正式公網環境仍需既有主機、網域、DNS 與登入權限。先以自己的管理流程將專案放上主機，讓 DNS A／AAAA 指向實際對外 IP，確認對應 80／443 到 Gateway。設定 `.env.deploy.production` 的 `VIBICLE_DOMAIN` 為正式主機名，`PUBLIC_ORIGIN` 精確匹配 HTTPS Origin，`CADDY_TLS_DIRECTIVE` 留空使用 Automatic HTTPS，`HTTP_PORT=80`、`HTTPS_PORT=443`、`BIND_ADDRESS=0.0.0.0`。三個秘密各自產生，限制檔案可讀權限。Docker Gateway subnet 必須沒有衝突，若重配要讓 Caddy IP 和 API 的 trusted proxy 參照同一設定。

在主機用 `docker compose --env-file .env.deploy.production -f compose.deploy.yaml up -d --build --wait`。首次部署後用受信任 Client 驗 HTTPS、憑證名稱與鏈、Redirect、深層連結、Cookie flags、登入和圖片授權，並確認 PostgreSQL／API port 只在 Docker 網路可用。公網部署狀態以 [正式部署與驗證](../docs/DEPLOYMENT_REPORT.md) 為準。[Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)

### 備份、隔離還原與清理

先停止 API、Caddy 和所有 Writer／Cleaner，只留 DB。由 web-app 跑 `./scripts/Backup-Vibicle.ps1`，產生 custom PostgreSQL dump、Private Image archive 及 SHA256 manifest。備份包含受保護的資料，要限制存取並在 Docker Host 外另存。完成後以原 Compose 設定 `up -d --wait` 恢復入口。[PostgreSQL pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)

還原使用全新的 project，準備獨立 env，將 Gateway subnet／IP、Port 避開原專案。執行 `./scripts/Restore-Vibicle.ps1 -BackupPath <目錄> -EnvironmentFile <環境檔> -ProjectName vibicle-restore-<唯一值>`。腳本會拒絕已存在的目標 project、核對 checksum、還原 DB 和圖片、撤銷還原資料中的全部 Session／preauth 並檢查目前主圖。切流量前還要驗證登入、車庫、履歷、圖片及舊 Cookie 拒絕。維護時可以由一個受控管理程序執行 `python -m vibicle_api.clean_images --writers-stopped`，先確認所有 API Writer 已停止並使用正確 DB 與 Volume。

## 7. 審查順序

1. 從 `App.tsx`、`auth.tsx`、`api.ts` 跟 E01／E03／E05。
2. 看 `services/auth.py` 如何使用 PG 判定期限、Rotation、Logout 和 Touch。
3. 對照 Migration 0002～0004 與 `services/vehicles.py`、`services/history.py` 的共同鎖、H 與 C。
4. 看 `upload.py`、`image_worker.py` 和 `services/images.py` 的有界處理及可見性。
5. 用 `compose.deploy.yaml` 和 `Caddyfile` 追同 Origin、TLS、Network、Volume 及備份還原。

## 8. 五項取捨

| 取捨 | Vibicle 的做法 |
| --- | --- |
| Session 與限流 | 與業務資料共用 PostgreSQL，跨 Worker 有一致的撤銷與 Counter；PG 故障時認證必須拒絕。 |
| Browser Cookie 協調 | 方案 A 用 Web Locks、Epoch 與非秘密 Pending marker。已提交但結果不明的 Login 保持 Uncertain；Set-Cookie 重排的反例仍成立。 |
| 聚合一致性 | Row Lock 保護跨列業務驗證，Revision 保護舊表單。有效履歷透過 Current Version Pointer 查詢，舊版可追蹤。 |
| 私有圖片與 DB | 圖片 bytes 另存 Volume，DB 控制 metadata、主圖與可見性。替換與備份需協調兩種資源，失敗靠保留舊圖與維護清理處理。 |
| 同 Origin 與部署 | Caddy 同 Origin 交付 React 和 API，降低 Cookie 與 CORS 配置負擔；正式憑證、DNS、Gateway 與防火牆仍需在實際主機驗收。 |
