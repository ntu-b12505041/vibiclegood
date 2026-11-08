# Vibicle 正式部署與驗證

正式入口為 [https://vibicle.app](https://vibicle.app)。React SPA、FastAPI 與 PostgreSQL 由 Docker Compose 部署在 Ubuntu VPS。Caddy 負責 TLS、靜態檔案與同 Origin API 代理。PostgreSQL 和私有照片分別存於持久化 Volume，API 與資料庫連接埠只供 Docker 網路使用。

## 已驗證結果

| 項目 | 實際結果 |
| --- | --- |
| 公網入口 | DNS 指向部署主機，Let's Encrypt 憑證驗證通過。HTTP 保留路徑並轉址至 HTTPS。 |
| 應用程式 | SPA 深層連結、JS、CSS 與匿名 API 可存取。Chromium 實測註冊、登入、車輛建立與編輯、維修更正、照片、上架與搜尋。 |
| 權限 | 登出後舊 Session 重放回 401，缺少 CSRF Token 的變更回 403。下架後訪客讀取舊照片和詳情 API 回 404，車主仍可查看。 |
| 選圖修正 | 2026-11-08 重新部署前端，正式站重播選圖視窗返回焦點的順序，確認檔名保留、圖片可上傳、車輛可上架。 |
| Migration 與持久化 | PostgreSQL 18.6，Alembic 到 `0004_vehicle_images`。容器重啟後讀回相同車輛版本、維修版本與圖片 SHA-256。資料庫和圖片的成對備份完成隔離還原。 |

[正式站公開車輛畫面（合成資料）](images/public-vehicle.png)

逐條 PRD 條件及本機測試見 [驗收紀錄](FINAL_VERIFICATION.md)。整機重啟、首次憑證自動續發及完整的跨分頁 Cookie 回應排序仍未驗證。
