# Vibicle — Step 1.5 Decision Log 與需求審查

- 文件版本：v0.3（Step 3A Scope 同步）；對應 [PRD v0.2.1](PRD.md)，保留Step 1.5原決策／歷史條款
- 日期：2026-11-05（Asia/Taipei）；原版2026-11-02
- 狀態：CP-01～05依Step 2C.5審查接受（CP-04須實測），CP-06有條件接受；非部署／實作或驗收完成
- 範圍：§6保留Step 2C.5四份文件同步歷史；最新§7記錄已接受CP-SCOPE-01～03。本輪只同步本文件及API_CONTRACT，另在web-app實作Step 3A；不是完整Auth或部署完成。
- 來源：保留Step 1.5 OQ-01～13候選歷史；本輪安全決策效力依使用者Step 2C.5對AUTH CP-01～06審查，見§6；其餘部署事項不自動核准
- 前版：PRD v0.1 的46個AC全部保留識別碼；4個停用並有替代，29個新增，現行有效AC共71個
- 閱讀順序：先§7確認最新MVP Scope，再查§6安全整合／風險、§1～5歷史決策；不把Deferred B當全部開發的前置。

## 1. Decision Log

D-01～13保留原OQ識別與產品基線；D-01／02的安全子題按Step 2C.5更新，CP審查效力見§6，未藉寫文件自動核准其他議題。主機／網域／費用／資源數值仍未確定。

| ID／原問題 | 候選決策 | 理由 | 影響 | 仍待確認或設計 |
| --- | --- | --- | --- | --- |
| D-01／OQ-01 | Email + Password、12–128字元、註冊後手動登入；Argon2id、normalized→PG lower | 沿用AUTH §3與CP-04，避免兩套canonical；CP-02固定窗可教學／驗收 | FR-001／002、BR-13、SEC-01／05、DAT-01；CP-02／04 | PG Encoding／Collation／Locale、Library與Unicode／KDF／Proxy實測仍須記錄；不宣稱Email驗證、完整Unicode等價或帳號復原。 |
| D-02／OQ-02 | PG Session／Token Hash＋HttpOnly __Host- Cookie、Synchronizer csrf_secret；preauth15分鐘、authenticated閒置30分鐘／絕對8小時，本次撤銷 | CP-01／03／05收斂Context／Rotation／Touch／Logout；CP-06只接受有限Browser協調 | FR-002／003、BR-14、SEC-02／03／07、REL-01～03；CP-01～06 | Cookie／來源／白名單已回填，DR-01仍未解；Step 2D定Recovery／逐操作契約，Browser／多Worker／Proxy須驗；實際網域／部署未定。 |
| D-03／OQ-03 | 未上架僅 Owner 可讀詳情／全部履歷版本／照片；首次交付 no-store、所有可控路徑驗證 | 避免直接 URL／Cache 繞過；明確只撤回後續受控交付，不能追回外部副本 | FR-008／010／012、BR-03／12、SEC-08 | 私有儲存／交付／Proxy設定：SDQ-03／04。無全域Cache刪除或在途回溯取消保證。 |
| D-04／OQ-04 | 僅合成VIN，trim＋大寫後唯一，一般編輯不改，公開末六碼 | 保留唯一性教學而不誤收真實車籍或聲稱驗證 | FR-005／006／010、BR-05／11／17 | 合成Fixtures及公開投影：SDQ-04／05；填錯以另一合成案例展示，不新增改VIN／刪車後台。 |
| D-05／OQ-05 | 建議採 A 的精簡子集：單事件、單鏈、完整替代版本＋理由，指向目前有效末端，原文保留；新增Must Have FR-013 | 數值更正必須能明確識別有效值；文字補充無法退出錯誤高值 | FR-013／010／011、BR-09、DAT-05；SH-04提升 | 新增的A-lite取捨仍待審閱；具體版本關聯／唯一性／並行策略：SDQ-02，不做批次、審批、分叉合併。 |
| D-06／OQ-06 | 允許任意順序補登；不同事件日期有效里程非遞減；同日不推定先後；目前值C與歷史分離且C≥H；不自動改C | 避免補登被「新值≥目前值」阻擋，避免歷史誤填自動污染目前值；保留日期一致性 | FR-006／011／013、BR-07／08／15／16、DAT-02 | C語意、同日規則、有理由下修是本次候選答案，需審閱；交易與衝突：SDQ-02。無儀表歸零模型。 |
| D-07／OQ-07 | 每車一張、建立無圖／上架必填、JPEG／PNG／WebP≤5MiB；候選各邊≤6000px、總≤1200萬px，單靜態；轉正／重編碼／移除Metadata | 壓縮檔大小不足以限制解碼資源；避免原檔洩漏 GPS 與直接存取 | FR-012／007、BR-12、SEC-09，SH-03部分提升 | 本次新增尺寸／像素／5秒與128MiB工作預算為待審候選，需在SDQ-03／DPQ-03選工具、隔離並校準，未宣稱已測。 |
| D-08／OQ-08 | 品牌／型號單字串包含、不分英文大小寫、最新實際上架優先、每頁12筆 | 固定可測查詢，不把Scan占位或任意排序當完成 | FR-009、BR-04／11 | 同值穩定排序、分頁Contract：SDQ-04／05；跨頁併發上下架不保證快照固定。 |
| D-09／OQ-09 | TWD正整數／km非負整數；沿用PRD合理上下限 | 減少單位／精度分支，使驗收可重複 | FR-005／006／007／011／013、BR-06 | 保存與輸入型別／數值規則：SDQ-05；不因此建立Schema。 |
| D-10／OQ-10 | 僅供合成資料作業展示，不宣稱真實交易可用 | 誠實界定身分、資料真實性與維運能力 | 全站定位、FR-005／010、BR-17、UX-02 | 展示註冊／訪問限制、清除與結束日：DPQ-05；仍需防濫用。 |
| D-11／OQ-11 | 無購買／付款／過戶／聊天／聯絡賣家，定位改為履歷與出售資訊展示 | 使用流程沒有成交或聯絡能力，不能以文案誤導 | Problem Statement、FR-010-AC06、BR-17、Won't Have | UI落實指定用語與提示；需求不再留假購買／聯絡按鈕。 |
| D-12／OQ-12 | 優先比較同Origin入口，React與Python API保持獨立服務 | 前後端分離不要求跨網域；讓Cookie與CSRF邊界較易解釋 | CON-05／06、DEP、SDQ-01／03 | 實際Proxy、主機、網域、DNS、TLS、費用、儲存全部未決：DPQ-01／02／04。 |
| D-13／OQ-13 | Must Have、權限、一致性、測試、部署先行；撤回現階段P95≤2秒門檻，待資源定版 | 沒有主機數據不能承諾容量；保留量測流程 | NFR-PERF-01、第7節、追蹤與驗收 | 排程／資源／量測門檻：DPQ-01／03；非功能做越多越好。 |

NFR 欄中的 SEC／DAT／DEP 等省略共同前綴 `NFR-`。

### 1.1 日期、目前值與更正的選擇理由

**建議選擇「歷史有效集合 E」與「目前申報里程 C」分離，不由歷史自動推高 C。** 所有有效歷史≤C，不同日期不得倒退。較早維修里程可以低於C，不受車輛資料建立日期阻擋；事件日期與Server申報時間分開。

補登／更正若高於C，Owner先明確更新C；歷史更正不自動降C。若C也錯誤，先排除有效歷史中的錯誤高值，再有理由地下修C，且保留前後值。這比自動採歷史最大值更容易解釋：修正一筆不會偷偷改另一個使用者申報欄位，也不會把錯誤原文當永久下限。

替代方案「C自動等於歷史最大值」會忽略尚未維修時的目前里程；「新增紀錄自動取max(C,m)」會讓誤填高值污染C。兩者都需要額外復原語意，本輪不採作候選。

同日紀錄只有日期、沒有真實時刻，故不按申報順序判里程。以同日區間對前後不同日期驗證，主線顯示再按里程與穩定鍵排序；這是展示順序，不是實測時間證明。PRD第5.1節列出可直接轉成測試的接受／拒絕例子。

### 1.2 履歷更正 A／B 比較與 MVP 成本

