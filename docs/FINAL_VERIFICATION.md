# Vibicle 最終驗收對照

13 項 Must Have 的 71 項有效 AC 均已取得本機驗收證據。另列 T／SR 壓力、故障與平台子案例的剩餘驗證，公網部署仍待外部資源。

| Requirement ID | PRD 驗收條件 | 狀態／證據 |
| --- | --- | --- |
| FR-001-AC01 | 有效新資訊可完成註冊，之後可使用該憑證登入。 | Pass — Browser-Auth + test_registration_rotation_replay_logout_other_device |
| FR-001-AC02 | 不分大小寫或帶前後空白的同一 Email，不得建立第二個帳號；同時提交也不能重複建立。 | Pass — test_email_unique_and_wrong_credentials，NFC／Unicode 空白／兩連線 201＋409 |
| FR-001-AC03 | 不合規輸入不建立帳號；失敗訊息不回傳既有帳號資料；密碼不出現在回應或日誌。 | Pass — Native malformed registration 422，response 無原值，API／Caddy logs 無合成密碼與 CSRF canary |
| FR-001-AC04 | 註冊不宣稱 Email 已驗證、使用者是真實車主，或已取得機構資格。 | Pass — Browser-Auth 註冊頁與手動登入導引，E02 只回 registered／manual_login |
| FR-001-AC05 | 註冊成功僅引導手動登入，不能直接讀取車庫；註冊頁明示只供合成資料展示。 | Pass — Browser-Auth 與 test_email_unique_and_wrong_credentials，註冊後車庫 401 |
| FR-002-AC01 | 正確憑證登入後可查看車庫；有效期間內重新整理不需重複輸入密碼。 | Pass — Browser-Garage／Browser-MVP，重新整理後仍可讀自己的車輛 |
| FR-002-AC02 | 不存在的帳號與錯誤密碼使用同一類失敗訊息；登入失敗不建立已驗證狀態。 | Pass — test_email_unique_and_wrong_credentials，兩種失敗同 401 且無 Cookie |
| FR-002-AC03 | 偽造、缺少或過期憑證不能讀取車庫或執行寫入；過期後提示重新登入，不把空車庫當作成功結果。 | Pass — 真 PG 缺／偽造／到期 401，Browser 私人路由要求重新登入 |
| FR-002-AC04 | Server 在距最後有效活動達 30 分鐘或距本次登入建立達 8 小時時拒絕 Session；Cookie 未到期也不能繞過；活動不能延長 8 小時絕對期限，舊 Session 不自動復活。 | Pass — exact predicate boundaries + test_absolute_expiry_and_activity_policy on PG |
| FR-002-AC05 | 有效活動限定為經定義且成功授權的業務 Request；照片、靜態資產、自動身分確認、背景輪詢與遭拒請求不延長閒置。以受控時間測試 29:59／30:00 與 7:59:59／8:00:00 邊界；具體活動清單在 API Contract 明列。 | Pass — test_exact_expiration_predicate、test_absolute_expiry_and_activity_policy、Browser-Auth 焦點不讀車庫 |
| FR-002-AC06 | 每次成功登入使用新的 Session ID，替換並撤銷該 Browser 的舊本次 Session；舊 ID／晚到回應不能恢復它。不同裝置的獨立 Session 不因此失效。 | Pass — test_registration_rotation_replay_logout_other_device + test_same_context_concurrent_rotation |
| FR-002-AC07 | 同 Origin 分頁在登入／登出通知、重新取得焦點或恢復頁面時重新確認目前身分；不得沿用先前帳號的私有快取或接受舊帳號請求結果。背景／凍結分頁恢復時先遮蔽私有內容再驗證，不承諾作業系統凍結時同步。 | Pass — Browser-Account-Switch、Browser-Auth、Browser-Tab-Recovery，跨帳號晚到私人資料與凍結恢復 |
| FR-002-AC08 | 登入與註冊也有 CSRF 防護；缺失／錯誤 Token 或不受信任 Origin 的 Browser 操作不得建立／替換有效登入。正常同 Origin 流程及符合 Contract 的獨立 HTTP Client 可成功。 | Pass — Browser-Cross-Origin-Auth 真 403；test_source_csrf_gate_and_expiry、Native／Browser 合法來源 |
| FR-003-AC01 | 撤銷提交完成後才進行 Session 授權判定的新 Request 必須拒絕原憑證，涵蓋讀取與寫入。已在撤銷前通過授權的在途工作不保證回溯取消；此界線不得描述成能撤回已完成操作。 | Pass — test_logout_replay_and_touch_waiter 與 Browser-Auth |
| FR-003-AC02 | 重新整理、上一頁與開啟分頁不恢復舊 Session；登出清除 App 私有 State／Query Cache／可控照片預覽。其他分頁依 FR-002-AC07 確認，已保存的外部副本不在可清除範圍。 | Pass — Browser-Tab-Recovery／Browser-Auth，登出後 Back、Reload、凍結分頁恢復及私人資料遮蔽 |
| FR-003-AC03 | 重複登出不造成錯誤資料；若無法確認 Server 端結果，顯示尚未完成或結果不明並允許重試。 | Pass — Browser-Logout-Recovery，真撤銷後中斷，保留同 Context 才能重試 |
| FR-003-AC04 | 兩分頁共用同一 Session 時，A 登出後 B 的舊憑證遭拒；在正常可執行分頁的展示測試中，事件送達後最遲 5 秒清除私有 UI。另一 Browser／裝置的獨立 Session 仍可用；同 Browser 分頁不算獨立登入。 | Pass — Browser-Auth 兩分頁 5 秒上限，test_registration_rotation_replay_logout_other_device 驗獨立裝置 |
| FR-003-AC05 | 登出／過期後晚到的查詢或續期回應，不得重新填入舊私有資料或重建失效 Session；登出不能以普通 GET 觸發，且需通過 CSRF 驗證。 | Pass — Browser-Auth 晚到車庫回應；test_logout_replay_and_touch_waiter 拒舊 SID，Logout GET／CSRF 負面測試 |
| FR-004-AC01 | A、B 各自建立車輛後，A 的車庫不包含 B 的車；修改查詢參數也不能取得 B 的私有車庫。 | Pass — test_vehicle_owner_and_initial_ledger，兩帳號各有車，Owner query 竄改 422 |
| FR-004-AC02 | 新會員顯示空狀態與新增車輛入口；查詢失敗顯示重試，不誤顯示成沒有車輛。 | Pass — Browser-Tab-Recovery，模擬 503 顯示錯誤，重試後才出現空狀態 |
| FR-004-AC03 | 成功新增、編輯、上下架後，重新取得資料可看到已保存結果；Owner 可以查看自己未上架車輛的完整資料。 | Pass — Browser-MVP，建車、編輯、上下架後重新取得資料 |
| FR-005-AC01 | 有效資料只建立一台車，Owner 由登入身分決定；Request 不能指定其他 Owner。 | Pass — test_hidden_vehicle_rejects_owner_override_and_rolls_back_initial_ledger |
| FR-005-AC02 | 新車不出現在公開 Marketplace，訪客不能由直接網址讀取其詳情或照片。 | Pass — test_hidden_vehicle_rejects_owner_override_and_rolls_back_initial_ledger + test_image_is_private_processed_and_replaced |
| FR-005-AC03 | 同一正規化 VIN 的先後或併發提交最多成功建立一台；失敗者得到可處理的衝突回饋。 | Pass — test_parallel_duplicate_vin_and_touch_failure，大小寫／空白兩連線 201／409 |
| FR-005-AC04 | 輸入與保存失敗時不留下可見的半成品車輛，也不對外揭露重複 VIN 所屬帳號。 | Pass — test_hidden_vehicle_rejects_owner_override_and_rolls_back_initial_ledger，真 PG Rollback |
| FR-005-AC05 | 新增流程提示使用合成 VIN／合成車輛；公開只顯示末 6 碼，不宣稱 VIN 或 Owner 經車籍驗證。 | Pass — Browser-Garage／Browser-MVP 合成 VIN 提示及公開遮罩 |
| FR-006-AC01 | Owner 可保存允許欄位，重新整理後內容一致；不能改 Owner、紀錄來源或申報時間。 | Pass — Browser-MVP 編輯持久化，test_revision_lock_and_mileage_ledger 拒偽造可信欄位 |
| FR-006-AC02 | B 直接送出 Request 編輯 A 的車必須被拒絕，且所有欄位保持不變。 | Pass — test_revision_lock_and_mileage_ledger，跨 Owner PATCH 404，合法者仍從原版本提交 |
| FR-006-AC04 | 不同分頁同時保存時不得默默覆蓋較新的版本；至少一方得到重新載入最新資料的衝突提示，保護方式待 Step 2。 | Pass — test_revision_lock_and_mileage_ledger，兩個同版本請求 200／409 |
| FR-006-AC05 | 已上架車不得保存無效售價；一般文字／價格編輯不得直接改寫任何原履歷、更正版本、來源或申報時間。 | Pass — test_listing_projection_unlisting_and_old_photo，對已有履歷的上架車送無效價格和新品牌，公開投影與版本不變 |
| FR-006-AC06 | 目前申報里程 C 必須在允許範圍且至少等於全部有效版本的最大里程 H；沒有有效紀錄時 H=0。已被更正取代的舊高值不得參與 H；與補登／更正同時發生時仍需保持 C≥H。 | Pass — test_concurrent_current_mileage_and_new_history + test_correction_is_append_only_releases_high_mileage |
| FR-006-AC07 | 降低 C 必須填理由、明確確認，並與前後值、Owner、Server 時間一起保存；有效歷史不符則拒絕且提示先更正。合法下修不會被已停用 AC03 阻擋；展示里程下修標記及摘要，不能悄悄抹除前值。 | Pass — Browser-MVP 展開公開摘要、test_revision_lock_and_mileage_ledger 檢查前後值與理由 |
| FR-007-AC01 | 有效上架後，新的公開查詢包含該車；無維修紀錄的車仍可上架，顯示尚無紀錄。 | Pass — Browser-Public-Errors，無履歷車可上架、公開市場及詳情讀回 |
| FR-007-AC02 | 缺少必要資料時維持未上架；另一會員不能替車主上架。 | Pass — test_listing_guards_empty_history_and_unlisting_noop，缺圖／價、跨 Owner |
| FR-007-AC03 | 重複對已上架車執行上架不產生第二份刊登；成功必須以已保存結果為準。 | Pass — test_listing_projection_unlisting_and_old_photo，重複上架 unchanged |
| FR-008-AC01 | 下架狀態提交完成後才進行的受控讀取／授權判定，不得向非 Owner 提供該車詳情、履歷或照片，公開列表的新查詢須排除該車；直接 URL、衍生圖與如有支援的條件／Range 請求同樣適用。 | Pass — test_listing_guards_empty_history_and_unlisting_noop、Browser-MVP，舊 URL、Range、條件 Header 與市場 |
| FR-008-AC02 | Owner 仍可在車庫讀取完整資料；下架不刪除資料，建議保留售價供再次上架。 | Pass — Browser-MVP／test_listing_projection_unlisting_and_old_photo，Owner 下架後仍能讀圖及資料 |
| FR-008-AC03 | 重複下架不破壞資料；下架不代表已售出或已過戶。 | Pass — test_listing_guards_empty_history_and_unlisting_noop，狀態不變並保留售價與圖片 |
| FR-008-AC04 | 不保證撤回已下載檔、截圖、先前已顯示畫面、不遵循指示的外部 Cache 或下架前已通過授權的在途傳輸；已開啟的公開頁面下次重新取資料或恢復焦點時檢查狀態，得知下架後移除內容。 | Pass — Browser-MVP 模擬焦點事件，新查詢 404 後移除舊詳情 |
| FR-008-AC05 | 從第一次交付即對車輛資料／照片設 no-store，App／受控 Proxy／CDN／Service Worker 不保留可繞過驗證的副本；下架後測試舊直接 URL、帶舊 ETag 的條件請求及新 Browser，均不能取得內容或有效 304。不能用無需重新授權的公開物件 URL 或未到期 Signed URL 滿足本條。 | Pass — Browser-MVP 與 test_listing_projection_unlisting_and_old_photo，獨立 Jar、直接 URL、條件 Header、no-store |
| FR-009-AC01 | 未登入者可操作；每張車卡顯示品牌、車型、年份、里程、TWD 售價、主照片與詳情入口。 | Pass — Browser-MVP，獨立訪客可使用搜尋並讀取公開資料與照片 |
| FR-009-AC02 | 關鍵字 trim 後空白等同全部已上架車，最多 50 字元；整段輸入在品牌或型號任一欄位包含即可符合，不分英文大小寫，不暗中加入 VIN 或描述搜尋。 | Pass — test_listing_projection_unlisting_and_old_photo／test_marketplace_fixed_pagination_and_sort |
| FR-009-AC03 | 每頁 12 筆，依最近一次由未上架轉為已上架的時間新到舊，同值再用穩定唯一識別排序；重複對已上架車上架、編輯或更正不刷新上架時間。換頁維持條件，改條件回第一頁，超出最後頁顯示空結果；併發上下架時不承諾跨頁快照完全不變。 | Pass — test_marketplace_fixed_pagination_and_sort，13 筆及超頁；listing test 驗 No-op 刊登時間 |
| FR-009-AC04 | 搜尋、換頁或手動更改條件皆不能讀取未上架車；查詢失敗顯示錯誤與重試；無結果顯示清除條件入口。 | Pass — Browser-Public-Errors，無結果可清除，故障顯示重試，另有未上架查詢整合測試 |
| FR-010-AC01 | 已上架車可在未登入下閱讀；沒有履歷顯示「尚無自行申報維修紀錄」，不得暗示零事故或從未維修。 | Pass — Browser-Public-Errors，未登入讀取無履歷車輛及正確空文案 |
| FR-010-AC02 | 每筆有效紀錄顯示維修日期、里程、描述、申報時間及「車主自行申報・未經機構驗證」；依有效維修日新到舊，同日依里程大到小，再以申報時間／穩定識別排序。此順序只是顯示，不能把同日申報時間當成維修先後證據。 | Pass — Browser-MVP／test_backfill_and_concurrent_incompatible_events，來源與時間線 |
| FR-010-AC03 | 公開資料不含帳號 Email、Password、登入憑證或未遮罩 VIN；非 Owner 不能以直接網址或額外請求取得私有欄位。 | Pass — Browser-MVP 與 test_listing_projection_unlisting_and_old_photo，VIN、Email、提交者 ID 不外洩 |
| FR-010-AC04 | 深層連結重新整理可正常開啟；載入失敗不顯示成空履歷；照片失敗可顯示占位圖，不破壞其他資訊。 | Pass — Browser-Public-Errors／Browser-MVP，深層連結、圖片占位與履歷失敗重試 |
| FR-010-AC05 | 每個維修事件僅目前有效末端計入履歷筆數／里程規則；被取代版本標示「已被更正，非目前有效值」，可依鏈查看原文、各版完整內容、理由及 Server 時間，不把更正當成多次實際維修。非 Owner 只能在車輛上架時讀取這些內容。 | Pass — Browser-MVP 與 test_correction_is_append_only_releases_high_mileage |
| FR-010-AC06 | 首頁／註冊／Marketplace／詳情及車輛管理顯示合成資料與不供真實交易提示；無購買、付款、聯絡賣家、認證車主或真實車況保證文案／入口。 | Pass — Browser-Auth、Browser-Garage、Browser-MVP 走過各頁；全站 Layout 顯示展示警語 |
| FR-010-AC07 | 若目前申報里程曾下修，詳情顯示可展開的更正摘要（前後值、理由與申報時間），不含帳號 Email；讀取依同一車輛公開規則。紀錄里程更正與目前值更正分開標示。 | Pass — Browser-MVP 驗公開下修摘要，API 歷史可見性共用下架限制 |
| FR-011-AC01 | 只有 Owner 可以新增；篡改請求中的 Owner、來源、申報者或系統時間不能改變系統認定結果。 | Pass — test_history_owner_and_server_fields_are_enforced，跨 Owner 404，偽造可信欄位 422 |
| FR-011-AC04 | 每筆固定標示自行申報與未驗證；不能選擇「已認證機構」來源。文字中填寫機構名稱也不改變來源標記。 | Pass — Browser-MVP 與 test_listing_projection_unlisting_and_old_photo |
| FR-011-AC06 | 允許任意順序補登 1900-01-01 至今日的事件，包括早於車輛建立日／低於 C；驗證 m≤C、嚴格較早日期最大有效里程≤m≤嚴格較晚日期最小有效里程。缺少一側則無該側限制；同日不推定先後，但整日區間需與前後日期相容。 | Pass — test_history_owner_and_server_fields_are_enforced／test_backfill_and_concurrent_incompatible_events |
| FR-011-AC07 | 保存新事件時不修改 C；若 m>C，明確提示先更新目前申報里程而非偷偷提高或裁切 m。保存與當前有效歷史／C 的檢查必須一致；與補登、更正或目前里程更新併發時不能提交矛盾結果。 | Pass — test_backfill_and_concurrent_incompatible_events／test_concurrent_current_mileage_and_new_history |
| FR-011-AC08 | 原始版本不能直接編輯／刪除；更正需走 FR-013 的明確關聯，不能靠描述寫「前筆有誤」來排除原值。普通補登仍代表新事件，不會自動取代任何紀錄。 | Pass — test_native_maintenance_constraints_and_rollback，改刪 API 405，原鏈不變；Runtime 權限檢查 |
| FR-012-AC01 | 合法且不超過 5 MiB 的 JPEG／PNG／WebP 可保存；大小／內容需由 Server 驗證，不能只看副檔名或 Browser 宣告的類型。 | Pass — test_upload_three_formats_and_size_bound／test_image_is_private_processed_and_replaced |
| FR-012-AC02 | 其他會員不能上傳或替換；超限、偽裝格式、損毀檔案均被拒絕且不改變車輛主照片。 | Pass — test_listing_guards_empty_history_and_unlisting_noop、test_image_is_private_processed_and_replaced、test_upload_three_formats_and_size_bound |
| FR-012-AC03 | 替換失敗時舊照片仍可用；成功替換不產生兩張「目前主照片」，也不混入其他車輛照片。 | Pass — test_image_is_private_processed_and_replaced，舊圖保留／舊 URL 404 |
| FR-012-AC04 | 未上架車照片僅 Owner 可透過服務讀取；下架後新請求依 FR-008 控制；服務／Container 重建後照片仍存在。 | Pass — Browser-MVP 與 Browser-Persistence，非 Owner 404，Owner 及重建後可讀 |
| FR-012-AC05 | Server 拒絕長／寬不在 1–6,000 pixels 或總像素超過 12,000,000 的影像；拒絕動畫／多頁、截斷、損毀或解碼資源超限，不只看壓縮後 5 MiB。第 5.2 節的工作預算需在選定部署資源上驗證。 | Pass — 本機 Linux Docker check-image-budget.py，6000×2000 可處理、超界及截斷拒絕、128 MiB 與 5 秒限制；動畫另有測試 |
| FR-012-AC06 | 先依方向資訊正確轉正，再重編碼為允許的靜態格式，移除 EXIF／GPS／XMP／IPTC 與非必要文字 Metadata；輸出檔亦不超過 5 MiB。以含 GPS／拍攝資訊樣本檢查處理後檔案；原檔不可對外讀取，不承諾自動移除畫面中的車牌／人臉。 | Pass — test_jpeg_orientation_and_gps_removed 與 test_image_is_private_processed_and_replaced |
| FR-012-AC07 | 照片及所有如有提供的衍生圖透過可檢查當前車輛狀態的路徑交付，從首次回應設 no-store；不能以儲存桶／原始檔／未到期公開連結繞過。替換後舊主照片 URL 不再由受控服務提供；失敗時仍保留原主照片。 | Pass — test_image_is_private_processed_and_replaced + Browser-MVP |
| FR-013-AC01 | 只有 Owner 可更正同一車輛的目前有效紀錄；理由必填；系統決定申報者、Server 時間、來源及指向關係，不能指向另一車或任意偽造根事件。 | Pass — test_history_owner_and_server_fields_are_enforced，跨 Owner／跨車、理由及可信欄位 |
| FR-013-AC02 | 提交新增完整替代內容，保留所有舊版日期／里程／描述／來源／申報時間，不直接 UPDATE 原文或 DELETE 歷史；每個事件僅一個有效末端。 | Pass — test_correction_is_append_only_releases_high_mileage，原始與有效版同時可讀 |
| FR-013-AC03 | 以「排除被更正事件舊有效版，加入替代版」後的整體有效集合驗證日期／里程與 C；舊錯誤高值退出 H 及前後界線，不永久阻擋合理補登；不能忽略其他仍有效的高值。 | Pass — test_correction_is_append_only_releases_high_mileage，排除舊有效版本後允許下修 |
| FR-013-AC04 | 兩分頁同時更正同一末端，最多一方成功；另一方收到衝突並重新載入。不能產生分叉、循環、自我指向或一個版本被多次直接取代。 | Pass — test_correction_is_append_only_releases_high_mileage、test_native_maintenance_constraints_and_rollback |
| FR-013-AC05 | 更正不自動上／下調 C；先更正有效高值，再依法降低 C 的流程可完成。高於 C 的合法更正須先明確更新 C，不用隱含連動掩蓋目前值變更。 | Pass — Browser-MVP，依序更正誤值與明確下修 C |
| FR-013-AC06 | Owner 及符合公開權限的訪客能展開原文、關聯、更正理由與各版本來源，主時間線只計一次有效維修事件；鏈也受下架權限限制。 | Pass — Browser-MVP 公開展開兩個版本及 test_listing_projection_unlisting_and_old_photo 下架拒絕 |
| FR-013-AC07 | 若更正仍有誤，可針對目前末端再追加更正；不可回頭直接取代非末端舊版。MVP 不含批次更正、分叉合併、審批、刪除、撤回事件或跨車重掛。 | Pass — test_version_chain_second_correction_and_collection_pagination，21 版並拒絕舊 parent |
| FR-013-AC08 | 失敗時新版本與有效末端切換均不生效；逾時先查明結果，不能把重試變成第二次維修。對鏈的限制仍須在重送及併發時成立。 | Pass — test_native_maintenance_constraints_and_rollback、Browser-Account-Switch；失敗原子回滾，成功後回應中斷用讀回確認 |

