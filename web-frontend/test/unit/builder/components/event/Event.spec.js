import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { vi } from 'vitest'

import '@baserow/modules/builder/enums'
import EventComponent from '@baserow/modules/builder/components/event/Event'
import { Event as BuilderEvent } from '@baserow/modules/builder/eventTypes'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput.vue'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField.vue'
import { DATA_SCOPES } from '@baserow/modules/builder/constants'

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
  test.each([false, true])(
    'a table button action formula offers row fields when using a property: %s',
    async (usesProperty) => {
      const app = useNuxtApp()
      const parent = {
        id: 2,
        page_id: 2,
        type: 'repeat',
        data_source_id: 5,
        schema_property: null,
      }
      const element = {
        id: 3,
        page_id: 2,
        type: 'table',
        data_source_id: usesProperty ? null : 5,
        schema_property: usesProperty ? 'rows' : null,
        fields: [{ id: 1, uid: 'button-1', type: 'button', name: 'Notify' }],
      }
      const page = {
        id: 2,
        _: { dataSourceLoading: false, dataSourceContentLoading: false },
        workflowActions: [],
        dataSources: [
          {
            id: 5,
            type: 'local_baserow_list_rows',
            table_id: 1,
            schema: {
              type: 'array',
              items: {
                type: 'object',
                properties: usesProperty
                  ? {
                      parentName: { type: 'string' },
                      rows: {
                        type: 'array',
                        items: {
                          type: 'object',
                          properties: { cellName: { type: 'string' } },
                        },
                      },
                    }
                  : { field_1: { type: 'string', title: 'Name' } },
              },
            },
          },
        ],
        graph: usesProperty
          ? { 0: 2, 2: { children: { '': [3] } }, 3: {} }
          : { 0: 3, 3: {} },
      }
      const builder = {
        id: 1,
        pages: [{ id: 1, shared: true, dataSources: [], graph: {} }, page],
        theme: {},
      }
      app.$store.commit('element/SET_ITEMS', {
        builder,
        page,
        elements: usesProperty ? [parent, element] : [element],
      })

      const tableType = app.$registry.get('element', 'table')
      const event = tableType.getEvents(element)[0]
      const workflowAction = {
        id: 10,
        type: 'notification',
        title: { formula: '' },
        description: { formula: '' },
      }
      const wrapper = await mountSuspended(EventComponent, {
        props: {
          event,
          element,
          applicationContextAdditions: event.applicationContextAdditions,
          workflowActions: [workflowAction],
          availableWorkflowActionTypes: [
            app.$registry.get('workflowAction', 'notification'),
          ],
        },
        global: {
          provide: {
            applicationContext: {
              builder,
              page,
              element,
              mode: 'editing',
              dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
            },
            builder,
            elementPage: page,
            workspace: { id: 1 },
            mode: 'editing',
            formulaComponent: ApplicationBuilderFormulaInput,
            dataProvidersAllowed: ['current_record'],
          },
          stubs: {
            Context: ContextStub,
            SidebarExpandable: {
              template: '<div><slot name="title" /><slot /></div>',
            },
          },
          mocks: {
            $store: { dispatch: vi.fn().mockResolvedValue({}), getters: {} },
          },
        },
      })
      await flushPromises()

      const titleInput = wrapper.findComponent(FormulaInputField)
      const currentRecord = titleInput
        .props('nodesHierarchy')
        .flatMap((group) => group.nodes || [])
        .find((node) => node.identifier === 'current_record')
      const fields = currentRecord.nodes.map((node) => node.identifier)
      expect(fields).toContain(usesProperty ? 'cellName' : 'field_1')
      if (usesProperty) {
        expect(fields).not.toContain('parentName')
      }
      wrapper.unmount()
    }
  )

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
