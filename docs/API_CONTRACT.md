# Vibicle — REST API Contract Design

- 版本：v0.2／Step 3A MVP Scope 同步；日期：2026-11-05（Asia/Taipei）。
- 已讀取現行 [PRD v0.2.1](PRD.md)、[DECISIONS §6](DECISIONS.md)、[System Architecture v0.2](SYSTEM_ARCHITECTURE.md)、[Database Design v0.2](DATABASE_DESIGN.md)、[AUTH v0.1](AUTH_DESIGN.md)。CP-01～05已接受；CP-06仍有條件。AUTH中審查前狀態不覆蓋新版上游。
- Step 2D原輪次只建立本文件；2026-11-05依使用者同步MVP Scope，另在web-app開始Step 3A。只有匿名E05開始實作，不代表完整Auth、Schema實測或部署完成。
- **[B]** 已接受的基線；**[D]** 本輪Contract選擇、待審查；**[CP]** 尚未核准的上游變更；**[TEST]** 未來驗證，不是通過結果。
- **現行 MVP 採方案 A**：使用者已接受 CP-SCOPE-01～03；不建立第九表、不要求 Attempt ID，E06 Deferred、其他 ID 不重編。保留 Uncertain／CP-06 未解風險；不以方案 B 作任何開發的前置條件。本輪只授權 Step 3A Runnable Foundation，並非全部 Endpoint／Auth 已實作。

## 1. 第一優先：I-AUTH-01 Recovery Decision

### 1.1 問題與Failure Timeline

Cookie由Browser HTTP層處理，React丟棄JSON不取消Set-Cookie；Abort只停止Client等待，不證明Server工作Rollback。me只回答該次Cookie的當時身分，不能證明先前Login不會稍後完成。依據：[Fetch Standard](https://fetch.spec.whatwg.org/)；Vibicle要求與風險來源是DECISIONS §6.3／DR-01，而非已存在漏洞報告。

| 情境 | 時序／可能失敗 | 不能作的結論 |
| --- | --- | --- |
| A. 已Commit但Response延後 | C為舊Context；Login建立S、撤銷C，Set-Cookie(S)卡在網路。Client仍可能只有C。 | 清React／查C無效，不代表S未建立。 |
| B. Client Timeout | Server可能未收到、正在Verify、已Rollback，或已Commit。 | 不能一律自動重送Login／宣稱失敗；Abort不等於撤銷。 |
| C. 後送Auth先回 | 不受控流程先Bootstrap C2，再Logout C2回204；較早Login的Set-Cookie(S)後到。 | C2已登出不證明S已撤銷。 |
| D. React已清空 | 舊JSON被Epoch丟棄，Browser仍可能已套用Cookie。 | Epoch防資料填錯，不提供Cookie CAS。 |
| E. 兩Tab | Login A、Logout B各持舊畫面／Token；Cookie Jar共用，回應可能重排。 | 兩個Tab不是兩個獨立登入；只鎖單Tab State不足。 |

以上不推翻已接受的本次撤銷／在途界線：普通業務先授權者可完成，撤銷後新判定必拒。此處特別處理「未知Login可能產生新Session」的確認缺口，不降低FR-002-AC06／07、FR-003-AC05。

### 1.2 兩個候選方案

| 面向 | A：現有模型＋序列化／Uncertain | B：A＋Server Login Attempt取消紀錄 [CP] |
| --- | --- | --- |
| What | Web Locks序列化Bootstrap／Login／Logout，Epoch與BroadcastChannel隔離資料。 | 每Login使用Server先發放的非秘密Attempt UUID；PG保存狀態／父Context／結果Session，取消留下Tombstone。 |
| Why | 無Schema變更，容易完成正常Browser路徑。 | 在取消確認後，令晚到Cookie對應Session失效；阻止取消後的Login Finalize。 |
| How | Timeout進Uncertain，遮蔽、停Auth自動重試／Cookie變更；現有me／csrf只作觀測。 | Login準備／Finalize／Cancel競爭同Attempt Row；Cancel原子標取消並撤銷已產生的結果Session。 |
| Alternative | 直接重取preauth再Logout雖簡單，卻無法處理先前S。 | Session successor relation也可，但跨多次輪替、帳號切換、Cleanup鏈及舊Cookie撤銷範圍較難說明；不選通用Session Family。 |
| Failure | 無Server完成證據時可能長期卡住；單次me匿名不能解除Uncertain。 | 多一技術表、FK／Retention、Recovery專用授權與一個取消Endpoint；Cookie／Proof遺失時仍不能假確認。 |
| 保證 | 僅正常遵守Client協定且結果已收到的操作有序。 | 在有效Cookie／CSRF證明及成功取消Commit範圍內，該Attempt不會再產生可用Session；不保證任意外部操作順序。 |
| 現行範圍 | 已採MVP A；不宣稱I-AUTH-01完全解決，保留必要安全Gate。 | Deferred；只有重啟B才需模型／流程同步，非A實作前置。 |

**現行選擇：A 為 MVP；B 為 Deferred Design。** 上表保留能力差異，B 的推薦已由使用者本輪決策取代。A 不提供指定未知 Login 的確認取消；DR-01／I-AUTH-01 保留限制與必要反例測試，現有 AC 實測失敗仍阻擋相關安全驗收。

### 1.3 方案A可做與不可做的Recovery

Client狀態為anonymous／authenticated／pending／uncertain。Lifecycle Lock只包網路操作與回應處理，不持鎖等輸入。Login發送前清舊私有Cache／提升Epoch；登出或帳號切換事件讓其他Tab先遮蔽再重驗。

未知結果時：保存非秘密的Pending標記、停自動重送、停新的Bootstrap／Login／普通Logout，允許不改Cookie的me觀測；失效Context不自動Bootstrap覆蓋。me有User只能證明目前Cookie有效，me匿名不能證明先前Login結束。沒有可驗證完成證據時維持Uncertain，不能回「已登出」。

Crash／凍結／Privacy Storage清除、Native Client或不遵守Lock的Request仍可能破壞Cookie順序。這是A無法嚴格保證的地方，不能用「等幾秒應該沒事」解決。

### 1.4 CP-API-01：Scoped Login Attempt與取消（Deferred Hardening，非 MVP）

**本節全文僅保留 B 的歷史設計，沒有實作授權，不是現行 Schema／API 前提。** 若未來重啟，依 API_SCOPE_REVIEW §6～7 改為 POST Prepare，另審 Proof／Retention／鎖定與測試；下文 GET 準備構想未定版。

僅為Auth未知結果建立技術狀態，不將所有業務Request升級成通用Idempotency。推薦一個新增取消Endpoint，準備動作併入既有CSRF介面，不額外建通用Job／Operation服務。

**提案新增第九張技術表 auth_login_attempts；不是DDL或已存在表**：

| 欄位 | 提案型別／用途 |
| --- | --- |
| id | UUID PK；Server在E01 purpose=login準備時生成，Commit後才回Client保存。ID非秘密，不能單獨授權。 |
| parent_token_hash | BYTEA NN FK→auth_sessions.token_hash；登入原Context，只保留Hash。 |
| result_token_hash | BYTEA可null，FK→auth_sessions.token_hash；非NULL時Unique，使一個結果Session只屬一Attempt，不存raw Token。 |
| state | TEXT NN：prepared／verifying／succeeded／failed／cancelled。 |
| created_at | TIMESTAMPTZ NN，Server可信時間。 |
| deadline_at | TIMESTAMPTZ NN，候選min(parent absolute、建立＋120秒)；新Operation預算，非延長既定Session期限。 |
| completed_at | TIMESTAMPTZ可null；prepared／verifying為NULL，終態必有；成功後取消保留第一次完成時間。 |
| cancelled_at | TIMESTAMPTZ可null；cancelled必有，其餘NULL。 |
| retain_until | TIMESTAMPTZ NN；保守定為max(parent absolute, deadline＋8小時)，涵蓋所有可能結果；過期Proof不可繼續使用。 |

Native提案：PK／FK／Hash長度／state與NULL形態／列內時間順序；partial Unique(parent_token_hash) WHERE state IN(prepared,verifying)限制同Context最多一個進行中Attempt。不是用now()作Partial Index。succeeded需result／completed，failed沒有result，cancelled可保留既有result且必有cancelled_at。Service允許prepared→verifying／failed／cancelled、verifying→succeeded／failed／cancelled、succeeded／failed→cancelled；cancelled終態不重開。結果歸屬、deadline／Retention與跨列有效性由Service維持；不是Constraint可證明任意Writer都安全。

FK與Retention會改現有Cleanup：不能在父preauth15分鐘到期就刪掉還供Recovery證明的列。先清到期且不再有有效結果的Attempt，再清無引用Session；一般Runtime／Cleaner／Migration權限需審查。沒有額外Password／Request Digest／Raw Cookie／CSRF副本欄位。result Unique與active partial Unique有明確一致性用途；其他Index需實際Query計畫再決定。

**為何不只加successor_hash**：單欄輪替關聯較小，但還要表達尚未Finalize的取消狀態、長鏈Retention、原登入與後續帳號切換的撤銷邊界；不能只追一個Hash就聲稱所有晚到操作都取消。此處選一個有限、可鎖定的Attempt，不建通用Session Family或全裝置登出。

**準備／取消協定**：

1. E01 purpose=login在有效Context下準備Server ID；若已有未過期prepared則重用，verifying拒409。它在Commit後才把ID交Client，因此Cancel早於Login Request抵達也有既有Row可鎖，不允Client任選ID造Tombstone。準備Response丟失只留下技術列，不會自行登入。
2. Client在Login前保存**非秘密**Attempt ID／Pending狀態，跨Tab以Lifecycle Lock協調；Password／Cookie／CSRF不得寫Storage／通知。E03要求X-Auth-Attempt-ID，未知ID或重複消耗拒409，不建立／重建ID。prepared→verifying後才在鎖外作Verify。
3. 統一**parent Session→Attempt→result Session**鎖序。透過Cookie是result的Recovery先只讀Attempt以定位parent，不先持result Lock；取鎖後再重驗Cookie關聯。所有Auth操作不持Vehicle Lock。
4. Login最終短交易鎖parent／Attempt，驗state=verifying、deadline、原Context／Token／期限；以鎖後同一可信t驗t<deadline，再用t明填新S的created／last與absolute=t＋8小時；INSERT全新S、撤銷parent、設定result／succeeded同Commit。錯密碼僅在仍verifying時改failed，不撤銷原有效parent；若已cancelled，晚到Verify結果不得改回failed／succeeded。無法確定Commit不Set-Cookie假成功。
5. E01帶X-Auth-Attempt-ID作Recovery時，Cookie須匹配該Row的parent或result；來源有效後可由保留的失效列取得取消Token，**無Set-Cookie／Touch／新User權限**。已有效Session仍有原權限；失效列Token只可透過Recovery專用檢查，不能讀Private或Login。
6. E06 PUT cancellation需Cookie＋該列CSRF＋來源；只取消已存在、匹配Context的Attempt，未知／別人的ID404。Cancel先於Login抵達，prepared直接成cancelled；Late E03不可再進verifying。Server先發ID與Cookie綁定避免「拿自己Context搶占別人的公開ID」問題。
7. Login先Commit：Cancel鎖Row後原子撤銷result、置cancelled；晚到Set-Cookie(result)仍可能覆蓋Jar，但之後新認證拒該Token。Cancel先Commit：Finalize見cancelled，不能產生結果。204只代表取消已確認Commit，非已排程。
8. E06不Set／Clear Cookie、不Touch，也不撤銷尚未被替換的有效parent（例如A帳號要改登入B但先取消）；204不是「整個Browser已登出」。若User要Logout，先取消未知Attempt，再由E01／E04確認目前Context。其他獨立Attempt／裝置不受影響。
9. 普通E01／E04看到當前Cookie是尚有prepared／verifying或可能有效succeeded結果的parent，不以新preauth／Logout204掩蓋它，回409 AUTH_RECOVERY_REQUIRED且無Cookie，先走指定Attempt取消。[CP] Recovery與E06共用csrf_context 60／固定300秒配額，不新增Scope或數值；用途擴充也需審查。
10. 重複Cancel有相同可驗證證明則204，不重建登入。Client取得確認後才在Lock內安全Bootstrap／明確重登。舊無效Cookie晚到可能令新流程再失效，仍不得自動重送舊憑證。
11. 到deadline後不能Finalize；prepared／verifying逾期先在共同鎖內收斂failed，不能讓已超時Worker稍後成功。Retention到期時父／可能結果也已無效才可清Tombstone；Login從不因Row已刪又重建同ID。

**Failure Timeline B**：E01先Commit準備A與父C→E03(A)Commit S→Client Timeout→E01 Recovery以C或已收到的S取得Token→E06(A)Commit撤銷S／取消標記→晚到Cookie(S)→me匿名／受保護401。若E06先於E03抵達，Prepared Row已存在，同樣阻止Finalize。對**已確認取消的指定Attempt**，任意較晚Response也不能讓其SID有效；不要求網路準時，要求共同鎖／Retention／Fail Closed。

**限制**：Cookie／Attempt標記遺失、父Cookie已到期而結果Cookie未到、DB不可用、Cancel自身Outcome Unknown時無法證明取消；維持Uncertain，不回「已登出」。一次me匿名／新的preauth Logout不證明舊操作消失。任意Crash、Storage清除、非受控外部Login、另一個獨立Attempt及全域Cookie排序沒有嚴格保證；不以CSRF單獨當Bearer補Proof，也不假稱Web Locks提供全域順序。

**僅 B 的未來 Gate**：重新採 B 才需審查第九表、POST Prepare／Recovery／Cancel、Retention／權限／測試；不阻擋 A 的 Step 3A。E01 purpose=login、E03 Attempt Header及E06不納MVP；無Cookie／任意Crash確認取消仍未保證，不降低AC。

## 2. API Design Principles與資源取捨

只提供JSON API／受控圖片，React與API經同Origin Caddy；一個FastAPI Process內部的Router／Dependency／Service／Repository，不拆Microservices。/api為固定Base Path，不另加無需求的API版本URL。沒有真實交易／付款／過戶／聊天、刪車／刪履歷、批次更正、照片歷史管理或機構角色。

| 決策 | What／Why／How | Alternative／Failure |
| --- | --- | --- |
| Public／Owner分路徑 | 公開詳情及履歷只回Public；/me/vehicles/...專供Owner管理、成功主動讀取可Touch。 | 單一GET依Cookie換投影較短，但易洩VIN或使Public頁保活；本輪不選。 |
| Garage／Marketplace | 分別是Owner／已上架Vehicle Query，不新增Garage／Marketplace表。 | 不把篩選搬到Frontend全量下載；DB故障不是空列表。 |
| 編輯／C／價格 | 同一PATCH Vehicle承接允許欄位，C下修附理由／確認及Ledger，不多造三個Endpoint。 | 分開更直白但增加相同Lock／Version規則；混入is_listed或VIN則禁止。 |
| 刊登 | PUT Vehicle的單一listing子資源，完整指定is_listed；重複狀態可No-op。 | PATCH一般Vehicle易混權限／洗時間；POST /list與/unlist兩操作亦可但多Endpoint；本案選PUT /listing，不新增Listing表。 |
| 更正 | POST事件corrections追加完整替代版本，expected current ID必填。 | PATCH舊Version／文字補充不符合FR-013。 |
| 照片 | 同一POST /image上傳／替換、同步受限處理，單一Binary GET受控讀。 | 不建Jobs Queue／polling／公開Static URL；DB與File不能共同Rollback。 |
| Concurrency | Body expected_row_version及expected_current_version_id；衝突409。 | If-Match＋412也合理，但需強ETag表示不同投影／集合；本案不用，避免混用。 |
| Pagination | Marketplace固定12，其他集合固定20、完整可分頁；同車歷史以Vehicle revision防跨頁內容改變。 | 無界傳全部不可控；不把預設一頁當完整資料。 |

上述為[D]。資源是Vehicle、listing狀態、Maintenance Event／Version、Mileage Change及Current Image；不是每個DB表都開CRUD。來源類型與申報者由Server決定。HTTP方法／條件語意參考[RFC 9110](https://httpwg.org/specs/rfc9110.html)，本案的Endpoint命名與409選擇是設計取捨。


## 3. 共通Request／Response與Validation規格

### 3.1 Normative記號與Boundary

以下型別表是JSON結構加明確Validation政策的人工Contract，不是Pydantic／TypeScript實作；單靠JSON Schema不一定表達StrictInt對1.0等輸入表示的拒絕規則。`!`必有且不可null；`?`可省略；`T|null`明確允null；其餘不允null。未列入的Body／Query欄位拒422，重複JSON Key／Query Key／同名Cookie／單值安全Header拒400。所有Response Object也只序列化列出的欄位，不直接return ORM。

- Path UUID均嚴格解析並輸出canonical lowercase；格式錯422。Query page只接受十進位正整數字串，1～2,147,483,647，不把HTTP字串直接套StrictInt後拒絕所有正常Query。
- JSON整數用StrictInt語意，拒bool、小數、非有限值與數字字串，不四捨五入。布林只接受JSON true／false。
- VersionString為1～9,223,372,036,854,775,807的canonical十進位字串，不允正號／前導零；避免JS Number無法精確保存BIGINT。expected欄位是Client斷言，不是可覆寫Server row_version。
- 維修Date是有效YYYY-MM-DD日曆日，1900-01-01～Server判定Asia/Taipei今日；不接受Timestamp假裝Date。Response Timestamp為RFC3339 UTC Z。
- 文字長度以Unicode Code Points；品牌／型號trim後1～50／1～100，年份嚴格整數1900～Taipei當年＋1；描述0～2000，維修描述trim後1～2000，理由trim後1～500。Password例外不trim／正規化，12～128、可貼上、不強制組合。
- Auth JSON傳輸上限8 KiB；其他JSON Body上限32 KiB以容納2000字元／JSON escaping，並非擴大業務字數；超限413。GET無Body，Logout／Cancel無Body，其餘需application/json；錯Media Type415。
- Header接受名稱大小寫不敏感，值依嚴格格式。沒有Client可填的Owner／來源／申報者／時間／Hash；extra=forbid與Server allowlist共同防Mass Assignment。
- 每個API包括錯誤均Cache-Control: no-store。JSON為application/json；Binary例外見§9。Gateway傳輸錯誤可能沒有規範JSON，Client必須處理，不能誤判Rollback。
- FastAPI一般Dependency可能在Body／Form Parser之後；集中Header Guard／Route Wrapper先驗來源、Cookie／CSRF與Gate，對有Body的路由再進有界Parser；不能僅有Depends就聲稱已做到。參考[Pydantic Strict Mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)及AUTH §5.5。

### 3.2 Success、Error與Session Metadata

一般JSON成功為：
~~~json
{
  "data": {},
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "business_outcome": "committed",
    "session": {
      "activity": "touched",
      "requires_revalidation": false,
      "reason": null
    }
  }
}
~~~

Schema：`Success<T>={data:T!,meta:Meta!}`；Meta.request_id UUID!，business_outcome為read_only／committed／unchanged!；session.activity為not_applicable／not_touched／touched／not_extended／unknown!，requires_revalidation bool!，reason為null或SESSION_EXPIRED／SESSION_REVOKED／SESSION_STORE_UNAVAILABLE／RECOVERY_REQUIRED。理由不暴露其他User／Token。範例為結構示例，非實際已提交資料。

- Public／preauth／Auth觀測不Touch：not_applicable（無authenticated）或not_touched。合法Touch成功=touched。
- 業務已Commit後到期／撤銷：仍用該Endpoint的成功Status／data，business_outcome=committed、not_extended且requires_revalidation=true；Touch Store故障則unknown，不能轉成表示業務沒保存的503。
- No-op成功200、outcome=unchanged、changed=false，若是白名單可Touch；不增Vehicle版本／Ledger／刊登時間。
- Read成功為read_only。表中標Touch的讀取，其Touch失敗仍保留已讀結果及需重驗Metadata；UI若Epoch已變則丟棄私有資料。
- Logout／Cancel成功204無JSON，不塞Meta；用X-Request-ID、no-store，Cookie規則另列。Binary沒有JSON Meta、永不Touch。
- 「not_applied」只表示本次業務有效狀態未改，不表示Counter／技術Attempt／failed Image Metadata或孤立bytes完全沒有寫入。

Error固定為：
~~~json
{
  "error": {
    "code": "ROW_VERSION_CONFLICT",
    "message": "資料已更新，請重新載入後確認。",
    "outcome": "not_applied",
    "fields": [],
    "details": {
      "expected_row_version": "7",
      "current_row_version": "8"
    }
  },
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "session": {
      "activity": "not_touched",
      "requires_revalidation": false,
      "reason": null
    }
  }
}
~~~