## 最終測試結果

- 後端在隔離的 PostgreSQL 驗證 DB `vibicle_3a_verify_de65d4eb4bc1` 執行 `uv run --locked python -m pytest -q`，**94 passed、0 skipped、1 warning**。警告來自上游 Starlette TestClient 棄用提示。
- Ruff、Mypy（33 個來源檔）、TypeScript、5 個 Vitest 測試與 Linux Docker Production Build 均通過。
- Chromium 在實際 Caddy HTTPS 環境跑 Auth、車庫、履歷／更正、照片、市場、故障與 Restore；下列各列區分真資料流、受控故障注入與尚未執行的補充案例。
- 71 項有效 PRD AC 的本機驗收狀態為 **71 Pass**。此數字是逐條 PRD 的本機證據彙整。T／SR 另有故障、競態與外部環境子案例。

## Reproduce local verification

Browser 測試在 `web-app` 目錄執行。使用獨立測試 Context 與合成帳號。Playwright 的憑證例外只作用於該測試 Context，本機 CA 鏈另以 curl `--cacert` 驗證。

~~~powershell
New-Item -ItemType Directory -Force output\playwright | Out-Null
'{"browser":{"contextOptions":{"ignoreHTTPSErrors":true}}}' | Set-Content -Encoding utf8 output/playwright/local-config.json
npx.cmd --yes --package @playwright/cli playwright-cli -s vibicle-review open https://localhost:8443 --config output/playwright/local-config.json
npx.cmd --yes --package @playwright/cli playwright-cli -s vibicle-review run-code --filename scripts/Browser-MVP.js
npx.cmd --yes --package @playwright/cli playwright-cli -s vibicle-review close
~~~

