import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { vi } from 'vitest'

import EventComponent from '@baserow/modules/builder/components/event/Event'
import { Event as BuilderEvent } from '@baserow/modules/builder/eventTypes'

const ContextStub = defineComponent({
  name: 'Context',
  methods: {
    show() {},
    hide() {},
  },
  template: '<div><slot /></div>',
})

const ButtonTextStub = defineComponent({
  name: 'ButtonText',
  template: '<button><slot /></button>',
})

const workflowActionType = {
  label: 'Show Notification',
  icon: 'iconoir-chat-bubble-empty',
  image: null,
  getType: () => 'notification',
  isDeactivated: () => false,
  isDeactivatedReason: () => null,
  getDeactivatedClickModal: () => null,
}

describe('Event', () => {
  test('creates a workflow action selected from the shared menu', async () => {
    const builder = { id: 1 }
    const elementPage = { id: 2 }
    const element = { id: 3 }
    const workspace = { id: 4 }
    const store = {
      dispatch: vi.fn().mockResolvedValue({}),
      getters: {},
    }
    const event = new BuilderEvent({
      app: {},
      name: 'click',
      label: 'Click',
    })

    const wrapper = await mountSuspended(EventComponent, {
      props: {
        event,
        element,
        workflowActions: [],
        availableWorkflowActionTypes: [workflowActionType],
      },
      global: {
        provide: {
          applicationContext: { builder, page: elementPage, workspace },
          builder,
          elementPage,
          workspace,
        },
        directives: {
          autoOverflowScroll: {},
          tooltip: {},
        },
        stubs: {
          ButtonText: ButtonTextStub,
          Context: ContextStub,
        },
        mocks: {
          $store: store,
          $t: (key) => key,
        },
      },
    })

    await flushPromises()
    expect(wrapper.find('.menu-list__item-label').text()).toBe(
      'Show Notification'
    )

    await wrapper.find('.menu-list__item-button').trigger('click')
    await flushPromises()

    expect(store.dispatch).toHaveBeenCalledWith(
      'builderWorkflowAction/create',
      {
        page: elementPage,
        workflowActionType: 'notification',
        eventType: 'click',
        configuration: { element_id: element.id },
      }
    )
  })
})
