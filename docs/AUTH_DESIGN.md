# Vibicle — Authentication & Authorization Design

- 版本：v0.1，Step 2C 審閱提案；日期：2026-11-03（Asia/Taipei）。
- 基線：已讀取並核對 [PRD v0.2](PRD.md)、[DECISIONS](DECISIONS.md)、[System Architecture](SYSTEM_ARCHITECTURE.md)、[Database Design](DATABASE_DESIGN.md) 的現行內容。
- 本輪只有本文件。沒有安全機制實作、套件安裝、DB／Migration、Docker設定或部署；四份上游文件不變。
- **[基線]**＝上游候選要求；**[2C選擇]**＝本輪明確建議採用、待審查的設計；**[CP]**＝須回填上游的Change Proposal；**[TEST]**＝尚未實作／驗證。不存在「設計已寫好＝安全已通過」的推論。

## 0. 核心結論與範圍

本輪選擇：**PostgreSQL Server-side Session＋Host-only HttpOnly Cookie＋Synchronizer CSRF Token＋精確來源驗證＋Ownership授權**。Password Hash選Argon2id；限流先採明確定義的Fixed Window。不引入JWT、Redis、OAuth、第三方登入或複雜RBAC。

保留閒置30分鐘、絕對8小時、只撤銷本次Session；preauth是不同語意的登入前上下文，候選15分鐘、不滑動。註冊不登入，成功登入換新Session ID及CSRF Token，並撤銷Browser帶來的舊上下文。

**必要差異**：Synchronizer方案需在auth_sessions新增一個32-byte csrf_secret欄位提案；為避免匿名CSRF Context建立成為無限制DB寫入面，Rate-limit scope建議增加csrf_context。這些在第12節列CP，不直接修改Database Design或產生Schema。

**不變業務規則**：FR-013保留；C≥有效H、歷史補登與同日／跨日規則仍依Database Design §6／7；公開僅VIN末六碼、下架僅Owner可讀詳情／所有版本／照片。FR-006-AC03、FR-011-AC02／03／05仍停用。沒有新增車輛／維修／圖片完整REST Endpoint，本輪只草擬五個Authentication介面。

### 0.1 上游依據與主要安全邊界

| 文件／條款 | 這次必須維持的內容 |
| --- | --- |
| docs/PRD.md §4.0、FR-001～003、§5.3、BR-13／14 | 12–128字元、不擅自trim密碼、手動登入；Session期限、換ID、CSRF、跨分頁及在途界線。 |
| docs/PRD.md BR-01／03／05／09～12、NFR-SEC-01～09 | Server驗Owner、公開投影、單鏈更正、私有圖片、來源固定、所有寫入CSRF。 |
| docs/DECISIONS.md D-01～03／05～07、§4 | Authentication與CSRF／Store等細節待SDQ，不能以UI或簽章Cookie代替共享撤銷。 |
| docs/SYSTEM_ARCHITECTURE.md §6.4／6.5、§7.3、§9 | 任意Worker查PG；無Sticky Session必要；同Origin不免CSRF；照片API逐次授權。 |
| docs/DATABASE_DESIGN.md §4.1／4.2／4.8、§7.4、§8、§10 Q-06、DBQ-03～06 | Email／Hash、Token Hash PK、kind、期限／撤銷；續期另用短操作、不得復活；允許2C明示最小CSRF欄位修訂。 |

Browser與Request、所有Header／Cookie／Body都不可信。Caddy是受控入口，FastAPI是認證與業務授權邊界，PostgreSQL是Session與資料權威。Runtime角色不是User本人；共用DB帳號不會自動代替Ownership檢查。Host／DB管理者、備份與Secrets能破壞系統信任，仍須受控管理。

## 1. Authentication Fundamentals

### 1.1 Authentication與Authorization

- **Authentication：「這個Request是誰？」** 登入時比對Password Hash，之後由Cookie Token在PG找到有效Session，再得到User ID。React顯示「已登入」只是畫面狀態。
- **Authorization：「這個人可對這個資源做什麼？」** A有合法Session，只能編輯owner_user_id=A的車；B的已上架車可讀公開資訊，不能因此被A修改。照片、舊版本與完整VIN各自也有讀取條件。

例如A輸入B的Vehicle UUID：Session Lookup成功只能證明是A；Service仍須用Vehicle歸屬判斷並拒絕，不因路徑可猜／UUID難猜而改變。

### 1.2 不同名詞所在的層次

| 名詞 | What／Why | 在Vibicle如何使用／Alternative與Failure |
| --- | --- | --- |
| Cookie | Browser依Host／Path／Secure／SameSite等規則附送的小段資料，是傳輸／保存機制。 | 放不透明Session Token；Cookie存在不等於有效登入，也能承載其他資料，不能與Session混稱。 |
| Server-side Session | Server保存Token對應的User、期限、撤銷與CSRF上下文。 | PG保存，任何Worker均可查；只存在本機dict會在重啟／換Worker出錯。 |
| JWT | 表達Claims的Token格式；常見簽章形式可驗完整性，內容通常可讀。 | 本案不用作登入憑證；JWT不是自動加密、即時撤銷或OAuth，改成Cookie傳JWT仍有CSRF問題。 |
| OAuth 2.0 | 委派資源存取的Authorization框架。 | 「讓其他應用存取某服務」不是本案需求，不拿OAuth Token本身當作登入協定全貌。 |
| OpenID Connect | 建在OAuth 2.0上的身分層，定義登入身分／ID Token等。 | 第三方登入可用，MVP不需要；自行加入會多出Provider、回呼與Token驗證。 |