上述 Chromium 測試可產生本機公開手機版與車主桌面版截圖。完整腳本會在結束時下架測試車。

- 環境為 Docker Engine 29.9.2、PostgreSQL 18.6、四個 Migration 到 `0004_vehicle_images`。保留原 dev Volume，原開發 DB `vibicle_dev` 已增量升級。從空 DB 開始另驗 `vibicle_3a_verify_de65d4eb4bc1`，`alembic check` 無 Drift。
- Local TLS 以 Caddy Local CA 驗證 `https://localhost:8443`，HTTP `8080` 對同路徑回 301 至 `8443`。SPA deep link 200，容器內 Linux Production Build 通過。Windows 的 native Vite 寫出階段曾退出 1，Docker Build 為已驗證的 Production 建置路徑。
- `--force-recreate` 保留資料與照片。SQL 檢查確認 `vibicle_runtime` 非 Superuser，不能修改 csrf_secret 或刪除維修版本。
- 隔離還原 project `vibicle-restore-e382e6dc` 從驗證 bundle 還原，校驗 SHA256、讀回同一個 Vehicle Revision、兩版維修及相同照片 bytes。撤銷快照中的 1 筆 Session，還原後舊 Cookie 的 E05 為匿名，Owner 路徑 401，新登入可讀。
- 真實停止隔離 PostgreSQL 以注入故障的命令被自動審查拒絕，原因回報為 `blocked by policy`。該容器停止情境為 **Not Run**。應用層不可連線證據使用獨立 API Instance 對不可達 PostgreSQL Port，原資料庫持續保留。
- 本機驗收當時的公網環境另待部署。後續正式站結果見 [正式部署與驗證](DEPLOYMENT_REPORT.md)。

