# Step 3A Verification Record

- 首次驗證為 2026-11-05，PostgreSQL 補驗為 2026-11-06，均為 Asia/Taipei。
- 範圍：Runnable Foundation、三張Auth表的Model／Migration與匿名E05；沒有完整Auth或Production部署。
- **狀態：Step 3A 的本機驗證已完成。** Browser Smoke、PostgreSQL 連線、Online Migration、原生 Constraint 與保留 Volume 的容器重啟均已實測。
- Windows工作區原本沒有.git或Web3原始碼，無可報告的Working Tree／Branch。未Clone、Git init、Commit或Push；程式新增在web-app。
- 詳細操作／全部Files Changed／A～H教學見 [web-app/README.md](../web-app/README.md)。

## 1. 實際版本

| 工具／Library | 實際觀察／設定 |
| --- | --- |
| PowerShell | 7.6.5；操作手冊另提供Windows PowerShell單程序初始化指令 |
| Node／npm | 24.11.0／11.6.1 |
| uv／Python | 0.11.29／專案隔離3.13.14 |
| FastAPI／Pydantic | 0.162.0／2.14.2 |
| SQLAlchemy／Psycopg | 2.0.57／3.3.8 |
| Alembic | 1.20.1；Revision 0001_auth_foundation |
| React／Vite／TypeScript／Vitest | 19.3.1／8.3.5／7.0.2／5.1.0 |
| Docker CLI／Engine／Compose | 29.9.2／29.9.2／5.6.1，Desktop 4.98.0，`desktop-linux` |
| PostgreSQL | 18.6（Debian 18.6-1.pgdg12+2，x86_64），Image `postgres:18.6-bookworm` |
| Image RepoDigest | `postgres@sha256:f1ea2a1a4fb7b68d4836be1fdcb8a6466a89b072158bf9d97663600538c294c5` |
| PostgreSQL Encoding／Locale | 開發 DB 與驗證 DB 均為 `UTF8`，`lc_collate` 與 `lc_ctype` 均為 `C.UTF-8`，provider 回傳 `c`（libc），`collation_version` 回傳 SQL NULL |

原Python3.11.6在中文路徑editable .pth解碼失敗；改為專案.python-version固定3.13。uv sync --locked已成功，不修改全域Python。依賴精確版本見uv.lock／package-lock.json。

## 2. 實際執行結果

| 檢查 | 結果 | 證據與限制 |
| --- | --- | --- |
| Ruff check／format --check | Pass | 18個Python檔案格式檢查通過；無Lint錯誤 |
| Mypy strict | Pass | no issues found in 13 source files |
| pytest 全套 | **40 passed、0 skipped、1 warning** | 11-06 指定驗證 DB 後執行全套。11-05 Docker 尚未就緒時的結果為 14 passed、26 skipped、1 warning |
| 匿名E05完整Envelope／UUID／Header | Pass | FastAPI TestClient，200、read_only／not_applicable、user與absolute=null、no-store、X-Request-ID、無Set-Cookie |
| 匿名E05不查DB | Pass | monkeypatch阻擋make_engine，匿名仍正確200；實際DB不可用時HTTP／Browser也成功 |
| 偽造／歧義Cookie | Pass | 明顯無效Cookie不獲身分；可能有效43字元Cookie503 STORE_UNAVAILABLE且說明Lookup未接入；重複Cookie400 |
| Query／GET Body限制 | Pass | 未定Query422、重複Query400、非空Body422、超8KiB413；安全Error格式，沒有原input |
| 404／405與無診斷Endpoint | Pass | /api/dev/db為404，POST /api/auth/me為405；沒有公開DB診斷Route |
| 真連線失敗的Test | Pass | SQLAlchemy Engine連不可用Port1，實際OperationalError，不返回空資料 |
| Development DB CLI不可用行為 | Pass | 實際connect本機55432→DB_UNAVAILABLE，捕捉Exit Code=1；未冒稱查無資料／DB健康 |
| Production診斷保護 | Pass | API_ENV=production執行CLI，在連線前DB_DIAGNOSTIC_DISABLED，捕捉Exit Code=2 |
| Alembic Offline SQL | Pass（僅產生） | upgrade head --sql產出三表及工具alembic_version的DDL、PK／FK／Unique／CHECK／Index；未由PG解析或執行 |
| Alembic Online upgrade | Pass | `vibicle_dev` 實際套用 Migration，`alembic current` 回報 `0001_auth_foundation (head)` |
| 乾淨 DB 套用／alembic check | Pass | `Test-Database.ps1` 建立 `vibicle_3a_verify_04bfbdca06ab` 並套用 Migration；兩個 DB 均回報 `No new upgrade operations detected.` |
| Native CHECK／FK／UNIQUE／PK | Pass | 真 PostgreSQL 驗證 Email、Session 型態與期限、`csrf_secret`、FK RESTRICT、Rate-limit Bucket 等。整合測試 27 passed，含 1 項連線失敗測試 |
| PostgreSQL 啟動／健康／保留 Volume 重啟 | Pass | `docker compose up -d --wait` 回報 Healthy，Host 的 SQLAlchemy CLI 成功查詢。確認掛載 `vibicle-foundation_postgres_data` 至 `/var/lib/postgresql`。同一容器 stop／start 後再次 Healthy，兩個 DB 仍回報 `0001_auth_foundation (head)`，全套 pytest 通過 |
| Compose設定語法 | Pass | 直接使用已安裝docker-compose.exe config --quiet，Exit0；沒有輸出含密碼的完整config |
| PowerShell 腳本 | Pass | AST Parser 驗證兩支腳本語法，並以 `Test-Database.ps1` 實際建立驗證 DB、Migration、連線及跑整合測試 |
| TypeScript typecheck | Pass | tsc --noEmit |
| Frontend Unit Test | Pass | 1檔案／3個Vitest案例：匿名結構、503不可假匿名、假authenticated結果拒絕 |
| Frontend Build | Pass | Vite 8.3.5 Build成功；不是Production部署 |
| Browser開首頁／實際GET／UI更新 | Pass | Playwright CLI獨立session：初期API未啟動觀察502／無法確認；啟動後點重新檢查，Request16實際200，UI改未登入 |
| Browser實際Response／Header | Pass | response-body16與response-headers16：契約匿名Envelope、application/json、no-store、X-Request-ID，無Set-Cookie |
| Browser手機版 | Pass（Smoke） | Viewport390×844，innerWidth=390、scrollWidth=390；非完整Accessibility／全MVP驗收 |
| Secret檢查 | Pass（限定本輪來源） | 掃47份來源／文件／Lock（含本紀錄），實際本機亂數Password沒有出現在來源；.env／產物排除。不是通用Secrets Scanner或Git稽核 |
| 原文件保護 | Pass | PRD／SYSTEM_ARCHITECTURE／DATABASE_DESIGN／AUTH_DESIGN／API_SCOPE_REVIEW的SHA-256與進入Implementation前相同；只同步DECISIONS與API_CONTRACT |
| Register／Login／Session有效Lookup／CSRF／Rotation／Revocation | **Not implemented／Not Run** | 沒有相關Endpoint或Coordinator；不能將資料表CHECK當作功能完成 |
| Domain／TLS／Production／Caddy／車輛與照片 | **Not Run／Out of scope** | 本輪明確未實作／部署 |