定義依據：[JWT RFC 7519](https://www.rfc-editor.org/rfc/rfc7519)、[OAuth 2.0 RFC 6749](https://www.rfc-editor.org/rfc/rfc6749)、[OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)。這些比較不代表採用其中的登入流程。

### 1.3 Stateful Session與Stateless Worker可共存

HTTP不會自動替下一個Request記住User。Browser每次帶Cookie，API Worker向同一PG查Session，因此Worker A／B不需共用RAM登入Dict，亦不需Sticky Session。整個系統仍有State：PG與Private Volume並未變成Stateless。

| 位置 | 保存什麼 | 不應保存／信任什麼 |
| --- | --- | --- |
| Browser Cookie Jar | raw不透明Token，HttpOnly；本案同一Cookie名稱承接preauth或authenticated。 | 不把User ID當憑證；JS讀不到Session Token，亦不在localStorage／URL放副本。 |
| React記憶體 | 目前User顯示資訊、CSRF Token、UI身分世代、暫存資料。 | 不作登入／Owner權威；CSRF不持久化到Web Storage，不把舊User Cache當新身分資料。 |
| FastAPI Request Context | 本次驗證得到的User ID、Session Hash、來源／CSRF結果。 | 不在全域變數保存某User供後續Request使用；不以本機舊Session快取繞過撤銷。 |
| PostgreSQL | Password Hash、Session Token Hash、User關聯、時間／撤銷、擬新增CSRF Secret。 | 不存raw Session Token或原密碼；不把對應FK誤認成Request已授權。 |
| Caddy／Log | 受控路由、TLS與不含秘密的Request結果。 | 不記Cookie、CSRF、密碼Body或完整VIN；不把原始Client Header當可信代理資訊。 |

Session ID若直接用User ID，知道公開User ID的人就能冒用，且同User的多裝置無法獨立撤銷。32-byte Cryptographic Random Token使猜測不可行於本案威脅模型；改成時間戳／Email或一般random會破壞這個前提。UUID只用於資源識別，不能替代Bearer Secret。

## 2. Authentication Decision Matrix

| ID／What | Why／本輪選擇 | How | Alternative | Failure／限制 |
| --- | --- | --- | --- | --- |
| AD-01 Server Session | 直接對應本次撤銷與30分鐘／8小時；沿用基線。 | PG Lookup，Token Hash PK，kind分preauth／authenticated。 | JWT需補撤銷／閒置狀態；本機RAM不共享。 | PG故障即拒絕，不使用本機fallback。 |
| AD-02 Argon2id | 抵抗離線密碼猜測並保留128字元政策。 | 成熟pwdlib Argon2後端；成本與併行有界，§3。 | bcrypt有72-byte限制；PBKDF2可行但本案無特定合規需求。 | 參數太弱易猜，太高可能耗盡RAM／CPU，須量測。 |
| AD-03 Cookie | 同Origin Browser自動附憑證，JS不必持有Bearer。 | __Host-vibicle_session；Secure／HttpOnly／Lax／Path=/、無Domain。 | Header Bearer要求JS管理憑證；跨Origin增加配置。 | 被竊有效Cookie仍可重放；HttpOnly不消除XSS。 |
| AD-04 Synchronizer CSRF | 已有Stateful Store，流程容易解釋。 | 每Context 32-byte Secret，JSON發放，Header回傳，恆定時間比較。 | Signed Double Submit也可，但需簽章／Session綁定與另一Cookie協調。 | XSS可讀CSRF及代送Request；需CP-01欄位。 |
| AD-05 來源驗證 | 阻擋跨站及同Site不同Origin的Browser寫入。 | 固定PUBLIC_ORIGIN；Origin優先、Referer備援，兩者皆無拒絕；Fetch Metadata加強。 | 只SameSite／CORS不符合基線。 | Native Client可偽造Header，仍必須Cookie＋Token；Proxy配置要實測。 |
| AD-06 期限／續期 | 不以每次Response滑動Cookie，避免背景保活及晚到Cookie覆寫。 | PG條件Touch；普通API不Set-Cookie，成功活動白名單。 | 每Response重發Cookie增加競態；清理器當期限錯誤。 | 長工作成功但Session已過期可不續期，不能把業務成功說成未保存。 |
| AD-07 Ownership | 無複雜角色仍需要逐資源授權。 | Dependency建立Identity；Service＋有條件Query判Owner／公開狀態。 | 隱藏按鈕、信任Body Owner均無效。 | 漏一個圖片／舊版入口仍可造成BOLA。 |
| AD-08 Fixed Window | 對候選PG Bucket最小改動、可演示多Worker一致。 | UTC固定5分鐘／1小時窗，原子Counter，§9。 | Sliding更精確但需其他模型；Token Bucket語意不同。 | 邊界Burst／NAT／分散來源風險保留，不宣稱任意滑動窗上限。 |
| AD-09 UI世代／分頁協調 | 避免舊資料與Cookie生命週期競態。 | BroadcastChannel清理／重驗；Web Locks序列化Cookie變更流程，§6.6。 | 只有React State不能協調Tabs；只有Abort不能撤回Server操作。 | 凍結Tab無即時保證；Browser HTTP層Set-Cookie不能靠丟棄JSON取消。 |
| AD-10 Restore撤銷 | 備份可能還原已撤銷Session的舊狀態。 | 隔離恢復、失效全部Session含preauth，再開放服務。 | 只清Browser Cookie無法撤銷外部副本。 | 正常Container重啟與Backup Restore必須區分。 |

所有列皆為設計選擇，沒有部署或安全驗收結果。

## 3. Registration & Password Security

### 3.1 Password Hash、Encryption與Salt

Hash用於驗證猜測值，不提供解密取回原密碼的功能；Encryption可由持Key者還原，不適合作為本案主要Password保存方式。Password Hash是刻意昂貴的KDF，不是把SHA-256多呼叫幾次就自行發明一套。

每個Password Hash由Library產生獨立隨機Salt並把Salt／算法／成本一起編碼保存。Salt不必保密，可避免相同密碼得到同值與大量預計算共用成果；不能讓弱密碼變強。SHA-256太快，不適合使用者低熵密碼；Session的256-bit隨機Secret則採SHA-256作索引摘要，威脅模型不同。

### 3.2 三種算法比較及成本政策

| 算法 | 優點 | 取捨／本案結論 |
| --- | --- | --- |
| Argon2id | 可調記憶體與計算成本，現代Password Hash用途。 | 選用；需有界併行，避免高成本驗證阻塞Event Loop／耗盡主機。 |
| bcrypt | 既有系統成熟，CPU成本可調。 | 常見72-byte輸入上限與128字元UTF-8密碼不相容，不能偷偷截斷；本案不選，也不自行發明預雜湊方案。 |
| PBKDF2-HMAC-SHA256 | 廣泛支援、某些合規環境適用。 | 可作有理由替代；成本需正確配置，非Memory-hard。本案沒有迫使改用它的條件。 |

**[2C選擇]** 用維護中的pwdlib搭配Argon2後端（例如argon2-cffi），不自行寫KDF、Salt或比對演算法。初始參數候選：Argon2id m=19,456 KiB、t=2、p=1，Salt 16 bytes、Hash 32 bytes；符合查閱當時OWASP的其中一組建議起點，**不是此Host已達成安全／效能證明**。選定版本後核對API及維護狀態，於DPQ-03量測；可提高成本，不以量測慢為由直接換快速SHA。起步單Worker、每Process最多一個昂貴Hash／Verify工作，忙碌則有界拒絕／等待，不建無界Queue；多Worker的總預算需一併調整。

保存Library編碼的Hash字串於app_users.password_hash；驗證由Library完成，不自行用字串等號比Hash。可依Library判斷成功登入後是否需Rehash；用舊Hash條件更新避免覆蓋未來憑證變更，Rehash不是新Password變更功能。

依據：[OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)、[pwdlib官方文件](https://frankie567.github.io/pwdlib/)、[argon2-cffi參數指引](https://argon2-cffi.readthedocs.io/en/stable/parameters.html)。[FastAPI官方教學](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)採用pwdlib的Password Hash用法，不表示本案採JWT或OAuth登入。

### 3.3 12–128字元的具體政策

- 註冊接收Password及Password Confirmation，必須完全相等；長度12～128，包含兩個端點。
- 「字元」本案定為合法Unicode的Code Point數；Frontend不得直接把JavaScript UTF-16 length等同此規則，Server為最終判定。UTF-8編碼後交Library，不截斷為128 bytes。
- 允許貼上、空白、Unicode與Password Manager；不trim、不改大小寫、不作Unicode正規化、不要求大小寫／數字／符號組合、不加密碼定期到期或歷史禁用規則。
- 無效編碼／型別拒絕；不把數字／布林強制轉字串。登入亦先做同樣長度／型別檢查，不默默改成另一個密碼。
- Password與Confirmation不出現在Response、Log、Trace、Exception Payload或Analytics；登入／註冊以小型Request Body上限候選8 KiB防濫用，足容納128 Code Points及Email／Confirmation。這是傳輸預算，不縮短密碼政策。
- 無MFA、Email驗證、密碼找回／變更為本MVP既定範圍。12字元不代表抵抗所有弱密碼／Credential Stuffing；不得宣稱「已認證身分」。

### 3.4 Email正規化與DB一致性

**[2C選擇]** 一個共用Backend流程供註冊及登入：

1. 嚴格字串，移除前後Unicode空白（固定Python版本的strip語意）；中間空白不任意刪除。
2. 以成熟email-validator候選做語法／Unicode及Domain正規化，關閉deliverability／DNS查驗；不寄信、不宣稱郵箱存在。使用它的normalized形式，允許其支援的國際化地址；Library格式邊界／保留測試Domain應固定設定及Fixtures，不額外偷偷限定ASCII。
3. **大小寫Key由PostgreSQL lower決定**：Python不另用casefold或不同Locale產生另一把Key。Repository以參數化SQL取得／寫入lower(經驗證字串)，註冊與登入用同一DB語意。
4. 對最終canonical值重新檢查1～254 Code Points，存入唯一email欄位；不刪Gmail dots、加號標籤或推定不同地址同一人。
5. DB既有email=lower(email)、email=btrim(email)、長度CHECK及UNIQUE(email)保護保存形態／併發。DB Encoding／Collation／lower語意固定並記錄，不依機器預設悄悄改；非ASCII特殊大小寫以Fixtures驗證，不宣稱完整Unicode casefold／視覺相似地址等價。

採用DB lower作唯一大小寫權威，正是避免Python與PG各算不同Key；DB CHECK不代替完整Email語法驗證。Unicode正規化／Library升版可能造成canonical碰撞，須先檢查舊資料，不能直接改掉已存在帳號識別。依據：[email-validator作者文件](https://pypi.org/project/email-validator/)；本案選擇normalized而非自行拼一套Email解析器。

**併發註冊**：先查重只提供UX，兩個Request仍可能同時通過；最終靠UNIQUE(email)。一筆Commit後另一筆Unique Violation整交易Rollback，不能建立第二個帳號／Session。錯誤轉通用註冊衝突，不回傳既有User ID／Email資料／Hash。

### 3.5 註冊與登入的資訊洩漏界線

註冊：來源／限流／preauth CSRF通過→驗欄位與確認密碼→Canonical Email→Hash（交易外）→短交易INSERT User→Commit→201引導手動登入。保留原preauth、不設定authenticated Cookie、不把註冊視為登入。

登入：有效格式的不存在Email與密碼錯誤一律401、相同錯誤碼／Body「Email或密碼不正確」，不提供哪一欄錯誤。不存在User也用預先建立、相同參數的Dummy Hash走一次Verify，不用快速提前返回；限流政策不依帳號存在分流。無法保證網路／DB／快取後整體時間完全常數，但需測量明顯差異。

**誠實限制**：本候選註冊201與重複資料409仍可成為註冊存在性探測器；不因文字通用便宣稱完全防Enumeration。PRD只要求不回既有資料且登入錯誤一致，未要求註冊完全隱藏存在；若審查要強化，另提統一回應的UX需求，不能擅加Email驗證功能。參考 [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)。


## 4. Cookie Security Policy

### 4.1 Attribute比較與Production候選

| Attribute | What／How | Why／Alternative／Failure |
| --- | --- | --- |
| HttpOnly | Browser不讓document.cookie讀該Cookie；仍會隨符合條件的fetch／導覽Request附送。 | 減少XSS直接偷Token；XSS仍能在同Origin發合法Request、讀畫面／CSRF，不能宣稱全部XSS被擋。 |
| Secure | Cookie只在符合安全傳輸條件時附送；本案只經HTTPS入口。 | 不保護終端、Log或被竊Cookie，也不補救先前經HTTP傳出的密碼。 |
| SameSite=Lax | 本案明確設定；跨Site的部分頂層安全導覽可附Cookie，跨Site不安全方法通常不附。 | 讓外部連結進站符合預期；仍需CSRF及來源驗證，同Site不等於同Origin。 |
| SameSite=Strict | 更嚴格限制跨Site導覽帶Cookie。 | 可選但外部連結的初始Request可能不帶登入資訊；仍不是完整CSRF方案。 |
| Path=/ | 此Host的路徑皆可附Cookie，符合__Host-要求。 | Path是傳送範圍，不是跨應用安全隔離；不能把Path=/api與__Host-同時宣稱成立。 |
| 無Domain／Host-only | 只對設定它的Host，不共享到兄弟／子網域。 | 不設Domain=.example.com；Domain Cookie擴大風險。Cookie不以Port隔離。 |
| __Host- Prefix | 使用__Host-vibicle_session；要求Secure、Path=/且無Domain。 | Browser額外檢查設定，減少子網域Cookie注入；Prefix不自動附加HttpOnly或取代Server檢查。 |
| Max-Age | authenticated設28800秒；preauth設900秒；普通Request不刷新。 | Browser儲存期限只是上界提示；Server閒置／撤銷／絕對時間才是權威，不加Remember Me。 |

Header示意（只有Placeholder，未建立Cookie）：

~~~http
Set-Cookie: __Host-vibicle_session=<opaque-token>; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=28800
~~~

preauth同名Cookie以Max-Age=900設定，沒有User身分；成功登入替換成全新Token。清除時同一Name／Path、無Domain，Max-Age=0並保留Secure／HttpOnly／SameSite語意；不能清錯作用域而留下舊Cookie。

依據：[MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie)、[Chrome Cookie Prefix說明](https://googlechrome.github.io/samples/cookie-prefixes/)。Browser版本與實際Header仍須用DevTools驗證，不只看程式參數。

### 4.2 Browser實際如何附送

React向同Origin /api/...發fetch，使用明確same-origin credentials語意即可由Browser帶Cookie，JS不用也不能讀Session Token。跨Origin fetch不會因Frontend／Backend為不同Container就自動發生；本案公開入口同scheme＋host＋port，API由Caddy轉送。

SameSite按Site判斷，Origin按scheme／host／port判斷：evil.example.com與app.example.com可能同Site，卻不是同Origin；localhost的不同Port也不是不同Cookie Host。不能以SameSite=Lax取代精確PUBLIC_ORIGIN驗證。

Set-Cookie由Browser HTTP層處理，JS看不到Header內容，也不能靠「忽略Response JSON」取消Cookie寫入。普通讀寫API、身份確認、CSRF失敗、401／403／503不自動重發／刪Cookie，避免過時Response影響新登入。只允許第10節指定的Cookie生命週期操作設定／清除。

Path=/意味Browser對靜態檔也可能附Cookie；Gateway／Web日誌不得記錄它，靜態服務無需收到Cookie時由Gateway剝除，靜態Response不得設定登入Cookie。沒有把Cookie放URL或Query String的備援流程。

### 4.3 本機與Production TLS

候選本機以Caddy在例如https://vibicle.localhost:8443服務同Origin，內部轉Vite Dev與API；需先確認名稱解析、信任本機CA及實際Port，未假設已配置。Production換為使用者決定的正式HTTPS Origin，維持相同Cookie規則；憑證、DNS、TLS信任仍待部署階段。

HTTP診斷環境若需要獨立非Secure Cookie，必須用不同名稱／隔離資料與設定，不能使用__Host-前綴，也不能作Production Cookie驗收證據。本輪不建立這種環境或降低Production保護；不依賴Browser對localhost的特殊例外掩蓋問題。

FastAPI只信任受控Caddy提供的Scheme／Host資訊；PUBLIC_ORIGIN由配置指定，不以任意Host／X-Forwarded-Host反射決定允許來源。主機允許清單與API Port不公開是前提；TLS在Caddy終止，內網信任並不等於可接受不明代理Header。

## 5. CSRF Strategy — 本輪選擇Synchronizer Token Pattern

### 5.1 三種方案比較

| 方案 | 防禦／How | 複雜度、適用性與限制 |
| --- | --- | --- |
| A. Synchronizer Token | Server為每Session／preauth保存隨機Token，React在Request Header回傳，Server與同Context比對。 | 本案已有PG Session，最直觀；多一欄，Reload可重取同Token。按Context而非逐Request輪替，減少多Tab／返回頁面衝突。 |
| B. Signed Double Submit Cookie | 另外可讀Cookie中的Token帶HMAC並綁定目前Session，Header／Cookie及簽章／綁定都驗證。 | 可省每Context CSRF欄位，但多Cookie、Key與序列化／輪替；不是只比兩個相等字串。可行但本案不選。 |
| C. Origin／Referer／Fetch Metadata | Browser來源與跨站訊號可在Token前拒絕不可信請求。 | 作本案強制的多層防禦；Header可能缺失，Native Client可偽造，不能單獨證明身分或代替所有Token檢查。 |

Naive Double Submit只比可由Client控制的Cookie與Header／Body值，沒有簽章或Session綁定，可能遭Cookie注入；本案明確不採。選A＋C，而非將Signed Pattern拆掉簽章後自稱簡化。

模式依據：[OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)。下列Token長度、preauth 15分鐘與來源缺失政策是Vibicle本輪設計，不是OWASP替此站完成驗收。

### 5.2 Token生成、發放與最小欄位

- Session／preauth建立時，獨立產生32 Cryptographic Random bytes存擬新增auth_sessions.csrf_secret；與Session Token分開生成，不能直接使用／公開Session ID或token_hash當CSRF Token。
- React由受控Get CSRF Context取得base64url編碼的csrf_secret，保存在記憶體；Body與Response皆no-store，禁止Token進URL、Log、Analytics、Web Storage及分頁通知。
- 每次Mutation帶X-CSRF-Token Header。Server嚴格解析為32 bytes，用標準constant-time compare對照**Cookie查到那筆**csrf_secret；不跨User／Context搜尋Token。
- Token與該Context同壽命；preauth不滑動15分鐘，authenticated最長8小時且還受30分鐘閒置／撤銷。§6.4僅對Logout允許保留失效authenticated列的撤銷專用驗證，絕不因此准許業務寫入／續期。成功登入換新Cookie及Secret；失敗登入／註冊不改Secret或建立登入。
- Reload／另Tab可在有效Cookie下重取同Secret，不每次GET輪替，避免互相使表單失效。Server Token只保存在DB，任何Worker均查得到。
- 原Session ID仍HttpOnly，DB仍只存其Hash。CSRF Secret可原樣保存，因為它不是登入Bearer；只有這個Secret沒有Cookie無法取得身分。但它仍是秘密，受DB權限／Backup保護，不記錄。

**[CP-01]** csrf_secret BYTEA NOT NULL、octet_length=32、不設可猜Default、不建Index；由Service生成。GET要可重取既有Token，因此本方案不選「只存CSRF Hash卻沒有可重取原Token」的半套設計。既有測試Session需失效／清除後補此約束，非偷偷替舊Context加一個共用Secret；詳第12節。

### 5.3 Pre-auth Bootstrap與登入轉換

首次React需要註冊／登入時，先取Get CSRF Context：

1. 先通過本節來源規則及csrf_context限流。
2. 無有效Context Cookie：建立kind=preauth、user_id=NULL、created／last_activity=同一DB時間、absolute_expires=created＋15分鐘，並設定同名HttpOnly Cookie與獨立CSRF Secret。
3. 已有有效preauth或authenticated：重用該Context、回同CSRF Token，不Set-Cookie、不更新last_activity／任何期限。
4. preauth只有CSRF／流程用途，不能讀車庫或當User。authenticated Context也可提供Token供登出／其他寫入；Register僅接受preauth，Login可用preauth或有效authenticated Context重新登入。
5. 成功Login在同交易建立**新列**、撤銷舊列；不把preauth列就地改kind並保留ID。Login成功Response可帶新CSRF Token，或者由UI隨後重取；本提案選直接帶新Token，避免額外Cookie變更。

Get CSRF Context用GET只初始化安全流程，不登入／登出、不改車或業務資料，是明列的技術Bootstrap；其Cookie變更須按§6.6序列化。禁止用GET執行業務Mutation或撤銷登入。外站不能用一個頂層GET重設Context：來源／Fetch Metadata與限流在建立及Set-Cookie之前。

### 5.4 精確來源與缺失Header政策

本輪明確選擇：

1. 允許目標是配置的單一PUBLIC_ORIGIN；用URL Parser比scheme、hostname及有效port，不以字串contains／suffix／startsWith比對。Production必須HTTPS。
2. **Origin存在**：必須是單一、合法、精確匹配值；null、不同Origin、多值／格式錯誤一律403，不改用Referer挽救。
3. **Origin缺失**：解析Referer，取其Origin精確比對；缺失／無效／不同Origin一律403 source_not_allowed。沒有「缺Origin就當Native Client略過」分支。
4. 對Mutation與Get CSRF Context，Sec-Fetch-Site若存在只接受same-origin；cross-site、same-site、none或格式錯誤均拒絕。Header缺失時仍必須通過Origin／Referer，不因缺Fetch Metadata直接視為安全。
5. 符合Contract的獨立HTTP Client：Cookie Jar、Get CSRF Context、X-CSRF-Token，並明確送配置的Origin；無須載入React。它可以設定Origin不代表取得新信任，仍需憑證與正確Context。
6. 正常React fetch會有同Origin Referer／必要Origin；候選頁面Referrer-Policy採strict-origin-when-cross-origin，避免自家政策讓Bootstrap總被拒。若Privacy Extension移除兩者，明確失敗而非鬆綁；須用目標Chromium實測。

Fetch Metadata與Origin由Browser限制一般網頁隨意偽造，但非Browser工具能設定；它們是CSRF來源訊號，不是User Authentication。API不開任意CORS，不反射Access-Control-Allow-Origin，也不以CORS阻擋讀取的能力當成已阻止Request送達。

### 5.5 驗證順序與全Mutation涵蓋

基本順序：Gateway大小／TLS／Host→來源／Fetch Metadata→Auth公共介面限流→查Cookie Context→Token比對→Body Schema→Authentication／Ownership／業務規則→Commit。不同入口可依安全性細調，**不得先寫入／昂貴解碼再檢查CSRF**。

Cookie缺失／無效不能用Header Token單獨補登入；Cookie有效但Token缺失／錯誤／另一Session的Token，403且無業務／登入副作用、不續期、不Set-Cookie；已到達Gate的限流計數仍可累加。受保護資源缺有效authenticated Session則401；Auth失效與CSRF錯誤的優先序在§10明列。

| 操作 | Context／必要控制 | 失敗不允許的副作用 |
| --- | --- | --- |
| Register | 有效preauth＋來源＋X-CSRF-Token＋register限流。 | 不建立User、不自動登入。 |
| Login／重新登入 | 有效preauth或authenticated＋來源＋Token＋login限流。 | 不建立／替換登入、不撤銷原有效Session。 |
| Logout | 已知當前Context的Token＋來源；過期／重複流程見§6.4。 | 不用GET、不只清UI、不因CSRF錯誤清除另一個新登入Cookie。 |
| 新增／編輯車、C變更 | authenticated＋來源＋Token；現有車另驗Owner。 | 不接受偽造Owner；失敗不改C／Ledger。 |
| 上架／下架 | 同上，依Server目前狀態與expected版本。 | 不重洗時間或由別車Owner改狀態。 |
| 補登／更正 | 同上；更正驗事件歸屬與目前末端。 | 不分叉、不改原文、不自動改C。 |
| 上傳／替換主圖 | authenticated＋來源＋Header Token＋Owner，之後才進受限檔案工作。 | 不以multipart可送達為已驗證，不破壞舊圖／公開原檔。 |

JSON Auth介面要求application/json；拒絕拿text/plain／表單當JSON解析以繞流程。照片用multipart/form-data，但CSRF仍放Header，Browser自行產生Boundary；Gateway／API接收與Multipart Parser限制仍需在讀取前／途中實作，不聲稱單靠Dependency可以零成本擋住全部大檔案。

**FastAPI順序陷阱**：Request Body／Form可能在一般Dependency求值前已被讀取／解析。因此採外層ASGI Header Guard或等價的Route Wrapper，在Body Parser前做來源、Cookie Context／Header CSRF與必要Gate；結果只供本Request使用，Dependency再統一要求該Policy，不維護兩套不同規則。2D需把方法／路由的安全Policy集中對照並測試。依據：[FastAPI routing原始碼](https://raw.githubusercontent.com/fastapi/fastapi/master/fastapi/routing.py) 的Body讀取與solve_dependencies順序；實際鎖定版本須重新核對。傳輸／Schema解析錯誤仍可先被一般限制拒絕，不能承諾攻擊者完全不消耗解析／網路成本。


## 6. Session Lifecycle

### 6.1 共用表示與時間權威

**What／Why**：同名Cookie保存32-byte隨機Token的canonical base64url無padding形式（43字元），DB只保存原始32 bytes的SHA-256。Raw Token與CSRF Secret分開產生；Hash PK碰撞／異常時不能覆寫既有Session。

**How**：標準Python secrets／OS CSPRNG生成；嚴格解碼長度與字元，拒絕重複同名Cookie／多個Token Header造成解析歧義，不將Cookie值直接當User ID。Token Hash不加Salt：本身高熵，與人類Password不同；Hash可減少只讀DB外洩直接重放，不能防已竊raw Cookie或DB寫入權限。

時間取PG Primary可信Clock，TIMESTAMPTZ保存瞬間，UTC輸出；期限不按Browser Clock或Asia/Taipei顯示字串算。普通Lookup採新的短Statement為認證判定點；任何鎖等待後須取新Clock重新驗證，不能用長交易開始的now()假裝還沒過期。

參考：[Python secrets](https://docs.python.org/3/library/secrets.html)、[PostgreSQL時間函式](https://www.postgresql.org/docs/current/functions-datetime.html)。這不是自行實作亂數或密碼學Primitive。

### 6.2 成功Login及Session Fixation

1. Browser持有效Context Cookie與對應CSRF Token送Email／Password；來源、限流、Context及Token先通過。
2. 查canonical Email；在DB交易／長Row Lock之外作Library Verify（找不到User走Dummy）。失敗回同一401，沒有新Cookie、Session、撤銷或續期。
3. 驗證成功才開始短Transaction，鎖Browser帶來的**舊Context列**；用取得鎖後Clock再驗revoked／期限／kind與Token。已被另一Login／Logout消耗則拒絕，不接著創建第二個登入。
4. 產生全新Session Token＋全新CSRF Secret，INSERT authenticated列、user_id=經Password驗證的User、created=last_activity=t、absolute=t＋8小時。
5. 同交易將舊Context.revoked_at置t；原authenticated Session或preauth皆失效，其他獨立Token不變。COMMIT後才Set-Cookie及回User／新CSRF。
6. React先清舊身分資料，再以新Context重建狀態／通知分頁。不能沿用舊ID、接受Body帶來的Session ID、把舊preauth直接升級，或撤銷同User所有裝置。

若兩個Login先同時完成Password Verify，鎖與舊Context重驗使其中最多一個消耗同一有效Context。這保護Server狀態，仍需§6.6處理Browser Cookie回應順序。PG寫入／Commit失敗不得Set-Cookie「假登入」；Commit網路結果不明則走狀態讀回，不盲目再建Session。

### 6.3 後續Request與Identity

Browser附Cookie→FastAPI Cookie／Session Dependency→Hash Lookup→檢查：

- kind=authenticated、user_id存在；
- revoked_at IS NULL；
- 判定時間 < absolute_expires_at；
- 判定時間 < last_activity_at＋30分鐘。

等號即拒絕，兩種期限必須同時通過；測8小時邊界時要先維持最近有效活動，避免測到的其實是閒置到期。Session存在但preauth、過期或撤銷均無authenticated身分。建立Request範圍Identity後，Mutation驗CSRF／來源，Service再驗Owner、expected版本與業務規則，Repository使用參數化查詢。公開讀取可把不存在／無效Session當Anonymous，只回公開投影；PG不可用不會因而放行私人資料。

**認證判定點**與業務Commit不同：撤銷／過期後才開始的新判定必拒絕；已在之前通過的在途工作可能完成，包含已授權的照片處理。不得宣稱登出會回溯取消Request／復原已Commit操作。若某流程額外再次認證，就以那次新判定拒絕，但不將它描述成所有在途工作的全域取消保證。

### 6.4 Logout、過期及重複Logout

正常Logout：同Origin POST＋Cookie＋對應CSRF→短交易鎖目前列→設定revoked_at（已有值不清／不重設）→Commit→204＋清同名Cookie→React清私有State／Cache／照片預覽並通知其他分頁。不更新其他裝置的列；僅清React／Cookie會留下可重放的Server Session，因此不算完整Logout。

本輪選擇以下冪等／失效處理，**不是取消CSRF**：

- 已知authenticated列即使已過期／已撤銷，只要仍保存且原CSRF Token正確、來源通過，可完成「確保該Token已撤銷」並清Cookie，回204；這是Logout專用例外，不能讀私有資料或續期。
- 有效preauth Context也可POST Logout撤銷該上下文、清Cookie，回204；它本來就沒有登入身分。
- 無Cookie／未知或已清理列、preauth到期、沒有可驗證Token：拒絕403 csrf_context_required或csrf_context_invalid，不先清Cookie。UI在序列化流程中取新preauth Context，再對該Context送Logout完成回到匿名。不能把缺Token一律視為安全登出。
- PG不可用／未確定Commit：503／結果不明，不顯示「Server已撤銷」。UI可先遮蔽私人畫面，但要保留尚未確認提示與安全重試流程。
- 逾時重試針對同一Context；若Cookie已切換且舊CSRF與新Cookie不相符，拒絕，不能誤登出新的登入。

這讓過期／重複操作可回匿名，同時保持所有Logout都需來源＋Context Token。失效列保留多久不影響業務認證；清理後要重新Bootstrap，不要求永久保留所有撤銷列。

### 6.5 last_activity_at白名單與續期競態

| Request類別 | 是否續期 | Why／條件 |
| --- | --- | --- |
| 成功新增／編輯車、實際C異動、上下架、補登／更正、主圖成功替換 | 是 | 必須已authenticated、CSRF／Owner／規則通過且業務真正成功；已完整通過授權／驗證的冪等管理No-op（如重複上架）也算活動，但不改Vehicle狀態／刊登時間／無變更的row_version；2D需照此映射。 |
| Owner主動打開車庫／管理詳情／完整履歷 | 是 | 專用受保護Owner讀取操作成功才算；不自動刷新／輪詢／預抓該操作。具體路徑留2D。 |
| 公開Marketplace／公開詳情／搜尋 | 否 | 不要求登入，不能順便使Cookie保活。Owner管理讀取若與公開頁共用資料，需由Contract明分；不信任「human=true」旗標。 |
| Get Current User／Get CSRF Context | 否 | 恢復／焦點／跨Tab確認屬背景身分處理，不變更期限。 |
| 圖片讀取、靜態資產、預覽、背景輪詢／預抓 | 否 | 網頁開著或圖片重載不等於有效使用。 |
| 401／403／404／422／409／429、業務失敗／處理未完成 | 否 | 遭拒或尚未成功的Request不能保活。Logout也不續期。 |

MVP不對Owner業務讀取做自動輪詢／預抓。Server能限制哪些操作續期，但不能從任意HTTP Client證明「真的是人類點擊」；若日後新增背景資料更新，須先重審白名單與2D Contract，不能靠Client標記宣稱保證。

**Touch協定 [APP]**：

1. 業務Transaction已結束／讀取成功後，另用短Transaction鎖Session列；不持Vehicle Lock再等待Session Lock，沿用Database Design §7.4。
2. 鎖後重新取當時Clock；再次要求authenticated、未撤銷、閒置與絕對未過期。有效才把last_activity改為不倒退的可信時間；created／absolute／revoked永不因Touch改動。
3. 登出先Commit→Touch條件不成立；Touch先Commit→登出仍可撤銷。到期後不得以Request較早成功為由UPSERT／重新建列／清revoked復活。
4. 普通Response不Set-Cookie。若成功操作耗時跨過30分鐘或8小時，資料可以已Commit但Touch拒絕、需重登；不得將「未續期」說成「業務沒保存」。
5. Touch DB故障也不能抹消已Commit業務結果。保留成功事實，記不含秘密的續期失敗／需重驗資訊；2D為此定義回應Metadata，UI不盲重送Mutation。API只有在真正確認Rollback時才稱未保存。

清理是空間管理，不是期限判定；可按既有I-06回收。API重啟不重設時間，PG Volume仍在的正常重啟可繼續有效Session。DB暫停時受保護操作fail closed；Backup Restore先失效所有Session／preauth再開流量，避免舊Cookie復活。

### 6.6 Cross-tab與晚到Response：UI與Cookie要分開處理

**UI資料**：每Tab持本機authEpoch及目前User ID；Request發出時記錄這兩者。登入／登出／失效事件立即提升Epoch、清User Cache、遮蔽私人畫面、撤銷可控Object URL並取消舊請求。Response回來時，Epoch／User不符就丟棄，不准將A資料填進B帳號，即使兩次登入是同User亦看Epoch。

BroadcastChannel只傳「auth changed／invalidate」及不含秘密的通知識別，不傳Cookie、CSRF、Email或私人資料。可執行Tab在收到事件後≤5秒清理（PRD FR-003-AC04）；焦點／pageshow／BFCache恢復先遮蔽再Get Current User及取得目前CSRF，不依賴事件必定送達。Cookie Jar仍是共用，兩Tab不能宣稱各自登入不同帳號。

**Cookie回應**：Browser可能在JS丟棄JSON前已套用Set-Cookie，所以Auth Epoch與AbortController都不能撤回Header。本提案：

- 所有會寫Cookie的Bootstrap、Login、Logout，及需要協調它們的Auth狀態恢復，在目標HTTPS Chromium以同Origin Web Locks的同一鎖名稱序列化；鎖涵蓋fetch完成／Cookie已處理與本次身分確認，不只包本機State更新。
- 普通API、身分查詢、Touch、失敗Response不Set-Cookie；Context GET重用有效列也不Set-Cookie。因此晚到的舊資料／401不會再寫回舊登入Cookie。
- 同一舊Context只能一次成功轉登入，Server短交易／撤銷保護重複Login，不以Browser鎖替代Server安全。
- Auth Request網路不明時，暫停自動Login重試／其他Cookie變更，遮蔽並重新確認，不向使用者宣稱已登入／已登出。單次me回匿名不證明先前Login已結束；未能收斂就保持未確認，不自動解除防護。中止fetch不代表Server沒執行；須保留「結果不明」，不得Refresh就把尚未釐清的操作當沒發生。
- Web Locks支援、分頁崩潰／凍結、長時間網路不明與Cookie回應重排必須測試；不支援時先明確限制／拒絕並行Auth流程，不能用不具原子性的localStorage旗標冒充跨Tab鎖。跨任意不遵守Contract的Client，不保證所有Cookie Response有序。

**保證範圍**：Server絕不把已撤銷Token復活；UI丟棄舊資料；正常受控Browser流程協調Cookie寫入。舊Set-Cookie若因非受控並行回來，可能造成Cookie倒退／被清除而要重登，不能宣稱Browser有CAS保證或此情況不可能發生。任何新認證仍須查PG，不因Cookie又出現就恢復失效Session。

參考 [Web Locks API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API)。這是同Origin Browser協調機制，不是DB鎖、權限控制或分散式鎖服務。


## 7. Sequence Diagrams

圖中React在Browser執行；Cookie Jar由Browser管理；Caddy／FastAPI／PG在Server。Dependency與Business Service是同一FastAPI Process內部元件，箭頭是函式呼叫，不是Microservices。Client到Caddy經HTTPS，Caddy到API為受控內網HTTP，API到PG為私有DB連線；實際TLS內網設定留部署，不能把箭頭理解成所有鏈路已加密。

### 7.1 Login（含Pre-auth）

~~~mermaid
sequenceDiagram
    actor U as 使用者
    participant R as Browser React
    participant B as Browser Cookie Jar
    participant G as Caddy TLS入口
    participant A as FastAPI Auth Service
    participant D as PostgreSQL
    U->>R: 打開登入頁
    R->>R: 取得跨Tab Auth Lifecycle Lock
    R->>G: GET CSRF Context，同Origin
    G->>A: 受控轉送
    A->>A: 驗來源與Fetch Metadata
    A->>D: 原子csrf_context限流
    A->>D: 查Cookie對應Context（若有）
    alt 無有效Context
        A->>D: INSERT preauth與csrf_secret
        A-->>G: JSON CSRF Token＋Set-Cookie
        G-->>B: 設HttpOnly preauth Cookie
        G-->>R: Token，no-store
    else 已有有效Context
        A->>D: 讀既有Secret，不續期
        A-->>G: 同Token，無Set-Cookie
        G-->>R: Token，no-store
    end
    R->>R: 釋放Bootstrap Lock
    U->>R: Email、Password並送出
    R->>R: 再取得Lifecycle Lock，不持鎖等待使用者輸入
    R->>G: POST Login＋X-CSRF-Token，自動附Cookie
    G->>A: 轉送
    A->>A: 先驗來源／Fetch Metadata
    A->>D: login限流／Context Lookup
    A->>A: 驗Context／CSRF Header
    A->>D: canonical Email User Lookup
    A->>A: Library Verify或Dummy
    alt 憑證及安全驗證通過
        A->>D: BEGIN，鎖舊Context，鎖後重驗
        A->>D: INSERT全新authenticated Session與Secret
        A->>D: 撤銷舊Context，COMMIT
        A-->>G: User＋新CSRF Token＋新Set-Cookie
        G-->>B: 替換成全新HttpOnly Cookie
        G-->>R: 成功，no-store
        R->>R: 清舊Cache，更新Epoch，通知Tabs
    else 失敗
        A-->>G: 對應錯誤，不Set-Cookie、不建立登入
        G-->>R: 失敗結果
    end
    R->>R: 完成本次確認後釋放Lock
~~~

圖為高階成功路徑；實際先驗來源、限流、Context／CSRF才做昂貴Verify，失敗即停止，不是所有錯誤都回401。圖中Server錯誤Response也經Caddy回傳，省略部分返回箭頭以維持可讀性。註冊可重用同preauth流程，但只INSERT User並引導手動登入。

### 7.2 受保護業務Request

~~~mermaid
sequenceDiagram
    participant R as Browser React
    participant G as Caddy
    participant A as FastAPI Dependencies
    participant S as Business Service
    participant D as PostgreSQL
    R->>R: 記錄authEpoch與User ID
    R->>G: Mutation＋Cookie＋CSRF Header
    G->>A: 受控HTTP轉送
    A->>D: 新Statement查Session Hash／期限／撤銷
    alt Session有效且來源／Token通過
        A->>S: 本Request可信Identity
        S->>D: BEGIN，鎖自己的Vehicle
        S->>D: 鎖後新Statement讀有效資料／版本
        S->>S: Owner、expected版本、業務規則
        alt 全部通過
            S->>D: 寫入及COMMIT
            S->>D: 另個短交易條件Touch Session
            Note over S,D: 不清revoked、不延absolute；失敗不抹消業務成功
            S-->>A: 已保存結果
            A-->>G: 無Set-Cookie，no-store
            G-->>R: 成功事實及必要續期狀態
            R->>R: 只接受目前Epoch／User的Response
        else 越權／衝突／規則不符
            S->>D: ROLLBACK
            S-->>A: 404／409／422等，不續期
            A-->>G: 錯誤，無Set-Cookie
            G-->>R: 錯誤結果
        end
    else Session／來源／Token失敗
        A-->>G: 401或403，無業務寫入、不Set-Cookie
        G-->>R: 拒絕
    end
~~~

Owner成功讀取可以不取得寫入Row Lock，但仍以同一Statement驗可見性／投影；圖以已有Vehicle的Mutation為例。新建車沒有既有Row可鎖，依2B的Unique與建車交易。照片解碼不持Vehicle Lock，其最終指標切換仍遵守2B協定。

### 7.3 Logout與在途Request

~~~mermaid
sequenceDiagram
    participant T1 as Browser Tab A
    participant T2 as Browser Tab B
    participant G as Caddy
    participant A as FastAPI
    participant D as PostgreSQL
    T2->>G: 舊受保護Request
    G->>A: 受控轉送
    A->>D: 撤銷前先完成有效Session判定
    T1->>T1: Lifecycle Lock，提升Epoch／遮蔽私人內容
    T1->>G: POST Logout＋Cookie＋CSRF
    G->>A: 受控轉送
    A->>A: 驗來源／Context Token
    A->>D: BEGIN，鎖當前Session
    A->>D: 設revoked_at，COMMIT
    A-->>G: 204＋清Cookie
    G-->>T1: Server已確認撤銷
    T1->>T2: BroadcastChannel通知Invalidate
    T2->>T2: 收到後≤5秒清私有UI／舊請求世代失效
    T2->>G: 撤銷後的新受保護Request
    G->>A: 受控轉送
    A->>D: 查Session，已撤銷
    A-->>G: 401，無Set-Cookie
    G-->>T2: 新Request遭拒
    A-->>G: 先前在途Response可能晚到
    G-->>T2: 舊Response，無Set-Cookie
    T2->>T2: 依Epoch丟棄舊結果
    T1->>T1: 釋放Lifecycle Lock
~~~

若PG／網路失敗，不能走「Server已確認撤銷」分支。凍結Tab恢復先遮蔽再重驗；不宣稱它在凍結中仍能執行5秒清理。原本已判定通過的工作可完成，Cookie與Server撤銷的界線依§6。

## 8. Authorization & Ownership

### 8.1 Authorization Matrix

系統只有Anonymous Visitor與Authenticated User；下表的Owner／非Owner是**資源關係**，不是新增兩個帳號角色。

| 能力 | Anonymous | Authenticated，該車Owner | Authenticated，非Owner |
| --- | --- | --- | --- |
| Marketplace／品牌型號搜尋 | 可，只看已上架公開摘要 | 同公開規則 | 同公開規則 |
| 已上架詳情／有效履歷／全部更正版本／C下修摘要 | 可，公開投影 | 可，另可取Owner投影 | 可，公開投影 |
| 未上架詳情／全部版本／C下修摘要 | 不可 | 可 | 不可 |
| 自己的車庫 | 不可 | 可，僅Session User擁有的車 | 不可指定別人的User ID取得其車庫 |
| 建車 | 不可 | 可，新車owner=Session User | 可建立自己的車，不能指定別人Owner |
| 編輯車、C提高／有理由下修 | 不可 | 可，仍受規則／版本控制 | 不可 |
| 上架／下架 | 不可 | 可，上架驗價格／ready主圖 | 不可 |
| 上傳／替換主圖 | 不可 | 可，初始及最終歸屬／版本驗證 | 不可 |
| 讀目前主圖 | 僅已上架且current／ready | 自己的車可讀 | 僅已上架且current／ready |
| 新增維修紀錄 | 不可 | 可，歷史邊界／C驗證 | 不可 |
| 更正維修紀錄 | 不可 | 可，同車同事件目前末端＋理由 | 不可 |
| 完整VIN | 不可，僅公開末六碼 | 可 | 不可，即使車已上架 |
| 他人Email／帳號憑證／原始照片 | 不可 | 不可；Owner也不讀未處理Raw Upload | 不可 |

登入不賦予機構認證、保險、Admin或過戶能力；User可以同時是自己車的Seller與別車的Visitor。source由Server固定owner_self_reported，填機構名稱不會授予驗證資格。

### 8.2 FastAPI各層責任

| 層 | What／How | 不負責／Failure |
| --- | --- | --- |
| Middleware／Gateway | TLS／Host／可信代理、一般大小限制、基礎安全Header。 | 不靠URL含garage就當Owner；Caddy不讀車輛Ownership。 |
| Authentication Dependency | 從Cookie查共享Store；提供optional或required Identity，統一失效結果。 | 不把Cookie存在／Body user_id直接當身分；Starlette簽章SessionMiddleware不等於PG Store。 |
| CSRF／Source Dependency | 統一Context／來源／Header Token驗證，Protected Router預設要求，公用入口明示。 | 不在每個Handler複製容易遺漏的片段；不只依React流程驗證。 |
| Service Layer | 用可信User執行「操作這個資源」授權與交易規則，Mutation鎖後再驗Owner／版本。 | 不只驗登入便修改任意UUID；不能以單次頁面載入授權後續所有Request。 |
| Repository／ORM | Query帶可信User／可見性條件，參數Binding，明確Public／Owner投影。 | 不讓可見性驗證與實際讀取分成可被下架穿插的不同Snapshot；FK不代替業務授權。 |
| React | 依能力顯示按鈕／錯誤、清Cache／重驗。 | 隱藏按鈕只是UX；DevTools／curl可直接送Request。 |

### 8.3 防IDOR／BOLA與投影外洩

- Session的user_id才是可信Owner候選；Create Body根本不接受owner_user_id／source／submitted_by／Server時間。未知敏感欄位以Schema拒絕，不做Mass Assignment。
- 現有Vehicle寫入以id＋owner_user_id=可信User鎖定；Event／Version／Image ID都沿關係Join到Vehicle再判定，防跨車ID混用。更正另驗expected current，不只查Version屬User。
- Read以單一Primary Statement驗「is_listed OR owner_user_id=可信User」，並取對應投影；全部舊版、下修摘要、主圖各入口一樣。Owner完整VIN不可被Public Serializer順手帶出。
- UUID降低可猜性，不是安全檢查。公開知道某車存在，也不代表知道它下架後的私人狀態／圖片／完整VIN。
- 圖片只讀目前current且ready；先授權再導出Private key／串流，不提供可繞過的公開Static／Raw／永久簽章URL。下架Commit後新判定拒絕；已交付副本與已授權在途界線維持2A／2B。
- 所有動態JSON／圖片首次交付no-store；若2D加Range／ETag，必須先做同樣授權，不先回304。不可把no-store誤認為能刪掉JS Cache或外部截圖。

### 8.4 401／403／404政策

- **401 authentication_required**：要求authenticated的操作，Cookie缺失／preauth／失效。先拒絕身分，不查私人資源存在性。
- **403 csrf_invalid／source_not_allowed**：Context或來源安全條件未通過；不帶User／資源細節，不清新Cookie。
- **404 resource_not_found**：身分已驗證但無權管理／讀該私人資源，與不存在使用同類外部結果。即使該車曾公開，也不回「B車現在下架」等多餘資訊。
- **403 operation_not_allowed**：僅適用存在性本來公開且無需隱藏的非資源能力限制，例如已登入Context嘗試Register；不泛用於Private ID探測。
- **409 conflict**：已授權後的expected版本／目前末端／唯一性衝突；資料只引用使用者可見範圍。**422 validation_error**用於可回報欄位／業務界線。
- 錯誤碼一致可降低洩漏，不代表總時間／所有旁通訊號完全相同。詳細錯誤Response結構由2D統一，本輪只定Auth與權限語意。


## 9. Rate Limiting Design

### 9.1 算法比較與驗收語意

| 方法 | What／How | 優點 | Failure／本案取捨 |
| --- | --- | --- | --- |
| Fixed Window | 每來源／Scope在固定時間窗累加，換窗重新計數。 | 一列Bucket＋原子UPSERT，符合2B候選表，跨Worker好理解。 | 交界可Burst；本輪採用但須明示窗口。 |
| Sliding Window | 按最近T時間的事件Log或其他滑動算法計數。 | 精確Log可保證任意T內N次。 | 精確Log要更多列／清理；加權近似也不是嚴格精確，需要改表／算法說明。 |
| Token Bucket | 持容量、剩餘Token及最後補充時間，按速率回補。 | 可明確容許Burst並限制長期速率。 | 不是「每5分鐘最多N次」的同義詞，需原子計算另一組狀態，本案不選。 |

**[2C選擇] Fixed Window**，明確向PRD NFR-SEC-05／SDQ-01補充窗口解釋：

| Scope | 每可信來源候選上限 | UTC窗定義 | 適用 |
| --- | --- | --- | --- |
| login | 20次／300秒 | 以Unix Epoch對齊，每逢固定5分鐘邊界換窗。 | 每個通過來源檢查而到達Gate的Login，包括錯密碼／不存在帳號／CSRF或Body錯誤／成功。 |
| register | 10次／3600秒 | 以Epoch對齊的整小時窗。 | 到達Gate的Register，包含重複／格式／CSRF錯誤與成功。 |
| csrf_context [CP-02] | 60次／300秒 | 同固定5分鐘窗。 | Get CSRF Context，即使重用已有Context也計數；限制匿名建立PG列與Bootstrap濫用。 |

前N次可繼續後續檢查，第N＋1次起429、通用訊息＋Retry-After=到窗口結束剩餘整秒（向上取整至少1），不透露帳號是否存在、不永久鎖帳號。成功／失敗消耗額度後不退還；邊界／數值均為候選政策，部署後仍須驗證。

**Burst例**：04:59最後1秒接受20次，05:00新窗又接受20次，約2秒40次可能成立；不能對外宣稱「任意連續5分鐘最多20次」。現行PRD把數值與來源／儲存／窗細節留設計評估，並未承諾滑動窗，因此可提出此方案。若審查認為NFR本意是精確滑動窗，必須回到CP-02改模型／需求，不能偷偷以Fixed Window當等價實作。

### 9.2 PostgreSQL Bucket與多Worker

Key為(scope,subject_hash,window_start)，其中subject_hash為對canonical來源IP使用獨立Server Secret作HMAC-SHA256，32 bytes；不含Email／User ID，不依帳號存在而建立不同Counter。IP低熵，不用普通SHA-256假稱匿名；HMAC是去識別候選，不代表完全匿名資料。

- Server用PG可信時間求window_start／end，expires_at=window_end；不接受Client自報時間。
- 短交易一次原子INSERT／ON CONFLICT UPDATE計數，回傳本次判定。不得先SELECT count再在Python加一；Composite PK與PG衝突更新處理多Worker競爭。
- attempt_count可飽和在N＋1，持續拒絕不無限加到INTEGER溢位；這是Gate狀態，不是精確總流量分析。
- Gate交易獨立Commit，後續Password錯誤／User建立失敗不能Rollback已消耗額度。DB錯誤／Commit不明則不進行昂貴認證或創建登入，503，不使用各Worker本機Counter放行。
- 清理只回收expires_at已過的Bucket；背景清理停了不影響新窗口Key。正常PG重啟不歸零；HMAC Secret必須所有Worker一致並持久配置，輪替需在受控窗口／維護中規劃，不能每次API重啟換Key來重置限制。
- Database Design §4.8已有全部數值欄位；只需CP-02擴scope CHECK並定版政策，不新增Redis／事件表。若改Sliding／Token Bucket，才需要新Data Shape與審查。

原子語意參考 [PostgreSQL INSERT／ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html)。Constraint／原子更新並不代替可信IP、窗口、上限及清理政策的[APP]實作。

### 9.3 Caddy後的可信IP

候選只有Browser→Caddy→FastAPI一個受控入口，沒有假設CDN／額外Load Balancer：

1. Caddy從實際連線Peer識別來源，忽略／重建Client帶來的X-Forwarded-For等敏感代理Header；API Port不對外。
2. ASGI Server只信任**明確Caddy Peer／受限代理範圍**所提供的Forwarded資訊，再形成可信Request Client IP。FastAPI讀經這層處理的來源，不自行取任意XFF第一段。
3. 不設任意來源*或籠統信任所有Private IP；實際Docker Peer與信任設定需驗證。Header有值不代表可信；若信任邊界無法成立，部署不能宣稱限流有效。
4. IPv4-mapped IPv6等表示統一，用標準IP Parser；本輪按完整IP地址，不綁Session必須一直同IP。IPv6地址輪替、Botnet、多出口可繞單來源政策，保留殘餘風險。
5. 未來若加CDN，必須重新設計右到左的可信Proxy鏈、CIDR更新與直連封鎖；不能沿用單一入口假設。

參考 [Caddy reverse_proxy文件](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) 的Forwarded Header與trusted_proxies語意。它說明預設行為，不是本專案配置已完成的證據。

### 9.4 NAT、Availability與成本

同公司／校園NAT的人會共用額度，可能被同出口另一人耗盡；使用者看到通用429與可重試時間，展示可先配置合成帳號與受控訪問（DPQ-05），不新增永久帳號鎖／Captcha／人工Admin解鎖功能。

來源限流對Distributed Credential Stuffing不完整；本案無MFA，不能承諾防所有帳密重用攻擊。昂貴Hash工作另有有界併行與Gateway Body／連線保護候選，因為攻擊者可在到達應用Gate前耗費網路／解析資源。PG本身是Session與限流共同單點；故障503、不fail open。完整Edge流量保護與容量需部署量測，不以本表冒充DDoS防禦。

## 10. Authentication Interface Draft

### 10.1 共通Contract

以下五個路徑是**本輪候選介面**，尚未建立任何Endpoint；2D可統一命名／Envelope，但不能降低本文件語意。只定Auth，不定Vehicle／Maintenance／Image全部API。

所有Auth回應含錯誤均Cache-Control: no-store；不回Session Token／token_hash／Password Hash／DB路徑。Body Schema拒絕未知敏感欄位；不符Content-Type為415，Auth Body超8 KiB為413。錯誤Serializer不得原樣輸出Pydantic ValidationError的input／ctx／原始Body，需白名單投影loc／通用訊息；Proxy、APM與Debug Trace同樣不得捕捉Password／Confirmation或Cookie／CSRF。Cookie格式嚴格失敗視為無有效Context；重複Cookie等歧義Request可400，不自動Set-Cookie。Request ID與分類結果可Log，秘密／Body不得Log。

錯誤優先序：TLS／Host／大小等傳輸檢查→來源→Auth公共Gate（有者）→Context／required Identity→CSRF→Schema／憑證／Service。Protected Mutation缺有效登入401；Context有效但CSRF失敗403。Register／Login是登入前流程，沒有有效Context時403 csrf_context_required，而非把preauth誤判登入；同一錯誤碼不暴露User存在性。

### AI-01 Get CSRF Context

| 項目 | 候選行為 |
| --- | --- |
| Method／Path | GET /api/auth/csrf |
| Authentication／CSRF | 可未登入，沒有前置CSRF Header；必須§5.4來源／Fetch Metadata、csrf_context Gate。 |
| Request | Cookie可有；不接受user_id／指定Session Token。 |
| Response | 200：context_type（preauth／authenticated）、csrf_token、context的absolute_expires_at；Token不作User身分證明。 |
| Cookie | 無有效Context才新建preauth並Set-Cookie Max-Age=900；有效Context不重設Cookie、不續期。 |
| Failure | 403來源錯誤、429、400歧義Cookie、503 Store；失敗不Set-Cookie。 |
| PostgreSQL | Gate；Lookup；必要時INSERT preauth＋Secret。不建立User、不續期authenticated。 |

### AI-02 Register

| 項目 | 候選行為 |
| --- | --- |
| Method／Path | POST /api/auth/register |
| Authentication／CSRF | 有效preauth＋對應Header Token＋來源＋register Gate；authenticated Context嘗試註冊為403 operation_not_allowed，先由UI明確登出。 |
| Request | JSON：email、password、password_confirmation；不接受角色／owner／Hash。 |
| Response | 201：註冊完成、引導手動登入；不回新登入狀態或憑證。 |
| Cookie | 不改Cookie；preauth仍是preauth。 |
| Failure | 422不合規、409通用註冊衝突、403 Context／Token／來源、429、503。不能回既有User資料。 |
| PostgreSQL | canonical Email Lookup／Unique；交易外Hash，短交易INSERT app_users；唯一衝突Rollback。無authenticated INSERT。 |

### AI-03 Login／Re-login

| 項目 | 候選行為 |
| --- | --- |
| Method／Path | POST /api/auth/login |
| Authentication／CSRF | 有效preauth或authenticated＋目前Token＋來源＋login Gate。 |
| Request | JSON：email、password；不能指定Session ID／期限。 |
| Response | 200：authenticated=true、user（id／自己的canonical email）、新csrf_token、absolute_expires_at；不回raw Session Token。 |
| Cookie | Commit確認後設定全新Session Cookie Max-Age=28800；舊Context同交易撤銷。 |
| Failure | 有效格式但憑證錯誤統一401 invalid_credentials；422格式、403安全Context／Token／來源、429、503；初驗後Context被併發消耗可409 auth_context_changed。所有失敗不Set-Cookie／不續期。 |
| PostgreSQL | Gate、User／Context；短交易鎖舊Context再驗、INSERT新authenticated＋Secret、撤銷舊列。其他裝置不改。 |

### AI-04 Logout

| 項目 | 候選行為 |
| --- | --- |
| Method／Path | POST /api/auth/logout |
| Authentication／CSRF | 正常authenticated Context；有效preauth或保留的過期／撤銷authenticated列按§6.4處理。全部需來源＋對應CSRF。 |
| Request | 無必要業務Body；Cookie＋X-CSRF-Token，不能傳別的Session ID要求撤銷。 |
| Response | 204，表示已確認該Context不再可登入；前端才顯示Server登出完成。 |
| Cookie | Commit／已確認撤銷後清同Name／Path的Cookie。不得由一般401自動代做。 |
| Failure | 403 Token／來源／缺有效Context需安全Bootstrap；503／網路不明不宣稱撤銷成功。重複且能驗證Context的Logout仍204。 |
| PostgreSQL | 鎖目前Context、revoked_at單向更新或確認既有值；不影響其他Token、不Touch。 |

Cookie已未知／被清理時的Bootstrap僅為使重複登出有安全Context，不會撤銷另一個已登入帳號。遇到Context／User已變更的衝突，UI清舊資料並要求重讀／確認，不自動刷新Token後重送舊Logout或其他Mutation來操作新身分。

### AI-05 Get Current User

| 項目 | 候選行為 |
| --- | --- |
| Method／Path | GET /api/auth/me |
| Authentication／CSRF | Optional Session，無CSRF Header；不作業務Mutation／續期。Host／TLS仍檢查，無任意CORS。 |
| Request | Cookie可有；不接受「要查的User ID」。 |
| Response | 有效：200 authenticated=true、自己的User id／email、absolute_expires_at；無有效登入：200 authenticated=false、user=null。不得把DB故障當Anonymous。 |
| Cookie | 不設／刪／刷新Cookie。 |
| Failure | 400歧義Request、503 Store等；受保護業務API仍用401，不能將本介面的200匿名語意套過去。 |
| PostgreSQL | 新Statement按Q-06判期限／撤銷並Join User；不更新last_activity。 |

AI-01／AI-03會回CSRF Token是明確秘密傳輸面，需HTTPS／no-store／不Log。AI-05只供User資訊與UI同步，不發出登入Token；401／200不作Client端認證權威，所有業務Request仍再驗。


## 11. Threat Model & Security Testing

### 11.1 Scope、Assets、Attacker與Trust Boundaries

這是**設計階段Threat Model**，沒有可執行新版API可掃描；風險不是已證實程式漏洞，也不將上游提案標成已部署防線。候選公開網路展示、合成資料，實際訪問範圍待DPQ-05；即使資料是合成，Password仍可能被重用，Cookie與寫入權限仍有價值。

Assets：A1 Password／Hash；A2 raw Cookie、CSRF及配置Secret；A3未上架VIN／履歷／照片與User Email；A4有效更正鏈、C／H／Ledger及刊登狀態；A5 PG／CPU／RAM／磁碟可用性；A6 Backup與持久紀錄。

Attacker可以開外站誘導Browser、直接送HTTP、建立普通帳號A改UUID探測B、偽造一般Header或大量嘗試憑證；另評估已竊Cookie／只讀DB備份外洩。沒有假設一般Visitor可直接改PG／主機、解密TLS或控制Caddy。若Host／DB管理權已失陷，本案Hash／Ownership／Audit不能宣稱阻止管理者竄改，須另外做Secrets／備份／運維處置。

| Boundary | 資產／控制責任 | 尚待驗證 |
| --- | --- | --- |
| 不可信Browser→Caddy | TLS、Host、大小／連線、Cookie／來源訊號。 | DNS／Certificate／Proxy Header與實際暴露Port。 |
| Caddy→FastAPI | 只信可信Peer、Scheme／來源IP；Session／CSRF／Owner在API。 | XFF偽造、直接API入口、Docker Network可達性。 |
| API→PG | Binding、Runtime最小權限、短交易、共享Session／限流。 | DB角色、Unique／FK／Lock、故障與Retry。 |
| API→Private Volume | Query授權後讀current／ready；CPU／I/O隔離。 | 無Static旁路、檔案清理與替換／下架競態。 |
| User文字／API→React DOM | 純文字、安全Response投影、不信Storage／HTML。 | Stored／DOM XSS、安全Header與Cache。 |
| Backup／運維→Runtime | 受控Restore、全部Session失效、秘密／日誌最小化。 | 舊Cookie／CSRF重放、Backup存取及實際還原。 |

### 11.2 風險表

優先序是「若缺少所述控制的開發／驗收優先度」，非已量測事故機率。可能性／衝擊採高／中／低，假設公開展示且控制尚待實作；有既有上游設計不等於殘餘風險已消除。每列防線皆是[設計]，實作與測試皆[TEST]。

| ID／風險 | 攻擊路徑／資產 | 可能性×衝擊／優先序理由 | 本案防禦提案 | 限制與驗收 |
| --- | --- | --- | --- | --- |
| TH-01 SQL Injection | Email／搜尋／ID字串進SQL改變語意，A1／3／4。 | 中×高→高；一個拼接查詢可越權讀寫。 | Repository參數Binding、型別／欄位白名單、Runtime最小權限。 | ORM raw SQL仍可寫錯；AT-17注入字串不影響結構、不爆SQL／秘密。 |
| TH-02 XSS | 維修描述／URL／錯誤文字被當HTML／JS，A2／3／4。 | 中×高→高；同Origin腳本可代User操作。 | JSX文字呈現、不用未信任dangerouslySetInnerHTML；輸出投影；候選CSP與frame-ancestors由Gateway交付。 | HttpOnly不阻止代送或讀CSRF；AT-18驗純文字與Header，不宣稱CSP消除全部XSS。 |
| TH-03 CSRF | 外站用Victim Cookie登入／登出／改車／上傳，A2／4。 | 高×高→高；Browser自動附憑證。 | 同Context Synchronizer＋來源／Fetch Metadata＋SameSite，含preauth。 | XSS／已竊Cookie的Native Client不在CSRF防線內；AT-06／07／20。 |
| TH-04 Session Fixation | 先植入可預測／攻擊者已知ID，誘導受害者登入，A2。 | 中×高→高；若不換ID可接管。 | 32 random bytes、Server生成、不接受指定ID、Login新列＋撤銷舊Context。 | 不防直接竊取新Cookie；AT-04比較換ID／舊Context拒絕。 |
| TH-05 Session Hijacking | XSS、惡意Extension、Log或HTTP竊Cookie，A2／3／4。 | 中×高→高；Bearer可被持有人使用。 | HTTPS、HttpOnly／Secure／Host-only、少第三方JS、不Log、短期限／撤銷。 | Endpoint／Extension或主機被控制不能只靠Cookie flags解決；AT-05／17。 |
| TH-06 Credential Stuffing | 多來源嘗試外洩Email＋Password，A1／2。 | 中×高→高；人類重用密碼常見且可分散來源。 | Argon2id、同類錯誤、共享來源Gate、有界Hash工作。 | 無MFA且IP限流不擋Botnet；AT-03／13／14；不宣稱完全防禦。 |
| TH-07 Brute-force Login | 單來源大量猜密碼／耗KDF，A1／5。 | 高×中→高；公開入口成本不對稱。 | 20／固定300秒、Counter原子、Hash併行有界、Body大小。 | 窗交界Burst及NAT誤傷；AT-13／14，無帳號永久鎖。 |
| TH-08 IDOR／BOLA | A改Vehicle／Event／Version／Image ID取得B私有資料或修改，A3／4。 | 高×高→高；最直接的物件授權錯誤。 | 每入口沿關係驗Owner／公開狀態、固定投影、Service鎖後重驗、404。 | 漏一個舊版或圖片入口就失效；AT-08／20需直接HTTP而非只測UI。 |
| TH-09 Stolen Cookie Replay | 攻擊者持有效raw Token重送，甚至取自己的CSRF Token後寫入，A2／3／4。 | 中×高→高；不需猜密碼。 | Hash保存減少DB讀取直接重放；期限／本次撤銷、TLS與Cookie竊取面縮小。 | **有效Cookie被竊後仍可重放**；CSRF不阻擋持有人。AT-10：登出前可能成功、登出後新判定必拒。 |
| TH-10 Timeout／Revocation Race | 舊Touch／長Request在Logout後清revoked或重發Cookie，A2／4。 | 中×高→高；容易被只測單請求漏掉。 | 鎖後新Clock／條件Touch，不UPSERT、不Set-Cookie，明確在途界線。 | 先授權工作可完成；AT-09／11／15驗DB結果與UI。 |
| TH-11 Cross-tab Stale Data | A帳號Response晚到B帳號／凍結Tab顯示私有Cache，A3。 | 高×中→高；正常兩Tab就可觸發。 | Epoch＋User綁定、BroadcastChannel、焦點先遮蔽、Lifecycle Lock。 | 無凍結期間即時保證，非受控Cookie競態可能要重登；AT-12含Set-Cookie實際效果。 |
| TH-12 Backup Restore復活Session | 還原較早DB讓已登出的Hash再有效，A2／3／4。 | 中×高→高；正常Restore即可能觸發。 | 維護隔離、失效全部Session／preauth後再開入口。 | 只清Client或只排過期列無效；AT-16重放舊Cookie／CSRF皆拒。 |
| TH-13 Proxy／Rate-limit繞過 | 隨意XFF／改IP格式或Worker輪替得到新額度，A5／2。 | 中×中→中；配置錯誤使Gate近乎無效。 | 唯一入口、明確trusted peers、IP正規化、PG共用Counter／Secret。 | Botnet／IPv6輪替仍可繞；AT-13偽造XFF與多Worker總額。 |
| TH-14 Preauth／解析資源耗盡 | 無Cookie反覆Bootstrap寫PG，或大量JSON／multipart／昂貴Verify，A5。 | 高×中→高；未登入也可消耗。 | csrf_context Gate、15分鐘TTL、Body／Parser／工作預算、短交易清理。 | 到達Gate前仍耗資源；AT-14／20，網路DoS需部署量測。 |
| TH-15 Secrets／Cache外洩 | Log／Trace、URL、Public Serializer或Cache保存Cookie／私有內容，A1～3／6。 | 中×高→高；常見觀測／錯誤處理旁路。 | 不Log敏感Header／Body、no-store、Response白名單、私有檔案。 | no-store不回收已交付副本；AT-17／20及2B下架案例。 |

CSP候選需以正式Vite Build實測script-src等限制，避免為排錯直接加入unsafe-inline／unsafe-eval；frame-ancestors由HTTP Header交付防點擊劫持。這是Defense in Depth，不要求新增通用安全平台或把XSS全交給CSP。基礎原則參考 [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)。

## 12. Database Design Compatibility & Change Proposals

以下是**等待審查的回填清單**，沒有修改上游，也不是已套用Migration。除CP-01／02及可選的CP-03列內CHECK外，主要為定版語意。

| CP | 具體文件／條款 | 最小提案 | 相容性／Failure |
| --- | --- | --- | --- |
| CP-01 Synchronizer Secret | docs/DATABASE_DESIGN.md §4.2、§8.4、DBQ-04；§2 ERD | auth_sessions增加csrf_secret BYTEA NOT NULL，32 bytes，無Index／可猜Default；所有kind皆有獨立值。 | 保留Token Hash PK／User FK／kind。既有Session先失效再演進NN／CHECK，不用一個共用Default偽裝獨立Secret。只存CSRF Hash無法照本案重取原值。 |
| CP-02 Fixed Window與Bootstrap Gate | docs/DATABASE_DESIGN.md §4.8／DBQ-05；docs/PRD.md NFR-SEC-05／SDQ-01；docs/DECISIONS.md D-01／02剩餘項 | 保留Bucket欄位，scope CHECK增加csrf_context；定版20／300秒、10／3600秒、60／300秒固定Epoch窗、飽和Counter／Retry-After。 | 不與原Check login／register偷偷不一致；現有表只容納前兩Scope。若要精確Sliding，需另一模型，不能只改文案。 |
| CP-03 Preauth TTL | docs/DATABASE_DESIGN.md §4.2、§8.4 | preauth absolute=created＋15分鐘，last_activity=created、不得續期；可加kind條件CHECK。 | 現有created≤last<absolute可相容；authenticated仍恰8小時。15分鐘不是登入閒置期限的新值。 |
| CP-04 Email Canonical | docs/DATABASE_DESIGN.md §3／4.1、DBQ-03；docs/PRD.md §4.0／SDQ-05 | 固定validated normalized→PG lower；記錄UTF-8及一致Collation／Locale，Fixtures驗證idempotence與大小寫。 | 不必加raw Email／canonical_email第二欄或citext。實際PG映像Locale升版影響須測試；不能讓Python casefold另算Key。 |
| CP-05 Touch／Logout失效流程 | docs/DATABASE_DESIGN.md §7.4／8.2／8.4、Q-06；docs/SYSTEM_ARCHITECTURE.md §6.5 | 白名單、短Touch鎖後Clock／條件更新；Logout可驗保留失效列，但只作撤銷；一般Request永不重發Cookie。 | Q-06仍只查有效authenticated，不改成過期可讀資料；Logout另有專用Context讀取，不將例外套用全API。 |
| CP-06 Cookie／UI協調 | docs/SYSTEM_ARCHITECTURE.md §6.5、SDQ-01／05；docs/DATABASE_DESIGN.md DBQ-04／06 | 回填Cookie屬性、來源缺失拒絕、Web Locks／Epoch及結果不明策略。 | 不新增DB世代／全裝置登出表；不宣稱Epoch可取消Set-Cookie，非受控競態殘餘風險保留。 |

### 12.1 未改動的Schema與Native／APP保證

- app_users仍只有ID、canonical Email、Password Hash及建立時間；Argon2編碼不需新增Salt／Hash參數欄位。Email Unique提供併發保護，語法與大小寫流程仍依[APP]。
- auth_sessions仍一列代表一個Context；不另建JWT／Refresh Token表，不新增User角色。authenticated User非NULL／preauth User=NULL、絕對8小時、時間順序等既有[PG]列內Constraint保留。
- revoked單向、Clock有效性、活動白名單、CSRF來源與Token比對、Only Current Session撤銷是[APP]，不能拿普通CHECK保證「永遠不會復活」。
- Rate-limit Composite PK與原子更新是[PG]支援；來源信任／上限／窗口／HMAC Secret／過期清理是[APP]。
- Vehicle／Event／Version／Ledger／Image表及共同Vehicle Lock不變；Authenticator只提供可信Identity，不代替C≥H、更正鏈與圖片工作一致性。
- DB runtime／Migration角色分權與Append-only版本權限維持2B；本輪沒有執行任何GRANT、DDL或SQL。

### 12.2 現有設計是否矛盾？

沒有必要改掉PRD的Password、Session、Ownership、歷史／更正或公開邊界。上游原本留CSRF／限流／Email細節待2C，故本輪補方案不是功能變更。

但**未回填前確有兩個明確資料模型差異**：現行auth_sessions沒有csrf_secret，現行Rate-limit scope拒絕csrf_context；本文件不會宣稱現有Schema已能直接跑。CP-03是額外列內保護建議，CP-04～06是流程定版；若審查不同意新增欄位，應重選已綁Session的Signed方案並重審，而非移除CSRF或在欄位外偷偷存狀態。


## 13. Requirement Traceability

以下是設計覆蓋，不是驗收已通過。AC後綴沿用原PRD完整ID；未更改、刪除或重用任何FR／BR／NFR／AC。

| FR／現行AC | 本文件的Authentication／Authorization責任 | 主要測試 |
| --- | --- | --- |
| FR-001，AC01～05 | §3、§5、AI-02；Canonical Unique、Password／確認、preauth CSRF、註冊後手動登入、無認證宣稱。 | AT-01／02／06／17 |
| FR-002，AC01～08 | §4～7、AI-01／03／05；Cookie／PG Session、期限、換ID、非活動不續期、跨Tab／舊Response。 | AT-03～05／07／09／12／19 |
| FR-003，AC01～05 | §6.4～6.6、§7.3、AI-04；只撤銷本Token、5秒UI／在途邊界、結果不明、POST CSRF。 | AT-10～12／15／16 |
| FR-004，AC01～03 | Owner車庫、required Identity、Cache清理，§8。 | AT-08／09／12／15 |
| FR-005，AC01～05 | 可信Owner、Create欄位白名單、CSRF、預設未上架私有；不重定義VIN業務。 | AT-06／08／20及2B VIN競態 |
| FR-006，AC01／02／04～07 | 編輯／C更動Owner＋CSRF，Activity／Touch與版本控制；C≥H／Ledger沿用2B。 | AT-08／11／15；2B六Race |
| FR-007，AC01～03 | Owner＋CSRF／目前版本，上架資料完整性由Service維持。 | AT-06／08／20 |
| FR-008，AC01～05 | 下架後所有新讀取含圖／舊版Owner判定、no-store／在途界線。 | AT-08／12／20 |
| FR-009，AC01～04 | 匿名公開投影／固定搜尋能力、不藉Cookie延長Session。 | AT-08／09／17 |
| FR-010，AC01～07 | 有效及全部舊版／C下修摘要皆遵守可見性，完整VIN Owner-only、Email不外露。 | AT-08／12／17／20 |
| FR-011，AC01／04／06～08 | 補登Owner／CSRF，source／author由Server；日期／m／C沿用2B。 | AT-06／08／11；2B跨日／同日案例 |
| FR-012，AC01～07 | 上傳Header CSRF／Owner、受控圖授權、早期限制與失敗不換主圖。 | AT-06／08／14／20 |
| FR-013，AC01～08 | 同車Owner／CSRF／expected末端；不改原文、不自動改C、不刷新上架時間。 | AT-06／08／11；2B同末端競爭 |

停用條款：FR-006-AC03、FR-011-AC02／03／05；本文件不恢復「歷史不可低於C」「自動更新C」或「純文字補充即更正」等舊行為。

| 品質／待決ID | 覆蓋與剩餘責任 |
| --- | --- |
| BR-01～03／05／09～14／17 | §1、3、5、8：資源Ownership、公開投影、來源固定、無機構角色／真實認證。 |
| NFR-SEC-01～03 | Hash／Cookie／共享Store／每次身份；實作Log過濾、Dependency與Library驗證仍待完成。 |
| NFR-SEC-04／07／08 | TLS／同Origin、CSRF＋來源、no-store／私有圖；Proxy／Browser實測未做。 |
| NFR-SEC-05／09 | Fixed Window／共享PG、Header前置檢查／影像預算；窗口審閱與解碼實測。 |
| NFR-DAT-01～05 | canonical Unique、可信Owner／source／時間，Auth不破壞2B交易；更正／C業務仍在Service。 |
| NFR-REL-01～03 | Cookie只在確認Commit後設定／清除、未知結果不假稱成功、正常重啟／Restore不同。 |
| NFR-MNT-01／02、NFR-OBS-01／02 | 本表與AT測試ID；界線清楚、無敏感Log；尚待程式／可重複測試證據。 |
| NFR-DEP-01～03 | 獨立HTTP Client仍需Cookie Jar／來源／CSRF；沒有部署或設定檔產出。 |
| SDQ-01 | 本輪選Session／Cookie／CSRF／來源／活動／限流；CP-01～06待回填，Library版本／Proxy實測待後續。 |
| SDQ-02／03／04／05 | 保留共同Vehicle Writer協定、Header及圖片授權、Public投影／Cache、Error／Epoch；完整資源API留2D。 |
| SDQ-06／07、DPQ-01～05 | Restore撤銷、Secrets／依賴版本、主機／網域／容量／訪問範圍／實際預算未決，不宣稱已選服務。 |

## 14. Authentication驗收與親自演示清單

**全部未執行 [TEST]**。未來使用兩個合成User、兩個獨立Cookie Jar、同一Browser兩Tab、受控Clock／故障環境及至少兩Worker模式；不用真實個資。每案例記錄預期／實際HTTP、DB持久結果、Cookie Attributes與UI，不在報告／錄影公開raw Token或密碼。直接HTTP測試由使用者自己的展示帳號進行。

| ID | 可演示步驟／觀察 | 預期結果 |
| --- | --- | --- |
| AT-01 Password邊界／手動登入 | 新User分別測11／12／128／129 Code Points、Unicode、前後空白、貼上與確認不符。 | 12／128可、11／129拒；不trim／截斷；註冊後仍不能讀車庫，DB只有Library Hash，手動Login才有效。 |
| AT-02 Email一致／併發Unique | 同地址大小寫＋前後空白、normalized國際化等價範例；兩Client同時Register同canonical。 | 最多一User；重複409無既有資料；註冊／登入同Key；測F(F(email))=F(email)，固定Locale／Library後結果可重複。 |
| AT-03 Login錯誤／Dummy | 不存在User與存在User錯Password，以相同格式、未達Gate比較Body／Code及多次時間。 | 同401／同訊息；無新登入、不續期；均經Verify成本路徑，記錄可觀測差異，不承諾完美常數時間。 |
| AT-04 Fixation／Rotation | 保留preauth Token，成功Login後比較新Cookie；再重新登入並重放舊Token。 | 每次新Token；舊Context已撤銷、舊Cookie不能讀車庫；獨立裝置Session仍可用。 |
| AT-05 Cookie實測 | DevTools看Set-Cookie／Cookie；document.cookie、重新整理、本機TLS與正式TLS測試。 | Secure／HttpOnly／Lax／Host-only／Path=/／__Host-正確；JS無Session Token；Cookie存在但Server到期仍拒絕。 |
| AT-06 CSRF正反矩陣 | 每類Mutation測無Token、錯Token、另一Cookie Jar的Token；以有效Cookie直接HTTP測。 | 全部403無業務／登入副作用，既定Gate計數不回退；正常Token＋來源可成功；Register／Login亦涵蓋，不能只驗登入後。 |
| AT-07 Origin／Fetch／Native Client | Browser跨站表單、同Site不同Origin，null／假前綴／錯Port；缺Origin改同Origin Referer；兩者皆無；Native Jar＋明確Origin＋Token。 | 不可信／全缺拒絕；合規Referer備援與Native流程成功；不因SameSite先擋便省略API來源測試。 |
| AT-08 Owner／BOLA／投影 | A登入，把B車／Event／Version／Image ID送各讀寫操作，偽造Body Owner；再比較匿名、Owner、非Owner。 | Private／寫入不可越權、404／401依政策；上架只Public投影、完整VIN僅Owner，無他人Email／Hash。 |
| AT-09 期限／非活動 | 受控Clock測29:59／30:00及7:59:59／8:00:00；期間持續me／csrf／圖片／靜態／公開搜尋。 | 邊界前可、等號拒；背景不變last_activity；Owner成功業務可Touch但不改absolute；不提供Production改Clock入口。 |
| AT-10 Logout／Replay／分頁 | 有效Cookie自有Client重放可通過；同Tab Logout，再新判定重放；另Tab、另一裝置比較。 | Logout後原Token拒；同Jar Tab通知後≤5秒清私有UI；另一裝置有效。可示範Cookie被竊時CSRF不能補救Bearer失竊。 |
| AT-11 Touch／撤銷競態 | 兩連線控制Touch與Logout先後；另讓業務先授權、Logout後才Commit／回傳。 | revoked不被清、舊Token不復活；先授權工作可能完成且不被誤報未保存；之後新判定拒絕。 |
| AT-12 舊回應／Cookie重排 | 延遲A私有Response，登出／換B再釋放；延遲401；同Origin兩Tab同時Bootstrap／Login／Logout；測Timeout。 | Epoch阻止A資料填回；普通回應無Set-Cookie；Lifecycle Lock序列化受控Cookie操作；未知結果不假確認。凍結Tab恢復先遮蔽重驗。 |
| AT-13 Gate／Burst／IP | 同可信來源第20／21次Login、第10／11次Register；分配多Worker；偽造XFF；在窗邊界重測；Bootstrap第60／61次。 | N允許後續驗證、N＋1為429＋Retry-After；合計而非每Worker配額；XFF不另開Key；交界Burst按固定窗可能允許並如實記錄。 |
| AT-14 資源／格式 | 超8 KiB Auth JSON、惡意Content-Type、大量並行Verify、過多匿名Context；觀察Hash／DB／記憶體。 | 413／415或有界忙碌503等明確失敗；不無界Queue、不先解析巨檔再聲稱被Dependency保護；不建立假登入。 |
| AT-15 PG／網路故障 | Lookup／Gate時停PG；Logout結果不明；另在業務Commit後讓Touch失敗。 | 503不回Anonymous假正常／不fail open、不假確認Logout；已Commit業務保持成功事實，UI不盲重送。 |
| AT-16 Restore | 取Backup後Login／Logout，隔離還原舊備份，先失效全部Context才開入口；重放舊Cookie／CSRF。 | 所有舊Session／preauth拒絕；正常API重啟則未過期Session不被無故延長／撤銷。 |
| AT-17 Injection／Log／Error | Email／搜尋送引號與SQL片段；錯誤Password／JSON／Validation；檢查API、Proxy／Trace／Log及Public Serializer。 | 無SQL結構改變；不洩密碼、Cookie、CSRF、Hash、完整VIN或Raw Validation input；錯誤Body一致、no-store。 |
| AT-18 XSS／Cache | 自有合成描述存可執行HTML測試字串，查看公開／Owner／更正鏈／錯誤顯示；查CSP／Cache Header。 | 當文字呈現、不執行；不能用HttpOnly測試取代DOM／Header驗證；舊私有Client Cache在換身分清理。 |
| AT-19 CSRF壽命／多Tab | 同Context重取／Reload，兩Tab共用；Login後用舊Token配新Cookie；preauth到期再提交。 | 同ContextToken穩定且不Touch；換Context後舊Token拒；preauth過期需Bootstrap，絕不因此登入。 |
| AT-20 圖片／下架旁路 | 未授權或無CSRF上傳；已上架車下架後，用舊詳情／版本／主圖URL、條件Request及新Browser讀。 | 不能切主圖／讀Private，沒有Static Raw旁路；新判定拒絕、首次no-store；已交付與先授權在途界線如實說明。 |

至少AT-01、04、05、06、08、09、10可作面試的直接操作演示。AT-11～16需要可控測試環境，不在Production臨時斷DB／改時間或重放其他人的Token。

## 15. Remaining Questions & Step 2D Readiness

### 15.1 真正尚待確認的項目

| ID | 已選方向／剩餘問題 | 影響與進度 |
| --- | --- | --- |
| AQ-01 | 本輪選Synchronizer；審查是否接受CP-01的csrf_secret及既有Context失效策略。 | 接受後回填DB設計才可據此實作；不是再把「要不要CSRF」留空。 |
| AQ-02 | 本輪選Fixed Window；審查明確窗口／NAT取捨及csrf_context Scope／上限。 | 若要求精確Sliding，須改CP-02／資料模型；保持原PRD候選數值來源。 |
| AQ-03 | Email／Argon2方法已定；實際Python、PG UTF-8／Locale、Library與KDF成本／總併行。 | SDQ-05／07、DPQ-03；用AT-01～03／14驗證，不能只靠Library預設／機器Locale。 |
| AQ-04 | Cookie及來源規則已定；PUBLIC_ORIGIN實值、本機CA／DNS、trusted proxy Peer與Header／API Port設定。 | DPQ-01／02；環境未配置，不能宣稱Browser Cookie／CSRF已驗收。 |
| AQ-05 | 業務活動白名單已定；2D需映射Owner專用／Public讀取及已定義的成功No-op活動語意，並定Touch失敗Metadata／Error Envelope。 | 不允許背景Owner Query保活；Commit結果不明不能自動重送。 |
| AQ-06 | Web Locks＋Epoch為受控Browser方案；需驗支援、延後Set-Cookie、崩潰／Timeout／恢復路徑。 | AT-12是必要阻擋點。若非受控晚到Login回應仍可造成錯誤確認，須重審Server操作識別／輪替關聯，不以UI Epoch宣稱已解決。 |
| AQ-07 | Lock／Statement Timeout、有限Retry／Busy等待及Request上限的實值；Hash容量、圖片工作的總預算。 | 先依2B固定鎖序；資源／逾時量測後定值，不增加Redis或無界Queue。 |
| AQ-08 | Restore／秘密／Log／Bucket及孤立Context清理手順、資料保留、展示訪問與關閉日。 | SDQ-06、DPQ-04／05；Session撤銷是必做，備份實際演練尚未做。 |

### 15.2 是否足以開始REST API Contract Design？

**足以作為Step 2D的審查基礎，有條件進入設計；不代表可跳過審查直接實作。** 五個Auth介面、Context／CSRF傳遞、身份／Ownership、期限／續期、錯誤與限流語意已明確。2D可將這些規則映射到Vehicle／Maintenance／Image Contract，不必先部署或寫程式。

實作前須完成CP-01／02審閱、Auth未知結果／Cookie競態的可驗證策略，以及環境／Library配置；如果AT-12無法支持既定「晚到回應不恢復失效登入」邊界，須先修設計，不能把它標為Should Have或忽略FR-003-AC05。本階段只列風險與測試，沒有聲稱該競態已被驗證。

仍有殘餘風險：有效Cookie失竊、XSS同Origin權限、Distributed Stuffing、固定窗Burst／NAT、PG單點、終端／管理者被控制。學生MVP可明確說明取捨，但不能因此省略基線驗收。

## 16. 十個核心技術名詞

| 名詞 | 定義 | Vibicle用途 |
| --- | --- | --- |
| Authentication | 判斷Request身分。 | Password建立登入；後續Cookie→PG Session得到User。 |
| Authorization | 判斷身分可做哪些操作。 | 每台車依Owner與is_listed授權，不靠按鈕或角色猜測。 |
| Server-side Session | Server保存可撤銷的身分／期限上下文。 | PostgreSQL讓任意API Worker辨識同一Token。 |
| CSPRNG／Entropy | 密碼學安全亂數與不可預測程度。 | 獨立產生256-bit Session／CSRF Secret，不用User ID。 |
| Password Hash／KDF | 對密碼作刻意昂貴的不可逆驗證轉換。 | Argon2id防離線猜測；不是SHA-256或Encryption。 |
| Salt | 每筆Hash獨立隨機資料，可與Hash保存。 | 避免同密碼同值與共用預計算；由Library處理。 |
| HttpOnly Cookie | Browser保存但不讓JS直接讀取的Cookie。 | 承載raw Session Token；仍會自動附送，仍需要CSRF。 |
| CSRF | 利用Browser自動帶憑證誘導非預期操作。 | 用Session綁定Synchronizer Token＋來源驗證，含Login／Register。 |
| Origin／Site | Origin含scheme／host／port；Site用不同範圍判定。 | PUBLIC_ORIGIN精確比對；SameSite不等於同Origin。 |
| Session Revocation | Server把某Token標為不可再使用。 | Logout只撤銷本Session，新Lookup拒絕；不回溯取消已授權工作。 |

## 17. 五個面試官可能追問的問題

1. 為何PG保存Stateful Session，FastAPI Worker仍可稱Stateless？有合法Session為何還不能修改別人的車？
2. 為什麼256-bit隨機Session Token可以用SHA-256保存，人類密碼卻要Argon2id與Salt？bcrypt的72 bytes又如何影響128字元政策？
3. Session Cookie保持HttpOnly時，React如何取得CSRF Token？preauth如何防Login CSRF，又為何無法防已竊Cookie的攻擊者？
4. Logout、last_activity Touch與晚到Response同時發生時，各自在何處判定安全？為何Auth Epoch不能取消Set-Cookie，Web Locks也不是Server授權？
5. 登入20次／固定5分鐘為何可能在2秒接受40次？多Worker、XFF與NAT如何影響限制，為何不需立刻引入Redis？

## 18. 文件自我檢查與驗證限制

- 已核對四份上游的候選條款；FR-013／C與H／更正／Private讀取不變，四個停用AC不復活。
- Cookie名稱／屬性、Session格式／Hash、preauth／authenticated期限、CSRF壽命、Login Rotation、Logout例外與Touch白名單在文字／三張Sequence圖／五個Auth介面保持同一語意。
- Fixed Window與Counter欄位相容；新增Scope與CSRF欄位明列CP，沒有把現有DB設計說成已含它們。
- Threat Model涵蓋User指定的十二類風險並加入口／資源風險；所有防線是設計，測試ID可追。
- 引用官方OWASP／Browser／Python／FastAPI／PG／Library文件作原理查核；實際版本與配置仍需鎖定。
- 本輪只新增docs/AUTH_DESIGN.md；上游保留原內容。沒有程式／套件／DB／Migration／Docker／部署變更。
- **未驗證**：無可運行新版服務，未做HTTP／Browser／SQL／並發／滲透測試；Mermaid僅作文字結構檢查，未經Renderer；表中的驗收是未來計畫，非通過紀錄。

完成Step 2C即停止，等待審查；不自動開始Step 2D。