ErrorEnvelope={error:ErrorSchema!,meta:{request_id:UUID!,session:SessionMeta!}!}；Error Meta沒有Success專用business_outcome，以error.outcome表達。SessionMeta即上列activity／requires_revalidation／reason三欄。ErrorSchema：code固定列舉!、message安全文字!、outcome=not_applied|unknown!；fields為`[{field:string,code:string,message:string}]`，不帶input值；details為各Code白名單或null。僅已授權後才可回當前版本／同車衝突Event ID／里程界線。不得回Password／Confirmation、Email存在資訊、完整VIN、Owner、Token／Hash、SQL／Stack Trace／路徑。Pydantic input／ctx／原Body不原樣序列化或Log。

HTTP回應遺失時沒有可相信的HTTP Status或Server Error JSON；Client使用本機TRANSPORT_OUTCOME_UNKNOWN狀態，記已知Request／Attempt／Resource識別，不造假的「Server已Rollback」。Gateway 502／504或無效Body也不能據此斷定應用未Commit。

### 3.3 分頁與集合一致性

Page<T>為`{items:T[]!,pagination:{page:int!,page_size:int!,total_items:int!,total_pages:int!,has_next:bool!},vehicle_row_version:VersionString或null}`，放入Success.data。空集合total=0／pages=0／items=[]，page仍回Request值；超出最後頁正常200空items。

- E12固定12；車庫與其餘集合固定20，不提供任意page_size／sort。省略page=1，未知參數422。
- Marketplace排序last_listed_at DESC,id DESC；Garage created_at DESC,id DESC。兩者併發改變不承諾跨頁固定Snapshot；UI可重載，不能偷偷只下載第一頁稱全部。
- 同車有效履歷／版本／Ledger集合：page>1必帶snapshot_row_version（VersionString）；page=1可省略或帶來驗。一次Primary Statement驗可見性、revision與取得該頁／total；不符409 COLLECTION_CHANGED，UI丟棄舊頁從1重讀。回vehicle_row_version供後頁使用。
- 不能用舊Read Transaction／Replica／Cache繞過下架。Visibility先判，不向不可見對象回revision衝突。這是本輪[D]簡單防跨頁混版，不是新增DB Snapshot表。

## 4. Shared DTO與Public／Owner投影

| 型別 | 完整欄位（皆!；僅標null者可空） |
| --- | --- |
| CurrentUser | id:UUID、email:string（只本人canonical Email；不是Email已驗證）。 |
| ImageRef | id:UUID、url:string（只E23受控相對URL）、media_type（image/jpeg、image/png或image/webp）、byte_size:int、width_px:int、height_px:int、processed_at:Timestamp。沒有Private key／原始檔名。 |
| VehicleCard | id:UUID、vin_suffix:string長6、brand、model、model_year:int、current_mileage_km:int、price_twd:int、main_image:ImageRef或null、last_listed_at:Timestamp。只已上架。 |
| VehiclePublic | VehicleCard全部欄位＋description:string、is_listed:true、row_version:VersionString、effective_event_count:int、mileage_was_lowered:bool。 |
| VehicleOwner | id:UUID、owner_user_id:UUID、vin:string長17、brand、model、model_year、current_mileage_km、description、price_twd:int或null、is_listed:bool、last_listed_at:Timestamp或null、main_image:ImageRef或null、row_version:VersionString、effective_event_count:int、mileage_was_lowered:bool、created_at／updated_at:Timestamp。 |
| VersionPublic | id／event_id:UUID、version_no:int、previous_version_id:UUID或null、maintenance_date:Date、mileage_km:int、description、correction_reason:string或null、source固定owner_self_reported、source_label固定「車主自行申報・未經機構驗證」、submitter_label固定「車主自行申報」、submitted_at:Timestamp、is_effective:bool。 |
| VersionOwner | VersionPublic＋submitted_by_user_id:UUID；不加Email。 |
| EventPublic／EventOwner | id:UUID、current_version:相應Version DTO、version_count:int；沒有把每版算成一次維修。 |
| MileagePublic | id:UUID、previous_mileage_km:int、new_mileage_km:int、reason:string、created_at:Timestamp；只下修，故前值非null。 |
| MileageOwner | id／actor_user_id:UUID、previous_mileage_km:int或null、new_mileage_km:int、reason:string或null、vehicle_revision:VersionString、created_at:Timestamp；初始／增加／降低皆可讀。 |
| VehicleMutation | vehicle:VehicleOwner、changed:bool。 |
| EventMutation | event:EventOwner、vehicle_row_version:VersionString、created_version_id:UUID。 |
| ImageMutation | image:ImageRef、status固定ready、vehicle_row_version:VersionString、changed固定true。 |

Public DTO禁止email／owner_user_id／完整vin／Password／Session／提交者User ID；取得本人Session不會讓Public Endpoint自動升級投影。E12／13／15／17／20完全不建立Cookie身分，其session.activity固定not_applicable，不能藉Meta揭露登入狀態；E23例外作optional Identity但永不Touch。Owner Route若是非Owner，即使已上架也404；請改走Public Route，不Fallback成模糊200。

普通詳情不打包完整時間線：effective_event_count只計E，mileage_was_lowered為Ledger存在下修的衍生bool。後續分頁讀履歷／下修摘要；原文／更正版有清楚is_effective與previous關聯。Owner完整Ledger不是可改刪的Audit CRUD。

Server-only fields：owner_user_id、submitted_by_user_id／actor_user_id、source、id／event_id／previous_version_id的實際關聯、created_at／updated_at／submitted_at／刊登時間、Session User與期限、row_version／vehicle_revision、圖片key／狀態／尺寸。Client可送Path Selector／expected值，不能指定可信欄位的新值；Correction parent由Server在expected current吻合後決定。

## 5. Concurrency、No-op與Idempotency

