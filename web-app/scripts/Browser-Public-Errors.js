async (page) => {
  const origin = new URL(page.url()).origin
  const stamp = Date.now()
  const email = `public-${stamp}@example.test`
  const password = 'Synthetic public demo pass 2026'
  const vehicleName = 'Vibicle 青嶺展示車'
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
  await page.getByRole('link', { name: '新增車輛' }).click()
  await page.getByLabel('合成 VIN').fill('TEST' + String(stamp).padStart(13, '0'))
  await page.getByLabel('品牌').fill('Vibicle')
  await page.getByLabel('車型').fill('青嶺展示車')
  await page.getByLabel('年式').fill('2020')
  await page.getByLabel('目前里程 km').fill('23000')
  await page.getByLabel('售價 TWD（選填）').fill('280000')
  await page.getByLabel('車輛描述').fill('合成展示車。<img src=x onerror=alert(1)>')
  await button(page, '建立車輛').click()
  await page.getByRole('heading', { name: vehicleName }).waitFor()
  const id = page.url().split('/').at(-1)
  const png = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 320
    canvas.height = 240
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#16483b'
    ctx.fillRect(0, 0, 320, 240)
    ctx.fillStyle = '#e4edb9'
    ctx.font = '20px sans-serif'
    ctx.fillText('VIBICLE / SYNTHETIC', 55, 125)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  const input = page.locator('input[type=file]')
  await input.evaluate(node => { node.click = () => {} })
  await button(page, '選擇主照片').click()
  await input.setInputFiles({
    name: 'synthetic.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64'),
  })
  const upload = page.waitForResponse(r => r.url().endsWith('/image') && r.request().method() === 'POST')
  await button(page, '上傳主照片').click()
  const metadata = (await (await upload).json()).data.image
  await button(page, '上架車輛').click()
  await page.getByText('已上架。訪客可以查看公開車輛資訊。').waitFor()

  const visitor = await page.context().browser().newContext({ ignoreHTTPSErrors: true })
  try {
    const publicPage = await visitor.newPage()
    const fault = route => route.fulfill({
      status: 503, contentType: 'application/json',
      json: {
        error: { code: 'STORE_UNAVAILABLE', outcome: 'not_applied', message: '資料服務暫時無法使用。' },
        meta: { request_id: 'browser-fault-fixture' },
      },
    })
    await publicPage.route(origin + metadata.url, route => route.abort())
    await publicPage.goto(origin + '/marketplace/' + id)
    await publicPage.getByText('照片暫時無法載入。', { exact: true }).waitFor()
    await publicPage.getByRole('heading', { name: vehicleName }).waitFor()
    await publicPage.getByText('<img src=x onerror=alert(1)>', { exact: false }).waitFor()
    if (await publicPage.locator('img[onerror]').count()) throw new Error('HTML injection detected.')
    await publicPage.getByText('尚無自行申報維修紀錄。', { exact: true }).waitFor()

    const history = `**/api/vehicles/${id}/maintenance-events?*`
    const section = publicPage.getByRole('region', { name: '車輛履歷' })
    await publicPage.route(history, fault)
    await button(publicPage, '查看維修履歷').click()
    await section.getByRole('alert').getByText('資料服務暫時無法使用。').waitFor()
    if (await section.getByText('尚無自行申報維修紀錄。', { exact: true }).count()) {
      throw new Error('Error was shown as empty history.')
    }
    await publicPage.unroute(history)
    await button(publicPage, '重新載入').click()
    await section.getByText('尚無自行申報維修紀錄。', { exact: true }).waitFor()

    await publicPage.goto(origin + '/marketplace?q=synthetic-no-such-vehicle')
    await publicPage.getByRole('link', { name: '清除條件' }).click()
    await publicPage.getByRole('link', { name: vehicleName }).first().waitFor()
    const market = '**/api/marketplace/vehicles?*'
    await publicPage.route(market, fault)
    await publicPage.reload()
    await publicPage.getByRole('alert').getByText('資料服務暫時無法使用。').waitFor()
    if (await publicPage.getByText('本頁沒有符合條件的展示車輛。').count()) {
      throw new Error('Error was shown as empty marketplace.')
    }
    await publicPage.unroute(market)
    await button(publicPage, '重新載入').click()
    await publicPage.getByRole('link', { name: vehicleName }).first().waitFor()
  } finally {
    await visitor.close()
  }
  await page.goto(origin + '/garage/' + id + '/edit')
  await page.getByLabel('車輛描述').fill('使用合成資料建立的展示車。')
  await button(page, '儲存車輛').click()
  await page.getByText('使用合成資料建立的展示車。', { exact: true }).waitFor()
  return 'PASS: Public listing without history, safe text, unavailable-image placeholder, history/market error, clear search and retry.'
}
