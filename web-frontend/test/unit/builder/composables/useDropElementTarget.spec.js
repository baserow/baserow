import flushPromises from 'flush-promises'
import { defineComponent, reactive } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { useDropElementTarget } from '@baserow/modules/builder/composables/useDropElementTarget'
import { PAGE_PLACES } from '@baserow/modules/builder/enums'

describe('useDropElementTarget', () => {
  let testApp = null
  let store = null

  const page = { id: 1, shared: false, elementMap: {} }
  const sharedPage = { id: 2, shared: true, elementMap: {} }
  const builder = { id: 1, pages: [page, sharedPage] }
  const workspace = { id: 1 }

  const mountDropTarget = ({
    dndContext,
    parentElement = null,
    targetPagePlace = null,
  }) => {
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
          targetPagePlace,
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
      referenceElementId: null,
      position: 'south',
      placeInContainer: '',
      targetPage: page,
    })
    expect(dndContext.dropTargetId).toBe(null)
  })

  test.each(['footer', 'header'])(
    'does not allow dropping a shared %s element into the empty content zone',
    async (sharedType) => {
      const draggedElement = {
        id: 20,
        type: sharedType,
        page_id: sharedPage.id,
        parent_element_id: null,
        place_in_container: null,
      }
      const dndContext = reactive({
        draggedElement,
        dropTargetId: null,
      })
      const dispatchSpy = vi.spyOn(store, 'dispatch').mockResolvedValue()

      const wrapper = await mountDropTarget({
        dndContext,
        targetPagePlace: PAGE_PLACES.CONTENT,
      })
      const target = wrapper.find('[data-test-id="drop-target"]')

      // The zone must never light up as a valid target...
      await target.trigger('dragover')
      expect(dndContext.dropTargetId).toBe(null)

      // ...and a drop must not dispatch a move.
      await target.trigger('drop')
      await flushPromises()
      expect(dispatchSpy).not.toHaveBeenCalled()
    }
  )

  test('still allows dropping a regular content element into the empty content zone', async () => {
    const draggedElement = {
      id: 30,
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

    const wrapper = await mountDropTarget({
      dndContext,
      targetPagePlace: PAGE_PLACES.CONTENT,
    })
    const target = wrapper.find('[data-test-id="drop-target"]')

    await target.trigger('dragover')
    expect(dndContext.dropTargetId).not.toBe(null)

    await target.trigger('drop')
    await flushPromises()

    expect(dispatchSpy).toHaveBeenCalledWith('element/move', {
      builder,
      page,
      elementId: draggedElement.id,
      referenceElementId: null,
      position: 'south',
      placeInContainer: '',
      targetPage: page,
    })
  })
})
