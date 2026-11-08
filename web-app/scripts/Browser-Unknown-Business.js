async (page) => {
  const origin = new URL(page.url()).origin
  const vin = 'TEST' + String(Date.now()).padStart(13, '0')
  let sends = 0
  await page.route('**/api/vehicles', async route => {
    sends++
    const result = await route.fetch()
    if (result.status() !== 201) throw new Error('Vehicle creation failed before fault injection')
    await route.abort('failed')
  })
  await page.goto(origin + '/garage/new')
  await page.getByLabel('合成 VIN').fill(vin)
  await page.getByLabel('品牌').fill('Vibicle')
  await page.getByLabel('車型').fill('Unknown outcome fixture')
  await page.getByLabel('年式').fill('2020')
  await page.getByLabel('目前里程 km').fill('80000')
  await page.getByRole('button', { name: '建立車輛', exact: true }).click()
  await page.getByRole('alert').getByText('無法確認是否已儲存。').waitFor()
  if (sends !== 1) throw new Error('Mutation was retried automatically')
  await page.unroute('**/api/vehicles')
  await page.getByRole('link', { name: '返回車庫' }).click()
  await page.getByRole('link', { name: 'Vibicle Unknown outcome fixture', exact: true }).click()
  await page.getByText(vin, { exact: true }).waitFor()
  return 'PASS: business Commit then network loss is shown as unknown; owner can read the persisted vehicle without re-sending.'
}