| 面向 | A：完整更正關聯系統 | B：自由文字追加補充 | 本輪建議：A的精簡子集 |
| --- | --- | --- | --- |
| 資料一致性 | 可明確追蹤版本，但若加批次、審核、分叉，狀態複雜 | 人讀得懂補充，系統仍不知道哪個里程失效；錯誤高值仍參與驗證 | 明確指向一個目前有效末端，新版本提供完整替代內容；單鏈只有一個有效值 |
| 錯誤高里程 | 能在有效集合退出，但需定義連動 | 不能只憑文字可靠退出；若以關鍵字自動忽略，等同暗造另一套不明更正規則 | 排除舊有效版，驗證替代集合；C若另有誤再有理由下修 |
| 使用者體驗 | 能比較多版本，但進階流程容易過重 | 表單最少，讀者需自行比對，統計與提示可能仍錯 | 一個「更正」入口、完整替代表單＋理由；主線有效版、展開原文與鏈 |
| 實作成本 | 明確關聯與有效值管理本身為中等；若再加批次／審核／分叉才升高，這些不是A的必然要求 | 低，但無法滿足本輪數值一致性要求 | 中等：版本關聯、單末端併發保護、公開展示與測試；沒有免費或低成本保證 |
| 驗收 | 需更大測試矩陣 | 僅能驗收「文字有保存」，不能證明錯值已不阻擋 | 可驗收舊值退出、同末端最多一成功、原文保留、跨車／非Owner拒絕、下架控制 |
| 是否適合本MVP | 原文保留與明確關聯適合；通用進階流程不宜擴大 | 若只做文字記事可行，但與OQ-05／06候選目標衝突 | 建議納入FR-013 Must Have，只做單事件／單鏈／完整替代；無批次、審批、分叉、刪除或撤回 |

判斷：新增FR-013確實增加範圍，但為達成本輪要求有必要。建議保留可明確計算有效值的最小關聯流程，刪減相簿、進階篩選等Should Have。若使用者要退回B，需明確放棄「機器可判定的里程更正」並重寫C／歷史驗證與產品說明，不能將B宣稱為A的等價簡化。

### 1.3 錯誤復原與剩餘限制

候選更正不覆寫原文，也不要求將錯誤高值永久列入最大值。例如C=120,000、2月錯填110,000，可追加關聯更正為70,000，再補登3月80,000；若C也誤填，可留理由降為90,000。若另有仍有效100,000，就必須先更正它；不能只因其中一筆被更正就把其他有效高值一併忽略。

如果多筆錯誤彼此衝突，必須選擇保持當前有效集合一致的逐筆修正順序，並提示阻擋事件。MVP沒有一次任意修正整組紀錄或處理儀表重置；這是明確範圍與殘留風險，不是已完成的修復工具。

## 2. Requirements Conflict Analysis

下列條款都已同步修訂；不是只改OQ表。未逐字修改的AC也會依其所引用BR／共通規則受影響，設計與測試必須追蹤整個依賴。

| Conflict ID | v0.1受影響條款 | 衝突／不足 | v0.2處理 |
| --- | --- | --- | --- |
| CF-01 | §0.1「所有OQ未確認」、§9全部OQ、§10.3就緒門檻 | 使用者已給候選答案，仍全部掛未回答會無法前進；又不能假稱已核准 | OQ保留ID→D-01～13候選，另列SDQ／DPQ；整體仍Review Candidate |
| CF-02 | §0.2展示流程、§1.3定位、Persona註記、US-07／09／10／11語境、第7.3節、原專案對照、FR-010 | 沒購買／聯絡卻叫交易平台，可能誤導真實可用 | 統一出售資訊展示、合成資料提示、無購買／聯絡／認證文案，新增BR-17／UX-02與FR-010-AC06 |
| CF-03 | CON-03／05／06、NFR-SEC-04、DEP-01～03 | 同Origin候選被誤當主機／TLS已選定，或被誤認服務合併 | 保留獨立React／API，入口僅優先比較；供應商／費用仍DPQ |
| CF-04 | §4.0帳密、FR-001描述／正常結果、FR-002描述／AC04、BR-13／14、SEC-03／05 | 註冊後自動登入與Session期限未定；Store／限流混入產品問題 | 明確手動登入／Session基線，限流實現留SDQ；新增FR-001-AC05與FR-002-AC05～08 |
| CF-05 | FR-003全部流程／AC01～03、FR-002恢復、BR-14、REL-03 | 不區分分頁共用Session／裝置，沒處理過期與晚到回應 | 新增分頁共享、Server撤銷／期限與晚到回應隔離、在途界線；新增FR-003-AC04／05 |
| CF-06 | NFR-SEC-03、所有Mutation FR | HttpOnly不會自行阻擋CSRF，登入／登出與上傳也須涵蓋 | 新增SEC-07與§5.3、正常及跨站／錯Token驗收；具體Token流程SDQ-01 |
| CF-07 | §4.0目前里程、FR-006流程／錯誤／AC03、BR-07、DAT-02／03 | 「目前里程不得下降」會讓錯誤高值永久鎖死 | 停用FR-006-AC03，AC05～07分拆價格、C≥H與有理由下修；新增BR-16／DAT-05 |
| CF-08 | FR-011正常結果／AC02／03、BR-07／08、DAT-02／04、US-11及追蹤 | 新紀錄必須≥C及不可早於最後日期，無法補登；自動更新C污染目前值 | 停用AC02／03，改AC06／07，事件日期與申報時間分離、按有效集合驗證，C不自動變 |
| CF-09 | FR-011-AC05、BR-09、SH-04、第7.1／7.2、Traceability | 文字補充不能讓機器知道錯誤高值被取代；正式關聯原本可延期 | 停用AC05，新增AC08／FR-013／US-13；SH-04提升並保留追蹤 |
| CF-10 | FR-010-AC02、FR-011／006、BR-08 | 按同日申報時間推斷先後，會誤判補登里程 | BR-15明定跨日非遞減、同日區間，排序不是驗證；§5.1列例子 |
| CF-11 | FR-010內容／AC02、PERF-02、DAT-05、Traceability | 更正後原文如何看、有效事件如何計數、C下修是否可追查未定 | 主線只計有效末端，展開全部原文與鏈；FR-010-AC05／07及FR-013驗收 |
| CF-12 | FR-005／006／010、§4.0、BR-05／11、第8節 | 原對照仍允許真VIN，且一般修改／公開範圍未定 | 僅合成VIN、正規化唯一、不能一般改、末六碼、不宣稱驗證；FR-005-AC05 |
| CF-13 | FR-008正常結果／AC01／04、FR-010／012、BR-03／12、SEC-06 | 「下架後不能讀」沒區分受控新讀取、外部Cache、已授權傳輸 | 精確定義提交與授權邊界，增加AC05／SEC-08／§5.2；不保證追回已交付副本 |
| CF-14 | FR-012-AC01～04、SH-03、BR-12、SEC-06 | 5MiB無法限制像素／解碼；EXIF／方向仍列Should；原檔／舊URL可能繞過 | 新AC05～07與SEC-09，明定尺寸／工作預算、重編碼與Metadata清理；原檔不公開、舊URL停用 |
| CF-15 | NFR-PERF-01、OQ-13、DEP、§10.3 | 沒有主機卻把2秒門檻帶入可能被當保證 | 同ID保留量測目的、撤回尚未有依據的數值；資源與門檻DPQ-03 |
| CF-16 | NFR-REL-01／02／03、MNT-01／02、OBS-01／02 | 沒有更正原子性／單末端、持久化異動／日誌區分、Session重啟語意 | 擴充更正／C／CSRF／Cache案例與持久化歷史；通用重送仍Should但不能分叉 |
| CF-17 | 第3／7／8／9／10節全部追蹤與原比較 | 新增Must Have後仍稱12項，舊停用AC可能仍被測試 | 改13項、US-13、BR-15～17、新NFR；完整ID對照及歷史原文如下，未改寫原Web3 |

## 3. Revised PRD 與 ID 變更追蹤

現行需求全文：**[PRD.md v0.2](PRD.md)**。同步修訂Functional Requirements、Business Rules、AC、NFR、Scope、Comparison、Open Questions與Traceability。本文件保存前後對照，避免悄悄改變原ID意義。

### 3.1 AC變更總覽

- 原46個ID仍存在；其中4個明確停用，不再作現行驗收。
- 新增29個ID（含FR-013的8個）；總識別碼75個，現行有效71個。
- 其餘修改為原目的的明確化或擴充，原文及新文完整列在3.3節；未改變的ID不重編。
- 新增BR-15～17、US-13、FR-013；所有舊BR／NFR ID仍保留。SH-04提升；SH-03的Metadata／方向處理提升，非相簿整體提升。

### 3.2 停用AC與替代

| 停用ID | v0.1原文 | 替代與理由 |
| --- | --- | --- |
| FR-006-AC03 | 目前里程不得下降或低於既有紀錄里程；已上架車不得保存無效售價。一般文字編輯不得改變履歷內容。 | FR-006-AC05～07；分開價格／C不變量／下修理由，避免錯誤高值鎖死。 |
| FR-011-AC02 | 建議新紀錄里程不得小於目前里程；維修日期不可晚於 Asia/Taipei 今日，也不可早於最近一筆紀錄的維修日期。相同日期與里程可記錄不同維修項目；補登較早／較低里程紀錄待 OQ-06。 | FR-011-AC06、BR-07／08／15；允許補登，依有效事件日期界線驗證。 |
| FR-011-AC03 | 新增紀錄與目前里程更新一起成功或一起失敗；有併發更新時仍須保持此規則。 | FR-011-AC07、NFR-DAT-02；取消歷史自動同步C，仍保護一致性。 |
| FR-011-AC05 | 建議提交後不能編輯或刪除；如需更正，只能新增一般紀錄說明前筆錯誤，原紀錄保留；正式更正連結機制不列 Must Have，待 OQ-05。 | FR-011-AC08、FR-013；文字補充不能代替明確關聯更正。 |

