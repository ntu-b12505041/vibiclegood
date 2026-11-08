async (page) => {
  const origin = new URL(page.url()).origin
  const stamp = Date.now()
  const email = `garage-${stamp}@example.test`
  const password = 'Synthetic garage pass 2026'
  await page.goto(origin + '/register')
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByLabel('確認密碼').fill(password)
  await page.getByRole('button', { name: '註冊', exact: true }).click()
  await page.getByText('帳號已建立。請使用剛才的帳號登入。').waitFor()
  await page.getByLabel('電子郵件').fill(email)
  await page.getByLabel('密碼', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登入', exact: true }).click()
  await page.getByRole('heading', { name: '我的車庫' }).waitFor()
  await page.getByRole('link', { name: '新增車輛' }).click()
  await page.getByLabel('合成 VIN').fill('TEST' + String(stamp).padStart(13, '0'))
  await page.getByLabel('品牌').fill('Vibicle')
  await page.getByLabel('車型').fill('山路展示車')
  await page.getByLabel('年式').fill('2020')
  await page.getByLabel('目前里程 km').fill('80000')
  await page.getByRole('button', { name: '建立車輛' }).click()
  await page.getByRole('heading', { name: 'Vibicle 山路展示車' }).waitFor()
  await page.reload()
  await page.getByRole('heading', { name: 'Vibicle 山路展示車' }).waitFor()
  await page.getByRole('link', { name: '返回車庫' }).click()
  await page.getByRole('link', { name: 'Vibicle 山路展示車' }).waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  if (!(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))) {
    throw new Error('手機寬度出現橫向溢出。')
  }
  await page.screenshot({ path: 'output/playwright/garage-mobile.png' })
  return 'PASS: authenticated create, detail reload, persisted garage list, mobile viewport.'
}