import { mount } from '@vue/test-utils'
import {
  UserSubjectType,
  AgentSubjectType,
} from '@baserow/modules/core/subjectTypes'
import { TeamSubjectType } from '@baserow_enterprise/subjectTypes'

// The registry supplies the complete appearance, including shape, at either size.
test.each([
  ['user', new UserSubjectType()],
  ['agent', new AgentSubjectType()],
  ['team', new TeamSubjectType()],
])(
  '%s avatar owns its appearance in compact and large lists',
  async (_, type) => {
    const wrapper = mount(type.avatarComponent, {
      props: { subject: { name: 'Ada Lovelace' } },
    })
    try {
      expect(wrapper.html()).toMatchSnapshot('compact')
      await wrapper.setProps({ size: 'large' })
      expect(wrapper.html()).toMatchSnapshot('large')
    } finally {
      wrapper.unmount()
    }
  }
)