### 3.3 保留ID但明確修訂的AC

本表保留完整舊文／新文與原因；同一ID仍追蹤同一行為目的，重大相反規則已於3.2停用而非重用。

| ID | v0.1原文 | v0.2現行文字 | 理由 |
| --- | --- | --- | --- |
| FR-002-AC04 | 建議登入閒置 30 分鐘或建立滿 8 小時即失效，並由 Server 執行；值及是否保留多裝置登入待 OQ-02 確認。 | Server 在距最後有效活動達 30 分鐘或距本次登入建立達 8 小時時拒絕 Session；Cookie 未到期也不能繞過；活動不能延長 8 小時絕對期限，舊 Session 不自動復活。 | 將候選期限明確化為 Server 判定的 30 分鐘閒置／8 小時絕對期限。 |
| FR-003-AC01 | 登出成功後，原憑證不能再讀取車庫或新增／編輯資料。 | 撤銷提交完成後才進行 Session 授權判定的新 Request 必須拒絕原憑證，涵蓋讀取與寫入。已在撤銷前通過授權的在途工作不保證回溯取消；此界線不得描述成能撤回已完成操作。 | 界定撤銷完成後驗證的新請求與已通過授權的在途請求，避免無法實現的回溯取消承諾。 |
| FR-003-AC02 | 重新整理、上一頁或開啟另一分頁不能恢復有效寫入權限；私有資料 Cache 在前端登出時清除，其他分頁下次操作須重新驗證。 | 重新整理、上一頁與開啟分頁不恢復舊 Session；登出清除 App 私有 State／Query Cache／可控照片預覽。其他分頁依 FR-002-AC07 確認，已保存的外部副本不在可清除範圍。 | 補足本機 Cache、跨分頁與返回頁面的行為，未宣稱能撤回外部副本。 |
| FR-008-AC01 | 下架成功後，新的搜尋與詳情／履歷／照片請求不得向訪客或其他會員提供該車資料；直接網址同樣受限制。 | 下架狀態提交完成後才進行的受控讀取／授權判定，不得向非 Owner 提供該車詳情、履歷或照片，公開列表的新查詢須排除該車；直接 URL、衍生圖與如有支援的條件／Range 請求同樣適用。 | 把下架保證限定於狀態提交後的新授權判定，涵蓋直接 URL 與可控服務。 |
| FR-008-AC04 | 已下載的照片、截圖或瀏覽者既有副本無法撤回；產品不得承諾下架能收回既有副本。既有公開頁面下次取得資料時應更新狀態。 | 不保證撤回已下載檔、截圖、先前已顯示畫面、不遵循指示的外部 Cache 或下架前已通過授權的在途傳輸；已開啟的公開頁面下次重新取資料或恢復焦點時檢查狀態，得知下架後移除內容。 | 明確排除已下載、Browser 既有畫面、外部 Cache 與已授權在途傳輸。 |
| FR-009-AC02 | 空白查詢等同全部已上架車；關鍵字前後 trim，建議最多 50 字元；品牌或車型符合即可返回。 | 關鍵字 trim 後空白等同全部已上架車，最多 50 字元；整段輸入在品牌或型號任一欄位包含即可符合，不分英文大小寫，不暗中加入 VIN 或描述搜尋。 | 明確單一字串包含搜尋、固定 50 字元與英文大小寫語意。 |
| FR-009-AC03 | 建議每頁 12 筆，以最近上架優先並有穩定的同值排序；換頁維持搜尋條件。切換搜尋回到第一頁；超出最後頁顯示空結果而非錯誤。 | 每頁 12 筆，依最近一次由未上架轉為已上架的時間新到舊，同值再用穩定唯一識別排序；重複對已上架車上架、編輯或更正不刷新上架時間。換頁維持條件，改條件回第一頁，超出最後頁顯示空結果；併發上下架時不承諾跨頁快照完全不變。 | 確立候選每頁 12 筆、再次上架時間、重複上架不洗排序與固定同值排序。 |
| FR-010-AC02 | 每筆紀錄顯示維修日期、里程、描述、系統申報時間與「車主自行申報・未經機構驗證」；建議依維修日期新到舊排列，同日以申報時間排序。 | 每筆有效紀錄顯示維修日期、里程、描述、申報時間及「車主自行申報・未經機構驗證」；依有效維修日新到舊，同日依里程大到小，再以申報時間／穩定識別排序。此順序只是顯示，不能把同日申報時間當成維修先後證據。 | 保留來源顯示；排序改依有效版本的維修日／里程，不以補登時間推斷發生順序。 |

### 3.4 新增AC

