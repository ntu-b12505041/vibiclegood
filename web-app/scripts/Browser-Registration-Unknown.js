async (page) => {
  const origin = new URL(page.url()).origin
  const email = `register-unknown-${Date.now()}@example.test`
  const password = 'Synthetic pending account 2026'
  let requests = 0
  await page.route('**/api/auth/register', async route => {
    requests++
    const response = await route.fetch()
    if (response.status() !== 201) throw new Error('Registration did not commit.')
    if (response.headers()['set-cookie']) throw new Error('Registration modified the cookie.')
    await route.abort('failed')
  }, { times: 1 })
  await page.goto(origin + '/register')
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByLabel('確認密碼').fill(password)
  await page.getByRole('button', { name: '註冊', exact: true }).click()
  await page.getByRole('alert').getByText('註冊結果尚未確認', { exact: false }).waitFor()
  if ((await page.request.get(origin + '/api/me/vehicles')).status() !== 401) {
    throw new Error('Registration granted private access.')
  }
  await page.getByRole('link', { name: '登入', exact: true }).click()
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登入', exact: true }).click()
  await page.getByRole('heading', { name: '我的車庫' }).waitFor()
  if (requests !== 1) throw new Error('Registration was resent automatically.')
  return 'PASS: Registration committed but response was lost; app stayed anonymous and manual Login was available.'
}