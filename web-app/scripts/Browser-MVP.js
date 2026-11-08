async (page) => {
  const origin = new URL(page.url()).origin
  const email = `owner-${Date.now()}@example.test`
  const password = 'Synthetic fleet example 2026'
  const name = 'Vibicle 山徑展示車'
  const vin = 'TEST' + String(Date.now()).padStart(13, '0')
  const check = (value, message) => { if (!value) throw new Error(message) }
  const button = (p, label) => p.getByRole('button', { name: label, exact: true })
  const createPng = () => page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 480
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#183e35'
    ctx.fillRect(0, 0, 640, 480)
    ctx.fillStyle = '#e4edb9'
    ctx.fillRect(120, 220, 400, 120)
    ctx.fillRect(190, 150, 260, 95)
    ctx.fillStyle = '#252c2b'
    for (const x of [200, 450]) {
      ctx.beginPath()
      ctx.arc(x, 342, 43, 0, 2 * Math.PI)
      ctx.fill()
    }
    ctx.fillStyle = '#fff'
    ctx.font = '24px sans-serif'
    ctx.fillText('VIBICLE DEMO', 224, 420)
    return canvas.toDataURL('image/png').split(',')[1]
  })

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
  await page.getByRole('link', { name: '新增車輛' }).click()
  await page.getByLabel('合成 VIN').fill(vin)
  await page.getByLabel('品牌').fill('Vibicle')
  await page.getByLabel('車型').fill('山徑展示車')
  await page.getByLabel('年式').fill('2020')
  await page.getByLabel('目前里程 km').fill('900000')
  await page.getByLabel('售價 TWD（選填）').fill('330000')
  await button(page, '建立車輛').click()
  await page.getByRole('heading', { name }).waitFor()
  const id = page.url().split('/').at(-1)
  const ownerUrl = page.url()

  await button(page, '新增維修紀錄').click()
  await page.getByLabel('維修日期').fill('2020-03-10')
  await page.getByLabel('維修里程 km').fill('900000')
  await page.getByLabel('維修內容').fill('原始里程誤植，保留紀錄')
  let observed = page.waitForResponse(r => r.url().endsWith('/maintenance-events') && r.request().method() === 'POST')
  await button(page, '儲存維修紀錄').click()
  check((await observed).status() === 201, 'Maintenance failed')
  await page.getByRole('heading', { name }).waitFor()
  await button(page, '查看維修履歷').click()
  await button(page, '更正此筆紀錄').click()
  await page.getByLabel('維修里程 km').fill('70000')
  await page.getByLabel('維修內容').fill('修正後里程')
  await page.getByLabel('更正理由').fill('合成示例，原始輸入誤植')
  observed = page.waitForResponse(r => r.url().endsWith('/corrections') && r.request().method() === 'POST')
  await button(page, '儲存更正版本').click()
  check((await observed).status() === 201, 'Correction failed')
  await page.getByRole('heading', { name }).waitFor()
  await page.getByRole('link', { name: '編輯車輛與里程' }).click()
  await page.getByLabel('目前里程 km').fill('80000')
  await page.getByLabel('里程異動理由').fill('修正原本的目前里程')
  await page.getByRole('checkbox').check()
  await button(page, '儲存車輛').click()
  await page.getByRole('heading', { name }).waitFor()
  await page.getByText('目前里程曾下修').waitFor()
  // Prevent the OS dialog in automation so its focus/change ordering can be controlled.
  const input = page.locator('input[type=file]')
  await input.evaluate(node => { node.click = () => {} })
  await button(page, '選擇主照片').click()
  // A Windows picker can return focus before delivering the selected file.
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await button(page, '重新載入私人資料').waitFor()
  await input.setInputFiles({
    name: 'synthetic.png', mimeType: 'image/png', buffer: Buffer.from(await createPng(), 'base64'),
  })
  await page.getByText('已選擇 synthetic.png', { exact: true }).waitFor()
  observed = page.waitForResponse(r => r.url().endsWith('/image') && r.request().method() === 'POST')
  await button(page, '上傳主照片').click()
  const upload = await observed
  check(upload.status() === 200, 'Upload failed')
  const photo = (await upload.json()).data.image.url
  await button(page, '上架車輛').click()
  await page.getByText('已上架。訪客可以查看公開車輛資訊。').waitFor()

  const visitor = await page.context().browser().newContext({ ignoreHTTPSErrors: true })
  const listing = await visitor.newPage()
  await listing.goto(origin + '/marketplace')
  await listing.getByLabel('品牌或車型').fill('vIbIcLe')
  await button(listing, '搜尋車輛').click()
  await listing.getByRole('link', { name, exact: true }).first().click()
  await listing.goto(origin + '/marketplace/' + id)
  await listing.getByRole('heading', { name }).waitFor()
  await button(listing, '查看里程下修摘要').click()
  await listing.getByText('修正原本的目前里程', { exact: true }).waitFor()
  await button(listing, '查看維修履歷').click()
  await button(listing, '查看原文與版本（2）').click()
  await listing.getByText('版本 1 · 已取代').waitFor()
  await listing.getByText('版本 2 · 目前有效').waitFor()
  check(!(await listing.locator('main').innerText()).includes(vin), 'Public leaked full VIN')
  check((await visitor.request.get(origin + photo)).ok(), 'Public image not accessible')
  await listing.setViewportSize({ width: 390, height: 844 })
  check(await listing.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow')
  await listing.screenshot({ path: 'output/playwright/mvp-public-mobile.png', fullPage: true })
  await page.goto(ownerUrl)
  await button(page, '下架車輛').click()
  await page.getByText('未上架。只有你可以查看這台車。').waitFor()
  check((await visitor.request.get(origin + photo, { headers: { 'If-None-Match': '"old"' } })).status() === 404,
    'Delisted image remained accessible')
  check((await visitor.request.get(origin + '/api/vehicles/' + id)).status() === 404, 'Delisted details visible')
  check((await page.context().request.get(origin + photo)).ok(), 'Owner lost private photo')
  await listing.evaluate(() => window.dispatchEvent(new Event('focus')))
  await listing.getByRole('alert').getByText('找不到此車輛。').waitFor()
  check(!(await listing.getByRole('heading', { name }).count()), 'Delisted data remained after focus')
  await page.screenshot({ path: 'output/playwright/mvp-owner-desktop.png', fullPage: true })
  await visitor.close()
  return { result: 'PASS: Owner UI to public UI, correction, photo, listing, unlisting and privacy.', vehicle: id, image: photo }
}
