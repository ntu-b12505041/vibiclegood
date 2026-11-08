async (page) => {
  const origin = new URL(page.url()).origin
  const email = `tab-${Date.now()}@example.test`
  const password = 'Synthetic tab expiry pass 2026'
  const button = (p, name) => p.getByRole('button', { name, exact: true })
  await page.goto(origin + '/register')
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByLabel('確認密碼').fill(password)
  await button(page, '註冊').click()
  await page.getByText('帳號已建立。請使用剛才的帳號登入。').waitFor()
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await button(page, '登入').click()
  await page.getByRole('heading', { name: '我的車庫' }).waitFor()
  await page.getByText('本頁沒有車輛。').waitFor()

  const second = await page.context().newPage()
  const path = '**/api/me/vehicles?*'
  await second.route(path, route => route.fulfill({
    status: 503, contentType: 'application/json',
    json: {
      error: { code: 'STORE_UNAVAILABLE', outcome: 'not_applied', message: '資料服務暫時無法使用。' },
      meta: { request_id: 'browser-owner-fault' },
    },
  }))
  await second.goto(origin + '/garage')
  await second.getByRole('alert').getByText('資料服務暫時無法使用。').waitFor()
  if (await second.getByText('本頁沒有車輛。').count()) throw new Error('Owner error misreported as empty.')
  await second.unroute(path)
  await button(second, '重新載入').click()
  await second.getByText('本頁沒有車輛。').waitFor()

  // Real Chromium lifecycle suspension. No timing assertion while the target is frozen.
  const cdp = await page.context().newCDPSession(second)
  await cdp.send('Page.setWebLifecycleState', { state: 'frozen' })
  try {
    await button(page, '登出').click()
    await page.getByText('目前未登入', { exact: true }).waitFor()
  } finally {
    await cdp.send('Page.setWebLifecycleState', { state: 'active' })
  }
  await second.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })))
  await second.getByText('請先登入，再查看自己的車庫。').waitFor()
  if (await second.getByRole('heading', { name: '我的車庫' }).count()) throw new Error('Private UI remained on resume.')
  await page.goBack()
  await page.getByText('目前未登入', { exact: true }).waitFor()

  // Load the real loopback restore server and bypass its CSP only in this lab Context.
  const foreign = await page.context().browser().newContext({
    ignoreHTTPSErrors: true, bypassCSP: true,
  })
  const foreignPage = await foreign.newPage()
  await foreignPage.goto('https://localhost:9443/')
  const cross = foreignPage.waitForResponse(r => r.url() === origin + '/api/auth/csrf')
  await foreignPage.evaluate(async url => {
    try { await fetch(url, { mode: 'no-cors', credentials: 'include' }) } catch {}
  }, origin + '/api/auth/csrf')
  const rejected = await cross
  if (rejected.status() !== 403 || await rejected.headerValue('set-cookie')) {
    throw new Error('Cross-origin CSRF bootstrap was not rejected.')
  }
  await foreign.close()
  await second.close()
  return 'PASS: Garage failure and retry, Chromium frozen tab resume, browser Back after logout, cross-origin CSRF Bootstrap rejected.'
}
