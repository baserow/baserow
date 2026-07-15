import { mountSuspended } from '@nuxt/test-utils/runtime'

import SimpleContainerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/SimpleContainerElementForm'

describe('SimpleContainerElementForm', () => {
  const mountComponent = () => {
    return mountSuspended(SimpleContainerElementForm, {
      props: {
        defaultValues: {
          styles: {},
        },
      },
      global: {
        mocks: {
          $t: (key) => key,
          $registry: {
            getOrderedList: () => [],
          },
        },
        provide: {
          workspace: {},
          builder: {
            theme: {},
          },
          currentPage: {},
          elementPage: {},
          mode: 'edit',
        },
      },
    })
  }

  test('does not show page positioning controls', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain(
      'simpleContainerElementForm.noConfigurationOptions'
    )
    expect(wrapper.findComponent({ name: 'RadioGroup' }).exists()).toBe(false)
  })
})