| 新ID | 驗收內容 | 新增原因 |
| --- | --- | --- |
| FR-001-AC05 | 註冊成功僅引導手動登入，不能直接讀取車庫；註冊頁明示只供合成資料展示。 | 新增註冊後手動登入的可驗收行為，對應 OQ-01。 |
| FR-002-AC05 | 有效活動限定為經定義且成功授權的業務 Request；照片、靜態資產、自動身分確認、背景輪詢與遭拒請求不延長閒置。以受控時間測試 29:59／30:00 與 7:59:59／8:00:00 邊界；具體活動清單在 API Contract 明列。 | 新增閒置活動定義與背景輪詢不可延長期限。 |
| FR-002-AC06 | 每次成功登入使用新的 Session ID，替換並撤銷該 Browser 的舊本次 Session；舊 ID／晚到回應不能恢復它。不同裝置的獨立 Session 不因此失效。 | 新增成功登入時 Session 更新與舊本次 Session 失效，避免固定／復活。 |
| FR-002-AC07 | 同 Origin 分頁在登入／登出通知、重新取得焦點或恢復頁面時重新確認目前身分；不得沿用先前帳號的私有快取或接受舊帳號請求結果。背景／凍結分頁恢復時先遮蔽私有內容再驗證，不承諾作業系統凍結時同步。 | 新增跨分頁恢復時重新驗證與舊請求結果隔離。 |
| FR-002-AC08 | 登入與註冊也有 CSRF 防護；缺失／錯誤 Token 或不受信任 Origin 的 Browser 操作不得建立／替換有效登入。正常同 Origin 流程及符合 Contract 的獨立 HTTP Client 可成功。 | 新增登入 CSRF 驗收；HttpOnly 不代表不需 CSRF。 |
| FR-003-AC04 | 兩分頁共用同一 Session 時，A 登出後 B 的舊憑證遭拒；在正常可執行分頁的展示測試中，事件送達後最遲 5 秒清除私有 UI。另一 Browser／裝置的獨立 Session 仍可用；同 Browser 分頁不算獨立登入。 | 新增共用 Cookie 的分頁都受影響、其他獨立 Session 不受影響。 |
| FR-003-AC05 | 登出／過期後晚到的查詢或續期回應，不得重新填入舊私有資料或重建失效 Session；登出不能以普通 GET 觸發，且需通過 CSRF 驗證。 | 新增失效後晚到回應不可重建私有 UI 或 Session。 |
| FR-005-AC05 | 新增流程提示使用合成 VIN／合成車輛；公開只顯示末 6 碼，不宣稱 VIN 或 Owner 經車籍驗證。 | 新增合成 VIN／展示用途的文案與不得宣稱驗證。 |
| FR-006-AC05 | 已上架車不得保存無效售價；一般文字／價格編輯不得直接改寫任何原履歷、更正版本、來源或申報時間。 | 承接舊 AC03 的價格與不改寫履歷規則，不混入里程更正。 |
| FR-006-AC06 | 目前申報里程 C 必須在允許範圍且至少等於全部有效版本的最大里程 H；沒有有效紀錄時 H=0。已被更正取代的舊高值不得參與 H；與補登／更正同時發生時仍需保持 C≥H。 | 新增目前申報里程不低於有效履歷最大值，排除被更正舊版本。 |
| FR-006-AC07 | 降低 C 必須填理由、明確確認，並與前後值、Owner、Server 時間一起保存；有效歷史不符則拒絕且提示先更正。合法下修不會被已停用 AC03 阻擋；展示里程下修標記及摘要，不能悄悄抹除前值。 | 新增目前里程下修的理由、確認與可追查異動，不再一律拒絕。 |
| FR-008-AC05 | 從第一次交付即對車輛資料／照片設 no-store，App／受控 Proxy／CDN／Service Worker 不保留可繞過驗證的副本；下架後測試舊直接 URL、帶舊 ETag 的條件請求及新 Browser，均不能取得內容或有效 304。不能用無需重新授權的公開物件 URL 或未到期 Signed URL 滿足本條。 | 新增 no-store、直接／條件請求與儲存旁路測試。 |
| FR-010-AC05 | 每個維修事件僅目前有效末端計入履歷筆數／里程規則；被取代版本標示「已被更正，非目前有效值」，可依鏈查看原文、各版完整內容、理由及 Server 時間，不把更正當成多次實際維修。非 Owner 只能在車輛上架時讀取這些內容。 | 新增有效紀錄與更正鏈的公開／Owner 展示及去重計數。 |
| FR-010-AC06 | 首頁／註冊／Marketplace／詳情及車輛管理顯示合成資料與不供真實交易提示；無購買、付款、聯絡賣家、認證車主或真實車況保證文案／入口。 | 新增展示用途及禁止誤導交易／認證文案。 |
| FR-010-AC07 | 若目前申報里程曾下修，詳情顯示可展開的更正摘要（前後值、理由與申報時間），不含帳號 Email；讀取依同一車輛公開規則。紀錄里程更正與目前值更正分開標示。 | 新增目前里程下修的可見更正摘要。 |
| FR-011-AC06 | 允許任意順序補登 1900-01-01 至今日的事件，包括早於車輛建立日／低於 C；驗證 m≤C、嚴格較早日期最大有效里程≤m≤嚴格較晚日期最小有效里程。缺少一側則無該側限制；同日不推定先後，但整日區間需與前後日期相容。 | 新增允許較早日期／較低里程的補登，依有效歷史與目前值驗證。 |
| FR-011-AC07 | 保存新事件時不修改 C；若 m>C，明確提示先更新目前申報里程而非偷偷提高或裁切 m。保存與當前有效歷史／C 的檢查必須一致；與補登、更正或目前里程更新併發時不能提交矛盾結果。 | 新增履歷不自動改目前值，並要求與當前版本的併發一致性。 |
| FR-011-AC08 | 原始版本不能直接編輯／刪除；更正需走 FR-013 的明確關聯，不能靠描述寫「前筆有誤」來排除原值。普通補登仍代表新事件，不會自動取代任何紀錄。 | 保留原文不可改刪，改用 FR-013 明確關聯更正。 |
| FR-012-AC05 | Server 拒絕長／寬不在 1–6,000 pixels 或總像素超過 12,000,000 的影像；拒絕動畫／多頁、截斷、損毀或解碼資源超限，不只看壓縮後 5 MiB。第 5.2 節的工作預算需在選定部署資源上驗證。 | 新增影像尺寸、像素、動畫／多頁、資源超限驗收。 |
| FR-012-AC06 | 先依方向資訊正確轉正，再重編碼為允許的靜態格式，移除 EXIF／GPS／XMP／IPTC 與非必要文字 Metadata；輸出檔亦不超過 5 MiB。以含 GPS／拍攝資訊樣本檢查處理後檔案；原檔不可對外讀取，不承諾自動移除畫面中的車牌／人臉。 | 新增重編碼、方向處理與 EXIF／GPS／XMP／IPTC 移除。 |
| FR-012-AC07 | 照片及所有如有提供的衍生圖透過可檢查當前車輛狀態的路徑交付，從首次回應設 no-store；不能以儲存桶／原始檔／未到期公開連結繞過。替換後舊主照片 URL 不再由受控服務提供；失敗時仍保留原主照片。 | 新增受控讀取、舊 URL、衍生圖與原檔不可旁路的要求。 |
| FR-013-AC01 | 只有 Owner 可更正同一車輛的目前有效紀錄；理由必填；系統決定申報者、Server 時間、來源及指向關係，不能指向另一車或任意偽造根事件。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |
| FR-013-AC02 | 提交新增完整替代內容，保留所有舊版日期／里程／描述／來源／申報時間，不直接 UPDATE 原文或 DELETE 歷史；每個事件僅一個有效末端。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |
| FR-013-AC03 | 以「排除被更正事件舊有效版，加入替代版」後的整體有效集合驗證日期／里程與 C；舊錯誤高值退出 H 及前後界線，不永久阻擋合理補登；不能忽略其他仍有效的高值。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |
| FR-013-AC04 | 兩分頁同時更正同一末端，最多一方成功；另一方收到衝突並重新載入。不能產生分叉、循環、自我指向或一個版本被多次直接取代。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |
| FR-013-AC05 | 更正不自動上／下調 C；先更正有效高值，再依法降低 C 的流程可完成。高於 C 的合法更正須先明確更新 C，不用隱含連動掩蓋目前值變更。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |
| FR-013-AC06 | Owner 及符合公開權限的訪客能展開原文、關聯、更正理由與各版本來源，主時間線只計一次有效維修事件；鏈也受下架權限限制。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |
| FR-013-AC07 | 若更正仍有誤，可針對目前末端再追加更正；不可回頭直接取代非末端舊版。MVP 不含批次更正、分叉合併、審批、刪除、撤回事件或跨車重掛。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |
| FR-013-AC08 | 失敗時新版本與有效末端切換均不生效；逾時先查明結果，不能把重試變成第二次維修。對鏈的限制仍須在重送及併發時成立。 | FR-013單鏈關聯更正的必要可驗收行為，對應D-05／06。 |

### 3.5 Business Rules／NFR變更索引

以下保留前版原文並對照現行條款；完整新文在PRD第5／6節。這些是候選要求修訂，不是測試證據。