## API Contract T01～T35

`Not Run` 表示該測試列尚缺至少一個明列的子情境。表內已測部分可單獨引用。

| ID | 狀態 | 實測證據或剩餘項目 |
| --- | --- | --- |
| T01 | Pass | test_contract_validation.py、test_registration_validation_no_secret_echo、原生 Constraints |
| T02 | Pass | Browser-Auth、test_email_unique_and_wrong_credentials |
| T03 | Pass | Unicode＋大小寫／空白兩連線 UNIQUE 201／409 |
| T04 | Pass | 同 401、Rotation／重放、獨立裝置保留 |
| T05 | Not Run | 正常及 Auth／新增車缺 CSRF 已驗，所有 Mutation＋跨站 Browser 尚缺 |
| T06 | Not Run | 跨 Owner PATCH／影像／事件與 Public DTO 已驗，完整 Path／Versions 矩陣尚缺 |
| T07 | Pass | 大小寫與前後空白不同，真 PG 同 VIN 兩連線 201／409 |
| T08 | Not Run | 初始 Ledger flush 後注入失敗、資料 Rollback 已驗，PG Commit 傳輸故障尚缺 |
| T09 | Pass | E10 同版本 200／409，E11／E22 同一 Vehicle Revision 競爭只有一筆成功 |
| T10 | Pass | 下修 Ledger、有效 H、前端確認、已上架車無效售價拒絕 |
| T11 | Pass | 真 PG 兩連線 C 下修 vs 補登，`test_concurrent_current_mileage_and_new_history` |
| T12 | Pass | `test_listing_guards_empty_history_and_unlisting_noop` |
| T13 | Not Run | 重複上下架已測，真正重新上架時刻與多種異動組合待補 |
| T14 | Pass | 真 PG 13 筆、排序、分頁、literal 搜尋、超頁與 50／51 字元 |
| T15 | Pass | Browser-MVP、Public／Owner 欄位投影與來源標記 |
| T16 | Pass | 1900 邊界、未來、m>C、同日與跨日、C 不受補登變更 |
| T17 | Pass | 不相容補登真 PG 201／422 |
| T18 | Pass | 同 parent 201／409、原版仍在、指標與新版本同交易 Rollback；Native F-02／F-03／自環反例 |
| T19 | Pass | 誤值 900000 更正 70000，再將 C 降至 80000 |
| T20 | Not Run | 21 版鏈跨頁與事件 Snapshot 409 已測，超過 20 個有效事件的遍歷待補 |
| T21 | Not Run | Owner 初始／降低／提高及非 Owner 404 已驗，Public 混合集合的完整負面矩陣待補 |
| T22 | Pass（本機 Linux） | 三格式與 5 MiB、JPEG GPS／方向、超尺寸／動畫／截斷、12 MP 合法邊界及實際 worker 128 MiB／5 秒 |
| T23 | Not Run | 換圖失敗保留舊圖，DB＋File 故障／Cleaner Crash／並行尚缺 |
| T24 | Pass | Browser-MVP、test_images、Browser-Persistence |
| T25 | Not Run | 定時 predicate 等號、真 PG 閒置／絕對到期、普通觀測不 Touch 與 Browser 背景重驗已驗。逐支 Endpoint 的時間矩陣待補 |
| T26 | Pass | Commit 後 Touch 故障維持 201，撤銷後 Touch 不復活 |
| T27 | Not Run | 真連線不可達與 Client Gateway Unknown 有測，直接停止 PostgreSQL 容器的故障注入未執行 |
| T28 | Not Run | Cookie／5 秒／晚到 Garage／deep link 已驗，跨帳號、凍結及 BFCache 待補 |
| T29 | Not Run | 多 PG Connection 三 Scope 配額及隔離 Caddy 偽造 XFF 均驗；完整多 Process 與 UTC 邊界待補 |
| T30 | Not Run | 真 Login Commit 後中斷，保留 Uncertain／重載不重送；Header 亂序與中斷 Body 矩陣待補 |
| T31～T33 | Deferred | 方案 B / E06 專用 |
| T34 | Not Run | Browser-Unknown-Business 與 Browser-Account-Switch 驗建車及更正 Commit 後中斷且不重送，補登獨立故障案例待補 |
| T35 | Not Run | 參數化搜尋與安全錯誤已有，XSS／Log 審核矩陣待補 |

