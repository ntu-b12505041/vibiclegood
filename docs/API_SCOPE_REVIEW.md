# Vibicle — CP-API-01 Scope & Design Review

- 版本：v0.1 Review Proposal；日期：2026-11-04（Asia/Taipei）。
- 階段：Step 2D 後的最後範圍審查；本輪只新增本文件。
- **結論：推薦方案 A 作實習 MVP；CP-API-01 暫緩至 Hardening。** 保留現行八表、五個基本 Auth Endpoint、Server Rotation／Revocation／CSRF，以及受控 Browser 的 Web Locks／Auth Epoch／BroadcastChannel。Login 結果不明時維持 Uncertain，不提供「取消成功」的假保證。
- **這是待審閱的範圍建議，尚未取代 API_CONTRACT.md 的 B 推薦與 Blocking 狀態。** 接受後須依 §9 同步文件；本輪不修改上游、不宣稱任何 AC 已通過。
- **不推薦把「有可能建立的新 Session」直接當作「已撤銷 Session 復活」。** 二者需要不同證據與處理方式。B 增加的是指定 Login 的可確認取消能力，不是完成一般撤銷所必需的表。
- 維持 13 項 Must Have、71 項有效 AC 與 4 項停用 AC 的原狀；FR-013、歷史里程、C／H、未上架資料與照片隱私不變。沒有程式、Schema／Migration、SQL 執行、依賴安裝或部署。

## 1. 閱讀基線與結論依據

已完整閱讀以下六份文件。S1～S6 為本文件的來源簡寫；行號為本輪讀取的快照，後續改版需重新核對。