| ID | v0.1原文 | v0.2變更／理由 |
| --- | --- | --- |
| BR-01 | 登入會員可新增自己的車；Owner 由驗證後的身分決定。只有該 Owner 可編輯、上架、下架、上傳／替換照片、申報紀錄；其他會員沒有管理權。 | 同Owner管理規則延伸更正／C調整，FR-013。 |
| BR-02 | Buyer／Seller 是使用情境，不是兩種互斥帳號。MVP 沒有 Admin、Service、Insurance 特權，也不提供修改 Owner 或過戶。 | 角色與移轉邊界納入合成展示候選，不新增特權。 |
| BR-03 | 訪客可看已上架列表、搜尋、詳情、主照片及有標示的維修履歷；未上架車僅 Owner 可看。其他已登入會員的公開閱讀權與訪客相同。 | 明確下架保證只覆蓋受控新判定；外部副本不可追回，D-03。 |
| BR-04 | 車輛只有「未上架」「已上架」兩種產品狀態。新增預設未上架；上架需完整基本資料、有效售價與照片。下架不刪資料、保留售價，不代表已成交。 | 補足上架時間與重複操作，防止更正洗排序。 |
| BR-05 | VIN 正規化後全平台唯一，不依 Owner 或上架狀態分開計算。不得僅做「先查再新增」而忽略併發重複。VIN 建立後一般編輯不可更改；填錯的處理待決。 | 僅合成VIN及誤填處理，保留唯一性目的。 |
| BR-06 | 售價使用 TWD 正整數；里程使用 km 非負整數；拒絕負值、小數、NaN／Infinity、超出界線或格式錯誤的輸入。Frontend 與 Backend 規則一致。 | 固定沿用數值界線，不再未定幣別。 |
| BR-07 | 編輯的目前里程不可低於先前值或任何既有履歷里程。建議新增紀錄里程至少等於目前里程，成功後同步更新目前里程。 | 重大規則變更：C分離、可有理由下修、有效H；舊相反AC已停用。 |
| BR-08 | 維修日期是申報內容；申報時間是 Server 產生且不可由使用者指定。顯示與日期界線採 Asia/Taipei。建議紀錄只能依維修日期非遞減追加且不可填未來日期。 | 重大規則變更：允許補登，事件與申報時間分離；舊相反AC已停用。 |
| BR-09 | 車主提交後不能修改或刪除歷史紀錄；可用一般新紀錄補充／更正，舊內容保留。不可將此限制描述為 Blockchain 級不可竄改；平台仍管理資料。 | 重大規則變更：明確單鏈版本，代替自由文字；舊相反AC已停用。 |
| BR-10 | MVP 所有紀錄固定為「車主自行申報・未經機構驗證」。來源由系統決定，在新增提示與每筆公開履歷明顯顯示。無紀錄不代表無事故；申報內容不保證真實或完整。 | 來源標示延伸所有原文／更正版本。 |
| BR-11 | 完整 VIN 只給 Owner；公開末 6 碼，不以完整 VIN 提供公開搜尋。會員 Email 不公開、不作聯絡賣家功能。 | 公開欄位與搜尋／無聯絡功能候選明確化。 |
| BR-12 | 每車 1 張主照片；不接受維修紀錄附件。上架需照片，替換失敗保留舊圖；下架控制後續讀取，不保證撤回已下載副本。 | 補足處理安全及下架Cache邊界。 |
| BR-13 | 註冊只代表建立平台帳號；沒有 Email 驗證或車籍查驗時，不顯示「已驗證 Email／車主」。登入錯誤不區分帳號不存在與密碼錯誤。 | 帳密／手動登入／合成展示明確化。 |
| BR-14 | 建議本次登出立即撤銷本次登入，Server 執行過期控制；其他裝置不一起登出。資料異動必須等保存成功才顯示成功。 | Session期限／CSRF／共用分頁明確化。 |
| NFR-SEC-01 | 密碼只以具 Salt 的專用 Password Hash 保存，不存明文或可逆密碼；回應、Repository、日誌不含密碼、Session 秘密、私鑰或 Production Secrets。具體演算法與套件待設計。 | 保留秘密不外洩，擴及CSRF秘密。 |
| NFR-SEC-02 | 所有受保護的讀寫由 Backend 驗證身分；每次車輛／照片／紀錄寫入驗證 Owner。以 A／B 兩帳號、缺失／過期／偽造憑證直接測 API，越權不得讀取私有資料或改變資料。 | 權限案例含更正與C調整。 |
| NFR-SEC-03 | 登入憑證不得放 URL、日誌或可由 JavaScript 直接讀取的持久化儲存；建議採 Server Session + HttpOnly／Secure／明確 SameSite Cookie，並另設 CSRF 防護。此方案仍待 OQ-02；HttpOnly 不代替 CSRF 防護。 | 以本輪Server Session候選替代未決機制，分清Session與CSRF Token。 |
| NFR-SEC-04 | 正式環境對外使用 HTTPS，HTTP 導向 HTTPS；不公開 PostgreSQL 連線服務與秘密。若採跨 Origin，僅允許明確需要的 Origins；具體拓樸待 OQ-12。 | 同Origin仍為候選，不假稱部署已確定。 |
| NFR-SEC-05 | 登入／註冊具可驗證的請求限制；建議同一來源登入最多 20 次／5 分鐘、註冊 10 次／小時，超限顯示稍後重試，不永久鎖定帳號。門檻、來源辨識與共用網路影響待 OQ-01／Step 2。 | 保留限流評估值，實際來源／計數需在設計定版。 |
| NFR-SEC-06 | 描述以純文字安全呈現；資料查詢不拼接使用者輸入形成 SQL；照片須驗證內容與大小，不執行上傳內容；下架照片沒有繞過授權的永久公開讀取入口。 | 保留輸入安全，明列原檔／URL非權限。 |
| NFR-DAT-01 | 正規化 Email／VIN 的先後與併發重複建立均不得產生重複身分或車輛；Owner、來源、申報時間不可由使用者覆寫。 | 明列合成VIN且保留併發唯一性。 |
| NFR-DAT-02 | 新增維修紀錄與更新里程是同一個成功／失敗單位；以失敗及兩個同時提交案例驗證，不留下半套資料或里程倒退。 | 重大規則改變：不再自動更新C，改驗證有效集合／單末端；相反AC已停用。 |
| NFR-DAT-03 | 車輛更新與上架狀態變更須避免以舊資料默默蓋過新版本；任何異動後仍符合售價、照片及里程規則。衝突處理機制待設計。 | 併發保護延伸C／更正，不洗上架時間。 |
| NFR-DAT-04 | 日期、里程、價格的輸入、保存與顯示單位一致；價格不得有未定義的浮點截斷；公開讀取、照片關聯與 Owner 關聯一致。 | 保留單位／精度，區分事件與申報日期。 |
| NFR-REL-01 | 模擬資料庫或檔案服務失敗時，操作不顯示成功、舊資料不損毀；查詢失敗與空結果可以區分，頁面有重試入口。照片替換需驗證舊圖保留案例。 | 失敗保護延伸更正有效末端切換。 |
| NFR-REL-02 | Mutation 逾時時顯示「結果尚未確認」，引導重新取得資料再決定重試；不得自動盲目重送建立／履歷請求。是否實作一般 Idempotency Key 留為 Should Have，不保證所有手動重送零重複。 | 通用重送可延後，但單末端不能因重送分叉。 |
| NFR-REL-03 | 一次正常 Container 重啟與移除／重建後，已提交帳號、車輛、履歷與照片仍可取得；不把清除資料 Volume 的破壞操作當成一般重建。提供可操作的資料與照片備份／還原程序，至少以測試資料完成一次還原演練。無高可用或 SLA 承諾。 | 備份包含版本／異動；Session安全失效與業務資料持久化分開。 |
| NFR-PERF-01 | 建議測試資料為 100 台車、共 500 筆維修紀錄；在記錄 CPU／RAM、服務配置與測試方式的指定環境，暖機後以 3 個同時讀取者完成至少 30 次列表／搜尋／詳情請求，非照片、非登入查詢的 Server 回應 P95 目標不超過 2 秒。這是待實測調整的展示基線，並非容量估計或網際網路 SLA；未達時需保留量測證據並重新確認，不可宣稱已達標。 | 保留量測目的及工作負載；明確撤回v0.1的P95≤2秒候選門檻，DPQ-03再定。 |
| NFR-PERF-02 | Marketplace 使用有界的分頁回應，不先把全部車輛送到 Browser 才搜尋。履歷可採分批或明確有界載入，必須能繼續看到完整紀錄；不能默默截斷成「全部」。具體載入大小待設計。 | 有界讀取延伸版本鏈，有效事件不重複計數。 |
| NFR-UX-01 | 至少在目前穩定版 Chromium 桌面 1280px 與手機寬度 390px 驗證主要流程；沒有擋住表單的橫向溢出。輸入有 Label，錯誤不只靠顏色，主要操作可用鍵盤完成。這是基本可用性驗收，不宣稱完整無障礙認證。 | 保留展示可用性條件，不宣稱正式無障礙認證。 |
| NFR-MNT-01 | 每個 Must Have 可對應到需求 ID、設計項目與測試證據；核心規則、權限、登入失效、唯一性與失敗案例有可重複執行的自動化測試，展示流程另做端到端驗收。所有 UI 文案不必逐一建立機械式單元測試。 | 保留需求追蹤，加入版本／CSRF／Cache／時間測試與停用ID。 |
| NFR-MNT-02 | 明確區分 UI、API、業務規則與資料存取責任；有單一採用的依賴鎖定流程、無秘密的環境變數範例與啟動文件。Backend 規則不依賴某一個 React 頁面才能成立。實際目錄留待設計。 | 保留分層／依賴文件，區分持久化異動與Log。 |
| NFR-DEP-01 | Frontend、Python Backend、PostgreSQL 以 Docker 建置／啟動／連線，有可重現文件；在另一個乾淨的測試環境按文件完成。正式 Frontend 不以 Vite Dev／Preview Server 作為正式服務。 | 同Origin優先但仍獨立服務，正式Server未選。 |
| NFR-DEP-02 | 實際自訂網域能解析到部署入口，Browser 憑證有效、沒有 Mixed Content；可完成登入、公開查詢與照片操作。記錄 DNS、憑證續期、服務重新啟動與版本更新方式；開發者能解釋每一步。無本階段的購買或部署授權。 | 補上CSRF／照片交付驗收，重申未部署／購買。 |
| NFR-DEP-03 | 可在不載入 React 的情況下獨立呼叫 Backend API；Frontend 靜態服務與 Backend 業務服務有明確界線。資料與照片持久化生命週期有文件。 | API獨立呼叫須符合Cookie／CSRF，不意味可略過驗證。 |
| NFR-OBS-01 | 每次 API 請求可從日誌找到時間、Request ID、操作類別、結果與耗時；錯誤回饋有可對照的識別碼。日誌不記密碼、登入憑證、完整敏感 Payload 或完整 VIN。 | 保留請求追查，秘密排除含CSRF；不可拿日誌代替持久化版本。 |
| NFR-OBS-02 | 能觀察服務是否可接收請求及關鍵依賴是否可用；至少演示一次正常狀態、一次資料庫不可用及錯誤追查。健康資訊不揭露連線密碼或內部設定；日誌輪替／保留方式待設計，不要求另建監控平台。 | 觀察案例延伸Session／更正／解碼超限。 |

新增規則／品質ID（沒有取代重用舊ID）：

| ID | 新增原因 |
| --- | --- |
| BR-15 | 不同日期非遞減、同日區間及補登／更正共同不變量。 |
| BR-16 | C可有理由下修且持久追蹤。 |
| BR-17 | 合成展示定位與禁止交易／認證誤導。 |
| NFR-SEC-07 | 全部Mutation的CSRF驗收。 |
| NFR-SEC-08 | 首次交付no-store、受控撤回與URL／Cache旁路測試。 |
| NFR-SEC-09 | 尺寸／解碼／Metadata與工作預算。 |
| NFR-DAT-05 | 原文／更正／C異動持久保存，不靠輪替Log。 |
| NFR-UX-02 | 合成資料、更正有效性與C下修文案。 |

