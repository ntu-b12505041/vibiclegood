async (page) => {
  const origin = new URL(page.url()).origin
  const foreign = await page.context().browser().newContext({
    ignoreHTTPSErrors: true, bypassCSP: true,
  })
  try {
    const tab = await foreign.newPage()
    const setup = await tab.request.get(origin + '/api/auth/csrf', { headers: { origin } })
    if (setup.status() !== 200 || !(await foreign.cookies()).length) {
      throw new Error('Did not create the test preauth context.')
    }
    await tab.goto('https://localhost:9443/')
    for (const operation of ['register', 'login']) {
      const url = origin + '/api/auth/' + operation
      const observed = tab.waitForResponse(response => response.url() === url)
      await tab.evaluate(async target => {
        await fetch(target, {
          method: 'POST', mode: 'no-cors', credentials: 'include',
          headers: { 'Content-Type': 'text/plain' },
          body: '{"email":"foreign@example.test","password":"Synthetic cross origin 2026"}',
        })
      }, url)
      const response = await observed
      if (response.status() !== 403 || await response.headerValue('set-cookie')) {
        throw new Error('Cross-Origin browser mutation was not rejected.')
      }
    }
    const user = (await (await tab.request.get(origin + '/api/auth/me')).json()).data
    if (user.authenticated) throw new Error('Cross-Origin request produced authentication.')
  } finally {
    await foreign.close()
  }
  return 'PASS: Browser cross-Origin Register and Login returned 403 without changing the auth cookie.'
}