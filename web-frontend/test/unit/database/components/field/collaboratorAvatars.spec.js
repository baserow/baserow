import { TestApp } from '@baserow/test/helpers/testApp'
import FunctionalGridViewFieldMultipleCollaborators from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldMultipleCollaborators'
import FunctionalGridViewFieldLastModifiedBy from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldLastModifiedBy'

describe('Read-only field Subject avatars', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('renders human initials and the Agent icon in collaborator cells', async () => {
    const wrapper = await testApp.mount(
      FunctionalGridViewFieldMultipleCollaborators,
      {
        props: {
          value: [
            { id: 1, name: 'Alice Demo', type: 'auth.User' },
            { id: 2, name: 'Research Agent', type: 'core.Agent' },
          ],
        },
      }
    )

    expect(wrapper.get('.avatar--blue').text()).toBe('AD')
    expect(wrapper.get('.avatar--purple .iconoir-lock').exists()).toBe(true)
    expect(wrapper.html()).toMatchSnapshot()
  })

  test('renders an Agent avatar in author cells', async () => {
    const wrapper = await testApp.mount(FunctionalGridViewFieldLastModifiedBy, {
      props: {
        value: { id: 2, name: 'Review Agent', type: 'core.Agent' },
      },
    })

    expect(wrapper.get('.avatar--purple .iconoir-lock').exists()).toBe(true)
    expect(wrapper.html()).toMatchSnapshot()
  })
})