1. [D] PATCH／listing／主圖Request必有Body或Multipart expected_row_version；成功Mutation回新VersionString。既有車所有Writer鎖同Vehicle，拿鎖後新Statement讀最新資料與驗Owner／version／E；不是只加BEGIN。
2. [D] 更正只要求expected_current_version_id，加入獨立事件不要求全車expected版本；兩者仍同車Lock重讀C／E。所有實際聚合變動遞增Vehicle.row_version、updated_at；No-op不增。
3. 不採If-Match／HTTP ETag作版本協定；送If-Match到Mutation回400 UNSUPPORTED_PRECONDITION，不悄悄忽略。故不使用412；Body版本衝突409。若未來改ETag須另審，不同投影／歷史集合不能亂共用Tag。
4. 兩Tab持v7：A保存成v8，B在鎖後見expected7不符→409，所有有效狀態不變；UI保留B輸入、重載／顯示差異，User重新確認再送，不能自動把expected改8重送。
5. Listing重複同狀態且expected符合→200 changed=false、不洗時間。已成功一次後原Request用舊expected重放可能409，仍沒有第二份刊登；Optimistic Conflict不等於重複副作用。
6. Idempotency是同一Request避免重複生效，Optimistic Lock是拒絕舊版本；本案無通用Idempotency-Key去重。傳入該Header不代表保證，MVP明確400 IDEMPOTENCY_NOT_SUPPORTED，避免Client誤信。
7. 建車Unknown可透過Owner Garage的完整VIN查明是否已有該合成案例；唯一VIN防第二台，但不能靠公開VIN搜尋，不能把他人的重複VIN回成自己的成功。返回已存在錯誤409，User確認自己的車。
8. 補登Event沒有自然唯一鍵；同日／同里程／同描述仍可能是兩次事件，不能自行去重。Unknown時讀Owner事件／版本、保留不明提示，由User核對；無法唯一確認就不自動再POST。本輪不冒稱已保證Exactly Once。
9. Correction Unknown用Event的全部版本查expected parent是否已有後繼；若後繼存在，原parent不能再被直接取代。內容相符仍須核對User意圖，不自動把重試轉成新事件／新末端更正。
10. 照片Unknown讀Owner detail主圖ID／revision確認；舊expected重送只能Conflict或尚未變更後再由User確認，不能無限制再造候選圖。
11. DB已確定Rollback：error.outcome=not_applied；未知Commit：unknown，禁止API／Client盲重送。可重試Deadlock／Serialization只重跑整交易並重驗；Unique／舊版本／非末端衝突不盲重試。
12. Row Lock／Statement／Client timeout秒數需環境配置與量測；任一Client等待期限都不作「已取消Server」保證。B方案120秒deadline是新的CP，不是已接受的Session時間政策。

