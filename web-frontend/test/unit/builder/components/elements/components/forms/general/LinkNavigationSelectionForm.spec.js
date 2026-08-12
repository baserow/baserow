import { mountSuspended } from '@nuxt/test-utils/runtime'
import LinkNavigationSelectionForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkNavigationSelectionForm'

describe('LinkNavigationSelectionForm', () => {
  const pages = [
    {
      id: 2,
      name: 'Details',
      shared: false,
      order: 1,
      path: '/details',
      path_params: [],
      query_params: [],
    },
    {
      id: 3,
      name: 'Summary',
      shared: false,
      order: 2,
      path: '/summary',
      path_params: [],
      query_params: [],
    },
  ]

  const mountComponent = ({ props = {} }) => {
    const builder = { id: 1, theme: {}, pages }
    const page = pages[0]
    const workspace = { id: 1 }
    const mode = 'editing'
    return mountSuspended(LinkNavigationSelectionForm, {
      props,
      global: {
        provide: {
          workspace,
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: { builder, page, mode, workspace },
        },
      },
    })
  }

  const selectedPageName = (wrapper) => {
    const el = wrapper.find(
      '.link-navigation-selection-form__navigate-option-page-name'
    )
    return el.exists() ? el.text() : null
  }

  test('shows the destination page from the default values', async () => {
    const wrapper = await mountComponent({
      props: {
        defaultValues: { navigation_type: 'page', navigate_to_page_id: 2 },
      },
    })
    expect(selectedPageName(wrapper)).toBe('Details')
  })

  // An undo/redo reaches the sidebar form as: the store updates, then the parent
  // re-applies the reverted/restored values through the form mixin's `reset()`.
  const applyUndoRedo = async (wrapper, defaultValues) => {
    await wrapper.setProps({ defaultValues })
    await wrapper.vm.reset()
    await wrapper.vm.$nextTick()
  }

  test('re-syncs the selected page when the action is reset (undo/redo)', async () => {
    const wrapper = await mountComponent({
      props: {
        defaultValues: { navigation_type: 'page', navigate_to_page_id: 2 },
      },
    })
    expect(selectedPageName(wrapper)).toBe('Details')

    // Undo clears the destination: the dropdown must no longer show a page.
    await applyUndoRedo(wrapper, {
      navigation_type: 'page',
      navigate_to_page_id: null,
    })
    expect(selectedPageName(wrapper)).toBe(null)

    // Redo restores a (different) destination: the dropdown must reflect it.
    await applyUndoRedo(wrapper, {
      navigation_type: 'page',
      navigate_to_page_id: 3,
    })
    expect(selectedPageName(wrapper)).toBe('Summary')
  })

  test('resetting on undo does not write navigate_to_url back to a blank string', async () => {
    // Regression: the dropdown selection used to be mirrored in local state, and
    // re-syncing it wrote `navigate_to_url` back to '' (a string) which differs
    // from the stored object form. On undo that emitted a spurious change, which
    // registered a new action and discarded the redo stack ("No more actions to
    // redo"). Deriving the selection means the reset must not mutate the url.
    const wrapper = await mountComponent({
      props: {
        defaultValues: {
          navigation_type: 'page',
          navigate_to_page_id: 2,
          navigate_to_url: {},
        },
      },
    })

    await applyUndoRedo(wrapper, {
      navigation_type: 'page',
      navigate_to_page_id: null,
      navigate_to_url: {},
    })

    const emissions = wrapper.emitted('values-changed') || []
    for (const [payload] of emissions) {
      expect(payload.navigate_to_url).not.toBe('')
    }
  })
})