## Scope Review SR-T01～18

| ID | 狀態與證據 |
| --- | --- |
| SR-T01 | Pass，Rotation 換 Secret／SID、獨立裝置未撤銷 |
| SR-T02 | Pass，兩個 PG 連線競爭同 Context，200／409，失敗無 Set-Cookie |
| SR-T03 | Not Run，已驗 Logout 先提交且 Touch 不復活，反向可控排程待補 |
| SR-T04 | Not Run，已驗 Logout 與 A→B 的晚到 Garage，仍可擴充同 User 重新登入的延遲組合 |
| SR-T05 | Not Run，正常兩 Tab ≤5 秒與 Chromium CDP 凍結恢復已驗，真 BFCache 命中待測 |
| SR-T06 | Not Run，定時函式等號＋真 PG 閒置，仍缺完整 Store Clock／活動清單 |
| SR-T07 | Not Run，真 Login 先 Commit 後中斷，分開控制 Header／Body 未完成 |
| SR-T08 | Not Run，Reload marker、另一 Tab 保持 Uncertain 已驗，凍結與移除 marker 待補 |
| SR-T09 | Not Run，Browser-Logout-Recovery 已驗失去 204 後同 Context 可重試，Cookie 換成新身分時的負面案例待補 |
| SR-T10 | Not Run，同 Origin／不同 Port 與錯 CSRF 已有，多種類型全矩陣待補 |
| SR-T11 | Pass，真連線不可達與 Commit 後 Touch 失敗 |
| SR-T12 | Pass（負面控制），Browser-Cookie-Reorder 刻意繞過協調器。另一個已提交的新 Session 仍可在晚到 Set-Cookie 後使用，CP-06 保持開放 |
| SR-T13 | Pass，原 Session 與 Volume 重建後可用，隔離還原後舊 Cookie 拒絕 |
| SR-T14 | Not Run，正常 Pending 和中斷 Uncertain 已驗，Storage 不可用／受控結果收斂待補 |
| SR-T15～18 | Deferred，方案 B 專用 |

