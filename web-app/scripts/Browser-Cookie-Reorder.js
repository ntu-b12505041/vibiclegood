async (page) => {
  // Negative control for SR-T12. Bypass the app coordinator deliberately.
  const origin = new URL(page.url()).origin
  const cookieName = '__Host-vibicle_session'
  const email = `cookie-order-${Date.now()}@example.test`
  const password = 'Synthetic reorder password 2026'
  await page.goto(origin + '/register')
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByLabel('確認密碼').fill(password)
  await page.getByRole('button', { name: '註冊', exact: true }).click()
  await page.getByText('帳號已建立。請使用剛才的帳號登入。').waitFor()
  const getContext = async () => {
    const response = await page.request.get(origin + '/api/auth/csrf', { headers: { origin } })
    if (!response.ok()) throw new Error('Bootstrap failed.')
    return (await response.json()).data.csrf_token
  }
  const before = await getContext()
  let committed, release
  const committedResponse = new Promise(resolve => { committed = resolve })
  const delayed = new Promise(resolve => { release = resolve })
  await page.route('**/api/auth/login', async route => {
    const late = await route.fetch()
    committed(late.status())
    await delayed
    await route.fulfill({ response: late })
  }, { times: 1 })
  const uncoordinatedLogin = page.evaluate(async ({ csrf, email, password }) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify({ email, password }),
    })
    return response.status
  }, { csrf: before, email, password })
  try {
    const status = await Promise.race([
      committedResponse, new Promise(resolve => setTimeout(() => resolve(0), 12000)),
    ])
    if (status !== 200) throw new Error('Did not hold a successful login before headers.')
    // Mimic an external flow replacing the original browser context cookie.
    await page.context().clearCookies({ name: cookieName })
    const other = await getContext()
    const logout = await page.request.post(origin + '/api/auth/logout', {
      headers: { origin, 'x-csrf-token': other },
    })
    if (logout.status() !== 204) throw new Error('Other context logout did not commit.')
    const anonymous = (await (await page.request.get(origin + '/api/auth/me')).json()).data
    if (anonymous.authenticated) throw new Error('Expected anonymous before the late header.')
  } finally {
    release()
  }
  if (await uncoordinatedLogin !== 200) throw new Error('Did not deliver late browser response.')
  const after = (await (await page.request.get(origin + '/api/auth/me')).json()).data
  if (!after.authenticated || after.user.email !== email) {
    throw new Error('Expected the different committed session to be usable after late Set-Cookie.')
  }
  return 'PASS negative control: late Set-Cookie delivered a different committed Session after unrelated Logout. CP-06 remains open.'
}