依據：[PG Read Committed](https://www.postgresql.org/docs/current/transaction-iso.html)、[PG ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html)；本案Lock協定與重送策略是Service責任，未跑實際PG測試。


## 6. Endpoint Inventory暨Auth／CSRF／Touch Policy Matrix

U=app_users、S=auth_sessions、B=auth_rate_limit_buckets、V=vehicles、E=maintenance_events、R=maintenance_record_versions、M=vehicle_mileage_changes、I=vehicle_images；A=auth_login_attempts 僅Deferred B，不在現行八表。受保護操作另讀U／S，白名單成功後另Touch S。MVP所有Mutation驗來源／CSRF、所有API no-store。表內FR的AC後綴依原完整ID；逐項71 AC覆蓋在§12。

| ID | Method／URL | 功能 | 存取 | CSRF | last_activity | FR／AC | PG／其他儲存 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E01 | GET /api/auth/csrf | CSRF Context取得／必要preauth初始化 | Context／可匿名Bootstrap | 來源必驗，無前置Token | 否 | FR-001；FR-002 AC08；FR-003 AC03 | S／B |
| E02 | POST /api/auth/register | 建立合成展示帳號、手動登入 | 有效preauth | 是 | 否 | FR-001 AC01～05；FR-002 AC08 | U／S／B |
| E03 | POST /api/auth/login | 憑證驗證／新列Rotation，無Attempt ID | 有效Context | 是 | 不Touch舊列 | FR-002 AC01～08 | U／S／B |
| E04 | POST /api/auth/logout | 確認撤銷當前Context並清Cookie | Context及Logout專用失效例外 | 是 | 否 | FR-003 AC01～05 | S |
| E05 | GET /api/auth/me | 查目前身分；不是Keep-alive | Optional Session | 否 | 否 | FR-002 AC01／03～07；FR-003 AC02／04／05 | U／S |
| E06 [Deferred] | PUT /api/auth/login-attempts/{attempt_id}/cancellation | 未來指定取消，非MVP | Deferred | Deferred | 否 | 非現行AC唯一證據 | A僅未來提案 |
| E07 | GET /api/me/vehicles | 分頁完整車庫 | Authenticated；只自己的車 | 否 | 成功主動讀取是 | FR-004 AC01～03 | V／I／E／R／M |
| E08 | POST /api/vehicles | 建立未上架車及初始C Ledger | Authenticated | 是 | 成功是 | FR-005 AC01～05 | V／M |
| E09 | GET /api/me/vehicles/{vehicle_id} | Owner管理完整詳情 | Owner-only | 否 | 成功主動讀取是 | FR-004 AC03；FR-006 AC01；FR-008 AC02；FR-010 AC03／07 | V／I／E／R／M |
| E10 | PATCH /api/vehicles/{vehicle_id} | 基本資料／售價／目前C及下修確認 | Owner-only | 是 | 成功含合規No-op是 | FR-006 AC01／02／04～07 | V／E／R／M |
| E11 | PUT /api/vehicles/{vehicle_id}/listing | 指定上架／下架狀態 | Owner-only | 是 | 成功含合規No-op是 | FR-007 AC01～03；FR-008 AC01～05 | V／I |
| E12 | GET /api/marketplace/vehicles | 公開品牌／型號搜尋、固定12筆 | Public | 否 | 否 | FR-009 AC01～04 | V／I |
| E13 | GET /api/vehicles/{vehicle_id} | 固定Public投影，Owner不升級 | Public；只已上架 | 否 | 否 | FR-010 AC01／03／04／06／07；FR-008 AC01／04／05 | V／I／E／R／M |
| E14 | POST /api/vehicles/{vehicle_id}/maintenance-events | 任意順序補登新Event＋初版 | Owner-only | 是 | 成功是 | FR-011 AC01／04／06～08 | V／E／R |
| E15 | GET /api/vehicles/{vehicle_id}/maintenance-events | Public有效履歷分頁 | Public；只已上架 | 否 | 否 | FR-010 AC01／02／05；FR-008 AC01／05 | V／E／R |
| E16 | GET /api/me/vehicles/{vehicle_id}/maintenance-events | Owner有效履歷分頁 | Owner-only | 否 | 成功主動讀取是 | FR-010 AC01／02／05；FR-011 AC06／07 | V／E／R |
| E17 | GET /api/vehicles/{vehicle_id}/maintenance-events/{event_id}/versions | Public原文／全部更正版 | Public；只已上架 | 否 | 否 | FR-010 AC05；FR-013 AC02／06／07 | V／E／R |
| E18 | GET /api/me/vehicles/{vehicle_id}/maintenance-events/{event_id}/versions | Owner完整更正鏈 | Owner-only | 否 | 成功主動讀取是 | FR-013 AC02／06／07／08 | V／E／R |
| E19 | POST /api/vehicles/{vehicle_id}/maintenance-events/{event_id}/corrections | 指定目前末端的完整替代版本 | Owner-only | 是 | 成功是 | FR-013 AC01～08 | V／E／R |
| E20 | GET /api/vehicles/{vehicle_id}/mileage-changes | Public目前C下修摘要 | Public；只已上架 | 否 | 否 | FR-006 AC07；FR-010 AC07 | V／M |
| E21 | GET /api/me/vehicles/{vehicle_id}/mileage-changes | Owner完整C Ledger，只讀 | Owner-only | 否 | 成功主動管理讀取是 | FR-006 AC07；FR-010 AC07 | V／M |
| E22 | POST /api/vehicles/{vehicle_id}/image | 同步受限處理／上傳或替換主照片 | Owner-only | 是，Header在Parser前 | 只有有效主圖切換成功是 | FR-012 AC01～07 | V／I；Private Volume |
| E23 | GET /api/vehicles/{vehicle_id}/images/{image_id} | 目前ready主圖bytes | 已上架Public；未上架僅有效Owner | 否 | 否 | FR-012 AC04／07；FR-008 AC01／05 | V／I；Private Volume |

Public路徑從不因附有效Owner Cookie就改投影或Touch；Owner路徑成功才可Touch，且MVP禁止自動輪詢／預抓它。E23 bytes沒有Owner投影差異，故可共用單一路徑，但每次查current／ready／可見性，任何情況不Touch。所有401／403／404／409／422／429／500／503、尚未完成的圖片工作都不Touch。

**Retry分類（每個Endpoint適用）**：R=安全重讀（GET，資料可能已變；MVP E01只讀／必要preauth初始化，不準備Login Attempt）；W=不可盲重送的業務Mutation；L=Auth Lifecycle需Lock／狀態確認；C=取消可重試但仍需Proof。表列Touch=是的成功回應都可能有§3.2的Touch失敗Metadata；其他不會因Touch失敗新增錯誤。



## 7. Complete Authentication Contracts

本節 E01～05 為方案 A 的 MVP Contract，E06 僅 Deferred Hardening。CP-01～05 繼續有效，CP-06／未知 Login Cookie 排序風險保留。Step 3A 僅實作 E05 匿名分支，其他尚未實作。

所有Cookie Name為__Host-vibicle_session，Secure／HttpOnly／SameSite=Lax／Path=/／無Domain；SID只在指定Set-Cookie，不在JSON。成功新authenticated Max-Age=28800、preauth=900；清除用同Name／Path、Max-Age=0。需要來源檢查的範圍是所有Mutation及E01；普通安全Owner GET不要求Origin／CSRF Header，仍驗Cookie／Ownership／Host／TLS。來源精確PUBLIC_ORIGIN；Origin有值必匹配、缺失才Referer、兩者全缺拒403；Mutation及E01有Sec-Fetch-Site時只接受same-origin。Native Client不偽裝成Browser豁免，需Jar／Token／合法Origin。Cookie重複等歧義400；Header Token長度／base64url嚴格，恆定時間比對。

### E01 — GET /api/auth/csrf

- 無 Path／Query／Body；不提供 purpose=login 或 X-Auth-Attempt-ID 的 MVP 功能。
- 來源／Fetch Metadata及csrf_context Gate必驗，無前置Token；有效Context回同CSRF、不Touch／Set-Cookie，無有效Context才建立15分鐘preauth與必要Cookie。
- 200 Success.data={context_type:preauth|authenticated,csrf_token:string,absolute_expires_at:Timestamp}；Token為32 bytes的canonical base64url，HTTPS／no-store、不Log。
- Error 400歧義、403 SOURCE_NOT_ALLOWED、429 RATE_LIMITED、503 STORE_UNAVAILABLE；不發失敗Cookie。
- PG：B Gate／S Lookup及必要INSERT。Retry=L；未收斂Login時Client不得盲Bootstrap，沒有Attempt準備／Recovery，me匿名不是取消證據。
- Step 3A尚未實作此介面。

### E02 — POST /api/auth/register

- Query／Path無；JSON Body必填email:string、password:string、password_confirmation:string；其餘422。Header Content-Type application/json、Cookie、X-CSRF-Token；有效preauth＋來源＋register Gate。
- 依normalized→PG lower、最終Email1～254；Password與Confirmation完全一致、12～128 Code Points、不trim／截斷／組合規則；Library Argon2id Hash（參數／版本依上游實測）。有效authenticated Context不能直接Register：403 OPERATION_NOT_ALLOWED。
- 201 Success.data=RegistrationResult：status固定registered、next固定manual_login；不回User／憑證。Outcome committed、activity not_applicable。沒有Set-Cookie、不升級Context、不續期preauth。
- Error 409 REGISTRATION_CONFLICT（不回既有帳號資料）、422 VALIDATION_FAILED／PASSWORD_CONFIRMATION_MISMATCH、403 Context／來源／Token、429、413／415、503；皆不Set-Cookie。
- PG：B已獨立Commit；S讀；U短交易INSERT，UNIQUE(email)裁決併發；KDF在長鎖外。註冊201與409仍可能被用於存在性探測，保留AUTH限制，不宣稱完全隱藏。
- Retry=W：Unknown先手動Login／檢查，不盲重建帳號；不能把重複Email當已驗證成功。無Touch失敗路徑。

### E03 — POST /api/auth/login

- 無Path／Query；JSON必填email、password；Header Cookie、X-CSRF-Token、Content-Type application/json。**不要求Login Attempt ID**。
- 有效preauth或authenticated；來源→login Gate→Context／Token→Schema／憑證。不存在User與錯密碼同401 INVALID_CREDENTIALS／Dummy Verify。
- Verify在鎖外；短交易鎖Cookie的舊Context，鎖後新Clock重驗期限／revoked／Token，INSERT全新authenticated SID Hash／獨立csrf_secret／User、created=last=t、absolute=t+8小時並撤銷舊列，同Commit。其他裝置不變。
- 200 Success.data={authenticated:true,user:CurrentUser,csrf_token:string,absolute_expires_at:Timestamp}。Meta為committed／not_touched；確認Commit才Set-Cookie，不Touch舊列。
- Error 401、403 Context／Token／來源、409 AUTH_CONTEXT_CHANGED、422、429、413／415、500／503（含AUTH_BUSY）；所有失敗不Set-Cookie，無Attempt專用錯誤。
- PG U／S／B；Retry=L。Timeout／未確認結果進Uncertain，不自動重送、Bootstrap或普通Logout，不宣稱取消；E05匿名不能證明前一Login結束。
- Step 3A尚未實作Login／Rotation。

### E04 — POST /api/auth/logout

- 無Path／Query／Body；Cookie＋對應X-CSRF-Token＋來源，無Body不需Content-Type。
- 正常authenticated；保留的失效／撤銷authenticated列可用原CSRF作Logout專用確認；有效preauth可Logout。未知／已清理列或過期preauth403，不能略過CSRF。
- 短交易鎖當前可辨識Context，確認／更新revoked_at，確認Commit後204清同Name／Path Cookie；不Touch、不影響其他裝置。重複且可驗證者204，無Body。
- Error 403 CSRF_INVALID／CSRF_CONTEXT_REQUIRED／SOURCE_NOT_ALLOWED、400／422、500／503；不發失敗Cookie，普通401不可代做Logout。
- PG S；Retry=L。同Context可安全重試，身分／Cookie改變不可自動以新Token重送舊Logout。未知Login時Client保持Uncertain，禁止Bootstrap再Logout假稱另一個未知Session也已撤銷；八表Server不提供跨操作取消保證。
- 成功後清Epoch／私有Cache並通知Tabs；Step 3A尚未實作Logout／Auth Coordinator。

### E05 — GET /api/auth/me

- 無Path／Query／Body，不需CSRF Header；Cookie optional，無Token／Owner ID輸入；不Set／Clear Cookie、不Touch，Retry=R。
- 200 Success.data=IdentityResult：authenticated:bool、user:CurrentUser|null、absolute_expires_at:Timestamp|null；兩nullable欄在false時均null。Outcome read_only。
- 缺失／正常失效Session回200匿名；歧義Cookie400。PG Lookup不能完成503 STORE_UNAVAILABLE，不能假裝匿名；不發新preauth。
- PG Q-06新的Primary Statement讀S／U；過期等號拒絕。普通受保護業務仍401，不能照抄me的200匿名。
- 跨Tab通知／focus／pageshow先清／遮蔽，再me／安全CSRF恢復；只接受目前Epoch的Response。此觀測不構成未知Attempt已結束證據。

### E06 [Deferred] — PUT /api/auth/login-attempts/{attempt_id}/cancellation

**非MVP，不實作、不納現行安全驗收的唯一證據。以下保留未來B構想；POST Prepare等修正見API_SCOPE_REVIEW §7。**

- Path attempt_id:UUID；無Query／Body；Cookie＋X-CSRF-Token（可由E01 Recovery取得）、來源；與E01 Recovery共用csrf_context Gate[CP]，60／固定300秒。
- 只作用既有、Cookie匹配parent／result且now<retain_until的Attempt。未知／不屬該Context404，不替任意ID造Tombstone；無Proof／Token403。Attempt ID不是秘密／User Identity。
- 共同鎖序下標cancelled Tombstone、若有result則同交易撤銷它；保留既有completed_at、填cancelled_at，不重設Session期限。Cancel先／Finalize先兩者均須收斂；204只在確認Commit後。
- **不Set-Cookie、不清Cookie、不Touch**；同證明的重複Cancel204。若Verify尚未完，取消後不能發新可用SID；若SID回應晚到則新認證拒絕。
- 204表示指定Login Attempt已取消，不表示原本還有效的authenticated parent也登出。要登出整個受控流程，取消確認後再按E01／E04處理目前Context；不撤銷其他獨立Attempt／裝置。
- Error 400、403、404、422 path錯、429、500／503（unknown不得當成功）。PG A[CP]／S／B，Retry=C；失去Cookie或Record後沒有Proof仍不能假204。
- 本介面與模型未獲核准，不得實作／宣稱現有MVP多了一個可用Endpoint。



## 8. Complete Vehicle／Marketplace／History Contracts

共通Header／Schema／Auth／Error外殼依§3／6／10；本節沒有省略安全要求。所有Owner操作先required Session（失效401），Mutation再來源／CSRF，查不到自己的資源404。每個帶vehicle_id／event_id的Path皆UUID；沒有列出的Query／Body欄位422。成功白名單可能Touch失敗，但保留原成功Status與資料／Meta。

### 8.1 車輛與Marketplace

| ID／Request完整欄位 | 成功Response／PG行為 | 特有Error／Cookie／Retry |
| --- | --- | --- |
| E07 GET車庫：Query page?預設1；無Body／Content-Type／CSRF，required Session。 | 200 Success<Page<VehicleOwner>>，只Session User；page_size20，vehicle_row_version=null；V及需要的I／E／R／M投影，不全量下載再前端分頁。 | 401／422／503及共通錯誤；不Set-Cookie。Touch成功主動讀取；R，空items不是503。 |
| E08 POST建車：JSON vin!、brand!、model!、model_year!、current_mileage_km!；description?預設""；price_twd?可null預設null。 | 201 Success<VehicleOwner>，Location指E09管理詳情；V＋初始M同交易、owner取Session、is_listed=false、row_version="1"、image／last_listed=null，Event count=0。 | VIN衝突409 VIN_CONFLICT不回他人Owner；422輸入、401／403／503；不Set-Cookie。成功可Touch；W，Unknown用自己Garage完整VIN核對。 |
| E09 GET Owner詳情：無Query／Body／CSRF，required Session且Owner。 | 200 Success<VehicleOwner>，單次最新可見管理投影；自己的未上架亦可。 | 非Owner／不存在404 RESOURCE_NOT_FOUND；401、422 path錯、503；不Set-Cookie。Touch主動讀取；R。 |
| E10 PATCH編輯：JSON expected_row_version!；至少一個brand?、model?、model_year?、description?、price_twd?（可null）、current_mileage_km?；mileage_change_reason?、mileage_decrease_confirmed?預設false，條件見下文。 | 200 Success<VehicleMutation>；V Lock／expected／最新E；實際C變更同交易追加M；實際聚合變動遞增版本，No-op changed=false且原版本。 | 409 ROW_VERSION_CONFLICT；422 EMPTY_PATCH／LISTED_PRICE_REQUIRED／MILEAGE_BELOW_EFFECTIVE_HISTORY／MILEAGE_DECREASE_REASON_REQUIRED／MILEAGE_DECREASE_CONFIRMATION_REQUIRED／VALIDATION_FAILED；401／403／404／503；不Set-Cookie，成功含合規No-op可Touch；W。 |
| E11 PUT listing：JSON expected_row_version!、is_listed:bool!，不可帶價格／圖片／其他欄位。 | 200 Success<VehicleMutation>；Owner V Lock＋expected，false→true需有效欄位、正整數價格及current ready主圖；真正上架才更新last_listed，真正狀態變化增revision。重複狀態No-op不洗時間。 | 409版本；422 LISTING_NOT_READY；缺失／故障檔案503 IMAGE_UNAVAILABLE且不假上架；401／403／404／503；不Set-Cookie，成功可Touch；W，讀回後User確認，不盲改expected。 |
| E12 GET Marketplace：Query q?預設""、page?預設1；無Body／CSRF，忽略登入Cookie不升級投影。 | 200 Success<Page<VehicleCard>>，固定12，vehicle_row_version=null；q trim後0～50整段字面包含品牌或型號、不分英文大小寫，%／_不作wildcard；is_listed=true、last_listed DESC,id DESC。 | 422 VALIDATION_FAILED、503；改q回page1，超頁200空；不Set-Cookie／不Touch；R，併發跨頁可漂移。 |
| E13 GET Public詳情：無Query／Body／CSRF，忽略Cookie不升級。 | 200 Success<VehiclePublic>，PG同Statement限定已上架及Public投影／有效事件count／下修flag。沒有履歷count0，UI顯示尚無自行申報紀錄。 | 未上架／不存在一律404，即使是Owner也請用E09；422 path錯、503。no-store、不Set-Cookie／Touch；R。 |

**E08輸入條件**：VIN trim＋upper後17碼A～Z／0～9排除I／O／Q、全平台Unique；品牌／型號／年份／C與描述依§3。price_twd可空，非空必1～100,000,000 TWD嚴格整數；C為0～2,000,000 km嚴格整數。Client不能指定is_listed／Owner／圖／Row Version／時間。建車時沒有既有V可鎖；Unique是併發裁決，不只先查重。

E08的Success Owner物件不是一次性Token；Response遺失後不能因VIN查出任何User的車就回200，僅自己車庫供確認。失敗V／初始M全Rollback，無有效半成品。

**E10省略與null**：省略=維持；price_twd:null只限未上架；description用""清空而非null。VIN、Owner、id、is_listed、last_listed_at、row_version、來源／Event／Image欄皆不在允許清單，連「同值」也422，避免Mass Assignment。

C與其他欄位同Request全成全敗；拿V Lock後比較原C：
- newC>=H且在範圍；原C不變不寫M。提高可附1～500理由；降低必填理由及confirmed=true。
- confirmed=true但不是降低，或沒有實際C改變卻送reason，422 UNEXPECTED_MILEAGE_CONFIRMATION／UNEXPECTED_MILEAGE_REASON。其餘可省略confirmed或用false。
- Ledger存鎖後前值／新C／actor／Server時間／提交後vehicle_revision；更正歷史不代做這一步。
- 無效的已上架價格即使其他欄合法也全拒；下架先E11、再E10清售價，不能在單一PATCH偷改listing。
- No-op仍需目前expected／完整Auth與Validation；過時expected先409，不因「看起來同值」跳過。

**E11下架精確效果**：只改is_listed／updated_at／實際revision，保留價格、目前圖、last_listed_at、維修／Ledger。No-op沒有新刊登。新公開查詢在提交後排除／404，Owner讀取仍可；不保證回收已交付副本。ready Metadata不代表Filesystem永不壞，切換／讀取仍要處理Storage故障。

### 8.2 維修事件、更正版本與C異動

共通HistoryQuery：page?=1、snapshot_row_version?，page>1必填；固定20，按§3.3先判可見性，再判Revision／Query結果。下表所有GET無Body／Content-Type／CSRF。Owner GET可Touch主動讀取；Public GET忽略Cookie／不Touch。

| ID／Request | Success Schema／排序 | 特有Error／Retry／PG |
| --- | --- | --- |
| E14 POST新Event：JSON maintenance_date!、mileage_km!、description!；無expected_row_version，也不接受expected_current_version_id。 | 201 Success<EventMutation>；不設Location（集合不是新Event的單筆URI）；Body回Event／Version ID，以既有E18讀鏈，避免為形式多開GET。新E＋初版R、V版本遞增，C不變。 | 401／403／404；422 MILEAGE_ABOVE_CURRENT／MILEAGE_DATE_CONFLICT／VALIDATION_FAILED；503／500。無Set-Cookie，成功Touch；W，無一般去重。 |
| E15 Public有效E；vehicle_id＋HistoryQuery，僅上架。 | 200 Success<Page<EventPublic>>；有效date DESC、mileage DESC、submitted_at DESC、Version id DESC，與PRD顯示次序一致。 | 404、409 COLLECTION_CHANGED、422、503；R、No Touch。V→E→目前R Join，不查全部舊版本MAX。 |
| E16 Owner有效E；vehicle_id＋HistoryQuery。 | 200 Success<Page<EventOwner>>；與E15同排序／count；未上架可讀。 | 401／404、409／422／503；R、成功主動Touch；V／E／R。 |
| E17 Public versions；vehicle_id／event_id＋HistoryQuery。 | 200 Success<Page<VersionPublic>>；version_no ASC，全部原文／更正版都可翻完，不算多次維修。 | 車／事件不可見或不屬車404；409／422／503；R、No Touch；V／E／R。 |
| E18 Owner versions；同參數。 | 200 Success<Page<VersionOwner>>；同ASC及完整鏈，is_effective由E.current指標導出。 | 401／404／409／422／503；R、成功主動Touch。 |
| E19 POST更正：JSON expected_current_version_id:UUID!、maintenance_date!、mileage_km!、description!、correction_reason!；無一般PATCH／刪除。 | 201 Success<EventMutation>；不設Location；Body回新Version ID並由E18讀鏈；新增完整R、parent=鎖後目前版、version_no+1、E切指標、V增revision，C不變。 | 409 MAINTENANCE_VERSION_CONFLICT；422 MILEAGE_ABOVE_CURRENT／MILEAGE_DATE_CONFLICT／VALIDATION_FAILED；401／403／404／503。無Set-Cookie，成功Touch；W，先讀鏈確認。 |
| E20 Public下修摘要；vehicle_id＋HistoryQuery。 | 200 Success<Page<MileagePublic>>，僅new<previous，vehicle_revision DESC。 | 404／409／422／503；R、不Touch；V／M。 |
| E21 Owner完整M；vehicle_id＋HistoryQuery。 | 200 Success<Page<MileageOwner>>，vehicle_revision DESC；包含初始與增／降，無改刪功能。 | 401／404／409／422／503；R、成功主動管理讀取Touch；V／M。 |

E14／19：mileage嚴格整數0～2,000,000；日期／描述／理由依§3，reason不空。Owner／source／submitted_at由Server設定。所有Path關聯沿E.vehicle_id驗，不能拿別車Event ID當可讀或可更正目標。

**原子Service規則**：Auth／CSRF→BEGIN→Owner Vehicle FOR UPDATE→拿鎖後新Statement讀C／有效集合E→驗候選。新增m需介於嚴格較早日期最大L與嚴格較晚日期最小U且m<=C；缺一側則該側無界。同日各筆不比較先後，但仍各受外部日期L／U約束。Date可早於建車日，不以submit時間／年式推定先後。

E19先驗expected ID等於該Event目前末端，從候選E移除該事件舊有效版、加入完整替代版後再驗；被取代高值退出H，不忽略其他有效值。任何錯誤新R／current切換／V revision均Rollback。Native FK／Unique防錯配與同parent分支；跨日／C與末端協定仍靠共同Service。

每個合法Correction都追加一版，即使數值與文字相同而有理由；它不是管理PATCH的No-op。重複送舊parent至多一成功，其餘409；沒有批次／合併／撤回／刪除／跨車重掛。多個錯值互擋時只回本車可見界線／衝突ID，User依相容順序逐筆改。

**可解釋範例**：C=80,000，01-10=50,000、03-10=70,000，補02-10=60,000可；49,000或71,000拒。02-10另65,000可但75,000仍受03-10界線拒。誤填900,000先被正確70,000版本取代後，H不再含900,000，再由E10明確有理由下修C；E19永不自動降C。

**Rollback／Unknown／Conflict**：422或409且Server已確認無效狀態提交=not_applied；DB Commit傳送後失聯=unknown；資料已Commit但Touch失敗仍201＋成功data／Session Meta。Client Timeout沒有Server結論。新增Event不唯一，不能用「相同內容」自動判已執行，也不能當第二次POST天然冪等。


### 8.3 JSON例（全為合成示意，不是已保存資料）

E08 Request；Cookie／X-CSRF-Token在Header，不放Body：
~~~json
{
  "vin": "VBC12345678901234",
  "brand": "Demo",
  "model": "M1",
  "model_year": 2020,
  "current_mileage_km": 80000,
  "description": "合成展示案例",
  "price_twd": 250000
}
~~~

E08 201 Response例，完整Owner形狀；同一資料的Public接口在尚未上架時是404，不能把這份Body當Public DTO：
~~~json
{
  "data": {
    "id": "11111111-1111-4111-8111-111111111111",
    "owner_user_id": "22222222-2222-4222-8222-222222222222",
    "vin": "VBC12345678901234",
    "brand": "Demo",
    "model": "M1",
    "model_year": 2020,
    "current_mileage_km": 80000,
    "description": "合成展示案例",
    "price_twd": 250000,
    "is_listed": false,
    "last_listed_at": null,
    "main_image": null,
    "row_version": "1",
    "effective_event_count": 0,
    "mileage_was_lowered": false,
    "created_at": "2026-11-04T01:00:00Z",
    "updated_at": "2026-11-04T01:00:00Z"
  },
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "business_outcome": "committed",
    "session": {
      "activity": "touched",
      "requires_revalidation": false,
      "reason": null
    }
  }
}
~~~

