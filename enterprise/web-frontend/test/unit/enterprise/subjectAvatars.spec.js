import { mount } from '@vue/test-utils'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes'
import { TeamSubjectType } from '@baserow_enterprise/subjectTypes'

// The registry supplies the complete appearance, including shape, at either size.
test.each([
  ['user', new UserSubjectType(), 'human'],
  ['identity', new UserSubjectType(), 'identity'],
  ['team', new TeamSubjectType(), null],
])(
  '%s avatar owns its appearance in compact and large lists',
  async (_, type, userType) => {
    const wrapper = mount(type.avatarComponent, {
      props: { subject: { name: 'Ada Lovelace', user_type: userType } },
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
