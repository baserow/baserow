import { TestApp } from '@baserow/test/helpers/testApp'
import PasswordRegister from '@baserow/modules/core/components/auth/PasswordRegister'

describe('PasswordRegister', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  async function mountWithLink(invitationLink) {
    return await testApp.mount(PasswordRegister, {
      propsData: { invitation: null, invitationLink },
    })
  }

  test('names the object of a link created by someone', async () => {
    const wrapper = await mountWithLink({
      slug: 'abc',
      invited_by: 'Bram',
      workspace: 'Acme',
      scope_name: 'Sales',
    })

    const alert = wrapper.find('.alert')
    expect(alert.text()).toContain('Bram')
    expect(alert.text()).toContain('invitationLinkJoin.scopeIn')
  })

  test('names the workspace of a link to the workspace', async () => {
    const wrapper = await mountWithLink({
      slug: 'abc',
      invited_by: 'Bram',
      workspace: 'Acme',
      scope_name: null,
    })

    const alert = wrapper.find('.alert')
    expect(alert.text()).toContain('Acme')
    expect(alert.text()).not.toContain('invitationLinkJoin.scopeIn')
  })
})