## 公網驗收與補充測試

71 項 PRD 有效 AC 已有本機證據。公網 Release 和 T／SR 補充矩陣仍有外部條件與未執行子案例。後續 Hardening 可在 `web-app/backend` 對專用驗證 DB 擴充 `test_auth.py` 的時鐘／Touch／Logout 競態，再在本機 HTTPS Chromium 用隔離 Context 重播 SR-T04～SR-T12 的剩餘子案例。CP-06 的 Browser Cookie 回應順序風險保持開放。逐項以此文件表格為準。

## 補充運行證據

- `Browser-Registration-Unknown.js` 確認 E02 已提交後網路失敗，畫面仍允許手動登入確認；E02 沒有寫 Cookie。
- `Browser-Logout-Recovery.js` 確認丟失已提交的 204 時保留 Uncertain，舊 SID 不能讀車庫，有原 Context 的記憶體證明才重試 204。
- `Browser-Public-Errors.js` 確認無履歷也可上架，合成 XSS 字串以文字顯示、圖片失敗有提示、歷史與市場錯誤分開於空資料。測試後以正常描述保留本機展示車。
- `Browser-Cookie-Reorder.js` 確認方案 A 的 CP-06 殘餘風險。Server 不會復活已撤銷 SID；刻意不經 Coordinator 時，另一個新 Session 的晚到 Header 仍可能生效。
- Native 不合規註冊測試回 422；在回應與當下 API／Caddy 日誌查不到合成密碼和該請求的 CSRF canary，Request ID 可對應日誌。來源掃描檢查 99 份程式／設計檔，沒有出現本機已配置的密碼或限流秘密。

