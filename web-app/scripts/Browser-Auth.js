async (page) => {
  const origin = new URL(page.url()).origin
  const email = `demo-${Date.now()}@example.test`
  const password = 'Synthetic account pass 2026'
  const tab = await page.context().newPage()
  const requireText = (p, text) => p.getByRole('status').getByText(text, { exact: false }).waitFor({ timeout: 5000 })
  const login = async p => {
    await p.goto(origin + '/login')
    await p.getByLabel('電子郵件').fill(email)
    await p.getByLabel('密碼', { exact: true }).fill(password)
    await p.getByRole('button', { name: '登入', exact: true }).click()
  }

  await tab.goto(origin)
  await page.goto(origin + '/register')
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByLabel('確認密碼').fill(password)
  await page.getByRole('button', { name: '註冊', exact: true }).click()
  await page.getByText('帳號已建立。請使用剛才的帳號登入。').waitFor()
  await requireText(page, '目前未登入')
  await login(page)
  await requireText(page, '已登入 ·')
  await requireText(tab, '已登入 ·')
  const cookies = await page.context().cookies()
  const session = cookies.find(cookie => cookie.name === '__Host-vibicle_session')
  if (!session?.httpOnly || !session.secure || session.path !== '/' || session.sameSite !== 'Lax') {
    throw new Error('Browser 未收到具預期安全屬性的 Cookie。')
  }
  if (await page.evaluate(() => document.cookie.includes('__Host-vibicle_session'))) {
    throw new Error('JavaScript 不得讀取 Session Cookie。')
  }
  await page.reload()
  await requireText(page, '已登入 ·')
  await page.getByRole('heading', { name: '我的車庫', exact: true }).waitFor()
  let ownerReads = 0
  const countOwnerReads = request => {
    if (new URL(request.url()).pathname === '/api/me/vehicles') ownerReads++
  }
  page.on('request', countOwnerReads)
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await page.getByRole('button', { name: '重新載入私人資料' }).waitFor()
  if (ownerReads) throw new Error('背景身分確認不應讀車庫或 Touch。')
  await page.getByRole('button', { name: '重新載入私人資料' }).click()
  await page.getByRole('heading', { name: '我的車庫', exact: true }).waitFor()
  page.off('request', countOwnerReads)
  let release
  let authorize
  const reached = new Promise(resolve => { authorize = resolve })
  const hold = new Promise(resolve => { release = resolve })
  await tab.route('**/api/me/vehicles?*', async route => {
    const response = await route.fetch()
    authorize(response.status())
    await hold
    await route.fulfill({ response }).catch(() => {})
  })
  await tab.goto(origin + '/garage')
  if (await reached !== 200) throw new Error('未能暫留已授權車庫回應。')
  await page.getByRole('button', { name: '登出', exact: true }).click()
  await requireText(page, '目前未登入')
  await requireText(tab, '目前未登入')
  release()
  await tab.getByText('請先登入，再查看自己的車庫。').waitFor()
  if (await tab.getByRole('heading', { name: '我的車庫', exact: true }).count()) {
    throw new Error('晚到車庫回應重新顯示私人頁。')
  }
  const cookieAfter = await page.context().cookies()
  if (cookieAfter.some(cookie => cookie.name === '__Host-vibicle_session')) {
    throw new Error('確認登出後仍持有 Cookie。')
  }
  await tab.reload()
  await requireText(tab, '目前未登入')
  await tab.getByText('請先登入，再查看自己的車庫。').waitFor()

  let loginRequests = 0
  await page.route('**/api/auth/login', async route => {
    loginRequests++
    const response = await route.fetch()
    if (response.status() !== 200) throw new Error('故障注入未觸發實際成功的 Login。')
    await route.abort('failed')
  })
  await login(page)
  await requireText(page, '登入操作結果尚未確認')
  await requireText(tab, '登入操作結果尚未確認')
  await page.reload()
  await requireText(page, '登入操作結果尚未確認')
  if (loginRequests !== 1 || !(await page.getByRole('button', { name: '登入', exact: true }).isDisabled())) {
    throw new Error('Login 未確認後不得自動重送或允許新登入。')
  }
  await page.screenshot({ path: 'output/playwright/auth-uncertain.png' })
  await tab.close()
  return 'PASS: Register, Login, Secure Cookie, reload, cross-tab Logout, uncertain Login after real Server Commit and reload.'
}
