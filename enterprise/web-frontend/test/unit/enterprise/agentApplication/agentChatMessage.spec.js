import { mountSuspended } from '@nuxt/test-utils/runtime'

import AgentChatMessage from '@baserow_enterprise/components/agentApplication/AgentChatMessage'

const attachment = {
  name: 'abc.pdf',
  original_name: 'report.pdf',
  visible_name: 'report.pdf',
  mime_type: 'application/pdf',
  is_image: false,
  size: 1234,
  url: 'http://localhost/media/user_files/abc.pdf',
  thumbnails: {},
}

describe('AgentChatMessage', () => {
  test('clicking an attachment opens the file preview modal read-only', async () => {
    const wrapper = await mountSuspended(AgentChatMessage, {
      props: {
        event: {
          type: 'human',
          content: 'Here you go',
          attachments: [attachment],
        },
      },
      attachTo: document.body,
    })

    expect(document.body.querySelector('.file-field-modal')).toBeNull()
    await wrapper
      .find('.agent-chat__attachment-chip--clickable')
      .trigger('click')
    await wrapper.vm.$nextTick()

    const modal = document.body.querySelector('.file-field-modal')
    expect(modal).not.toBeNull()
    expect(modal.textContent).toContain('report.pdf')
    expect(modal.querySelector('.iconoir-bin')).toBeNull()
    expect(modal.querySelector('.iconoir-download')).not.toBeNull()
    wrapper.unmount()
  })
})
