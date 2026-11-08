async (page) => {
  const origin = new URL(page.url()).origin
  const email = `logout-${Date.now()}@example.test`
  const password = 'Synthetic account logout 2026'
  const button = text => page.getByRole('button', { name: text, exact: true })
  await page.goto(origin + '/register')
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByLabel('確認密碼').fill(password)
  await button('註冊').click()
  await page.getByText('帳號已建立。請使用剛才的帳號登入。').waitFor()
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await button('登入').click()
  await page.getByRole('heading', { name: '我的車庫' }).waitFor()
  const cookie = (await page.context().cookies()).find(item => item.name === '__Host-vibicle_session')
  if (!cookie) throw new Error('Missing session cookie.')
  await page.route('**/api/auth/logout', async route => {
    const committed = await route.fetch()
    if (committed.status() !== 204) throw new Error('Logout failed before interruption.')
    // Model a lost response before its Set-Cookie reaches the Browser.
    await page.context().addCookies([cookie])
    await route.abort('failed')
  }, { times: 1 })
  await button('登出').click()
  await page.getByText('登入操作結果尚未確認', { exact: false }).waitFor()
  if ((await page.request.get(origin + '/api/me/vehicles')).status() !== 401) {
    throw new Error('Committed logout allowed old SID on private API.')
  }
  const retry = page.waitForResponse(r => r.url().endsWith('/api/auth/logout'))
  await button('重新確認原登出').click()
  if ((await retry).status() !== 204) throw new Error('Same-context retry failed.')
  await page.getByText('目前未登入', { exact: true }).waitFor()
  await page.reload()
  await page.getByText('請先登入，再查看自己的車庫。').waitFor()
  return 'PASS: Lost Logout response stayed uncertain; revoked SID failed; retry with the same in-memory proof confirmed 204.'
}