| 來源 | 文件與關鍵位置 | 本輪用途 |
| --- | --- | --- |
| S1 | [PRD.md v0.2.1](PRD.md#L166)：§4 FR-002／003、§5.3、NFR-REL-02 | AC 原文與安全／未知結果要求 |
| S2 | [DECISIONS.md v0.2](DECISIONS.md#L305)：§6.3 I-AUTH-01、§6.6 DR-01 | 已接受 CP-01～05／有條件 CP-06；區別設計缺口與既有 AC |
| S3 | [SYSTEM_ARCHITECTURE.md v0.2](SYSTEM_ARCHITECTURE.md)：§6.5、R-09、§10 | 同 Origin、共享 PG Store、單一 API、Cookie 邊界 |
| S4 | [DATABASE_DESIGN.md v0.2](DATABASE_DESIGN.md#L196)：§4.2／4.8、§7.4／8、Q-06／10 | 現行設計仍是八表，並無 Attempt 關聯 |
| S5 | [AUTH_DESIGN.md v0.1](AUTH_DESIGN.md#L286)：§6.2／6.4／6.6、AI-01～05、AT-12／AQ-06 | 受控 Lifecycle／Uncertain 與原 Logout 例外；審查前歷史狀態依 S2 §6 解讀 |
| S6 | [API_CONTRACT.md v0.1](API_CONTRACT.md#L9)：§1、E01／03／04／05／06、§12～14／18 | B 為未核准 CP；原稿將完整 Recovery 列為實作 Blocking |

所有「可保證」均指依設計正確實作、所有相關 Writer 遵守協定、可信 PG／Clock／配置正常的條件；不是只靠紙上 CHECK 或 Browser Lock 即成立。「設計可覆蓋」不等於「已實作」，更不等於「測試通過」。

### 1.1 為何改推薦 A

S1 FR-003-AC03 明文允許無法確認時顯示尚未完成／結果不明；S1 NFR-REL-02 禁止盲目重送。S5 §6.6 也已規定未收斂就維持未確認。因此 MVP 可以誠實停止有風險的 Auth 操作，而不必先提供一個必能成功的取消功能。

S6 §1.2／§18 把「I-AUTH-01 尚未完全解決」直接綁成「必須新增 Attempt 才能實作」，擴大了進入實作的門檻。本輪建議以具體 AC 測試作 Gate，不把所有未知 Login 的即時可取消性暗升為 Must Have。**這是對 S6 範圍與 Gate 的變更提案，不是宣稱 DR-01 已關閉，也不是刪除晚到 Response 測試。**

A 的代價是可用性：部分 Timeout／Crash 後可能長期無法安全繼續 Auth。若驗收要求「Timeout 後仍可取消並很快重新登入」，A 不達成；此時須明確選 B 並接受成本。不能把 Uncertain 改名成已登出以過關。

## 2. 五個情境：精確區分保證與缺口

以下 C 是 Login Request 帶來的原 Context（preauth 或原 authenticated）；S 是該 Login 新建立、與 C 不同的 Session。L 是 Login，O 是 Logout。**C.revoked 不會因 Browser 再送 C 而改回有效；S 有效則是另一筆狀態。**

「現行」指 S2～S5 的八表基線；S6 的 B 分支尚未接受，不算現有能力。

| 情境 | 現行能否處理／明確 AC | Server 能保證 | Browser／Best-effort | 尚不能保證／額外強化 |
| --- | --- | --- | --- | --- |
| A. 登出後 Browser 又送已撤銷舊 Token | **設計可處理**。FR-003-AC01／02／04／05、FR-002-AC04／06；新的授權判定拒絕該 Token。 | 新 Lookup 讀 Primary、revoked／期限拒絕；Touch 不 UPSERT、不清 revoked。即使 Jar 留舊 Cookie也不能授權。 | 清 Jar、跨 Tab 清 UI；外部保存 Cookie 不可追回，但仍被拒。 | 撤銷前已授權工作可能完成，S1 已明列界線。B 對此不增加必要保護。 |
| B. 登出後舊資料查詢 Response 晚到 | **設計可處理，必須 E2E 驗證**。FR-002-AC07、FR-003-AC02／04／05。 | 普通查詢／Touch／錯誤 Response 不含 Set-Cookie；舊 Session 不被續期復活。不能回收早已授權的 bytes。 | 每請求綁 Epoch＋User；登出／切換前失效世代、清 Cache／Object URL；通知／focus／pageshow 先遮蔽重驗。Abort 只減少工作。 | 凍結期間即時清除與追回截圖不在 AC 保證內；若恢復後接受舊資料則是 AC 失敗，不能列為可接受風險。 |
| C. Login Commit S，Cookie 尚未到 | **Server Rotation 已覆蓋，完成／取消證據不足**。FR-002-AC06 要新 ID／撤銷 C；NFR-REL-02 涵蓋回應不明。 | L 的 INSERT S＋撤銷 C 同交易；C 後續認證拒絕；其他裝置不變。 | 受控流程序列化、不接下一個 Cookie 變更；可顯示 pending／uncertain。 | C 無效不證明 S 不存在；沒有現行 AC 明文要求「尚未收到 S 也一定可撤銷 S」。B 在 Proof 完整時提供這項新增能力。 |
| D. Login Timeout，不知是否登入 | **能誠實處理未知，不能總是收斂**。NFR-REL-02；若接著要求登出，FR-003-AC03 適用。 | 有 Cookie 的 E05 只證明該次判定的身分；不能藉 Timeout 推論 Rollback。 | Uncertain、遮蔽私有 UI、停止 Login 重送／Bootstrap／普通 Logout；E05 只觀測、不清 Pending。 | Timeout 後指定取消／有界恢復時間不是現行明確 AC。B 可在有 Proof 時確認取消；Cancel 自己 Timeout 仍未知。 |
| E. Timeout 後欲取消，但 Cookie 或 Attempt ID 遺失 | **八表無取消功能；B 也不普遍保證**。FR-003-AC03／NFR-REL-02 仍要求誠實未確認；沒有「無 Proof 必能取消」AC。 | 不把知道非秘密 ID／User ID／CSRF 單獨當撤銷權；不回假的 204。 | 尚有可用證明時嘗試限定 Recovery；遺失後只能顯示限制、保留未確認，不宣稱完成。 | B 有 Cookie 無 ID 時有有限查找機會（§6），無 Cookie 則無受信任綁定。全裝置登出、重新驗密碼復原、帳號管理都是新範圍，不加入 MVP。 |

來源：S1 FR-002／003、§5.3；S2 I-AUTH-01；S4 §8；S5 §6.2～6.6；S6 §1／E01～06。

### 2.1 不能混同的三個命題

1. **「C 已撤銷」**：PG 中 C 失效，可用新 Request 重放 C 驗證。A／B 都必須做到。
2. **「目前 Cookie 顯示匿名」**：E05 對該次 Request 的觀測，不證明網路上沒有 L 的 Set-Cookie(S)。
3. **「指定 L 已取消，不能再產生可用 S」**：需要對 L 的持久化識別與取消／Finalize 共同協定；A 不提供，B 才提出有條件保證。

例如 L 先 Commit S，另一流程以 C Bootstrap 成 C2，再 Logout C2 回 204，最後 S Cookie 到達：有效的是 S，並非 C2 復活。若 UI 先說整個登入流程已登出，這是**錯誤確認**。A 必須阻止這段受控流程；若仍能發生，不得用「S 是新 Session」替錯誤的成功文案辯護。S2 DR-01 必須保留。

### 2.2 Browser 平台邊界

Fetch 處理 Cookie 與 JS 使用 Body 是不同步驟；丟棄 JSON 不能作撤回 Cookie 的協定。Web Locks 是同一 Storage Bucket／Origin 內合作式協調，文件卸載會終止相關鎖，不能證明 Server 已完成。這些平台原理支持上述風險判斷；本案的實際 Abort／凍結／Header 時序仍未測。[Fetch Standard](https://fetch.spec.whatwg.org/)、[Web Locks Working Draft §2.6](https://www.w3.org/TR/web-locks/#termination)

## 3. 逐項 AC 對照與驗收 Gate

本表逐項列出本次直接相關的 FR-002 八條、FR-003 五條；沒有改寫其 ID 或要求。FR-001 及其他 FR 的完整對照仍沿 S6 §12，不能以本表取代全部 71 項驗收。

狀態：「可覆蓋／未測」指有設計手段，還沒有通過證據；「有限／未保證」不可勾選成整項已通過。

| AC | 原目的／關鍵文字 | A | B | 必須保留的驗證／不符合時的決策 |
| --- | --- | --- | --- | --- |
| FR-002-AC01 | 正確憑證可看車庫，有效期內 Reload 恢復 | 可覆蓋／未測；正常路徑成立，Unknown 可能停住 | 同 A；多 Attempt 準備步驟 | 正常 Register→手動 Login→E07→Reload。不能以 Unknown UI 取代正常登入能力 |
| FR-002-AC02 | 不存在／錯密碼同類錯誤，失敗無 authenticated | 可覆蓋／未測 | 同 A，技術 Attempt 可 failed，但不是登入 | 同 401、Dummy Verify、不產生可用 S；安全拒絕與技術寫入區分 |
| FR-002-AC03 | 偽造／缺失／過期不能讀寫 | 可覆蓋／未測 | 同 A；Recovery 例外不能外溢 | E07／Mutation／Private Image 直接測，PG 故障不假匿名 |
| FR-002-AC04 | 閒置30分鐘、絕對8小時，等號拒絕、不復活 | 可覆蓋／未測 | 同 A；120秒不是新 Session TTL | Clock 邊界、Lock 等待後重驗、普通重啟／Restore |
| FR-002-AC05 | 成功業務活動白名單，背景不保活 | 可覆蓋／未測 | 同 A；Prepare／Cancel 也不 Touch | E01／05／Public／圖片不 Touch；成功寫入與 Touch 失敗分報 |
| FR-002-AC06 | 「每次成功登入使用新的 Session ID，替換並撤銷該 Browser 的舊本次 Session；舊 ID／晚到回應不能恢復它。不同裝置的獨立 Session 不因此失效。」 | Rotation／C 拒絕可覆蓋；任意 Auth Response 順序**未保證** | Rotation 同 A；確認取消的指定 S 可拒絕，任意 Cookie 全域順序仍**未保證** | 新舊 ID、同 C 雙 Login 最多一成功、延遲 Cookie／另一裝置。不能拿 UI Epoch 代替 Server 斷言；若既有 AC 案例失敗，該項未達成 |
| FR-002-AC07 | 「同 Origin 分頁在登入／登出通知、重新取得焦點或恢復頁面時重新確認目前身分；不得沿用先前帳號的私有快取或接受舊帳號請求結果。背景／凍結分頁恢復時先遮蔽私有內容再驗證，不承諾作業系統凍結時同步。」 | UI 協定可覆蓋／未測；遺失協調標記／非受控切換有剩餘風險 | **不能由 Attempt 表代替**；同樣需 UI 協定與測試 | A→B 舊資料、同 User 換世代、focus／BFCache、事件未送達後恢復。任何接受舊帳號結果的重現都是失敗 |
| FR-002-AC08 | Register／Login CSRF，正常同 Origin／獨立 Client 可用 | 可覆蓋／未測 | 同 A，Prepare／Cancel 另擴測 | Cookie 無 Token、跨 Context、Origin／Referer／Fetch、Native Jar |
| FR-003-AC01 | 撤銷 Commit 後新判定拒絕原憑證；先授權工作不回溯取消 | 可覆蓋／未測 | 同 A；取消結果 S 也按同界線 | 舊 Token 新 Request 401；在途成功不能誤報 Rollback |
| FR-003-AC02 | Reload／上一頁／分頁不恢復舊 Session；清私有 State／Cache | 可覆蓋／未測 | 同 A | 清 Cache／預覽、BFCache 先遮蔽，不能假裝清 Cookie 就是 Server 撤銷 |
| FR-003-AC03 | 「重複登出不造成錯誤資料；若無法確認 Server 端結果，顯示尚未完成或結果不明並允許重試。」 | 已辨識同 Context 的 Logout 可安全重試；未知 Login 的整體 Logout **不能確認**，必須保留未確認 | 有 Proof 可先取消再 Logout；失 Proof／取消 Unknown 仍**不能確認** | 重複 Logout、PG／網路失敗；「允許重試」不代表盲目換 Context 重送，更不表示任何故障都必須成功恢復 |
| FR-003-AC04 | 共用 Session 新 Request 拒，通知送達可執行 Tab 後≤5秒清 UI；另一裝置保留 | 可覆蓋／未測 | 同 A | Chromium 雙 Tab／另一 Jar、事件後時間；不能靠圖片 no-store 代替 UI 清理 |
| FR-003-AC05 | 「登出／過期後晚到的查詢或續期回應，不得重新填入舊私有資料或重建失效 Session；登出不能以普通 GET 觸發，且需通過 CSRF 驗證。」 | 普通 Response 無 Cookie＋Epoch＋條件 Touch 可覆蓋；Auth 另造 S 的錯誤確認風險仍開放 | 同 A；指定 Attempt 取消可加強 S 拒絕，Proof 遺失仍不完整 | 延遲資料／401／Touch、POST＋CSRF；不得因它叫新 S 就略過「錯誤宣告登出後再登入」整合反例 |

### 3.1 AC 不變，Scope 必須明示

**不能對 A 或 B 宣稱「全部現有 AC 已滿足」。** 未有可執行程式／測試；跨分頁與晚到 Auth Response 的廣泛情境均未證實。A 對「指定未知 L 確認取消」明確不提供；B 對「失 Proof 仍保證取消」也不提供。

本輪的建議是：保留 AC 原文與全部必要測試，將「指定 Attempt 的可靠取消」明確列為額外 Hardening，不以它阻止第一個正常端到端 Slice。若審查認定既有 AC 原意已包含任意 Timeout／Proof 遺失下必能完成登出，**兩方案均不得被判通過**；A 不達成，B 在 E 情境也不達成，需另行需求決策，不能偷偷限縮原 AC。

這不是把已知失敗測試改成 Should Have：A 中 Token 撤銷、舊 UI 污染、普通續期復活、CSRF 任一失敗，均是 Release Blocker。只有先前沒有獨立明文 AC 的「積極取消未知 Login」能力建議延期。S2 DR-01 廣義結案仍有條件。

## 4. A／B 比較：表數只是成本的一部分

| 面向 | A：八表＋受控 Client 協調／Uncertain（推薦 MVP） | B：CP-API-01（候選 Hardening，需 §6／7 修正） |
| --- | --- | --- |
| 現有 AC | §3 的正常撤銷／Rotation／CSRF／UI 群可設計覆蓋；Auth 非受控重排未保證 | 同 A；多了指定取消，不自動使全部 AC 通過 |
| 可提供保證 | 撤銷 C 不復活；同 C 至多一個成功 Rotation；不假確認 Unknown；受控 UI 拒舊世代 | A 全部＋有完整 Proof 且 Cancel Commit 後，指定 Attempt 不能再產生可用結果 S |
| 無法處理 | 沒有結果證據時無法確定 L 已終止／撤銷 S；可能長期卡 Uncertain | Cookie／標記遺失、保留期後、DB 故障／Cancel 自身 Unknown、獨立其他 Attempt；不提供全域 Cookie CAS |
| Security Risk | 錯把 Lock 釋放／E05 匿名當完成，或遺失 Pending 後盲目 Bootstrap | 所有 A 風險＋Recovery 負面權限濫用、狀態轉移／FK／Cleanup、錯把取消當 Logout |
| Tables | 原八表，不加 Session successor／Attempt 狀態欄 | 原八表＋auth_login_attempts；或者等價持久關聯設計，不能只拿 Browser RAM 替代 |
| Auth Endpoints | E01～05；E06 保留 ID 但不納 MVP。其餘 E07～23 不重編，共22個候選介面逐 Slice 做 | 原五個＋Prepare POST＋E06 Cancel，共7個 Auth／總24個候選介面；原 GET 準備需移除 |
| PostgreSQL Transaction | Gate 獨立；鎖 C 重驗、INSERT S＋撤銷 C 同短交易；Logout／Touch 各短交易 | 另加 Prepare、verifying claim、Finalize、Cancel、Retention Cleanup 的協同交易及 FK／Unique |
| Browser 成本 | 一個 Auth coordinator、跨 Tab 世代／通知、Pending marker／Uncertain UI；**仍非零成本** | A 全部＋Attempt 保存／Proof 選擇／取消重試／取消後 Logout，更多路徑；Lock 仍需要 |
| 測試成本 | §8 的必要測試；真實 Cookie 重排／Clock／PG 必做 | 再加 Attempt 狀態全轉移、兩種取消順序、Proof／Cookie／Deadline／Cleanup／Restore，Mock 不足 |
| 維護 | 五個基本介面、已知可用性限制較易教學 | 九表不是大型系統，但負面權限／Retention 與連續登入鏈必須持續維護 |
| Intern MVP | **適合**：先交付可解釋端到端功能，保留真實限制及驗收 Gate | 僅在明確要求「可靠取消」時值得；不能只因上一版寫了就成為 MVP 必要 |
| 失效方式 | PG 故障 fail closed；Unknown 不假成功，犧牲恢復便利 | 同 A；Cancel 失敗也只能 Unknown，不能假 204；表本身不解決網路及 Proof 遺失 |

方案 B 沒有引入分散式系統，仍在同一 FastAPI＋PG 內；成本來自新增可撤銷 Operation 的狀態與證據，不是服務數。兩者都不需要 Redis／JWT／MQ／Microservices。


## 5. Failure Timelines：兩方案實際在哪裡分歧

時間 t0～t5 是邏輯順序，非宣稱網路固定延遲。下表列滿 A～E；不把 Cancel 構想畫成已存在 API。

| 情境 | A 的時間線與結果 | B 的時間線與結果 |
| --- | --- | --- |
| A 舊 Token 重送 | t0 O(C) Commit revoked；t1 204；t2 Jar 或自有測試 Client 重送 C；t3 新 Lookup 拒絕。Touch 晚到也不能清 revoked。 | 完全相同，不用 Attempt 才能做到 |
| B 舊查詢晚到 | t0 查詢以 C 授權、記 epoch=7；t1 登出意圖先使 epoch=8／遮蔽；t2 撤銷 Commit；t3 普通查詢回來無 Set-Cookie；t4 epoch 不符丟棄。另一 Tab 收通知／恢復時做同樣隔離。 | 完全相同，Cancel 表不替代 epoch／User 綁定 |
| C S 已建立但 Cookie 延後 | t0 L(C) 發出；t1 PG INSERT S＋revoke C Commit；t2 Header 延遲；t3 E05(C) 匿名；t4 **仍不能認定已登出**；t5 晚到 S 可能有效，須保持未確認而非宣稱 C 復活 | t0 先 Prepare L；t1 Finalize S Commit；t2 Header 延遲；t3 用保留 C＋CSRF＋Attempt 取消；t4 Cancel Commit revoke S；t5 Cookie(S) 到也不能通過新認證。若 Proof 不足則退回 Unknown |
| D Login Timeout | t0 L 送出／標 Pending；t1 Timeout，Server 可能尚未 Verify、已 Rollback 或已 Commit；t2 Uncertain；t3 不自動 Bootstrap／Login／Logout；t4 觀測不構成完成證據。可能無法安全恢復 | t0 Prepare ID 已知；t1 L Timeout；t2 Recovery／Cancel；t3 有確認 204 才標該 L cancelled；t4 如仍想登出，再對可辨識當前 Context Logout。Cancel Timeout 自己也維持 Unknown |
| E 證明遺失 | t0 L Timeout；t1 Cookie／Pending marker 遺失或頁面崩潰；t2 無法確認 Server，可能不再知道要暫停。受控 marker 有助攔截，但不是安全憑證／永不遺失保證 | t0 L Timeout；t1 ID 或 Cookie 遺失；t2 只有非秘密 ID 不可取消。僅 ID 遺失但仍有匹配 Cookie 可有限查找；無 Cookie 時不可假 204。FK 保留不會讓 Browser 找回 Cookie |

### 5.1 A：受控操作維持 Uncertain；錯誤恢復是反例

~~~mermaid
sequenceDiagram
    participant R as React／Auth Coordinator
    participant J as Browser Cookie Jar
    participant A as FastAPI
    participant P as PostgreSQL
    R->>R: Lifecycle Lock／記 Pending／提升 Epoch
    R->>A: POST Login，Cookie C＋CSRF
    A->>P: Verify 後短交易：新 S＋撤銷 C
    P-->>A: Commit
    A->>A: 成功 Response 的 Header 待交付／延遲
    R->>R: Timeout，Uncertain，停止其他 Cookie 變更
    R->>A: GET me，仍帶 C
    A->>P: C 已撤銷
    A-->>R: 匿名，不 Set-Cookie
    Note over R,P: 此結果不能證明 S 沒建立；不能回已登出
    opt Header 稍後仍交付 Browser
        A-->>J: 晚到 Set-Cookie(S)
        J->>J: Jar 可能改成 S
    end
    Note over R,J: Epoch 不能取消 Cookie；Uncertain 不自動清除
~~~

**必測反例 A-X**：略過協調，先 Bootstrap C2 並 Logout C2，再釋放 Set-Cookie(S)。S 仍可能有效，Server 八表無法由 C2 推得它；若畫面顯示「已登出」再恢復登入就是錯誤確認。這條測試要留下，不能只測「按鈕 disable」便聲稱任意 Client 都無風險。對不受控 HTTP 流程，A 不提供跨操作取消保證；獨立 HTTP Client 正常流程仍須遵守同樣的未知結果規則。

A 不可以用等待 120 秒／關頁／清 Cookie 當取消證據。已接受的期限會限制每筆 S 的有效時間，但不提供立即恢復；Browser Clock、Cookie Max-Age 也不是 Server 確認。只持有已知 C 的資訊，無法從八表回推出未知 S 是否有效。新正常請求仍會逐次驗權，不因 UI 藏起來就算撤銷 S。

### 5.2 B：兩種 Commit 順序的保證

~~~mermaid
sequenceDiagram
    participant R as React／Cookie Jar
    participant L as Login Handler
    participant C as Cancel Handler
    participant P as 同一 PostgreSQL
    Note over L,C: Handler 是同一 API 的兩個 Request，非 Microservices
    R->>L: 已 Prepare 的 Attempt ID＋C Cookie／CSRF
    L->>L: Verify 在鎖外
    R->>C: Timeout 後取消，匹配 Proof
    alt Cancel 先取得共同鎖並 Commit
        C->>P: 鎖 parent→Attempt，標 cancelled
        P-->>C: Commit
        C-->>R: 204，僅此 Attempt 取消
        L->>P: Finalize 拿鎖重讀 state
        P-->>L: cancelled，禁止建立結果
        L-->>R: 拒絕，無新 Cookie
    else Login Finalize 先 Commit
        L->>P: 鎖 parent→Attempt，新 S／revoke parent／link result
        P-->>L: Commit
        Note over L,R: Set-Cookie(S) 仍可能在網路中
        C->>P: 同鎖序，revoke S＋標 cancelled
        P-->>C: Commit
        C-->>R: 204，僅此 Attempt 取消
        L-->>R: 若仍交付，晚到 Set-Cookie(S)
        R->>L: 後續經 API 以 S 作新認證
        L->>P: 新 S Lookup
        P-->>L: S 已撤銷
        L-->>R: 401，不能取得私有資料
    end
~~~

圖中兩個 Handler 是同一 FastAPI 的 Request 處理，Client HTTP 皆經 Caddy；圖為省略 Gateway 的高階競態圖。取消後已先授權的業務仍沿 FR-003-AC01 的在途界線；B 不保證回溯回滾。

## 6. CP-API-01 技術審查：方向可行，原稿不能直接凍結

即使本輪推薦 A，仍完整審核 B，以免把它當成沒有代價的安全升級。

| #／問題 | 審查結果 | 必要條件／後續測試 |
| --- | --- | --- |
| 1 Attempt ID 遺失 | **部分可恢復，不是無條件**。有 parent Cookie 時 S6 E01 普通分支可用 409 的可見 attempt_id 引導；有 result Cookie 可藉 Unique result 關聯查找，但 E01 未完整定義這個無 ID 分支 | 不得由 Email／任意 UUID 查別人操作；如採 B，補明同 Cookie 的限定 lookup。Cookie／ID 都無則無恢復保證 |
| 2 preauth 15分鐘 | **確有 Proof 空窗**。例如 14:59 Login，15:00 Cookie 消失而 S Header 還未到；DB 保留 C 不會讓 Browser 重新送出它 | 有 Cookie 但 Server C 過期／撤銷，與 Browser 已刪 Cookie 不同。前者可依 CP 的限定例外，後者不能。不可延長 15分鐘政策假裝解決 |
| 3 deadline 120秒 | **與 Session TTL 可相容，但只是候選操作預算**。deadline=min(parent absolute, prepare+120秒)；authenticated parent 還要過 idle 檢查 | Verify／等待鎖跨 deadline 拒絕；鎖後取新 Clock，S.created=t、absolute=t+8小時。不 Touch preauth、不延 parent／result。Prepare 應在提交意圖時做，避免等待填表消耗預算 |
| 4 parent 已撤銷、S Cookie 未到 | **仍持有原 Cookie 時有條件可取消**：retained C＋其 CSRF＋綁定 Attempt；新增負面權限例外 | 不能把普通有效 Session Lookup 用於此例外。若 C Cookie 已過期／刪除，單持 CSRF／ID 不足 |
| 5 Login／Cancel 同時 | **共同鎖可使指定 Attempt 線性化**：鎖 parent→Attempt→既有 result，取鎖後新 Statement 重讀狀態／關聯，Cancel／Finalize 原子 Commit | Cancel 先→不准 Finalize；Finalize 先→Cancel revoke S。不能在拿鎖前檢查 state 後直接寫；不是只鎖不同的 Session 就安全 |
| 6 Cleanup 過早刪除 | **FK 只防錯刪引用，不決定正確保留期**。retain_until=max(parent absolute, deadline+8小時) 在可信時間／期限協定下可涵蓋可能有效 S | 先鎖／重驗 Attempt 終態與 deadline、無仍有效結果；按協定刪 Attempt 再刪無引用 Session。Pending／Crash／Restore／Clock 偏移都需測；Cleaner 不得與延後 Finalize 競速重建已刪 ID |
| 7 非 Owner／其他 Session 濫用 | 權限是 **Attempt 的 parent／result Context 關係**，不是 Vehicle Owner，也非任意同 User Session | 精確 Cookie Hash 關聯＋對應 CSRF＋來源＋Retention＋Gate；他人／另一裝置不匹配拒。已竊舊 parent Cookie 可造成該結果被撤銷的 DoS，必須保留風險，ID 本身不授權 |
| 8 Deadlock／長交易 | 全部 Writer 遵循鎖序可降低風險，**不等於已證明沒有 Deadlock**。Verify／網路等待不持鎖 | 持 result S 再追 parent C，會與 C→Attempt→S 形成反序。E04／Recovery 先只讀定位、依共同序鎖定後重驗；Cleaner／FK／後續 Attempt 也要納測。40P01 Rollback 後僅有界整交易重試 |
| 9 Cancel 後晚到 Cookie | **Jar 可以被 S 覆寫，Server S 仍 revoked**；新業務 401，E05 匿名。Cookie 倒退可能使之後合法流程需重登 | 不宣稱 Set-Cookie 被擋住或 Cookie 全域有序。跨獨立 Attempt 的新 Session 不在此取消範圍 |
| 10 取消不等於登出 | S6 §1.4／E06 已正確區分，但後續 UI／測試必須延續 | 若原 authenticated parent A 尚有效、Login B 在 Finalize 前取消，A 可以仍有效；204 只代表該 L 已取消。要登出需另 E04 確認當前 Context |

來源：S6 §1.4、E01／03／04／06、T31～33。上述是文件審核，沒有執行鎖／Cleanup 實驗。Row Lock 支援順序的原理與 Deadlock 注意事項參照 [PostgreSQL Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)；Vibicle 的 Parent／Attempt／Result 協定仍由 Application 維持。

### 6.1 B 還有兩個容易漏掉的邊界

- **取消 A1 不等於取消它結果之後的獨立 A2**：S1 被取消前可能已作為下一個 Login 的 parent 並產生 S2。B 保證 A1 的結果 S1 不能再用，不保證順帶撤銷 S2 或所有裝置。要做 family 撤銷是另一個需求，本輪不擴大。
- **Cancel 的 204 必須在已確認 Commit 後**：連線斷線、鎖逾時／結果不明不能轉成成功。若後端已成功但回應遺失，只有同 Proof 的可重試確認可收斂；Proof 再遺失仍 Unknown。第九張表不能消除這一點。

### 6.2 第九張表是否必要？有沒有更小但等價的設計？

**不是數學上必須九張表；需要的是能在 Crash／多 Worker 後仍保留的操作關聯與取消事實。** B 選獨立表，目的是把 Session 與 Operation 分清楚，非因八張表不安全。

可考慮在 auth_sessions 放 successor／取消標記而不另建表；但若要與 B 相同的「每個 Attempt 獨立、Cancel 不撤銷仍有效 parent、失敗後可再登入、結果可查、重試／Retention」能力，仍需操作識別／狀態／關聯／保留協定，只是塞入 Session。會擴大 Session 更新權限與條件約束，不必然更容易理解。

更小的「Cancel 只 revoke parent」：若 Cancel 先 Commit，能阻止尚未 Finalize 的 L；若 L 已 Commit S，僅 revoke parent 沒有用。沒有 parent→result 關聯不能撤銷未知 S，**不等價**。把每個 parent 限制成一個永久單次 Login 並強迫取消時登出 parent，可縮減狀態，但改變 B 保留原身分的行為與既有 Context 流程，不能當免費替代。

結論：**現行 MVP 要求用 A 即可先實作必要能力；若日後真的要 B 的指定取消保證，獨立有限 Operation 表比隱藏同等狀態更清楚。** 不另開第三套半成品設計，也不採用延遲幾秒、記憶體 cancel flag、PG Advisory Lock 當持久取消紀錄。


## 7. E01 GET 建立 Attempt 的 HTTP 語意與最小調整

### 7.1 審查結論

**不接受 S6「GET /auth/csrf?purpose=login 明確準備 Login Attempt」直接作定版。** Server 有寫入並非一律違反 Safe Method（例如計數／Log）；但這裡 Client 明確要求建立可被消耗／取消的 Operation，且會排斥另一個進行中 Login。它已超出單純讀取 CSRF 與附帶安全初始化，應用 POST 表達。no-store、來源檢查、重用 prepared ID 都不會把這個意圖變成 Safe。依據：[RFC 9110 §9.2.1／§9.3.3](https://httpwg.org/specs/rfc9110.html#safe.methods)。

本輪推薦 A，因此最小 MVP 是**不加入 Attempt 準備分支**，不是為了修 GET 又多加一個 MVP Endpoint。既有 E01 的匿名 preauth Bootstrap 屬 S1／S5 已接受的受控安全初始化：不建立 User 身分、不撤銷／更換有效 Context；有效 Context 只重取同 Token。不能由此推論任意 Auth Operation 都能塞 GET。

### 7.2 如果日後選 B：最小 API Delta（僅提案）

| 步驟／介面 | 行為與安全條件 |
| --- | --- |
| 1 E01 GET /api/auth/csrf | 回既有 Context 的 Token；無有效 Context 才依已接受來源／Gate規則建立15分鐘 preauth 並必要 Set-Cookie。**不建立 Attempt**。第一次沒有 CSRF Token 是 Bootstrap 的明示例外：精確來源／Fetch Metadata＋SOP／無任意 CORS＋no-store＋Gate；不是停用 Login 的 CSRF |
| 2 新 AP-PREPARE POST /api/auth/login-attempts | Cookie＋E01取得的 X-CSRF-Token＋來源／Gate；無 Password。鎖有效 parent、準備 Server ID 並 Commit 後201回 ID／deadline；不 Set-Cookie、不 Touch。已有 prepared 可回同一操作的200，verifying 衝突409。只在提交登入意圖時做 |
| 3 E03 POST /api/auth/login | Cookie＋CSRF＋Server Attempt ID＋Email／Password。按 B claim／Verify／Finalize；200 僅在 Commit 確認後 Set-Cookie。無 Token／錯 Context 不進 Verify |
| 4 E01 限定 Recovery | 既有 Attempt＋匹配 retained parent／result Cookie，來源／Gate；讀取消用 Token，不改 Attempt／Cookie。無 ID 查找若保留，需限定同 Cookie 的關聯與狀態，不對外查帳號 |
| 5 E06 PUT .../cancellation | 匹配 Cookie＋對應 Token＋來源／Gate；按共同鎖取消及 revoke result。204 不清 Cookie、不 Touch，不能改稱 Logout |

AP-PREPARE 是本文件暫用識別，**不是已加入原 inventory 的 E24**。若選 B 才同步 S6／DB／AUTH，決定介面 ID，不能悄悄讓 A 實作它。Prepare／Recovery／Cancel 共用 csrf_context 配額的用途擴充也屬 CP，數值仍60／固定300秒；不增加第四種演算法或 Redis。

Prepare 自己 Timeout，但尚未送 E03：只可能留下 prepared 技術操作，不會自行變 authenticated。保留同 parent 唯一 active Attempt、在確認狀態後重取既有 prepared，可減少恢復面；不能直接替未知 verifying 操作換一個 ID。

這項修正增加 B 一個 Endpoint，但減少 GET 的責任混用。若另要把「首次建立 preauth」也改為 POST Bootstrap，那是獨立介面整潔化提案；仍需無 Token 的來源防護例外，**本輪不要求 A 先完成它**。

## 8. 最小方案 A 的落地規則與可執行驗證規格

### 8.1 五個 Auth Endpoint 的 MVP Scope

| ID | A 保留的行為 | 明確不納入的 B 行為／仍需小心 |
| --- | --- | --- |
| E01 | 正常 CSRF 讀取／必要 preauth 初始化；來源／Fixed Window、15分鐘、不 Touch | 不接受 purpose=login／Recovery Attempt；未收斂 Auth 時 Client 不得呼叫會換 Cookie 的 Bootstrap |
| E03 | 現行 Cookie＋Token＋Email／Password；Verify 鎖外、鎖 C 重驗、新 S／新 Secret＋revoke C 同交易 | 無 Attempt Header。兩個同 C Login 最多一成功，另一衝突，不發失敗 Cookie |
| E04 | POST＋CSRF＋來源，確認目前可辨識 Context 撤銷後204清 Cookie；原失效 authenticated 專用例外保留 | 不回跨未知 L 的保證。若 Client 正在 uncertain Login，UI 顯示「尚無法確認登出」，不得新 Bootstrap／Logout 後假確認 |
| E05 | 新 Primary Lookup，200 身分／匿名，DB失敗503；不 Cookie、不 Touch | me匿名、甚至一次正向身分觀測，都不是所有先前 Auth 操作已完成的證明 |
| E06 | **Deferred／不實作**；ID 留作歷史追蹤 | 不假造取消204、不接受任意 attempt_id、不在八表暗藏 Operation 狀態 |

E02 註冊不變：preauth／CSRF、Argon2id、canonical Email、成功201後手動登入。E07～23 的業務要求與 ID 不變；不為縮 Auth Scope 砍 FR-013／照片權限。

### 8.2 Client 狀態及確認規則

狀態保持 anonymous／authenticated／pending／uncertain，全部是 UI 狀態，不能替代 Server 權限。最低規則：

1. 一個同 Origin Auth Coordinator 管 E01 可能 Set-Cookie、E03、E04；受控 Tabs 用同一 Web Lock。獲鎖後重新確認本機已知 Pending／Uncertain 與當前世代，不能只在排隊前檢查。
2. 在發出 Auth Request 前提升本機 Epoch、遮蔽私有畫面、通知其他 Tabs invalidation；Request 結果綁 Epoch＋User。只有 HTTP／內容與協調狀態均符合本次操作，才更新 UI；失敗／晚到結果不填入舊私有資料。
3. 在可用的同 Origin Storage 保存**非秘密**的 Pending marker（操作種類、隨機本機識別、開始時間／是否未確認），用於 Reload 後阻止失憶；不存 SID、CSRF、Password／Email／私有資料。marker 不是 Server Attempt ID，也不是鎖／授權證明。Storage 不可用時明確停用無法安全協調的 Auth 操作，不能以非原子的旗標假冒 Web Locks。
4. 網路不明，保留 marker／Uncertain，鎖即使因頁面卸載釋放也不等於完成。獲鎖者見 marker 不自動開始新 Cookie 變更。不用 Web Locks steal 或固定等待當成取消。
5. E05 可有限次觀測，不能清除未知 L 的 marker。能取得原受控操作已完成的可信結果，才依該結果與新身分確認收斂；Abort／關頁／重新整理、只看 Jar 或把匿名看成結束均不行。
6. 已明確確認的同 Context Logout 可由 User 重試；若 Cookie／身分變更或 CSRF 不匹配，先停下，不自動拿新 Token 重送舊 Logout。Pending Login 與單純 Logout Response 遺失分開處理。
7. Unknown UI 可顯示：「登入結果尚未確認。為避免錯誤切換登入，目前暫停登入與登出；公開資訊仍可瀏覽。」不要有其實只清 UI 的「安全登出」／「取消成功」按鈕。已有私有輸入可提示尚未提交，但不持久化秘密。

Client marker 仍可能因清 Storage、Crash 邊界或非受控 Client 而遺失；這是 A 的限制，不能稱已消除。公開瀏覽可繼續，不代表未知 S 已撤銷。**若審查要求無 marker 也必能恢復並確認取消，須選 B 的有限保證或新增需求；不能用更複雜的本機旗標無限修補。**

### 8.3 必要測試：A 必做，B 另有條件測試

以下是**未來可執行的案例規格，全部尚未執行**。沿用 S5 AT／S6 T ID 作關聯；SR-T 為本輪新增測試計畫識別，非新 AC。真實 PG 用至少兩連線／兩 Worker；Browser 用目標 Chromium、兩 Tabs／兩 Jar、可控延遲 Header／Body、凍結／pageshow。只延遲 JSON 無法覆蓋 Cookie 重排。

| 測試 ID／層級 | 控制步驟與客觀斷言 | AC／原測試／Gate |
| --- | --- | --- |
| SR-T01 Integration | 登入取得 C→重登入成 S；比對新 Secret／SID，重放 C 新 Request 拒絕；獨立 Jar 不變 | FR-002-AC06；AT-04／T04；A 必做 |
| SR-T02 Concurrency | 同 C 的兩個 Login 在 Verify 後競爭，最多一筆 Rotation；另一409、無 Set-Cookie | AC06；AT-04／T28；A 必做 |
| SR-T03 Concurrency | Touch 等鎖期間 Logout Commit，釋放 Touch；revoked 不清、last不更新；倒序則最後仍 revoked | FR-003-AC01／05、FR-002-AC04；AT-11／T26；A 必做 |
| SR-T04 Browser E2E | 延遲舊 Garage Response，Logout後／換B後釋放；舊資料不填入；同User新世代也丟棄 | AC07、FR-003-AC05；AT-12／T28；A 必做 |
| SR-T05 Browser E2E | 兩 Tab 通知後≤5秒清 UI；未收通知的 Tab 在 focus／BFCache恢復先遮蔽再 E05 | AC07、FR-003-AC02／04；AT-12；A 必做 |
| SR-T06 Integration＋Clock | 29:59／30:00、7:59:59／8:00:00；以近期活動排除idle干擾；preauth15分鐘等號拒絕，E01／05／圖不續期 | AC04／05、CP-03；AT-09／19／T25；A 必做 |
| SR-T07 Browser E2E＋fault | L Commit後延遲Header／另測Header到但Body斷，Client Timeout；保持Uncertain、不重送L／Bootstrap／假Logout | FR-003-AC03、NFR-REL-02／DR-01；T30；A 必做，斷言是誠實未確認 |
| SR-T08 Browser E2E | SR-T07後 Reload／關原Tab／凍結，另一Tab取得Lock；有marker時仍阻止新Cookie變更；故意移除marker保留殘餘反例 | AC07／DR-01；AT-12／T30；前者必做，後者記限制不冒稱保證 |
| SR-T09 Integration＋Browser E2E | Logout撤銷成功但204遺失；匹配同Context／原CSRF可重試；若Cookie已換不可自動登出新身分 | FR-003-AC03；AT-15；A 必做 |
| SR-T10 Integration＋Browser E2E | E01／02／03／04缺Token、跨Context、來源全缺／錯Port／Fetch不符；合規Native Jar成功；普通API／錯誤無Set-Cookie | AC08、FR-003-AC05、NFR-SEC-03／07；AT-06／07／T05；A 必做 |
| SR-T11 fault＋Integration | Gate／Session Lookup PG不可用→503；業務Commit後Touch斷線仍保留200／201已保存事實 | NFR-REL-01／02、FR-002-AC03／05；T26／27；A 必做 |
| SR-T12 Browser E2E，負面控制 | A-X刻意繞過Client協調：C2 Logout204後釋放S Cookie；記錄S可用；正式受控UI不得宣告整體Logout完成 | DR-01／I-AUTH-01；T30；保留反例，不標為「B已實作」或全部AC通過 |
| SR-T13 Integration＋Restore | 正常重啟原期限不變；舊備份還原隔離失效全部Context後重放拒絕 | AC04／06、FR-003-AC01／05、NFR-REL-03；AT-16；MVP Release必做 |
| SR-T14 Unit＋Browser E2E | Coordinator pending→uncertain→受控完成轉移；舊世代／User錯誤結果不得套用，Storage不可用明確限制 | AC07、FR-003-AC03／05；T28／30；A 必做 |
| SR-T15 Concurrency [B] | Prepared取消先於L抵達／Verify中取消；Finalize後取消再釋放Cookie；204後指定SID新Lookup均拒絕 | 額外指定取消保證；T31／32；採B才必做 |
| SR-T16 Integration＋Clock [B] | parent15分鐘到期且Jar移除、只有ID／只有CSRF、resultCookie仍未到；拒絕假取消，不發私有權限 | E情境／Recovery授權；T33；採B才必做 |
| SR-T17 Integration [B] | 遺失ID但保留parent／resultCookie限定查找；別人／同User不同Session不能查／取消 | Recovery Proof／BOLA；T31／33；採B才必做 |
| SR-T18 Concurrency＋fault [B] | deadline前後、鎖等待、Cleaner／FK／Finalize／Cancel／後續獨立Attempt、Cancel204遺失／Restore | 狀態轉移終態不重開、無有效結果早刪、整交易Rollback／有界Retry；T31～33；採B才必做 |

A 必做測試不因 CP-API-01 Deferred 而延期；B 的 T31～33 不再作既有 AC 的唯一證據。若 SR-T01～14 出現落在現行 AC 內的反例，標記該 AC 未達成，修設計或回報需求衝突，不以「學生 MVP」接受它。

## 9. 必須回填的 Change Proposals（本輪只提出）

| ID／建議 | 需回填的文件／位置 | 接受後的最小動作／Gate |
| --- | --- | --- |
| CP-SCOPE-01：MVP採A，CP-API-01 Deferred | S6 §1.2／1.3／7 E01／03／04／05／06、§6 Inventory、§11.1圖、§12 Trace、§13 T30～33、§14／18；S2 §6 I-AUTH-01／DR-01／Handoff | 不加第九表、移除E01／03的MVP Attempt前提、E06保留為Deferred歷史ID；相關Attempt專用Error Code／DTO欄位也移出MVP契約，E01／03／04恢復五介面基線，其他ID不重編。正常流程共22候選介面但分Slice實作。改正「一定先做B才能開始任何實作」；仍保留Auth安全驗收Gate。必須先審閱並同步，不能拿本文件當上游已改 |
| CP-SCOPE-02：不擴張AC的Recovery界線及Client流程 | S1 §5.3／SDQ-01可加審閱註記但不改AC；S2 §6.3／6.6；S3 §6.5／R-09；S4 §8.4／DBQ-04；S5 §6.4／6.6、AI-04／AQ-06 | 明確分撤銷C、舊UI隔離、Unknown不假確認、額外指定L取消；已知pending／uncertain時禁止Bootstrap後假Logout，補marker／失效流程。S5若維持凍結，先在S2寫現行補充及來源差異，不擅改歷史。保留DR-01有條件，不宣布完整解決 |
| CP-SCOPE-03：驗收證據分流 | S2 DR-01 Gate、S6 §12／13／18；S1 AC原文不變 | §3及SR-T01～14對應現行AC；B取消案例獨立標Hardening。任何已有AC實測失敗照樣Block，不因改推薦A而刪測試／恢復停用AC |
| CP-SCOPE-04：若日後採B，修GET Prepare及Recovery細節 | S6 E01／03／06與§1.4、S4新增有限Attempt模型／Retention／角色、S5準備／取消／Logout及S2決策 | 採§7的POST Prepare；補無ID但有Cookie的限定恢復、鎖序／Cleanup／期限及額度用途；用SR-T15～18驗證。**採A時不是Blocking工作**，不提前建立表或Endpoint |

以上均**尚未核准／尚未回填**。CP-01～05既有決策繼續有效，CP-06仍有條件；不把舊CP重新改成候選。FR-002-AC06／07、FR-003-AC03／05文字不刪不換義；若Reviewer要求比本輪列明範圍更強的保證，需顯式決策，不能悄改ID。

### 9.1 本次評估的停止線

接受 CP-SCOPE-01～03 後，可先授權 §11 Slice 1 的正常 Auth 端到端實作與必要反例測試；**不是直接批准全部功能或上線**。若測試證明 A 的受控流程仍違反現行 AC，先修該失敗，不預先強制啟動通用取消平台。

只有確定要提供「可確認取消未知 Login」的使用者功能，才啟動 CP-SCOPE-04／B。不再為無 Cookie、無 marker、任意外部請求全序或全裝置撤銷擴大本 MVP；這些不被宣稱已保證。


## 10. Remaining Risks 與不可延期的工作

| Risk ID／風險 | 對應驗收／範圍 | 處理階段與停止條件 |
| --- | --- | --- |
| SR-R01 受控UI仍接受舊帳號資料，或普通Touch復活Session | FR-002-AC04／06／07、FR-003-AC01／02／04／05 | **必要安全，不延期**。Slice1建立防線，各Slice持續用SR-T01～06；最終Release必通，失敗即Block |
| SR-R02 Unknown後誤Bootstrap／假Logout完成 | FR-003-AC03、NFR-REL-02、DR-01／I-AUTH-01 | **必要安全，不延期**。Slice1做Uncertain與SR-T07～09／12／14；不能對A-X顯示整體成功 |
| SR-R03 Cookie重排、Crash／marker遺失／非受控Auth | FR-002-AC06／07、FR-003-AC03／05、CP-06 | A不能保證全域排序或所有未知L可撤銷；Slice1與8記錄實際Chromium證據及反例。現行AC內的失敗照樣Block；額外取消能力另列Hardening，不宣稱DR-01全解 |
| SR-R04 B的Proof遺失、過早Cleanup或錯誤狀態轉移 | 額外指定取消保證；仍受NFR-SEC-02／07、FR-003-AC03約束 | A不建此機制；若B獲准必先定POST準備、Retention／權限並執行SR-T15～18，不能直接照原稿實作 |
| SR-R05 PG／Clock／Restore故障及固定窗NAT／Burst | FR-002-AC03～05、NFR-SEC-05、REL-03 | 單PG仍單點；Slice1測fail closed與多WorkerGate，Slice8測Restore／可信Proxy。Burst／NAT保留，不新加Redis |
| SR-R06 Private Image授權／Metadata／資源及清理錯誤 | FR-008-AC01／05、FR-012-AC01～07 | **不是Auth Hardening延期項**。Slice6／7驗真解碼、去Metadata、保舊圖／無公開旁路；工作預算在Slice8資源校準 |
| SR-R07 C／E／H、單末端／版本並行不一致 | FR-006-AC04／06／07、FR-011-AC06／07、FR-013全部 | **既定Must Have**。Slice3～5真PG雙連線／Rollback；不因Auth縮Scope刪FR-013或舊版鏈 |
| SR-R08 有效Cookie失竊、XSS代送、Distributed Stuffing／主機未定 | NFR-SEC-01～07、DPQ-01～05 | 基本防線仍做；不宣稱可防所有終端失陷／Botnet，MFA／帳號復原非MVP。部署資源與展示期限需在Slice8前由User決定，沒有購買或部署動作 |

適合留後續 Hardening：指定 Login Attempt 取消、失Proof的帳號復原、任意非受控Auth全序、跨多次輪替family撤銷、一般業務Idempotency。**不能留後續**：密碼Hash、Server撤銷／期限／Rotation、CSRF／來源、逐資源Owner、舊UI隔離、Unknown誠實回饋、資料一致性與Private Image。

## 11. 建議的八個 Vertical Slices（僅順序，不是實作授權）

每個 Slice 都包含 UI→HTTP→FastAPI→PG→UI 的可操作結果；先做使用者流程，不按「先寫完所有Repository／23個Endpoint」切割。只有全部Must Have及部署驗收完成才可稱MVP完成，早期Slice可展示不代表可提前公開上線。

共同要求：使用合成帳號／VIN；所有Protected Endpoint讀app_users／auth_sessions，所有Mutation驗來源／CSRF，Auth Gate使用auth_rate_limit_buckets；成功業務依白名單Touch、Commit與Touch錯誤分報。下列Tables列業務額外責任。未來Migration須完整保留已接受Constraint／FK依賴，可先建立核准八表再逐Slice開介面；不得為分段驗收暫時關FK或硬編碼H=0。**本輪不建立任何表或Migration。**

### Slice 1 — 帳號與目前登入身分

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | 註冊後手動登入，看到本人身分；重新整理恢復；登出；錯誤／Unknown明確顯示 |
| React | RegisterPage、LoginPage、CurrentUserPanel、AuthProvider／Coordinator、UncertainBanner |
| FastAPI | E01 GET /api/auth/csrf、E02 POST /api/auth/register、E03 POST /api/auth/login、E04 POST /api/auth/logout、E05 GET /api/auth/me；不做E06 |
| PostgreSQL | app_users、auth_sessions、auth_rate_limit_buckets |
| 必測 | SR-T01～10／14；正確／錯誤憑證、canonical併發Unique、密碼Code Points／Hash／秘密不Log、三Scope多Worker固定窗；PG失效SR-T11 |
| 必須理解 | Password KDF與Session Hash不同；Cookie Jar／CSRF Bootstrap；Commit不等於Client收到；HTTP Stateless與PG共享State |
| 客觀完成 | 正常UI及獨立Jar皆可Register→手動Login→E05→Logout；重放舊SID拒絕；兩Tab／Clock／延遲Response按預期；Unknown不假成功。沒有取消未知L保證，限制可展示與說明 |

第一個真正端到端里程碑就是本Slice，無須車輛、照片或全部資源API先完成。Auth安全測試需隨後持續跑，不以「正常登入可用」宣稱已通過全部安全驗收。

### Slice 2 — 新增合成車與自己的車庫

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | 建無圖／無價的未上架車，重新載入車庫及自己的管理詳情 |
| React | GaragePage、CreateVehicleForm、OwnerVehiclePage基本區塊 |
| FastAPI | E07 GET /api/me/vehicles、E08 POST /api/vehicles、E09 GET /api/me/vehicles/{vehicle_id} |
| PostgreSQL | vehicles＋vehicle_mileage_changes同交易；Owner DTO依需要讀vehicle_images／maintenance_events／maintenance_record_versions，不以假資料取代 |
| 必測 | T06～08、SR-T11；A／B隔離、偽造Owner、同VIN雙連線最多一成功、初始Ledger失敗全Rollback、空車庫與DB錯誤分開、20筆可翻頁 |
| 必須理解 | FK與Ownership不同；Unique裁決併發；201／Location；初始C與Ledger的原子性 |
| 客觀完成 | A建車後Reload仍在；B直接管理URL得404；同正規化VIN最多一台；DB僅有完整Vehicle＋初始Ledger，不能公開讀未上架內容 |

### Slice 3 — 編輯車輛、價格與目前里程

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | 編輯允許欄位；明確確認有理由的C下修；另一分頁過時保存得到衝突 |
| React | EditVehicleForm、MileageDecreaseConfirmation、ConflictNotice、OwnerMileageLedger |
| FastAPI | E10 PATCH /api/vehicles/{vehicle_id}、E21 GET /api/me/vehicles/{vehicle_id}/mileage-changes；沿用E09 |
| PostgreSQL | vehicles／vehicle_mileage_changes；讀maintenance_events→current maintenance_record_versions求H，即使目前尚無UI新增事件 |
| 必測 | T09～11、SR-T03／11；相同expected最多一實際修改、C≥H、下修理由／確認、No-op不增版本、C＋Ledger失敗全Rollback、Commit成功Touch失敗仍200 |
| 必須理解 | Row Lock與Optimistic Version不同；BIGINT字串；省略／null；跨列規則不是普通CHECK |
| 客觀完成 | 兩Tab舊版本不默默覆寫；C變動與Ledger一致；低於有效H拒絕；輸入失敗不部分保存，UI保留可重新確認的輸入 |

### Slice 4 — Owner補登歷史維修

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | 任意順序補登合理過去維修，管理頁讀有效時間線，來源固定自行申報 |
| React | AddMaintenanceForm、OwnerMaintenanceTimeline、來源提示 |
| FastAPI | E14 POST /api/vehicles/{vehicle_id}/maintenance-events、E16 GET /api/me/vehicles/{vehicle_id}/maintenance-events |
| PostgreSQL | maintenance_events＋maintenance_record_versions初版、vehicles聚合revision；C不自動改 |
| 必測 | T16／17及T11；早於建車／低於C可補、未來日期／跨日倒退拒絕、同日不推順序、兩筆各對舊E合法但合併非法時不能都提交、事件＋初版原子 |
| 必須理解 | DATE與submitted_at不同；有效集合E／L／U；Deferred FK初始化；鎖後新Statement讀取 |
| 客觀完成 | PRD接受／拒絕例子可逐一演示；20筆以上可翻完；新事件不修改C；非Owner不能新增，併發不留下矛盾歷史 |

### Slice 5 — 更正錯高里程並保留原文

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | 對目前末端追加完整更正版、展開全部原文與理由；錯高值退出H後有理由下修C |
| React | CorrectionForm、VersionHistoryPanel、有效／已被更正標記；沿用Slice3下修 |
| FastAPI | E18 GET /api/me/vehicles/{vehicle_id}/maintenance-events/{event_id}/versions、E19 POST /api/vehicles/{vehicle_id}/maintenance-events/{event_id}/corrections；沿用E10／16／21 |
| PostgreSQL | Event／Version／Vehicle同交易；C異動另由vehicle_mileage_changes保存 |
| 必測 | T18～21／34；同末端雙更正最多一成功、非末端／跨車拒絕、原文不可UPDATE／DELETE、切pointer失敗全Rollback、超20版可完整翻頁、更正Unknown不盲重送 |
| 必須理解 | 事件與版本不同；Unique parent與Service末端驗證各自責任；更正歷史不自動更正C |
| 客觀完成 | 900000→70000更正後原文仍可追，H不含舊高值，再合法降C至80000；沒有分叉、刪除或把更正當第二次維修；FR-013完整保留 |

### Slice 6 — 私有主照片上傳／替換

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | Owner上傳／替換單張照片，重讀管理頁可看；替換失敗保留舊圖 |
| React | MainImageUploader、受控ImagePreview、上傳錯誤／Unknown回饋 |
| FastAPI | E22 POST /api/vehicles/{vehicle_id}/image、E23 GET /api/vehicles/{vehicle_id}/images/{image_id}；沿用E09 |
| PostgreSQL／File | vehicle_images／vehicles；Private Volume與受限處理工作，不建Queue服務 |
| 必測 | T22／23／24的Owner部分；5MiB、真解碼三格式、像素／動畫／破損、方向／Metadata、資源終止、非Owner、舊URL／claim／Cleanup／DB及File故障；照片不Touch |
| 必須理解 | Multipart／Body限制；ready≠current≠檔案存在；DB／Filesystem沒有共同ACID；逐次授權及no-store |
| 客觀完成 | 合法圖可讀，原檔／舊主圖／他人未上架圖不能由受控服務讀取；失敗不破舊圖；無兩張current；Private Volume重建後可還原證據待Slice8完成 |

### Slice 7 — 上下架與公開Marketplace／履歷

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | Owner有價格／ready圖後上架；訪客搜尋／詳情／全部履歷鏈／下修摘要；Owner下架後訪客新讀取拒絕 |
| React | ListingControls、MarketplacePage、PublicVehiclePage、PublicTimeline／VersionHistory／MileageSummary |
| FastAPI | E11 PUT /api/vehicles/{vehicle_id}/listing、E12 GET /api/marketplace/vehicles、E13 GET /api/vehicles/{vehicle_id}、E15 Public maintenance-events、E17 Public versions、E20 Public mileage-changes；沿用E23 |
| PostgreSQL | vehicles／vehicle_images／maintenance_events／maintenance_record_versions／vehicle_mileage_changes，Public projection不升級Owner DTO |
| 必測 | T12～15／20／21／24；缺價／圖拒、No-op不洗時間、品牌型號大小寫／literal搜尋、固定12筆／排序／超頁、非Owner管理拒；下架後舊詳情／版本／圖片／條件Request無內容／無304 |
| 必須理解 | 資源與Projection；public不Touch；下架的Commit／新授權邊界；SPA Shell與私有API內容不同 |
| 客觀完成 | 13台以上可搜尋換頁；Public無Email／完整VIN；原文與來源可讀且一事件只計一次；下架後匿名新Request404、Owner仍能管理；無購買／聯絡假入口 |

### Slice 8 — 同Origin HTTPS完整展示與故障驗收

| 項目 | 可獨立驗收內容 |
| --- | --- |
| 使用者功能 | 在自訂網域完成整套展示；服務重建資料仍在，故障有可追查回饋 |
| React | 既有頁面深連結、手機寬390px／桌面1280px、共通錯誤／Request ID；不新增業務功能 |
| FastAPI | 驗證前七Slice的實際Endpoint，沒有新增業務／運維公開Endpoint要求 |
| PostgreSQL／File | 全部核准八表、Private Volume、受控備份／Restore；Session失效與業務資料保留分開 |
| 必測 | SR-T01～14回歸、T24～29／35；真TLS Cookie／來源／可信Proxy、DB fail closed、Container重建、一次隔離備份還原、Secret／Log檢查、指定工作負載量測與影像預算校準 |
| 必須理解 | DNS不等於主機、TLS Termination、Image／Container／Network／Volume、環境設定／Secrets、Observability／Restore |
| 客觀完成 | 選定並記錄主機／Domain／費用後，乾淨環境可按文件重現；有效HTTPS與無Mixed Content；完整Must Have／71有效AC有證據或明確未達成記錄，未達必須項不能稱Release通過；沒有未經驗證SLA |

實作前先接受本輪 Scope／同步 CP，並由使用者另行授權開始。Slice8的主機／網域／費用是部署決策，不是假設已購買資源。SR-T15～18與第九表不在這八個Slice的MVP範圍。

## 12. 我應該能親自回答的五個問題

1. C已撤銷但Browser再送C，與Server已建立S但Cookie尚未到達，為什麼不是同一種「Session復活」？各要查哪一筆PG狀態才能證明？
2. Login Timeout後E05回匿名，為什麼不足以宣稱已登出？Web Locks、Auth Epoch、BroadcastChannel各保護哪一層，哪一層不在它們控制內？
3. 不用第九張表時，如何原子完成新Session／撤銷舊Context，並讓Logout與Touch競爭仍不復活？為什麼不能持鎖做Argon2 Verify？
4. 若真的提供指定Attempt取消，Cancel先Commit與Finalize先Commit各怎麼處理？若只有Attempt ID沒有Cookie、或15分鐘preauth Cookie消失，為何不能回204？
5. 為何GET取得CSRF與POST準備Login Operation應分開？第一次沒有Token時如何安全Bootstrap，之後Login又如何把Token綁到同一Context？

## 13. 審查交付與停止點

本次提出可採取行動的結論：**MVP採A；保留必要安全與Unknown限制；CP-API-01的指定取消留Hardening；先審閱CP-SCOPE-01～03並同步，再依Slice1開始後續實作。** 若使用者要求Timeout後的積極、可確認取消，選B並先修POST準備／Recovery／Retention，再做其對應測試，不同時維護兩套Auth協定。

本輪只建立本Markdown，六份來源不改；既有B推薦／Blocking尚待審查後回填，不能宣稱已撤銷。驗證限於文件引用、AC／Endpoint／Slice／測試對照與圖的文字結構；沒有運行API、SQL、Browser／Concurrency測試，也沒有Mermaid Renderer驗證。所有Slice與測試均為將來工作。

完成本次Scope Review後停止，等待審查；不開始實作或下一階段。