E19更正例；需使用真正讀到的目前Version ID，以下UUID僅示意：
~~~json
{
  "expected_current_version_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "maintenance_date": "2026-03-10",
  "mileage_km": 70000,
  "description": "合成保養紀錄，修正里程誤植",
  "correction_reason": "原申報里程誤填，保留原文並追加更正"
}
~~~

若另個案例原C=900000、有效高值已更正成H=70000，E10可明確提出：
~~~json
{
  "expected_row_version": "7",
  "current_mileage_km": 80000,
  "mileage_change_reason": "先更正履歷誤植，再重新申報目前里程",
  "mileage_decrease_confirmed": true
}
~~~

這不是把兩Request原子合併；其中任何版本／界線不符，依其實際Status拒絕。普通JSON Mutation被拒時不改有效資料，已消耗Gate／技術紀錄另按上文處理。



## 9. Image Upload／Access Contract

### E22 — POST /api/vehicles/{vehicle_id}/image

- Path vehicle_id UUID，Query無。Header Cookie、X-CSRF-Token、Content-Type multipart/form-data（含合法Boundary，由Browser／Client Library產生）。required Session、Owner、來源先驗，拒絕前不進昂貴解碼；初始Owner查詢不持V鎖等傳輸。
- Multipart **恰兩part**：file!（單檔bytes）與expected_row_version!（VersionString文字，至多19 ASCII digits）。重複同名part400、未知／缺欄422；不接受image_id／路徑／狀態／其他Metadata／多檔。
- 單檔1～5,242,880 bytes；整體Multipart傳輸預算[D]6 MiB（6,291,456 bytes）、parts=2、part Header預算8 KiB／個；目的為有界接收，不把File上限變成6 MiB。超限413 PAYLOAD_TOO_LARGE，途中串流也計數，不只Content-Length。
- part宣告類型需image/jpeg／image/png／image/webp，且真實格式／解碼吻合；不靠副檔名。其他415 IMAGE_MEDIA_TYPE_UNSUPPORTED／IMAGE_MEDIA_TYPE_MISMATCH；合法格式但損毀／截斷422 IMAGE_DECODE_FAILED。
- 驗單張靜態，寬／高1～6000、總像素<=12,000,000；動畫／多頁422 IMAGE_FRAMES_UNSUPPORTED，尺寸422 IMAGE_DIMENSIONS_INVALID。受限可終止子程序：候選5秒／128 MiB及總併行需部署實測；超工作預算422 IMAGE_PROCESSING_LIMIT，忙碌503 IMAGE_PROCESSOR_BUSY，不假稱所有上限內圖片都能成功。
- 依方向資訊轉正，重編碼同一允許的靜態格式、去EXIF／GPS／XMP／IPTC／非必要文字，輸出也<=5 MiB，超過則422 IMAGE_OUTPUT_TOO_LARGE，不切主圖。畫面中的人臉／車牌不宣稱自動辨識；本平台只用合成／有權示範素材。

**處理／交易**：解析／驗expected基本形態→建立自己的I pending→有界processing／私有Temp→保存全新UUID key最終bytes→短交易V Lock→I Lock／Claim及Lease→重驗Owner／expected／ready所需Metadata→原子切current指標、I ready、V revision遞增→Commit→條件Touch。Decode／File I/O不持長V鎖。每步遵守2B F-04、Claim／Lease／清理協定。

**成功**：200 Success<ImageMutation>，無論首張或替換；此POST是對current主圖的處理／切換操作，不另外增加Create／Replace Endpoint。Meta.outcome=committed、可能Touch失敗但仍200；不Set-Cookie。Response Location指E23新圖，status=ready是完成，不用202／Job Polling。

**Failure／Unknown**：401／403／404、409 ROW_VERSION_CONFLICT、413／415／422、500／503。處理失敗不換pointer／不破壞舊圖／價格／listing；候選I failed或孤立檔可留下待清。PG Commit可能unknown時不能一律說「舊圖未換」；outcome=unknown，Client以E09讀current ID／revision核對，禁止盲重傳。Server確認Rollback才not_applied，仍不表示Filesystem也Rollback。

Retry=W；舊expected重送不會默默覆寫其他更新，但不是通用去重。圖片Metadata狀態pending／processing／failed／deleting／deleted是內部工作模型，**沒有新增可公開輪詢的狀態Endpoint**。若首次傳輸逾時，E09是目前有效結果觀測，無法據此聲稱孤立工作全部不存在。若舊Image URL因切換成404，先重讀E09／E13取得當前Ref，不無限重試舊URL。

### E23 — GET /api/vehicles/{vehicle_id}/images/{image_id}

- 兩Path UUID，Query／Body無；不需CSRF。Session optional：列出時Public可讀；未上架只有效Owner。Cookie無效不能得到Owner權限，Store不能查503而不是假放行。
- 新Primary Statement Join V／I，要求i.vehicle_id=v.id、v.current_image_id=i.id、i.status=ready、is_listed或可信Owner。非current舊圖、跨車Image、未上架非Owner、缺資源一律404；先判可見性，才處理後述傳輸條件。
- 成功200 **原始處理後bytes，不是JSON envelope**；Content-Type為已驗media_type、Content-Length為實際bytes（Gateway不二次變換／壓縮此圖）、X-Content-Type-Options:nosniff、Cache-Control:no-store、X-Request-ID。不回路徑／原檔名、不Set-Cookie／Touch。
- [D] MVP不支援ETag／Last-Modified／304或部分圖；不輸出ETag／Last-Modified／Accept-Ranges。Range忽略，授權通過後回完整200（不206）。If-None-Match／If-Modified-Since／If-Match／If-Unmodified-Since在授權後400 CONDITIONAL_REQUEST_UNSUPPORTED，不先回304／412。舊ETag在下架後仍先404。
- 已授權卻檔案遺失／Storage故障503 IMAGE_UNAVAILABLE，安全JSON Error而非Public Raw fallback；尺寸Metadata與實檔不一致視Storage Integrity Failure，不串不明內容。
- 若已送200 Header後才發生讀取／網路中斷，只能終止串流並讓Client顯示載入失敗，不能在圖片中塞JSON或追改503。Retry=R；在途已授權串流可能於下架後完成，不能追回bytes。實體key只由Server Image UUID在Private Root導出，不可/static/uploads，也沒有未到期即免重驗的Signed URL。

### 9.1 舊圖清理與DB／File邊界

不提供DELETE Image或清理Endpoint。受控Cleaner找非current且Lease失效／工作已中止的候選，V→I共同鎖／Claim、deleting後才刪可信key、確認不存在再deleted，Crash可重試。新圖ready≠current；舊圖成功替換後即使bytes尚在Disk，E23也因不current而404。

DB只能原子切Metadata與pointer，不能Rollback已寫bytes／讓unlink自動恢復；先存新檔、短交易切換、之後清孤立檔是補償策略。Restore／重建要DB＋Private Volume協調，不能由API Contract假裝完成Deployment驗收。失效Token／Lease不能讓晚到工作重選deleting圖；細節沿用Database Design §9。

## 10. Error Handling Specification

### 10.1 Status／Code對照

Attempt／Recovery專用Code僅Deferred B，不由MVP A發出；其他錯誤Profile維持不變。

所有表中Error使用§3.2結構；確定拒絕／Rollback為not_applied，Commit不確定為unknown。欄位格式錯在授權後回安全fields；不回原input／ctx／SQL／完整VIN／其他Owner／Token。404統一RESOURCE_NOT_FOUND，無存在性說明。

| HTTP | 穩定Code（本Profile） | 語意／Client動作 |
| --- | --- | --- |
| 400 | MALFORMED_REQUEST、DUPLICATE_FIELD、AMBIGUOUS_COOKIE、UNSUPPORTED_PRECONDITION、IDEMPOTENCY_NOT_SUPPORTED、CONDITIONAL_REQUEST_UNSUPPORTED | 解析／Header Profile不符；修Request，不能自動當成功。 |
| 401 | AUTHENTICATION_REQUIRED、INVALID_CREDENTIALS | 業務無有效登入或格式有效但Login憑證錯；後者不區分帳號不存在。 |
| 403 | SOURCE_NOT_ALLOWED、CSRF_INVALID、CSRF_CONTEXT_REQUIRED、OPERATION_NOT_ALLOWED、RECOVERY_PROOF_REQUIRED[CP] | 來源／Token／Context流程錯；不Set／Clear Cookie，不自動把舊Mutation套新User。 |
| 404 | RESOURCE_NOT_FOUND | 不存在／Private不可見／跨車關係／Recovery Attempt不屬Cookie同形；不回Owner資訊。 |
| 409 | ROW_VERSION_CONFLICT、MAINTENANCE_VERSION_CONFLICT、COLLECTION_CHANGED、VIN_CONFLICT、REGISTRATION_CONFLICT、AUTH_CONTEXT_CHANGED；[CP] AUTH_OPERATION_PENDING、AUTH_RECOVERY_REQUIRED、AUTH_ATTEMPT_NOT_PREPARED、AUTH_ATTEMPT_REUSED、AUTH_ATTEMPT_CANCELLED、AUTH_ATTEMPT_EXPIRED | 已授權後的唯一性／版本／流程衝突；只回安全details，不自動重寫expected。 |
| 412 | 本Profile不產生 | 不採If-Match；Body版本衝突409，不能同一錯誤有時409有時412。未來改協定另審。 |
| 413 | PAYLOAD_TOO_LARGE | Auth8 KiB／其他JSON32 KiB／Multipart6 MiB／File5 MiB的相應界線；不留下有效半成品。 |
| 415 | UNSUPPORTED_MEDIA_TYPE、IMAGE_MEDIA_TYPE_UNSUPPORTED、IMAGE_MEDIA_TYPE_MISMATCH | JSON／Multipart／實際檔案格式不符，不能單信副檔名。 |
| 422 | VALIDATION_FAILED、EMPTY_PATCH、PASSWORD_CONFIRMATION_MISMATCH、LISTED_PRICE_REQUIRED、LISTING_NOT_READY、MILEAGE_ABOVE_CURRENT、MILEAGE_BELOW_EFFECTIVE_HISTORY、MILEAGE_DATE_CONFLICT、MILEAGE_DECREASE_REASON_REQUIRED、MILEAGE_DECREASE_CONFIRMATION_REQUIRED、UNEXPECTED_MILEAGE_CONFIRMATION、UNEXPECTED_MILEAGE_REASON、IMAGE_DECODE_FAILED、IMAGE_FRAMES_UNSUPPORTED、IMAGE_DIMENSIONS_INVALID、IMAGE_PROCESSING_LIMIT、IMAGE_OUTPUT_TOO_LARGE | 具體欄位／業務規則；日期／C衝突在最新資料驗證，不用此Status掩蓋舊Version衝突。 |
| 429 | RATE_LIMITED | 三Scope Fixed Window第N＋1次起；Retry-After整秒向上取整至少1，保留Burst／NAT風險。 |
| 500 | INTERNAL_ERROR | 非預期Server錯，沒有Stack Trace；僅已確定Rollback可not_applied，無法判定就是unknown。 |
| 503 | STORE_UNAVAILABLE、AUTH_BUSY、IMAGE_PROCESSOR_BUSY、IMAGE_UNAVAILABLE、CONCURRENCY_BUSY、COMMIT_OUTCOME_UNKNOWN、REVISION_EXHAUSTED | Store／資源／Lock等待不可用；Commit已成功只Touch失敗不可用此Code否認成功，按200／201 Meta分開。 |
| 405 | METHOD_NOT_ALLOWED | 既有Resource未提供方法，例如PATCH Version／DELETE履歷；Allow只列支持方法，不暗加功能。 |

