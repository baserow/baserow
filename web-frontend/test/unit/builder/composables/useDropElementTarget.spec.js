import flushPromises from 'flush-promises'
import { defineComponent, reactive } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { useDropElementTarget } from '@baserow/modules/builder/composables/useDropElementTarget'

describe('useDropElementTarget', () => {
  let testApp = null
  let store = null

  const page = { id: 1, shared: false, elementMap: {} }
  const sharedPage = { id: 2, shared: true, elementMap: {} }
  const builder = { id: 1, pages: [page, sharedPage] }
  const workspace = { id: 1 }

  const mountDropTarget = ({ dndContext, parentElement = null }) => {
    const DropTarget = defineComponent({
      template: `
        <div
          data-test-id="drop-target"
          @dragenter="onDragEnter"
          @dragover="onDragOver"
          @dragleave="onDragLeave"
          @drop="onDrop"
        />
      `,
      setup() {
        return useDropElementTarget({
          parentElement,
          page,
        })
      },
    })

    return mountSuspended(DropTarget, {
      global: {
        provide: {
          builder,
          dndContext,
          workspace,
        },
      },
    })
  }

  beforeEach(() => {
    testApp = useNuxtApp()
    store = testApp.$store
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('can drop on an empty placeholder after dragover without dragenter', async () => {
    const draggedElement = {
      id: 10,
      type: 'heading',
      page_id: page.id,
      parent_element_id: null,
      place_in_container: null,
    }
    const dndContext = reactive({
      draggedElement,
      dropTargetId: null,
    })
    const dispatchSpy = vi.spyOn(store, 'dispatch').mockResolvedValue()

    const wrapper = await mountDropTarget({ dndContext })
    const target = wrapper.find('[data-test-id="drop-target"]')

    await target.trigger('dragover')

    expect(dndContext.dropTargetId).not.toBe(null)

    await target.trigger('drop')
    await flushPromises()

    expect(dispatchSpy).toHaveBeenCalledWith('element/move', {
      builder,
      page,
      elementId: draggedElement.id,
      beforeElementId: null,
      parentElementId: null,
      placeInContainer: null,
      targetPage: page,
    })
    expect(dndContext.dropTargetId).toBe(null)
  })
})
