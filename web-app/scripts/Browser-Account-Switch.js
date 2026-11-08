async (page) => {
  const origin = new URL(page.url()).origin
  const stamp = Date.now()
  const ownerEmail = `owner-switch-${stamp}@example.test`
  const otherEmail = `other-switch-${stamp}@example.test`
  const password = 'Synthetic account switch 2026'
  const name = 'Vibicle 私有帳號切換測試'
  const button = (p, label) => p.getByRole('button', { name: label, exact: true })
  const credentials = async (p, email) => {
    await p.getByLabel('電子郵件').fill(email)
    await p.getByLabel('密碼', { exact: true }).fill(password)
  }
  for (const email of [ownerEmail, otherEmail]) {
    await page.goto(origin + '/register')
    await credentials(page, email)
    await page.getByLabel('確認密碼').fill(password)
    await button(page, '註冊').click()
    await page.getByText('帳號已建立。請使用剛才的帳號登入。').waitFor()
  }
  await credentials(page, ownerEmail)
  await button(page, '登入').click()
  await page.getByRole('link', { name: '新增車輛' }).click()
  await page.getByLabel('合成 VIN').fill('TEST' + String(stamp).padStart(13, '0'))
  await page.getByLabel('品牌').fill('Vibicle')
  await page.getByLabel('車型').fill('私有帳號切換測試')
  await page.getByLabel('年式').fill('2020')
  await page.getByLabel('目前里程 km').fill('80000')
  await button(page, '建立車輛').click()
  await page.getByRole('heading', { name }).waitFor()
  const ownerUrl = page.url()
  await button(page, '新增維修紀錄').click()
  await page.getByLabel('維修日期').fill('2020-03-10')
  await page.getByLabel('維修里程 km').fill('70000')
  await page.getByLabel('維修內容').fill('第一次申報')
  const event = page.waitForResponse(r => r.url().endsWith('/maintenance-events') && r.request().method() === 'POST')
  await button(page, '儲存維修紀錄').click()
  if ((await event).status() !== 201) throw new Error('Could not seed maintenance.')
  await button(page, '查看維修履歷').click()
  await button(page, '更正此筆紀錄').click()
  await page.getByLabel('維修里程 km').fill('69000')
  await page.getByLabel('維修內容').fill('更正後保留歷史')
  await page.getByLabel('更正理由').fill('更正回應中斷測試')
  let requests = 0
  await page.route('**/corrections', async route => {
    requests++
    const response = await route.fetch()
    if (response.status() !== 201) throw new Error('Correction did not commit.')
    await route.abort('failed')
  }, { times: 1 })
  await button(page, '儲存更正版本').click()
  await page.getByRole('alert').getByText('無法確認是否已儲存。', { exact: false }).waitFor()
  await page.goto(ownerUrl)
  await button(page, '查看維修履歷').click()
  await button(page, '查看原文與版本（2）').click()
  await page.getByText('版本 1 · 已取代').waitFor()
  await page.getByText('版本 2 · 目前有效').waitFor()
  if (requests !== 1) throw new Error('Correction was automatically re-sent.')

  const tab = await page.context().newPage()
  let ready, release
  const gotOwnerResult = new Promise(resolve => { ready = resolve })
  const delayed = new Promise(resolve => { release = resolve })
  await tab.route('**/api/me/vehicles?*', async route => {
    const response = await route.fetch()
    const value = await response.json()
    ready(response.status() === 200 && value.data.items.some(item => item.model === '私有帳號切換測試'))
    await delayed
    await route.fulfill({ response }).catch(() => {})
  }, { times: 1 })
  await tab.goto(origin + '/garage')
  if (!(await Promise.race([gotOwnerResult, new Promise(resolve => setTimeout(() => resolve(false), 12000))]))) {
    release()
    throw new Error('Failed to hold the first account private result.')
  }
  try {
    await page.goto(origin + '/login')
    await credentials(page, otherEmail)
    await button(page, '登入').click()
    await page.getByText(otherEmail, { exact: false }).waitFor()
    await tab.getByText(otherEmail, { exact: false }).waitFor()
  } finally {
    release()
  }
  const reveal = button(tab, '重新載入私人資料')
  if (await reveal.count()) await reveal.click()
  await tab.getByText('本頁沒有車輛。').waitFor()
  if (await tab.getByText(name, { exact: true }).count()) throw new Error('Previous user leaked into new user view.')
  await tab.close()
  return 'PASS: Correction Commit with lost response read back as two versions; delayed private result was discarded after switching accounts.'
}