details白名單：ROW_VERSION_CONFLICT={expected_row_version,current_row_version}；MAINTENANCE_VERSION_CONFLICT={event_id,current_version_id}；COLLECTION_CHANGED={current_row_version}；里程規則可回同車effective_max_mileage_km／lower_bound_km／upper_bound_km與conflict_event_ids；[CP]Auth流程可回Cookie已授權的attempt_id。其餘null，fields只含安全欄位名稱與Code／訊息；不回被碰撞VIN／Email值或其Owner。

### 10.2 錯誤優先順序

1. TLS／Host／傳輸大小／歧義Header等廉價檢查；405／Malformed不查資源存在性。Source policy適用所有Mutation與E01；一般安全GET只Host／TLS、無任意CORS。
2. 來源／Fetch Metadata失敗先403；Auth E01／E02／E03到達Gate後先固定窗原子計數、Commit。超限429先於CSRF／Credential；未通過CSRF亦消耗已到Gate額度，不能在回Error時Rollback它。
3. Context／required Identity：Protected無authenticated先401、不查私人物件；Register／Login缺流程Context403。普通Owner GET不要求CSRF／Origin Header，Cookie／Ownership仍每次判定。
4. Mutation Header CSRF、Body／Query／Path形態、Ownership與最新業務規則。Body不可在CSRF前無界解析；Path格式不合法可422，無須假查UUID。
5. 存取已授權才能回版本衝突、里程界線等；Public／Private Query可見性與讀取同Statement。Conditional Image Header必在E23可見性後處理，避免304旁路。
6. DB查詢／認證Store故障503，不能把例外轉[]／404／me匿名。成功Commit後Touch錯只改成功Meta；Client沒有Response時維持Unknown，不能自行推論Server Code。

### 10.3 Fixed Window與安全Response

[B] login20／固定300秒、register10／固定3600秒、csrf_context60／固定300秒；UTC Epoch對齊、canonical來源IP的HMAC摘要、所有Worker同Policy／Secret／PG Primary、Counter飽和N＋1。Cookie／Email存在性不影響來源額度。Caddy忽略客戶端偽造XFF，ASGI只信受控Peer，API不直接公開。Counter原子UPDATE不是Session Touch的UPSERT許可。

Source先拒者不進Gate；Gate一旦接受計數不因憑證／Validation／後續交易失敗退還。429不回Account是否存在，不永久鎖帳；Window交界可短時Burst，NAT共額／IPv6輪替／Botnet殘餘風險保留。沒有新增Redis。

API錯誤與動態資料首次no-store；禁止Cookie／CSRF／Password／原Validation Payload／完整VIN進Log，只有安全Request ID／資源關聯ID／分類。無任何錯誤Response自動發新登入Cookie。5xx／Network Error不自動重送Auth／POST；只有讀取可依有限退避重讀，仍要新授權。



## 11. Complete Request Lifecycle Sequence Diagrams

Browser／Cookie Jar在Client；Caddy為TLS入口，Router／Dependencies、Service、Repository／SQLAlchemy是**同一API Process的內部呼叫**，不是獨立Microservices。API到PG為私有DB連線，到Volume為本機受控I/O。圖中省略部分函式return，HTTP一律經Router→Caddy回Browser，不存在直接Public PG／File服務。Jar箭頭是同一次Browser Request自動附Cookie的組成，不是額外HTTP Request或獨立網路Process。

### 11.1 A：Login後建立車輛

~~~mermaid
sequenceDiagram
    actor U as 使用者
    participant B as Browser React
    participant J as Browser Cookie Jar
    participant G as Caddy TLS
    participant D as FastAPI Router／Dependencies
    participant S as Service
    participant R as Repository／SQLAlchemy
    participant P as PostgreSQL
    U->>B: 送出登入意圖
    B->>B: Lifecycle Lock，清舊Epoch資料
    B->>G: E01，同Origin取得CSRF
    G->>D: 內網轉送
    D->>S: 來源／Gate／Context準備
    S->>R: 讀Context／必要preauth
    R->>P: 短交易Commit
    D-->>G: CSRF Token；必要時Cookie
    G-->>J: 僅新Context時Set-Cookie
    G-->>B: CSRF Token
    B->>B: 保存非秘密Pending標記
    J->>G: E03自動附Context Cookie
    B->>G: Email／Password＋CSRF
    G->>D: Login
    alt 來源／Context／CSRF不符
        D-->>G: 403，無登入／Cookie變更
        G-->>B: 拒絕，不送建車
    else 安全檢查通過
        D->>S: Argon2 Verify／Dummy，鎖外
        alt 憑證不符
            S-->>D: 同一401結果
            D-->>G: 無新Cookie／Session
            G-->>B: 登入失敗，不建車
        else 憑證符合
        S->>R: 短交易鎖舊Context、鎖後重驗
        R->>P: 新Session／撤銷舊列，同Commit
        D-->>G: 200 User／新CSRF＋Set-Cookie
        G-->>J: 新Session Cookie
        G-->>B: 確認登入，釋放Lock
        U->>B: 合成VIN與建車資料
        J->>G: E08附Cookie
        B->>G: E08 JSON＋CSRF
        G->>D: 新Session判定／來源／CSRF
        D->>S: 可信User與允許欄位
        S->>R: BEGIN，INSERT V＋初始M
        R->>P: 唯一VIN裁決
        alt 唯一性／DB失敗
            R->>P: 確認Rollback或Commit不明
            D-->>G: 409或503，標明outcome
            G-->>B: 不假顯示已建／未建
        else Commit成功
            R->>P: COMMIT
            S->>R: 另短交易條件Touch Session
            R->>P: 鎖後Clock檢查，不復活
            D-->>G: 201 VehicleOwner＋Session Meta，無Cookie
            G-->>B: 接受目前Epoch結果
        end
        end
    end
~~~

正常User之後在E07／09看新車；非Owner不存在於Create Body。若Login Commit結果未知，保持Uncertain、不進建車，不能靠一次me匿名自動重登。VIN衝突不洩漏Owner；Touch失敗不否認V／M已Commit。本圖是MVP A的目標流程；Step 3A僅匿名E05，Login／建車均未實作。

### 11.2 B1：補登歷史維修

~~~mermaid
sequenceDiagram
    participant B as Browser React
    participant J as Cookie Jar
    participant G as Caddy
    participant D as Router／Dependencies
    participant S as Service
    participant R as Repository／SQLAlchemy
    participant P as PostgreSQL
    B->>B: 記Epoch，準備歷史date／m／description
    J->>G: E14附Cookie
    B->>G: POST E14＋CSRF
    G->>D: 受控Header／Body流程
    alt 未登入／CSRF失敗
        D-->>G: 401／403，不寫Event
        G-->>B: 重驗／修正流程，不Touch
    else 有效Identity／Token
        D->>S: User＋候選
        S->>R: BEGIN，查自己的V FOR UPDATE
        R->>P: Vehicle Row Lock
        alt 非Owner／不存在
            R->>P: ROLLBACK
            D-->>G: 404
            G-->>B: 無他人資料
        else 自己的V
            S->>R: 下一Statement讀最新C／E／日期界線
            R->>P: 當前有效版本Query
            S->>S: m<=C、L<=m<=U、同日／Date規則
            alt 另一補登先Commit使候選衝突或DB失敗
                R->>P: ROLLBACK或辨識Commit unknown
                D-->>G: 422或503＋outcome
                G-->>B: 不自動再POST
            else 合法
                S->>R: 新E＋初版R＋V revision
                R->>P: COMMIT，C不變
                S->>R: 另短交易Touch
                D-->>G: 201 EventMutation＋Meta
                G-->>B: 更新有效時間線
            end
        end
    end
~~~

例如兩筆各自對舊E合法但合併倒退：同車鎖後重新查界線，第二方拒絕；不是只鎖各自新Event。圖的Permission／DB分支與成功分支使用同一Service協定。

### 11.3 B2：針對目前版本更正錯誤里程

~~~mermaid
sequenceDiagram
    participant B as Browser React
    participant J as Cookie Jar
    participant G as Caddy
    participant D as Router／Dependencies
    participant S as Service
    participant R as Repository／SQLAlchemy
    participant P as PostgreSQL
    J->>G: E19 Cookie
    B->>G: 完整替代值／理由／expected current＋CSRF
    G->>D: Auth／來源／CSRF／Schema
    D->>S: 本Request可信User
    S->>R: BEGIN，自己的V FOR UPDATE
    R->>P: 鎖V，再讀Event目前指標
    alt 非Owner／Event不屬該車
        R->>P: ROLLBACK
        D-->>G: 404，無新Version
        G-->>B: 拒絕
    else Owner／歸屬正確
        alt expected current已被另一更正取代
            R->>P: ROLLBACK
            D-->>G: 409 MAINTENANCE_VERSION_CONFLICT
            G-->>B: 保留輸入，重讀鏈，不自動接新末端
        else 仍為有效末端
            S->>R: 新Statement讀E，排除被改事件舊版
            R->>P: 最新C／有效里程界線
            S->>S: 加入新候選驗整體，原文不改
            S->>R: INSERT R＋更新E指標／V版本
            R->>P: COMMIT或確認Rollback／unknown
            alt 提交成功
                S->>R: 短Touch
                D-->>G: 201，C不變
                G-->>B: 只當一次有效事件，原文可追
            else DB結果未確認
                D-->>G: 503 outcome=unknown，無Cookie
                G-->>B: E18讀鏈核對，禁止盲重送
            end
        end
    end
~~~

跨日／m>C錯誤在INSERT前422＋Rollback；不能為了解除高值而忽略其他仍有效Event。Permission／CSRF若更早失敗也不會走到V鎖。

### 11.4 B3：更正後有理由下修目前C

~~~mermaid
sequenceDiagram
    participant B as Browser React
    participant J as Cookie Jar
    participant G as Caddy
    participant D as Router／Dependencies
    participant S as Service
    participant R as Repository／SQLAlchemy
    participant P as PostgreSQL
    B->>B: E09讀最新revision，User確認下修
    J->>G: E10 Cookie
    B->>G: PATCH C／理由／confirmed／expected＋CSRF
    G->>D: 驗Identity／來源／Token
    alt 認證／CSRF失敗
        D-->>G: 401／403
        G-->>B: 不改C／M
    else 通過
        D->>S: User與候選C
        S->>R: BEGIN，Owner V FOR UPDATE
        R->>P: Lock＋expected比較
        alt 非Owner或版本已變
            R->>P: ROLLBACK
            D-->>G: 404或409
            G-->>B: 不覆寫新狀態
        else Owner且版本吻合
            S->>R: 新Statement計H，只取各Event current
            R->>P: H及鎖後原C
            alt 新C低於H／無理由／未確認
                R->>P: ROLLBACK
                D-->>G: 422，先更正仍有效衝突
                G-->>B: 不以已被取代高值阻擋
            else 合法下修
                S->>R: UPDATE C／revision＋INSERT M前後值
                R->>P: COMMIT
                S->>R: 另短交易Touch
                D-->>G: 200已保存；Touch失敗仍保留事實
                G-->>B: 展示下修摘要，必要時重驗
            end
        end
    end
~~~

C更新和新履歷同時發生時都鎖同V；先提交78,000有效事件後，75,000的下修會因stale revision／H拒絕。E19把誤填高值退出E後才可合法下修，不自動聯動兩個Request。

### 11.5 C：Owner上架，Visitor搜尋／詳情／照片

~~~mermaid
sequenceDiagram
    participant B as Browser React（Seller／Visitor）
    participant J as 各自Cookie Jar
    participant G as Caddy
    participant D as Router／Dependencies
    participant S as Service
    participant R as Repository／SQLAlchemy
    participant P as PostgreSQL
    participant F as Private Image Storage
    B->>G: Seller E11 is_listed=true／expected＋CSRF
    J->>G: Seller Cookie
    G->>D: Auth／來源／Token
    D->>S: 可信Seller User
    S->>R: BEGIN，Owner V Lock／新Statement讀主圖
    R->>P: Owner／revision／price／ready檢查
    alt 非Owner
        R->>P: ROLLBACK
        D-->>G: 404
        G-->>B: 無修改
    else stale revision或DB／必要Storage失敗
        R->>P: ROLLBACK或標記unknown
        D-->>G: 409或503
        G-->>B: 不假顯示上架成功
    else 資料完整
        S->>R: 狀態真轉移才設last_listed／增revision
        R->>P: COMMIT
        S->>R: 另短交易Touch
        D-->>G: 200 VehicleMutation，無Cookie
        G-->>B: Seller確認
    end
    B->>G: Visitor E12 q／page，無需登入
    G->>D: Public Policy，不Touch
    D->>S: 搜尋
    S->>R: 已上架／包含／12筆／固定排序
    R->>P: Primary Query
    D-->>G: 200 Public cards，no-store
    G-->>B: Visitor選車
    B->>G: E13 Public detail
    G->>D: Public Route
    D->>S: 固定Public投影
    S->>R: 同Statement驗已上架
    R->>P: V／有效count／下修flag／image ref
    D-->>G: 200或下架後404
    G-->>B: 無完整VIN／Email
    B->>G: E23 image UUID URL
    G->>D: 每次重新驗讀圖權限
    D->>S: current／ready／visibility
    S->>R: Primary Join
    R->>P: 查主圖與車輛最新狀態
    alt 已下架且非Owner／已替換舊圖
        D-->>G: 404，不能先304
        G-->>B: 不取File，UI移除或占位
    else 可讀
        S->>F: 由可信UUID key讀處理後bytes
        F-->>S: bytes或故障
        D-->>G: 200 bytes或503，no-store
        G-->>B: 圖片或占位，不Public Raw fallback
    end