Pytest warning來自目前Starlette TestClient對httpx的棄用提示，不是測試失敗；未將警告靜默忽略。未來升版需處理TestClient支援，但不宣稱此warning代表Production Auth已驗證。

## 3. Browser證據

本機頁面只透過127.0.0.1:5173，Vite Proxy轉127.0.0.1:8000：

- Request14：GET /api/auth/me，StrictMode Effect Cleanup造成ERR_ABORTED。
- Request15：API尚未啟動，Proxy回502；UI正確顯示無法確認。
- Request16：API啟動後點按重新檢查→200；畫面顯示API已連線／未登入與同一Request ID。
- 成功Response Request ID：62f8e971-6fd1-4e62-ad75-46563166664c；不是Secret。
- 首頁桌面與手機版截圖由本機驗證產生，屬於忽略的測試產物。

驗證後已關閉該Playwright session，停止本輪API PID40708與Vite PID25508。可依README重新開啟，沒有對外部署。

## 4. Docker 環境排除紀錄

開始時Docker CLI存在，但dockerDesktopLinuxEngine Pipe不存在。嘗試正常啟動Docker Desktop後，其backend.error.json回報：

~~~text
initializing Inference manager
listening on ...Docker/run/dockerInference
The file cannot be accessed by the system.
~~~

標準docker desktop restart --timeout 45仍卡住／context deadline exceeded，未得到Engine ready或PG Healthy。本輪沒有使用Docker Factory Reset、刪Volume或更動Docker設定來換取綠燈；沒有把替代Host PostgreSQL／SQLite的結果冒稱Compose成功。

自動審查曾拒絕「停止本輪 Docker 程序並刪除失效 IPC socket」，回覆為 blocked by policy。該命令未執行。

2026-11-06 使用者回報 Docker Engine 29.9.2 已就緒。Codex 執行程序仍持有舊 PATH，補入目前使用者安裝的 Docker CLI 路徑後即可執行 Compose。驗證完保留開發 DB、驗證 DB 和 Named Volume，專案 PostgreSQL 容器保持 Healthy，方便後續審查。

## 5. 尚存限制與停止點

- PostgreSQL 已驗證三張 Auth 資料表與 Alembic 版本。Volume 檢查涵蓋掛載及同一容器重啟，容器刪除後重建與備份還原未測。
- Session Cookie可能有效時明確503 fail closed；沒有登入身分恢復能力。沒有Cookie200匿名不是DB健康證據。
- Local HTTP尚未發放任何Auth Cookie，不代表Secure／HTTPS／CSRF已測。
- DB Runtime最小權限／Argon2id／Unicode一致性／完整Session生命週期須後續Step3C實作；CP-06 Cookie競態仍未解。
- CP-SCOPE-01～03 已同步。13 項 Must Have／71 項有效 AC 是完整 MVP 的需求範圍，本紀錄的測試只覆蓋 Step 3A。

Step 3A 已交付，等待程式碼審查。