- `Browser-Account-Switch.js` 實測 A→B 切換後釋放 A 的私人資料 Response，以及更正已 Commit 時中斷回應、重讀確認僅兩版。
- `Browser-Tab-Recovery.js` 透過 Chromium CDP 實際凍結頁籤，再觸發恢復事件，並驗登出後 Back 及車庫故障和空狀態。特定瀏覽器 BFCache 實際命中仍應另外驗證。
- `Browser-Cross-Origin-Auth.js` 以第二個本機 HTTPS Origin 發送註冊／登入請求，兩者均 403 且無 Set-Cookie。此隔離測試 Context 略過外部來源頁的 CSP，目標 API 自身政策照常生效。
- 在 `web-app` 執行 `Get-Content -Raw scripts/check-image-budget.py | docker compose --env-file .env.deploy.local -f compose.deploy.yaml exec -T api python -`。Linux worker 實測 6000×2000 合成 PNG 約 1.7 秒，拒絕超過 12M、超長邊、截斷，以及在 128 MiB 限制下嘗試配置 256 MiB。Linux CPU 與父程序時間上限均設定 5 秒。正式 VPS 資源仍待驗。

- 隔離 Caddy 環境以 21 個不同偽造 X-Forwarded-For 發送請求，固定窗口回 19 次 Context 拒絕與 2 次 429（同窗口已有一次消耗）。HTTP 實測未繞過配額。三種 Scope 的精確 N＋1 另由真 PG 多連線測試。