~~~

Seller與Visitor使用不同裝置／Jar，圖把同類Browser合併畫，不代表同Tab同時兩個登入。E13箭頭省略部分Gateway轉送但所有HTTP仍經Caddy。沒有維修紀錄也可上架，照片／價格缺失則不行；Visitor讀取不延長任何登入。深層SPA URL由Web交付Shell，/api錯誤不可Fallback成HTML成功。



## 12. API-to-Requirement Traceability

每行是一個**現行有效AC**，不是只用FR整組模糊覆蓋。E06 Deferred；MVP依A及API_SCOPE_REVIEW的SR-T01～14保留驗收，不表示已通過或可刪需求。四個停用AC（FR-006-AC03、FR-011-AC02／03／05）不進有效矩陣，也不恢復其規則。

非API責任：UI-DISCLOSURE＝合成展示／未驗證／無真實交易文案；UI-STATE＝Epoch／BroadcastChannel／焦點／BFCache先遮蔽與5秒通知清理；UI-ACTIVITY＝不輪詢／預抓Owner讀取；UI-HISTORY＝完整分頁／原文鏈／來源／下修標記；UI-ERROR＝成功、空、失敗、Unknown分開；WEB-DEEP＝SPA深層路由與/api不Fallback；SEC-STORE＝Hash／秘密與Log；OPS-PERSIST＝DB／照片Volume／重建／備份；OPS-TLS＝DNS／HTTPS／Caddy／可信Proxy。這些不能因不屬Endpoint而刪掉。

| Acceptance Criteria | API | 非API責任 | 未來測試 |
| --- | --- | --- | --- |
| FR-001-AC01 | E02/E03 | SEC-STORE | T01/T02 |
| FR-001-AC02 | E02/E03 | SEC-STORE | T03 |
| FR-001-AC03 | E02 | UI-ERROR/SEC-STORE | T01/T35 |
| FR-001-AC04 | E02 | UI-DISCLOSURE | T02/T15 |
| FR-001-AC05 | E02/E03/E07 | UI-DISCLOSURE | T02 |
| FR-002-AC01 | E03/E05/E07 | UI-STATE | T04/T28 |
| FR-002-AC02 | E03 | SEC-STORE | T04 |
| FR-002-AC03 | E05/E07/E10 | UI-ERROR | T06/T25 |
| FR-002-AC04 | E05/E07/E10 | UI-STATE | T25 |
| FR-002-AC05 | E01/E05/E07/E09/E12/E23 | UI-ACTIVITY | T25/T26 |
| FR-002-AC06 | E03/E05 | UI-STATE／Uncertain；另依Scope Review SR-T01～14 | T28/T30 |
| FR-002-AC07 | E01/E05 | UI-STATE | T28/T32 |
| FR-002-AC08 | E01/E02/E03 | OPS-TLS | T05/T28 |
| FR-003-AC01 | E04/E05/E07 | UI-STATE／Uncertain；另依Scope Review SR-T01～14 | T28 |
| FR-003-AC02 | E04/E05 | UI-STATE | T28 |
| FR-003-AC03 | E01/E04/E05 | UI-STATE／Uncertain；另依Scope Review SR-T01～14 | T30 |
| FR-003-AC04 | E04/E05/E07 | UI-STATE | T28 |
| FR-003-AC05 | E04/E05 | UI-STATE／Uncertain；另依Scope Review SR-T01～14 | T28/T30 |
| FR-004-AC01 | E07/E09 | — | T06 |
| FR-004-AC02 | E07 | UI-ERROR | T02/T27 |
| FR-004-AC03 | E07/E08/E09/E10/E11 | — | T08/T09/T13 |
| FR-005-AC01 | E08 | — | T06/T08 |
| FR-005-AC02 | E08/E12/E13/E23 | — | T06/T24 |
| FR-005-AC03 | E08 | — | T07 |
| FR-005-AC04 | E08 | UI-ERROR | T07/T08 |
| FR-005-AC05 | E08/E13 | UI-DISCLOSURE | T15 |
| FR-006-AC01 | E09/E10 | — | T09/T10 |
| FR-006-AC02 | E10 | — | T06 |
| FR-006-AC04 | E10/E11/E22 | UI-ERROR | T09/T23 |
| FR-006-AC05 | E10 | — | T10/T12 |
| FR-006-AC06 | E10/E14/E19 | — | T10/T11/T19 |
| FR-006-AC07 | E10/E13/E20/E21 | UI-HISTORY | T10/T19/T21 |
| FR-007-AC01 | E11/E12/E13/E15 | UI-HISTORY | T12/T13 |
| FR-007-AC02 | E11 | — | T06/T12 |
| FR-007-AC03 | E11/E12 | UI-ERROR | T13 |
| FR-008-AC01 | E11/E12/E13/E15/E17/E20/E23 | — | T24 |
| FR-008-AC02 | E09/E11/E16/E18/E21/E23 | — | T24 |
| FR-008-AC03 | E11 | UI-DISCLOSURE | T13 |
| FR-008-AC04 | E13/E15/E17/E23 | UI-STATE | T24/T28 |
| FR-008-AC05 | E11/E13/E23 | OPS-TLS/UI-STATE | T24/T28 |
| FR-009-AC01 | E12/E13/E23 | UI-HISTORY | T14/T24 |
| FR-009-AC02 | E12 | — | T14 |
| FR-009-AC03 | E11/E12 | UI-STATE | T13/T14 |
| FR-009-AC04 | E12 | UI-ERROR | T14/T27 |
| FR-010-AC01 | E13/E15 | UI-HISTORY | T12/T15 |
| FR-010-AC02 | E15/E16 | UI-HISTORY | T16/T20 |
| FR-010-AC03 | E09/E13/E15/E17/E20/E23 | — | T06/T15 |
| FR-010-AC04 | E13/E15/E23 | WEB-DEEP/UI-ERROR | T24/T27/T28 |
| FR-010-AC05 | E15/E16/E17/E18 | UI-HISTORY | T18/T20 |
| FR-010-AC06 | E02/E07/E09/E12/E13 | UI-DISCLOSURE | T15 |
| FR-010-AC07 | E13/E20/E21 | UI-HISTORY | T19/T21 |
| FR-011-AC01 | E14 | — | T05/T06 |
| FR-011-AC04 | E14/E15/E16 | UI-HISTORY | T15/T16 |
| FR-011-AC06 | E14 | — | T16/T17 |
| FR-011-AC07 | E10/E14/E19 | UI-ERROR | T11/T16 |
| FR-011-AC08 | E14/E19/E17/E18 | UI-HISTORY | T18/T20 |
| FR-012-AC01 | E22/E23 | — | T22 |
| FR-012-AC02 | E22 | — | T06/T22 |
| FR-012-AC03 | E09/E22/E23 | — | T23 |
| FR-012-AC04 | E09/E22/E23 | OPS-PERSIST | T24 |
| FR-012-AC05 | E22 | OPS-PERSIST | T22 |
| FR-012-AC06 | E22/E23 | UI-DISCLOSURE | T22 |
| FR-012-AC07 | E22/E23 | OPS-TLS | T23/T24 |
| FR-013-AC01 | E19 | — | T05/T06/T18 |
| FR-013-AC02 | E17/E18/E19 | UI-HISTORY | T18/T20 |
| FR-013-AC03 | E19/E10/E14 | — | T16/T19 |
| FR-013-AC04 | E19 | UI-ERROR | T18 |
| FR-013-AC05 | E10/E19 | UI-HISTORY | T19 |
| FR-013-AC06 | E15/E16/E17/E18 | UI-HISTORY | T20/T24 |
| FR-013-AC07 | E17/E18/E19 | UI-HISTORY | T18/T20 |
| FR-013-AC08 | E18/E19 | UI-ERROR | T18/T34 |

NFR也保留：DEP-01～03需Docker Build／Run、獨立API、Domain／DNS／HTTPS與可重現環境；REL-03需重建／Restore且失效所有Session／Attempt；PERF-01用原100車／500有效事件及更正鏈測量，不恢復2秒SLA；SEC-01～09／DAT-01～05／MNT／OBS依上游與本測試矩陣。此處沒有實作或替部署驗收背書。



## 13. API Verification Plan（全部未執行）

Unit驗純規則／Schema，Integration連實際PG／Store及隔離File目錄，Concurrency至少兩個獨立DB連線／多Worker控制先後，Browser E2E驗Cookie／來源／UI／Cache；不能用單執行緒Mock證明鎖或Browser行為。Deployment檢查Docker／DNS／HTTPS／Volume另留證據，不以API JSON測試取代。

| ID | 層級 | 操作 | 預期／重點 |
| --- | --- | --- | --- |
| T01 | Unit | StrictInt／bool／VersionString／Date／Password Code Point邊界；unknown欄位／重複Key | 小數／bool當km、錯型別／null／溢位拒絕；12／128字元可，不trim；時間用Taipei今日 |
| T02 | Integration | E01→E02合法Register，再直接E07；手動E03後E07 | 201註冊不登入／無新SID；之前401，Login後自己Garage200空 |
| T03 | Concurrency＋Integration | 同canonical Email兩連線Register，混大小寫／Unicode／空白 | 最多一User，另一409；PG lower／normalized一致、無Password／既有資料外洩 |
| T04 | Integration | E03有效格式，不存在User／錯Password／正確Password | 同401形狀與Dummy成本路徑；成功新SID及Secret，不影響另一裝置 |
| T05 | Integration＋Browser E2E | 所有Mutation含MVP Auth（不含Deferred E06），Cookie有但Token缺／錯／另一Context；跨站／同Site不同Origin | 403且無業務／登入副作用；Gate可計數；Native明確Origin＋Jar＋Token成功 |
| T06 | Integration | A登入對B車／Event／Version／Image操作；Body偽造Owner／source | Owner Route404／缺登入401；額外可信欄位422，不修改B；Public永不升級VIN／Email |
| T07 | Concurrency | 兩連線同VIN trim／upper後POST E08 | 一201、一409 VIN_CONFLICT；不回另一Owner；不能產生兩台 |
| T08 | Integration fault | E08 V已INSERT時讓初始M／Commit失敗 | 確認Rollback則兩者皆無；Commit不明標unknown，不能當空Garage正常 |
| T09 | Concurrency | 兩分頁持相同expected E10／E11／E22 | 實際首寫後另一409，無默默覆寫；合規No-op不增版本／Ledger |
| T10 | Integration | E10 C下修缺理由／未確認／低於H／合法；同時價格無效 | 422或合法200＋M前後值；部分欄位失敗全Rollback，下修摘要可見 |
| T11 | Concurrency | C=80000／H=70000，A降75000、B插78000有效歷史 | 共同V鎖後至少一操作拒；不能Commit C<H |
| T12 | Integration | 缺價格／ready主圖上架，之後補齊，另測無維修紀錄上架 | 422保持未上架；完整則200，E15空集合不暗示無事故 |
| T13 | Integration | 相同listing重複、下架重複、重新上架、文字／更正更新 | No-op changed=false不洗時間；真正再上架更新時間；下架保留價／圖／歷史 |
| T14 | Integration | 13台以上車，E12大小寫、50／51字元、空白、literal %_、超頁 | 每頁12／固定排序／不搜VIN；超長422、空白全部、超頁200空，無未上架 |
| T15 | Integration＋Browser E2E | JSON allowlist／Public與Owner對照、來源／合成提示 | Public無完整VIN／Email／Author ID；Owner完整VIN；來源固定、不宣稱機構認證／真實交易 |
| T16 | Unit＋Integration | 歷史1900／未來／早於建車、L/U、同日高低值、m>C | 按候選E接受／422，與submitted順序無關，C不自動改 |
| T17 | Concurrency | 各對原E合法的02-10=65000與02-20=60000同時補登 | 第一提交後第二鎖後重讀最新E，拒絕合併倒退 |
| T18 | Concurrency＋Integration fault | 兩分頁更正同parent、插R後令切pointer失敗 | 最多一201其餘409；Rollback原文／current不變、無分叉／自環／跨車 |
| T19 | Integration | 有效900000誤值更正70000，再由E10有理由降C | 舊版保留不計H，合理下修成功；仍有效的高值不能忽略 |
| T20 | Integration | 超20事件／超20版本的完整翻頁，翻頁間新增更正 | 可翻完鏈與有效E；snapshot改變409不是默默截斷，is_effective與count正確 |
| T21 | Integration | 初始／提高／降低C混合Ledger，E20／E21不同User | Public僅下修、Owner完整Ledger，按revision序；無Email、下架權限同Vehicle |
| T22 | Integration resource | 合法三格式、5MiB等號／超過、6000邊／12M像素／動畫／壞檔／GPS／方向 | 邊界正確，413／415／422對應；去Metadata、輸出<=5MiB；5秒／128MiB須量測而非只Mock |
| T23 | Concurrency＋fault | Decode中下架／其他編輯；File寫好DB失敗；pointer切換後Cleaner crash | 舊expected409／不亂上架；失敗保舊有效圖／孤立可清；沒有DB+File共同Rollback假設 |
| T24 | Integration＋Browser E2E＋Deployment | 下架／換圖後舊URL、If-None-Match、Range、新Browser；Container重建 | 非Owner新判定404／無304；Owner無條件讀自己current200；Range授權後完整200；Volume持久化另驗 |
| T25 | Integration clock | 控制29:59／30:00、7:59:59／8:00:00，絕對測試維持近期活動 | 等號拒；me／csrf／圖片／Public／靜態不Touch；拒絕不保活、不延8小時 |
| T26 | Integration fault | E08／E10等Commit後讓Touch失敗或與Logout競爭 | 仍201／200 committed＋not_extended或unknown，不回業務未保存；revoked不被清、不UPSERT |
| T27 | Integration fault | Session Lookup／Public Query／Gate時PG失效；Gateway逾時／非JSON | 503非[]／404／me假匿名；無回應／502／504歸Transport Unknown，不盲重送 |
| T28 | Browser E2E | Cookie flags／JS不可讀、兩Tab通知≤5秒、換User／凍結／BFCache／延遲私有Response／SPA深連結 | 只Cookie指定操作Set-Cookie；Epoch阻舊資料；焦點先遮蔽；API錯誤不Fallback HTML |
| T29 | Concurrency＋Deployment | 多Worker同IP Login第20／21、Register10／11、CSRF60／61；XFF偽造／窗邊界 | 合計配額、429 Retry-After；固定窗Burst如實允許，NAT風險不假消除，Proxy信任實測 |
| T30 | Browser E2E [baseline limitation] | 延遲Login回應、Abort、me匿名、先清State及兩Tab亂序 | 方案A仍進Uncertain，不把新preauth Logout當取消、不宣稱Epoch攔Set-Cookie |
| T31 | Concurrency [Deferred B] | Server先準備ID；Cancel先於Login抵達／Verify中取消；猜別人／未知ID | 204後不得Finalize；未知／他人404不造Row；Token／Cookie不匹配403；ID本身不授權 |
| T32 | Concurrency＋Browser E2E [Deferred B] | Login已Commit S但Cookie延後，Cancel再釋放Response；Parent原是有效A帳號 | S晚到也401／me匿名或保留本來A；Cancel不等同Logout parent；新Attempt／其他裝置不被誤撤銷 |
| T33 | Integration clock／Recovery [Deferred B] | 逾deadline／Attempt Cleanup／父Context保留／Cookie或Pending標記遺失／Crash | 過期Worker不可Finalize、FK／Retention不早刪；失Proof維持Uncertain，不假取消成功 |
| T34 | Integration transport | 建車／補登／更正Commit後Response丟失，重查／舊parent重送 | VIN防第二車但需自己確認；Event不自動去重／重送；Correction舊parent409，不變第二事件 |
| T35 | Unit＋Integration＋Browser E2E | SQL片段、XSS文字、錯誤Validation／APM／Proxy Log檢查 | Binding不注入、純文字不執行；無密碼／Token／raw input／完整VIN／路徑／SQL外洩 |

