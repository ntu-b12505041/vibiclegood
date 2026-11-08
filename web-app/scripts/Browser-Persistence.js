async (page) => {
  const source = 'https://localhost:8443'
  const target = 'https://localhost:9443'
  const id = page.url().split('/').at(-1)
  const check = (condition, message) => { if (!condition) throw new Error(message) }
  const who = (await (await page.request.get(source + '/api/auth/me')).json()).data
  check(who.authenticated, 'Source session did not survive container recreation')
  const path = '/api/me/vehicles/' + id
  const original = (await (await page.request.get(source + path)).json()).data
  check(original?.main_image?.url, 'Source vehicle/photo metadata did not persist')
  check((await page.request.get(source + original.main_image.url)).ok(), 'Source photo did not persist')
  const replay = (await (await page.request.get(target + '/api/auth/me')).json()).data
  check(!replay.authenticated, 'Restored DB accepted a pre-backup session')
  check((await page.request.get(target + path)).status() === 401, 'Restored DB gave private access to an old session')

  const isolated = await page.context().browser().newContext({ ignoreHTTPSErrors: true })
  try {
    const login = await isolated.newPage()
    await login.goto(target + '/login')
    await login.getByLabel('電子郵件').fill(who.user.email)
    await login.getByLabel('密碼', { exact: true }).fill('Synthetic fleet example 2026')
    await login.getByRole('button', { name: '登入', exact: true }).click()
    await login.getByRole('heading', { name: '我的車庫' }).waitFor()
    const restored = (await (await isolated.request.get(target + path)).json()).data
    check(restored.id === original.id && restored.row_version === original.row_version,
      'Restored vehicle version differs')
    check(restored.effective_event_count === original.effective_event_count && restored.mileage_was_lowered,
      'Restored vehicle history summary differs')
    const versions = (await (await isolated.request.get(target + path + '/maintenance-events')).json()).data
    check(versions.items[0].version_count === 2, 'Restored version chain missing')
    const a = await (await page.request.get(source + original.main_image.url)).body()
    const b = await (await isolated.request.get(target + restored.main_image.url)).body()
    check(a.equals(b), 'Restored photo differs from backed-up bytes')
  } finally {
    await isolated.close()
  }
  return 'PASS: existing session and vehicle/photo survive recreation; restored old SID rejected; new login and matching history/photo confirmed.'
}