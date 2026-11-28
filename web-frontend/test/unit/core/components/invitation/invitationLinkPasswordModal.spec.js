import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import InvitationLinkPasswordModal from '@baserow/modules/core/components/invitation/InvitationLinkPasswordModal'

describe('InvitationLinkPasswordModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function showModal(invitationLink) {
    const wrapper = await testApp.mount(InvitationLinkPasswordModal, {
      props: {
        workspace: { id: 1 },
        target: { type: 'workspace' },
        targetType: { updateInvitationLink: vi.fn() },
      },
    })
    wrapper.vm.show(invitationLink)
    await flushPromises()
    return wrapper
  }

  const link = (wrapper) =>
    wrapper.vm.getTeleportedElement().querySelector('.action__links a')

  // Leaving the empty password input shows its validation error, which moves
  // the links down before the click lands on them.
  test.each([
    ['cancel', { id: 1, has_password: false }, 'action.cancel'],
    [
      'remove',
      { id: 1, has_password: true },
      'invitationLinkPasswordModal.remove',
    ],
  ])(
    'the %s link keeps the focus in the password input',
    async (name, invitationLink, label) => {
      const wrapper = await showModal(invitationLink)
      expect(link(wrapper).textContent.trim()).toBe(label)

      const mousedown = new MouseEvent('mousedown', {
        bubbles: true,
        cancelable: true,
      })
      link(wrapper).dispatchEvent(mousedown)

      expect(mousedown.defaultPrevented).toBe(true)
    }
  )
})