測試Fixtures用兩個合成User、至少13台已上架車、未上架車、同日／補登／錯高值／深版本鏈、原圖含GPS的合法素材；受控Clock與Fault Hook只在隔離測試環境，不開Production改時間／任意停DB的管理Endpoint。驗證Status／Code／Cookie／Session時間／PG有效狀態／File與UI皆須看，不能只assert HTTP 200。



## 14. Design Trade-offs、Change Proposals與Open Questions

### 14.1 本輪選擇與必要回填

| ID | 來源／選擇 | 上游影響／是否Blocking |
| --- | --- | --- |
| CP-API-01 | 指定Login Attempt取消／第九表，Deferred B | 不阻擋MVP A；重啟B才需POST Prepare／Proof／Retention／權限與測試。現階段不建立第九表，不提供E06。 |
| D-API-02 | Public／Owner分開投影與Touch；Body expected版本／409；No-op不洗時間。 | 不改DB欄位／產品AC，於此Contract審查；不能用JSON Number承載任意BIGINT。 |
| D-API-03 | Marketplace12、其他集合20；同車分頁snapshot版本不符409。 | 無新Schema；Query例依舊為教學，實作需有界分頁／單Statement可見性。可審查成本，不能降為只看第一頁。 |
| D-API-04 | 同一PATCH處理C／價／一般編輯、PUT listing、POST同步主圖；無Jobs／delete／Static旁路。 | 不改既有模型；Multipart6MiB總預算／Parser限制是本輪傳輸設計，不改File5MiB。工作預算仍待部署校準。 |
| D-API-05 | 成功Meta分開business outcome／Touch狀態，Error區分not_applied／unknown；Body與Cookie Header分開。 | 回填／解釋I-AUTH-02的範圍，沒有禁止必要Set-Cookie；2C來源不在本輪改。不把Touch錯誤轉成假Rollback。 |

**關於CP-API-01的新增風險**：允許保留的失效preauth Cookie作「只取消該Attempt結果」證明，較現有普通Logout的例外更窄目的但多一個負面權限；舊Cookie持有人可能造成該結果Session被撤銷的DoS。不能用它登入或讀Private。Proof期限不得超Retention，Cookie／ID關聯與來源需嚴格驗；必須明確審查，不能當作CP-01～05自動核准的內容。

### 14.2 真正尚未決定／驗證

| 問題 | 預設提案／處理Gate |
| --- | --- |
| Auth Recovery Scope | 使用者已採A；未知保持Uncertain，指定取消留Hardening。DR-01風險與現有AC測試保留，不宣稱完整解決。 |
| Deferred B的Attempt期限／Retention／權限／Cleanup | 僅重啟B才審查120秒deadline、Retention／Migration／角色與故障測試；非MVP A前置。 |
| 精確PG版本／Encoding／Collation／Locale／Library與KDF成本 | 沿CP-04已定normalized→PG lower／Argon2id，不重選算法；記錄實值與Unicode／成本證據，不能稱全部大小寫／同形字解決。 |
| Caddy／PUBLIC_ORIGIN／TLS／可信IP／Body／Parser／CPU隔離 | 實際主機／網域／預算仍未定；所有設定與Browser Headers必須在部署測，沒有現階段SLA／高流量保證。 |
| Server／Client／DB等待期限與有限Retry | 不能用Timeout當取消／Rollback；校準Lock／Statement及影像預算，Client不得因有限等待結束就自動重送。 |
| 主動活動辨識 | Server只保證操作白名單；不能從HTTP或human=true證明真人。React不輪詢Owner Endpoint；任意自動Client可重複合法成功活動，這不是可宣稱已消除的風險。 |
| Logs／備份／Image Cleaner與Restore | 沿上游隔離還原、全部Session失效；[CP]還原也要失效／取消舊Attempt，防復活。沒有實際執行或新增運維Endpoint。 |

沒有發現必須刪FR-013、改歷史補登／C≥H、恢復停用AC或降低未上架隱私才能定義資源API的衝突。必要Gate是現行AC／未知結果不假確認的實作證據；Deferred B不是開始任何開發的前置條件。

## 15. 十個API核心概念

| 名詞 | 短定義／Vibicle用途 |
| --- | --- |
| Resource與Representation | Vehicle是資源；Public／Owner DTO是不同可見表示，不是兩台車或兩張表。 |
| HTTP Method | GET讀、POST建立／處理、PATCH局部編輯、PUT完整指定listing狀態；不讓GET登出或改車。 |
| Status Code | HTTP層結果類別；200空集合、401失效、404不可見、409版本衝突、503 Store故障不可混淆。 |
| Schema Validation | 在信任Boundary驗型別／範圍／extra與null／省略；Pydantic不代替Owner／跨日業務規則。 |
| Authentication／Authorization | Cookie→PG得到User，再逐Vehicle判Owner／公開狀態；登入不是可操作任意UUID。 |
| CSRF | Browser自動附Cookie帶來的跨站操作風險；Synchronizer＋來源涵蓋Login／Logout／上傳。 |
| Optimistic Concurrency | expected版本拒絕舊畫面覆寫；同車Lock另負責最新跨列不變量，兩者互補。 |
| Idempotency | 同Request不重複生效；本案沒有通用去重，不能拿409／相同描述假裝Exactly Once。 |
| Transaction與Commit Outcome | V／版本／Ledger原子保存；回應遺失可能不知道是否Commit，File bytes不在PG共同交易。 |
| Cache與Conditional Request | no-store控制受控交付，不能追回副本；本Profile不支援304／ETag／Partial Image，所有讀取先判可見性。 |

## 16. 五個面試追問

1. 為何Public與Owner使用不同GET路徑？如果Owner打開Marketplace，如何保證不洩完整VIN又不延長Session？
2. 為何版本放Body用409，而不是If-Match／412？同一PUT listing重試出409，是否代表它不再有冪等的狀態效果？
3. 為何同日同里程的兩個新Event不能自動去重？Unknown Commit與Concurrent Conflict各應如何提示User？
4. Login Timeout後me匿名為何不能直接顯示「已登出」？Server先準備Attempt、再確認取消能多保證什麼，失Proof時又少了什麼？
5. 新bytes寫入成功但PG pointer切換失敗，怎樣保留舊主圖、清孤立檔、拒舊URL，為何不能說兩者一起Rollback？

## 17. 三個curl／Postman演示（未執行）

本輪無網站／可運行API。以下是**實作且CP審閱後**的演示腳本思路；不用安裝套件或在現在呼叫。Postman Base URL用未來同Origin HTTPS，啟用自己的Cookie Jar；Password／CSRF僅Private變數或記憶體，不匯出公開Collection／報告。curl亦須自己Jar＋Origin＋Header，不能從沒有Token的Request推論功能有Bug。curl不能證明Browser SameSite／跨Tab／Set-Cookie處理順序。

### Demo A：手動登入與CSRF Boundary

1. E01取得preauth／CSRF；先故意不帶X-CSRF-Token送E02，應403且未建User。
2. 正常Token送E02成功201；立刻E07仍401，證明註冊沒有自動登入。
3. E01取得目前CSRF，再E03送Email／Password／CSRF，觀察新Cookie及User／新CSRF；E07只看自己車。
4. 重新Login更換Session ID，拿先前自己的Cookie測E07應401；另一個獨立Jar仍可用。報告只留遮罩後Attributes，不展示Bearer值。

### Demo B：Owner／版本衝突與No-op

1. A用E08建合成車，記E09的row_version；準備兩份E10 Request都帶同expected。
2. 第一份改description成功200、新revision；第二份舊expected送出409，讀回確認沒覆蓋第一份。
3. B獨立Jar拿A車ID送管理讀寫應404；傳owner_user_id／vin等Server-only／不可編輯欄位422（但不能因此修改任何資料）。
4. A備妥價格／主圖後E11上架，再用最新expected重複相同狀態：changed=false，last_listed與revision不變；不要把舊expected自動改掉重送。

### Demo C：更正退出高值與下架後圖片

1. 用隔離合成案例建立合理日期的錯高維修值，E19附expected current及理由更正；E18仍看得到原文，但E15有效只計一次。
2. E10有理由且明確confirmed下修C，不低於新H；E20看到下修摘要，證明履歷更正與C更動分開。
3. 保存E23目前圖URL；E11下架後以匿名新Jar直接讀詳情／舊鏈／圖片（含If-None-Match）都404、沒有304；Owner無條件讀自己current圖200。
4. Storage／Cookie重排／雙連線Race不能只靠這三段手動流程驗證，另依T17／18／23／28／30～33做自動與Browser測試。

## 18. 自我檢查、凍結與停止點

本文件保留23個Endpoint識別，其中E06 Deferred，MVP為22個候選介面、完整共用DTO／Error／Policy、71項有效AC逐列對應、35項未來測試。驗證檢查Endpoint ID／Path／Schema／Status／Touch／資料表／可信欄位及圖的責任一致；不以圖表存在當成安全證明。

**現行MVP Gate**：CP-SCOPE-01～03已接受，採A／八表／五Auth介面，E06 Deferred。必要的Rotation／撤銷／CSRF／舊UI隔離及Uncertain驗收仍必做；CP-06／DR-01未結案。Step 3A可建立Foundation，不能宣稱完整Auth已實作或全部AC通過。

未來有界分頁／Strict Schema／版本Body／Error Envelope等屬本輪Contract取捨，審閱後才實作；Step 2D原輪次未執行HTTP／SQL／Browser測試；本次Step 3A的實測與Not Run以STEP_3A_VERIFICATION.md為準，不能推定完整Auth驗收通過。Mermaid仍未經Renderer。本次依使用者進入Step 3A，僅匿名E05開始實作；完成Foundation後停止等待程式碼審查。


## 19. 2026-11-05 Scope Acceptance 與 Step 3A 實作邊界

CP-SCOPE-01～03由使用者接受，與DECISIONS §7一致。四個停用AC不復活；13項Must Have／71有效AC及全部業務規則不變。Step 3A僅E05缺Cookie或格式無效Cookie的匿名分支；可能有效的Cookie在Session Lookup未接入時fail closed，以現有503 STORE_UNAVAILABLE Error Envelope說明尚未提供驗證，不假稱查PG後無Session。沒有Cookie可直接匿名，不證明DB健康；DB連線另以Development CLI診斷。E05新增Query／Body／歧義Cookie仍按既有Contract拒絕。Step 3C才做完整Lookup／期限／撤銷／Rotation；本輪不做Login／CSRF／Coordinator。
