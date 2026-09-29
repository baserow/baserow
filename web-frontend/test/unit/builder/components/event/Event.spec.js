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

const coreGroup = {
  id: 'core',
  label: 'Core',
  icon: 'iconoir-package',
}

const workflowActionType = {
  label: 'Show Notification',
  description: 'Show a notification message to the user.',
  icon: 'iconoir-chat-bubble-empty',
  image: null,
  group: coreGroup,
  getType: () => 'notification',
  isDeactivated: () => false,
  isDeactivatedReason: () => null,
  getDeactivatedClickModal: () => null,
}

const localBaserowGroup = {
  id: 'integration-local_baserow',
  label: 'Local Baserow',
  image: '/local-baserow.svg',
  icon: null,
}

const createRowWorkflowActionType = {
  label: 'Create row',
  description: 'Add a new record to a table.',
  icon: 'iconoir-plus',
  image: null,
  group: localBaserowGroup,
  getType: () => 'create_row',
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
        availableWorkflowActionTypes: [
          workflowActionType,
          createRowWorkflowActionType,
        ],
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
    expect(
      wrapper
        .findAll('.grouped-menu__navigation .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Core', 'Local Baserow'])
    expect(
      wrapper
        .findAll('.grouped-menu__actions .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Show Notification'])
    expect(
      wrapper
        .findAll('.grouped-menu__actions .menu-list__item-description')
        .map((item) => item.text())
    ).toEqual(['Show a notification message to the user.'])

    await wrapper
      .findAll('.grouped-menu__navigation .menu-list__item-button')
      .find((item) => item.text().includes('Local Baserow'))
      .trigger('click')

    expect(
      wrapper.find('.grouped-menu__actions .menu-list__item-description').text()
    ).toBe('Add a new record to a table.')

    await wrapper
      .findAll('.grouped-menu__actions .menu-list__item-button')
      .find((item) => item.text().includes('Create row'))
      .trigger('click')
    await flushPromises()

    expect(store.dispatch).toHaveBeenCalledWith(
      'builderWorkflowAction/create',
      {
        page: elementPage,
        workflowActionType: 'create_row',
        eventType: 'click',
        configuration: { element_id: element.id },
      }
    )
  })
})
