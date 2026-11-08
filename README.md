# Vibicle

Vibicle 是二手車履歷與出售資訊展示平台。車主可新增車輛、上傳照片、補登及更正維修紀錄，再決定是否公開。訪客可搜尋已上架車輛，查看維修履歷與更正版本。本站使用合成資料，僅供展示。

[正式網站](https://vibicle.app) · [公開車市](https://vibicle.app/marketplace)

## 啟動與驗收

前端使用 React、TypeScript 與 Vite，後端使用 FastAPI 與 SQLAlchemy。PostgreSQL 儲存車輛資料和伺服器端 Session，Caddy 提供 HTTPS 及同 Origin API 代理。Alembic 管理 Schema 版本。

- [本機 Docker 啟動、測試與程式結構](web-app/README.md)
- [產品規格](docs/PRD.md) · [系統架構](docs/SYSTEM_ARCHITECTURE.md) · [ERD](docs/DATABASE_DESIGN.md)
- [Authentication 設計](docs/AUTH_DESIGN.md) · [API Contract](docs/API_CONTRACT.md)
- [逐項驗收](docs/FINAL_VERIFICATION.md) · [正式部署與驗證](docs/DEPLOYMENT_REPORT.md)