SH-03原文「額外照片相簿與照片方向／隱私處理」拆分：相簿仍Should，方向與Metadata成FR-012-AC06 Must。SH-04原文「明確關聯原紀錄的更正流程」提升至FR-013 Must，舊Should列保留歷史標記。第7節不再同時承諾／延期同一功能。

## 4. Remaining Open Questions

產品答案與安全CP進度見§1／6；安全CP已接受的部分不再列為尚未選方案。其餘需設計／部署的問題及Gate見[PRD第9節](PRD.md#9-remaining-open-questions-與風險)：

- SDQ-01：CP-01～05已收斂Store／Secret／TTL／Cookie／來源／活動／限流；CP-06有條件接受。仍需Step 2D逐路由契約／未知結果與Browser／Proxy／多Worker實測，見§6。
- SDQ-02：事件版本／有效末端／C異動關聯與併發一致性。
- SDQ-03：檔案私有交付、處理隔離／資源上限、替換／清理與Cache設定。
- SDQ-04：公開／Owner投影、完整版本讀取與分頁、條件請求及頁面重驗證。
- SDQ-05：API錯誤／輸入Contract與時間／併發／CSRF／Cache驗證計畫。
- SDQ-06：備份／還原、持久化稽核與運行日誌、健康檢查／秘密。
- SDQ-07：候選框架與版本相容性、依賴鎖定及獨立服務邊界。
- DPQ-01～05：主機／預算／排程、網域DNS／TLS、實測門檻／影像預算、容量備份及展示存取／結束日。

本輪不替使用者決定供應商、費用、實際Domain或完整部署拓樸。數值調整需回寫PRD／Decision Log，不能用「已有候選」掩蓋尚未量測。

## 5. Design Readiness（Step 1.5歷史評估；現行進度見§6.7）

**需求內容已能支援ERD、API Contract、Authentication與系統架構設計；流程上仍需使用者審閱候選並下達下一階段指示。**

- ERD可用有效事件、版本鏈、C／歷史語意及唯一性規則作輸入；本輪未建立Table或Column。
- API可依Owner／公開讀取、搜尋、補登、更正、衝突與Session／CSRF行為設計；本輪未定義Endpoint。
- Authentication已有Session期限、撤銷、分頁與CSRF驗收，可在SDQ-01比較安全實現。
- 架構可比較同Origin獨立服務、私有檔案交付與持久化；實際主機／費用／TLS／效能門檻仍不能凍結。

主要殘留風險：關聯更正的中等成本、多筆錯誤需逐筆相容更正、C下修仍是自行申報而非真實防詐、外部副本不可撤回、Session在途工作不能回溯取消，以及影像資源隔離須依實際主機驗證。

本輪只做文件一致性與ID檢查；沒有執行功能、安全或效能測試，也沒有宣稱功能已完成。

**Step 1.5到此停止，不自動進入Step 2。**

## 6. Step 2C.5 Design Reconciliation

### 6.1 決策效力與來源

日期2026-11-04；來源是使用者對AUTH_DESIGN v0.1 CP-01～06的本輪審查。**CP-01／02／03／05接受，CP-04接受方向但須實測，CP-06有條件接受**。只同步既有設計，不宣稱功能、Schema、Migration或安全驗收完成。

現行閱讀優先序：本節審查結論＋PRD v0.2.1需求約束→System Architecture v0.2／Database Design v0.2已整合模型→AUTH_DESIGN v0.1流程來源。AUTH原檔不變；其§0／12／AQ中「尚待回填／待審查、Schema尚無欄位」是2026-11-03歷史狀態，現在由本節確認已接受並完成文件回填，不把它當作目前模型仍缺欄位。未接受的部署參數與CP-06風險不能藉此優先序自動結案。

| CP | 審查結果／同步內容 | 仍未宣稱 |
| --- | --- | --- |
| CP-01 | Session模型加獨立32-byte csrf_secret，NN／長度CHECK、無共用Default／Index；Synchronizer發放／Header／來源及User身分分工。 | 已建立欄位、Native CHECK可證明隨機獨立性、CSRF能防Cookie失竊／XSS。 |
| CP-02 | PG Fixed Window三Scope：login20／300秒、register10／3600秒、csrf_context60／300秒；UTC Epoch、共享HMAC／原子Gate、429。 | 精確Sliding、無Burst／NAT誤傷、已測多Worker吞吐。 |
| CP-03 | preauth無User、last=created、絕對15分鐘／不滑動；authenticated 30分鐘閒置／絕對8小時；新列Rotation，禁止原列升級。 | 普通CHECK可保證所有狀態轉移；欄位權限與Service尚未配置。 |
| CP-04 | 驗證器normalized→PG lower作唯一canonical，Argon2id／原Password政策依AUTH §3；不另用casefold。 | 所有Unicode大小寫／同形字等價、Library／PG Locale或Hash成本已實測。 |
| CP-05 | 成功活動白名單、鎖後新Clock條件Touch、Logout失效列專用例外、普通API無Set-Cookie、Commit與Touch失敗分開。 | Touch能延長absolute／復活列、登出能取消先授權工作、已Commit失敗可盲重送。 |
| CP-06 | Epoch／BroadcastChannel／焦點重驗、候選Web Locks及Cookie回應限制寫回；保留DR-01／I-AUTH-01。 | Browser Cookie CAS、所有非受控請求有序、Timeout意味沒成功、競態完全解決。 |

### 6.2 Change Summary與需求影響追蹤

保留原章節與ID；局部替換過時的Auth說明／狀態，沒有大規模重寫業務內容。§2／3的Step 1.5歷史原文／AC變更記錄保留，§5標為該輪歷史評估。

| 文件 | 實際修改章節／內容 | 修改前→修改後／理由 |
| --- | --- | --- |
| PRD.md v0.2.1 | Metadata／§0、FR-002描述、BR-13／14、§5.3、SEC-01／03／05／07、OQ-01／02、SDQ-01／05、§10.3／版本紀錄。 | Auth細節待選→回填已接受CP及條件風險。SEC-01「不得回CSRF秘密」與本來允許Token供JS的§5.3／SEC-03作一致澄清：SID只允指定Set-Cookie，CSRF只允受控Token Body介面，普通Body／Log不能外洩；不更動AC原文。 |
| DECISIONS.md v0.2 | Metadata／D-01／02／SDQ-01與本§6。 | 待審方案→記錄使用者CP結果、原因、模型Delta、Issues／Risk／Handoff；原候選歷史不刪。 |
| SYSTEM_ARCHITECTURE.md v0.2 | Metadata／§0狀態、TD-05／06、§3邏輯Store標籤、§5.2登入圖／說明、§6.2／6.5、R-09／§10.1、SDQ-01／05、§14.1／版本。 | 尚待Auth選擇→PG Token Hash／Secret／三Scope Gate／TTL／Touch／Cookie等已選；服務數與部署候選不變，仍非已部署。 |
| DATABASE_DESIGN.md v0.2 | Metadata／摘要、ERD／§3、§4.1／4.2／4.8、§5權限說明、§7.4／8、Q-06界線＋新Q-10、§11.2、DBQ-03～06／§12、§13品質Trace／§17。 | 缺CSRF欄位／scope／preauth約束→模型局部Delta；九個舊Query SQL不變，新增一個未執行Gate教學例；查登入、Touch、Logout分開。其餘業務模型不變。 |
| AUTH_DESIGN.md v0.1 | **未修改**。 | 保留已審來源；歷史狀態按§6.1解讀，設計缺口記Issue，不在原檔暗改。 |

下表追蹤所有受影響的FR／BR／NFR／SDQ；「影響」包括其Auth入口／契約，**不代表改動了該ID的業務規則或AC**。

| 來源／原因 | FR／BR | NFR／SDQ |
| --- | --- | --- |
| CP-01／03：綁Context的CSRF、preauth型別／TTL與新列Rotation。 | FR-001～003；BR-13／14。 | SEC-02／03／07、DAT-01；SDQ-01／05／07。 |
| CP-01／05：所有管理Mutation統一Identity／CSRF，既有Owner／歷史／照片規則不變。 | FR-005～008、011～013；BR-01／07～10／12／14～16只加入口與契約對照，不改里程／鏈／圖規則。 | SEC-02／06／07、DAT-02／03／05、REL-01／02；SDQ-01～05。 |
| CP-04、AUTH §3：單一canonical Email／Argon2id及版本／Unicode驗證。 | FR-001／002；BR-13，原12～128／手動登入保留。 | SEC-01、DAT-01／04、MNT-01／02；SDQ-01／05／07。 |
| CP-02：共享固定窗／Bootstrap Gate／可信來源，保留Burst／NAT風險。 | FR-001／002及其安全Bootstrap；BR-13／14。 | SEC-05、REL-03、OBS-01／02；SDQ-01／05／06／07。 |
| CP-05：成功活動白名單／Commit後Touch，Public讀取不保活。 | FR-002～013的活動分類；BR-03／04／14，Public FR-009／010仍匿名可讀、不Touch。 | SEC-02／03、REL-01～03、DAT-03、MNT-01；SDQ-01／02／04～06。 |
| CP-06：分頁與Cookie邊界、來源／Native Client／Timeout未確認。 | FR-002／003／004／008／010／012；BR-03／11／12／14。 | SEC-03／04／07／08、REL-01／02、DEP-03、MNT-01；SDQ-01／03～07、DPQ-02／04。 |

NFR表省略共同前綴NFR-。13項Must Have與全部75個AC定義（71有效／4停用）原文及狀態不變；FR-013、BR-07／08／09／15／16與未上架隱私要求不被本輪放寬。

### 6.3 Design Consistency Report（含指定A～F檢查）

| 檢查 | 結論分類 | 結果／責任邊界 |
| --- | --- | --- |
| A. Touch vs Q-06／鎖／到期 | **已解決文件分工；需實作測試** | Q-06只作新的有效authenticated認證，不Touch、不可拿其舊Snapshot續期。業務交易後另鎖Session，鎖後Clock重驗、條件UPDATE；Logout例外另讀、不放寬Q-06。鎖順序維持2B，無Session／Vehicle交錯長鎖。 |
| B. 同表兩kind | **已解決模型缺項；需實作測試** | 加Secret／preauth15分鐘與last=created CHECK；User NULL／非NULL、Hash PK不變。CHECK不防任意UPDATE提升；新列Rotation、明確kind與欄位更新權限共同防錯，Runtime不可為Table Owner／Superuser或繼承廣權。 |
| C. Rotation／Logout／Set-Cookie | **有條件接受＋仍需設計** | Server鎖舊Context重驗、原子新列／撤銷，普通Response無Cookie可減少風險；Auth Response晚到仍可能影響Cookie。DR-01／I-AUTH-01沒有被資料模型或Web Locks自動消除。 |
| D. Bootstrap／來源 | **設計相容；需Browser實測** | app內same-origin fetch可帶Cookie及正常Origin或Referer；Get CSRF Context是受控安全初始化，不改登入／業務。Privacy／Referrer移除、Sec-Fetch-Site=none／跨Site／同Site不同Origin、Port／TLS／BFCache等須AT-07／19；不允全缺來源靜默放行。 |
| E. Fixed Window多Worker | **原生機制可支持；實效未測** | PK＋單Statement ON CONFLICT DO UPDATE序列化同Key；Q-10前N次true後false，Counter飽和N＋1，Gate獨立Commit。Window／可信N／HMAC／Proxy及所有Worker同Policy是APP責任，不由PK證明；AT-13實測。 |
| F. 2D不能只留高階的事項 | **仍需設計Contract** | 逐路由安全／Activity矩陣、Auth／CSRF錯誤順序、Cookie唯一寫入點、Mutation版本與Unknown／Retry／Commit後Touch Metadata、Private圖／舊版／VIN投影；詳§6.5。 |

**已解決**：四份上游不再把csrf_secret／scope／TTL／Cookie／來源／Touch／Fixed Window當尚未選方案。跨文件關鍵數值一致；未建立任何Schema。

**有條件接受**：CP-04僅接受canonical方向，Unicode／Locale／版本須證據；CP-06僅接受有限防線，不能寫成「Cookie競態已解決」。

**仍需設計**：I-AUTH-01的Recovery／確認完成條件，2D路由Policy及回應／版本／錯誤精確契約、必要逾時／重試值；不是重開是否採Session／CSRF／Fixed Window。

**需實作測試**：Secret獨立生成、權限／CHECK、真實Clock／鎖與Counter、Cookie Header／Origin、Chromium Tabs／凍結／網路重排、Restore；對應AUTH AT-01～20與下表Risk。

#### I-AUTH-01：未知Auth結果與Logout Recovery的銜接未完整定義

位置：AUTH_DESIGN.md §6.4、§6.6、AI-04、AQ-06。§6.4允許未知／已清理Context先Bootstrap再Logout；§6.6又要求未收斂的Auth Request暫停其他Cookie變更。五個介面尚未精確規定「何時確定前一Login已結束，能安全從暫停進入Bootstrap／Logout」。

具體風險：Login可能已Commit新Session但Set-Cookie回應延後；若另一流程把Bootstrap後的preauth登出204當成先前Login也已撤銷，就可能在晚到Cookie後再次呈現登入。它不一定是「清revoked復活舊列」，但仍可能不符合既有晚到登入／Cookie驗收。受控Web Locks正常路徑可減少觸發，不能證明任意Timeout／Crash都安全。

這是**設計缺口／DR-01，非已證實的程式漏洞**。本輪不修改AUTH、不新增輪替關聯欄位或降AC。Step 2D須定義未確認狀態、禁止操作、讀回／完成證據及Cookie寫入順序；若需Server操作識別／輪替關聯，再提Delta審查。單次me匿名、忽略JSON、Abort與重取CSRF都不是「Server肯定沒成功」的證據。

此外AUTH的「待審CP／尚無欄位」為歷史狀態差異，依§6.1標示來源版本即可，不視為邏輯錯誤並回改原檔。

#### I-AUTH-02：Response Body與Set-Cookie Header的文字範圍

AUTH_DESIGN §10.1「不回Session Token」若被解讀成所有HTTP Header禁令，會與其§4明確Set-Cookie範例矛盾。依既定機制合讀，應是禁止Body／其他通道返回raw SID，僅允指定Set-Cookie；CSRF Token則可在受控no-store Body發放，其他Session欄位不能整列序列化。本輪只明確化上游NFR-SEC-01並列出此文字Issue，**不修改AUTH原檔、不增加憑證交付通道**；Step 2D必須分列Body／Response Header契約。

### 6.4 Database Delta（相對Step 2B v0.1）

| 面向 | 原v0.1→已同步v0.2 | 保證／未來Migration |
| --- | --- | --- |
| 欄位 | auth_sessions新增csrf_secret BYTEA NN／32 bytes、無Default／Index；ERD及Dictionary同步。 | PG驗存在／長度，APP驗CSPRNG／獨立生命週期；既有Context需受控失效，不能共用Default補值。 |
| CHECK | scope擴login／register／csrf_context；preauth absolute=created＋15分鐘、last=created。 | kind／User條件、共同時間順序、authenticated absolute＋8小時等舊Constraint保留；Native CHECK不會隨Clock自動讓列消失。 |
| Keys／Index | Token Hash PK、User FK、Bucket Composite PK／Hash長度／expires>start、各Unique與I-01～07不變；無新表或Index。 | runtime權限需移除／避免Table-wide Session UPDATE，僅允last／revoked更新的防錯提案，非已執行GRANT。 |
| Email／Password | 無新欄；normalized→PG lower、Argon2id編碼存原欄。 | 記UTF-8／Locale／Collation／Library版本；Fixtures與既有canonical碰撞預檢，管理升版。 |
| Session SQL | Q-06及原九段Query SQL不變；補明只讀有效authenticated、無Secret輸出，Touch／Logout另有流程。 | 過期Logout查詢不可代替Q-06；Touch鎖後新Clock，不UPSERT／延absolute。 |
| Rate-limit SQL | 新Q-10文件教學例：可信Server參數＋原子UPSERT，LEAST(count,N)＋1，回admitted，無溢位前加法。 | 同Key多Worker序列化，Counter最多N＋1；先Commit Gate再往下，不可HTTPException Rollback掉計數。SQL未執行／測Plan。 |
| Migration範圍 | 未來加一欄、擴一個scope CHECK、補preauth條件／權限及Fixtures；八表與其他業務Schema不變。 | 暫停舊Writer／受控維護，失效既有技術Context後加NN／CHECK，檢查Revision與新Writer相容；本輪沒有Migration檔或DB。 |

### 6.5 Step 2D Handoff（必須寫進Contract，現在不定全部Endpoint）

| 類別 | Step 2D必須具體表達 |
| --- | --- |
| Authentication／Authorization | 每操作public／optional／required Identity；以Session User驗Owner而非Body user_id；一般Private不存在／非Owner同404，無登入401；已上架也不能給非Owner完整VIN／Email。沿Event／Version／Image到Vehicle驗歸屬。 |
| CSRF／來源 | 所有Mutation含五Auth行為的適用性（Bootstrap GET只技術初始化）；Context kind、X-CSRF-Token、Token發放／輪替、Origin／Referer／Fetch缺失政策、Native Client Jar流程；早於Body Parser的Guard與路由Policy不能只寫Depends即算。 |
| Cookie／Lifecycle | 只有必要Bootstrap、成功Login、確認Logout可Set／Clear；Name／Path／Flags／Max-Age、哪些錯誤絕不改Cookie；Login舊Context被消耗的衝突、I-AUTH-01未確認狀態與重新確認條件。Web Locks只候選，不當Server Auth。 |
| Error Handling | 定義401／403／404／409／422／429／503與413／415，Auth Context／Token／來源／Gate／格式的優先序；me的200匿名不可套用Private業務，DB故障503而非假匿名；Validation input／ctx／密碼／Token不可原樣回傳／Log。 |
| Session Touch | 逐操作白名單，Owner成功主動讀取／管理No-op與Public／背景區分；禁止自動Owner輪詢；成功條件、鎖後Clock、過期不Touch、Touch失敗但業務已Commit的Response Metadata／UI處理；無新Cookie。 |
| Request／Response | Password／Confirmation及Code Points、Email normalized→PG lower；型別／Extra欄位拒絕、公共／Owner投影、CSRF秘密介面例外與no-store、Auth小Body／檔案有界傳輸；不回Raw SID／Hash／Raw檔路徑。 |
| 版本／Concurrency | expected vehicle row_version與expected current Version ID的精確載體、成功／No-op／衝突回應；保留同車Lock→新Statement讀E→驗C≥H／跨日／同日→原子寫入，不能把Actor／source給Client覆寫。 |
| Private Image Access | 每次Primary判斷current／ready與Owner／is_listed，舊版／下修摘要同權限；條件／Range先授權；首次no-store，不公開Raw／Static旁路；下架只保證新判定、不追回副本。 |
| Rate-limit | 明定三Scope／N／固定Epoch窗口／可信IP、達Gate哪些錯誤仍計數、429／Retry-After、Burst／NAT說明；Counter與業務分交易，多Worker同Policy／Secret，不能用Rate UPSERT Touch Session。 |
| Timeout／Retry／Unknown Outcome | 明分尚未執行／已確認Rollback／已Commit但回應未知／Touch失敗；不把網路錯誤當未成功，不盲重送登入或Mutation；定義可讀回資料／關聯識別／使用者確認。有限DB整交易Retry重驗規則，不自動把舊末端改新末端；一般Idempotency仍Should Have，不暗升或假稱現已保證。 |

### 6.6 Remaining Risks與驗收Gate

| Risk／對應來源 | 尚未解決的風險／驗收ID | 處理階段與證據 |
| --- | --- | --- |
| DR-01／CP-06、I-AUTH-01 | Auth晚到Set-Cookie、未知Login／Logout Recovery及Epoch／Web Locks能力邊界。FR-002-AC06／07、FR-003-AC03／05、NFR-REL-02。 | Step 2D先定Recovery／確認條件；實作Chromium雙Tab／凍結／Timeout／重排AT-12。不能證明符合就阻擋規格凍結／相關安全驗收，不降低AC。 |
| DR-02／CP-01／06 | Bootstrap GET常無Origin，需Referer／Fetch政策與TLS／Host／Port相容；Privacy Extension／BFCache／跨Site／同Site不同Origin。FR-002-AC08、NFR-SEC-07、NFR-DEP-02／03。 | 2D精確Header錯誤／Native流程；實作＋部署AT-05～07／19，Caddy與Browser實際Header證據。來源全缺仍拒絕。 |
| DR-03／CP-01／05 | FastAPI可能先解析Body才跑一般Dependency；Guard／Parser／Header policy若只紙上正確仍有旁路／資源面。FR-002-AC08、FR-012-AC05／06、NFR-SEC-07／09。 | 2D集中逐路由Guard；鎖定框架版本、實作AT-06／14／20與大檔／錯Content-Type測試。 |
| DR-04／CP-04 | Unicode／Locale／Collation／版本變動造成canonical不一致／碰撞，KDF成本未校準。FR-001-AC01～03、FR-002-AC02、NFR-DAT-01、NFR-SEC-01。 | 實作前記PG Encoding／Locale／Library版本、Unicode及並發Fixtures AT-01～03；部署量測Hash成本，不宣稱完整Unicode等價。 |
| DR-05／CP-02 | 多Worker配置／可信XFF／HMAC／窗口／Gate交易邊界錯誤，Burst／NAT及分散來源殘餘風險。NFR-SEC-05、FR-001-AC03、FR-002-AC02。 | 2D定Policy／429；實作PG多連線／多Worker AT-13，部署測Proxy直連與偽造Header，不以PK或SQL範例當通過。 |
| DR-06／CP-05 | Commit後Touch失敗、等號到期／Lock等待／Logout競爭與回應不明。FR-002-AC04／05、FR-003-AC01／03／05、NFR-REL-01／02。 | 2D定成功事實＋續期／Unknown Metadata；實作受控Clock／雙連線／故障AT-09／11／15，Q-06不能被誤當續期。 |
| DR-07／CP-01／03／05 | 就地提升、錯誤角色權限、Secret共用、過期Cleanup延遲或Restore讓舊Cookie／CSRF復活。FR-002-AC03／04／06、FR-003-AC01／05、NFR-REL-03。 | Schema／權限實作與Migration預檢；AT-04／16／19、受控Restore與Token重放。管理者仍能修改DB，不宣稱絕對不可竄改。 |

有效Cookie被竊仍可重放、XSS同Origin代送、無MFA的Distributed Stuffing、PG單點等原有殘餘風險保留於AUTH TH-02／05／06／09；不是以合成展示用途免除保護。

### 6.7 同步驗證與停止點

本輪已完成文件靜態核對：只有四份上游Markdown變更、AUTH原SHA-256不變、75個AC定義／71有效／4停用原文一致、13個Must Have與里程／更正／未上架隱私未變；ERD／Dictionary欄位一致，Q-06與九個舊Query SQL保留、新Q-10僅教學例，沒有執行SQL或建立Schema。Mermaid未Renderer驗證，HTTP／PG／Concurrency／Browser測試皆未做。

結論：**已形成可審閱的Step 2D輸入基線，並非已完成Step 2D，也非所有設計風險已結案。** 先審閱本次差異；下一階段須收斂I-AUTH-01及§6.5的Contract缺口，之後以§6.6證據驗收。完成Step 2C.5即停止，不自動設計完整REST API或開始實作。



## 7. Step 3A — 使用者接受 CP-SCOPE-01～03（2026-11-05）

本節是最新Scope決策，補充§6而不改PRD／AC或AUTH歷史來源。使用者正式採用API_SCOPE_REVIEW.md的A方案；同步API_CONTRACT v0.2。本輪僅授權Runnable Foundation，不授權完整帳號／車輛系統或部署。

| 決策 | 接受內容／影響 | 保留Gate |
| --- | --- | --- |
| CP-SCOPE-01 | MVP A／現有八表；不新增auth_login_attempts；E06 Deferred、其他ID不重編；E01／E03不要求Attempt ID。B保留為Hardening歷史設計，不再阻擋任何開發。 | 指定未知Login的可靠取消未提供；不假稱B功能已存在。 |
| CP-SCOPE-02 | Server Session／CSRF／Rotation／Revocation不變；Login未知保持Uncertain，不盲Bootstrap／重送／假Logout。AUTH §6.4的Bootstrap說明遇到未收斂Login須服從此限制；原檔保持歷史來源。 | DR-01／I-AUTH-01及CP-06仍未完全解決；Epoch／Web Locks不取消Set-Cookie、me匿名不證明L結束。 |
| CP-SCOPE-03 | 13 Must Have、71有效AC／4停用原狀；必要證據依Scope Review §3／SR-T01～14；B取消測試另列Deferred，不作既有AC唯一證據。 | 舊SID復活、舊UI污染、CSRF或其他有效AC實測失敗仍Block相關驗收，不降低要求。 |

**Step 3A交付**：獨立web-app React／Vite／TS、FastAPI／SQLAlchemy／Pydantic、Compose本機PostgreSQL、Alembic三張Auth表、匿名E05與真實DB診斷。只缺Cookie時可直接匿名；可能有效Cookie因Lookup尚未接入而503 fail closed，不能冒用。§6的「完整Recovery未定即阻擋全部實作」由本節收斂為必要AC的驗收Gate；不表示安全驗收已通過。主機／網域／正式HTTPS／其餘業務與完整Auth不在本輪範圍。


## 參考與版本

- 安全／Cache／影像的官方資料與適用界線見PRD第5.2／5.3節；查閱日2026-11-02。照片與Session的專案數值是候選政策，非外部來源通用門檻。
- v0.1（2026-11-02）：建立本Decision Log、衝突索引、舊AC原文／替代與新增清單、BR／NFR變更及Readiness；對應PRD v0.2，等待使用者審閱。

- v0.2（2026-11-04）：依Step 2C.5審查同步安全CP，新增§6 Change Summary／Consistency Report／Database Delta／Handoff／Risks；AUTH來源不修改，既有AC與非Auth業務規則保留，未實作或測試。
