import { reactive } from 'vue'
import resolveFormulaMixin from '@baserow/modules/builder/mixins/resolveFormula'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import HeadingElement from '@baserow/modules/builder/components/elements/components/HeadingElement.vue'
import GeneralSidePanel from '@baserow/modules/builder/components/page/sidePanels/GeneralSidePanel.vue'
import FormContainerElement from '@baserow/modules/builder/components/elements/components/FormContainerElement.vue'
import FormContainerElementForm from '@baserow/modules/builder/components/elements/components/forms/general/FormContainerElementForm.vue'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput.vue'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField.vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import { DATA_SCOPES } from '@baserow/modules/builder/constants'
import TableElement from '@baserow/modules/builder/components/elements/components/TableElement'
import RecordSelectorElement from '@baserow/modules/builder/components/elements/components/RecordSelectorElement'

describe('Builder data provider types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('previous action provider resolves list workflow action results', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'previous_action')

    const workflowAction = {
      id: 10,
      type: 'csv_file_reader',
      service: {
        id: 20,
        type: 'csv_file_reader',
        schema: {
          items: {
            properties: {
              Email: { title: 'Email' },
            },
          },
        },
      },
    }
    const page = { id: 1, workflowActions: [workflowAction] }
    const applicationContext = {
      page,
      previousActionResults: {
        10: {
          results: [{ Email: 'a@example.com' }, { Email: 'b@example.com' }],
          has_next_page: false,
        },
      },
    }

    expect(dataProvider.getDataChunk(applicationContext, ['10'])).toEqual([
      { Email: 'a@example.com' },
      { Email: 'b@example.com' },
    ])
    expect(dataProvider.getDataChunk(applicationContext, ['10', '1'])).toEqual({
      Email: 'b@example.com',
    })
    expect(
      dataProvider.getDataChunk(applicationContext, ['10', '*', 'Email'])
    ).toEqual(['a@example.com', 'b@example.com'])
  })

  test('previous action provider exposes list workflow action schemas', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'previous_action')

    const previousWorkflowAction = {
      id: 10,
      type: 'csv_file_reader',
      event: 'click',
      element_id: 100,
      order: 1,
      service: {
        id: 20,
        type: 'csv_file_reader',
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              Email: { title: 'Email', type: 'string' },
            },
          },
        },
      },
    }
    const currentWorkflowAction = {
      id: 11,
      type: 'notification',
      event: 'click',
      element_id: 100,
      order: 2,
    }
    const page = {
      id: 1,
      workflowActions: [previousWorkflowAction, currentWorkflowAction],
    }
    const applicationContext = {
      page,
      element: { id: 100 },
      workflowAction: currentWorkflowAction,
    }

    expect(dataProvider.getDataSchema(applicationContext)).toEqual({
      type: 'object',
      properties: {
        10: {
          title: 'serviceType.coreCSVFileReader ',
          type: 'array',
          items: {
            type: 'object',
            properties: {
              Email: { title: 'Email', type: 'string' },
            },
          },
        },
      },
    })
  })

  /** Build a reactive form with child inputs shared by scope regression tests. */
  const formContainerPage = () => {
    const formContainer = {
      id: 2,
      type: 'form_container',
      page_id: 1,
      _: { elementNamespacePath: [] },
    }
    const nameInput = {
      id: 3,
      type: 'input_text',
      page_id: 1,
      _: { elementNamespacePath: [] },
      label: { formula: "'Name'" },
      default_value: { formula: '' },
      placeholder: { formula: '' },
    }
    const emailInput = {
      id: 4,
      type: 'input_text',
      page_id: 1,
      _: { elementNamespacePath: [] },
      label: { formula: "'Email'" },
      default_value: { formula: '' },
      placeholder: { formula: '' },
    }
    const page = reactive({
      id: 1,
      _: { dataSourceLoading: false, dataSourceContentLoading: false },
      elementMap: { 2: formContainer, 3: nameInput, 4: emailInput },
      orderedElements: [formContainer, nameInput, emailInput],
      graph: {
        0: 2,
        2: { children: { '': [3] } },
        3: { next: { '': [4] } },
        4: {},
      },
      formData: {
        3: { value: 'Ada', isValid: true, touched: true },
        4: { value: 'ada@example.com', isValid: true, touched: true },
      },
    })
    return {
      builder: { id: 1 },
      workspace: {},
      page,
      element: formContainer,
    }
  }

  test('form data provider dispatches the inputs of a submitted form', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'form_data')
    const applicationContext = formContainerPage()

    expect(dataProvider.getDataContent(applicationContext)).toEqual({
      3: 'Ada',
      4: 'ada@example.com',
    })
    expect(dataProvider.getActionDispatchContext(applicationContext)).toEqual([
      { 3: 'Ada', 4: 'ada@example.com' },
      {},
    ])
  })

  test('form data provider applies its requested data scope', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'form_data')
    const applicationContext = formContainerPage()
    const excludingTargetSubtreeContext = {
      ...applicationContext,
      dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
    }

    expect(dataProvider.isValid(['3'])).toBe(true)
    expect(dataProvider.isValid(['3'], applicationContext)).toBe(true)
    expect(dataProvider.isValid(['3'], excludingTargetSubtreeContext)).toBe(
      false
    )
    expect(
      Object.keys(dataProvider.getDataSchema(applicationContext).properties)
    ).toEqual(['3', '4'])
    expect(
      dataProvider.getDataSchema(excludingTargetSubtreeContext).properties
    ).toEqual({})
  })

  test('form submit label editor offers inputs inside the form', async () => {
    const applicationContext = formContainerPage()
    const { page, element, builder } = applicationContext
    builder.theme = {}
    const wrapper = await mountSuspended(FormContainerElementForm, {
      props: { defaultValues: { ...element, styles: {} } },
      global: {
        provide: {
          ...applicationContext,
          currentPage: page,
          elementPage: page,
          mode: 'editing',
          formulaComponent: ApplicationBuilderFormulaInput,
          dataProvidersAllowed: ['form_data'],
          applicationContext: {
            ...applicationContext,
            dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
          },
        },
        stubs: { CustomStyleButton: true },
      },
    })
    const input = wrapper.findComponent(FormulaInputField)
    const formDataNode = input
      .props('nodesHierarchy')
      .flatMap((group) => group.nodes || [])
      .find((node) => node.identifier === 'form_data')
    expect(formDataNode.nodes.map((node) => node.identifier)).toEqual([
      '3',
      '4',
    ])
    wrapper.unmount()
  })

  test.each(['editing', 'public'])(
    'form submit label reads child inputs in %s mode',
    async (mode) => {
      const applicationContext = formContainerPage()
      const { page, element, builder } = applicationContext
      builder.theme = {}
      page.workflowActions = []
      element.styles = {}
      element.submit_button_label = { formula: "get('form_data.3')" }
      const wrapper = await mountSuspended(FormContainerElement, {
        props: { element },
        global: {
          provide: {
            ...applicationContext,
            currentPage: page,
            elementPage: page,
            mode,
            applicationContext: {
              ...applicationContext,
              mode,
              dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
            },
          },
          stubs: {
            ElementPreview: true,
            PageElement: true,
            ABButton: { template: '<button><slot /></button>' },
          },
        },
      })
      expect(wrapper.find('button').text()).toBe('Ada')
      await useNuxtApp().$store.dispatch('formData/setFormData', {
        page,
        uniqueElementId: '3',
        payload: { value: 'Grace', isValid: true, touched: true },
      })
      expect(wrapper.find('button').text()).toBe('Grace')
      wrapper.unmount()
    }
  )

  test.each([
    [3, '4', 'ada@example.com'],
    [4, '3', 'Ada'],
  ])('input %s can read its sibling input %s', (targetId, siblingId, value) => {
    const applicationContext = formContainerPage()
    applicationContext.element = applicationContext.page.elementMap[targetId]
    applicationContext.dataScope = DATA_SCOPES.EXCLUDE_TARGET_SUBTREE
    const provider = testApp
      .getRegistry()
      .get('builderDataProvider', 'form_data')
    expect(provider.getDataChunk(applicationContext, [siblingId])).toBe(value)
    expect(
      Object.keys(provider.getDataSchema(applicationContext).properties)
    ).toEqual([siblingId])
  })

  test.each(['before form', 'after form', 'inside form'])(
    'a heading %s can select and render form inputs',
    async (position) => {
      const { page, builder, workspace } = formContainerPage()
      const heading = {
        id: 5,
        type: 'heading',
        page_id: page.id,
        level: 1,
        styles: {},
        value: { formula: "get('form_data.3')" },
      }
      page.graph[5] = {}
      if (position === 'before form') {
        page.graph[0] = 5
        page.graph[5] = { next: { '': [2] } }
      } else if (position === 'after form') {
        page.graph[2].next = { '': [5] }
      } else {
        page.graph[4].next = { '': [5] }
      }
      builder.theme = {}
      builder.pages = [page, { id: 2, shared: true, dataSources: [] }]
      page.dataSources = []
      const store = useNuxtApp().$store
      store.commit('element/SET_ITEMS', {
        builder,
        page,
        elements: [...page.orderedElements, heading],
      })
      for (const element of page.orderedElements) {
        await store.dispatch('element/_setElementNamespacePath', {
          page,
          element,
        })
      }
      builder.selectedElement = page.elementMap[5]
      const applicationContext = {
        page,
        builder,
        workspace,
        element: builder.selectedElement,
        mode: 'editing',
        dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
      }
      const provide = {
        builder,
        workspace,
        currentPage: page,
        elementPage: page,
        mode: 'editing',
        formulaComponent: ApplicationBuilderFormulaInput,
        applicationContext,
      }
      const editor = await mountSuspended(GeneralSidePanel, {
        global: { provide, stubs: { CustomStyleButton: true } },
      })
      const formDataNode = editor
        .findComponent(FormulaInputField)
        .props('nodesHierarchy')
        .flatMap((group) => group.nodes || [])
        .find((node) => node.identifier === 'form_data')
      expect(formDataNode.nodes.map((node) => node.identifier)).toEqual([
        '3',
        '4',
      ])
      const rendered = await mountSuspended(HeadingElement, {
        props: { element: builder.selectedElement },
        global: { provide },
      })
      expect(rendered.text()).toBe('Ada')
      await store.dispatch('formData/setFormData', {
        page,
        uniqueElementId: '3',
        payload: { value: 'Grace', isValid: true, touched: true },
      })
      expect(rendered.text()).toBe('Grace')
      editor.unmount()
      rendered.unmount()
    }
  )

  test('current record dispatch preserves nested row indexes', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'current_record')

    expect(
      dataProvider.getActionDispatchContext({
        recordId: 42,
        recordIndexPath: [0, 1],
      })
    ).toEqual({ record_id: 42, index_path: [0, 1] })
  })

  test('current record provider applies target element data scopes', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'current_record')
    const table = {
      id: 2,
      type: 'table',
      page_id: 1,
      data_source_id: 1,
      schema_property: 'rows',
    }
    const page = {
      id: 1,
      dataSources: [
        {
          id: 1,
          type: 'csv_file_reader',
          schema: {
            type: 'array',
            items: {
              properties: {
                rows: {
                  type: 'array',
                  items: { properties: { name: { type: 'string' } } },
                },
              },
            },
          },
        },
      ],
      elementMap: { 2: table },
      orderedElements: [table],
      graph: { 0: 2, 2: {} },
    }
    const applicationContext = {
      builder: { id: 1, pages: [page, { id: 2, shared: true }] },
      page,
      element: table,
    }

    expect(dataProvider.getDataSchema(applicationContext)).toBeNull()
    expect(
      dataProvider.getDataSchema({
        ...applicationContext,
        dataScope: DATA_SCOPES.INCLUDE_TARGET_ELEMENT,
      }).properties
    ).toHaveProperty('name')
    expect(
      dataProvider.getDataSchema({
        ...applicationContext,
        dataScope: DATA_SCOPES.INCLUDE_TARGET_DATA_SOURCE,
      }).properties
    ).toHaveProperty('rows')
  })

  test('table fields inside a repeat read their row while visibility reads the parent row', () => {
    const currentRecord = testApp
      .getRegistry()
      .get('builderDataProvider', 'current_record')
    const repeat = {
      id: 10,
      type: 'repeat',
      page_id: 1,
      data_source_id: 1,
      schema_property: null,
      _: {
        content: [
          { parentName: 'First', rows: [{ cellName: 'First cell' }] },
          { parentName: 'Second', rows: [{ cellName: 'Second cell' }] },
        ],
      },
    }
    const table = {
      id: 11,
      type: 'table',
      page_id: 1,
      data_source_id: null,
      schema_property: 'rows',
    }
    const heading = { id: 12, type: 'heading', page_id: 1 }
    const page = {
      id: 1,
      dataSources: [
        {
          id: 1,
          type: 'csv_file_reader',
          schema: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                parentName: { type: 'string' },
                rows: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: { cellName: { type: 'string' } },
                  },
                },
              },
            },
          },
        },
      ],
      elementMap: { 10: repeat, 11: table, 12: heading },
      graph: {
        0: 10,
        10: { children: { '': [11] } },
        11: { next: { '': [12] } },
        12: {},
      },
    }
    const builder = { id: 1, pages: [page, { id: 2, shared: true }] }
    const parentContext = {
      builder,
      page,
      element: repeat,
      recordIndexPath: [1],
      dataScope: DATA_SCOPES.INCLUDE_TARGET_ELEMENT,
    }
    const tableContext = { ...parentContext, element: table }

    // A normal element inside the repeat reads the selected repeat record.
    expect(
      currentRecord.getDataChunk({ ...parentContext, element: heading }, [
        'parentName',
      ])
    ).toBe('Second')
    // The table's collection field reads its own selected row.
    expect(
      TableElement.methods.resolveRowFormula.call(
        {
          $registry: testApp.getRegistry(),
          applicationContext: tableContext,
          resolveFormula: (_formula, formulaContext) =>
            formulaContext['current_record.cellName'],
        },
        'get(current_record.cellName)',
        0
      )
    ).toBe('Second cell')
    expect(currentRecord.getDataSchema(tableContext).properties).toHaveProperty(
      'cellName'
    )

    // The table's visibility formula uses its parent repeat record instead.
    const visibilityContext = {
      ...tableContext,
      dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
    }
    expect(currentRecord.getDataChunk(visibilityContext, ['parentName'])).toBe(
      'Second'
    )
    expect(
      currentRecord.getDataChunk(visibilityContext, ['cellName'])
    ).toBeNull()
    expect(
      currentRecord.getDataSchema(visibilityContext).properties
    ).not.toHaveProperty('cellName')

    // The nested collection's schema picker sees the parent row's `rows`
    // property, not the table row properties defined by that property.
    const dataSourceContext = {
      ...tableContext,
      dataScope: DATA_SCOPES.INCLUDE_TARGET_DATA_SOURCE,
    }
    expect(
      currentRecord.getDataSchema(dataSourceContext).properties
    ).toHaveProperty('rows')
    expect(
      currentRecord.getDataSchema(dataSourceContext).properties
    ).not.toHaveProperty('cellName')
  })

  test('record selector inside a repeat uses its own options but its parent for visibility', () => {
    const currentRecord = testApp
      .getRegistry()
      .get('builderDataProvider', 'current_record')
    const repeat = {
      id: 10,
      type: 'repeat',
      page_id: 1,
      data_source_id: 1,
      schema_property: null,
      _: {
        content: [{ parentName: 'First' }, { parentName: 'Second' }],
      },
    }
    const recordSelector = {
      id: 20,
      type: 'record_selector',
      page_id: 1,
      data_source_id: 2,
      schema_property: null,
      _: {
        content: [
          { id: 201, choiceName: 'First choice' },
          { id: 202, choiceName: 'Second choice' },
        ],
      },
    }
    const page = {
      id: 1,
      dataSources: [
        {
          id: 1,
          type: 'csv_file_reader',
          schema: {
            type: 'array',
            items: {
              type: 'object',
              properties: { parentName: { type: 'string' } },
            },
          },
        },
        {
          id: 2,
          type: 'csv_file_reader',
          schema: {
            type: 'array',
            items: {
              type: 'object',
              properties: { choiceName: { type: 'string' } },
            },
          },
        },
      ],
      elementMap: { 10: repeat, 20: recordSelector },
      graph: { 0: 10, 10: { children: { '': [20] } }, 20: {} },
    }
    const applicationContext = {
      builder: { id: 1, pages: [page, { id: 2, shared: true }] },
      page,
      element: recordSelector,
      recordIndexPath: [1],
      dataScope: DATA_SCOPES.INCLUDE_TARGET_ELEMENT,
    }

    const options = RecordSelectorElement.computed.resolvedOptions.call({
      $registry: testApp.getRegistry(),
      applicationContext,
      element: { option_name_suffix: { formula: '' } },
      elementContent: recordSelector._.content,
      getId: (record) => record.id,
      resolveFormula(_formula, formulaContext) {
        return resolveFormulaMixin.methods.getRuntimeFormulaContext.call(
          this,
          formulaContext(this.applicationContext)
        )['current_record.choiceName']
      },
      dataSourceType: { getRecordName: () => 'Option' },
      dataSource: page.dataSources[0],
      defaultValueOptions: [],
      fallbackOptions: [],
      $t: (key) => key,
    })
    expect(options.map(({ nameSuffix }) => nameSuffix)).toEqual([
      'First choice',
      'Second choice',
    ])
    expect(
      currentRecord.getDataSchema(applicationContext).properties
    ).toHaveProperty('choiceName')
    expect(
      currentRecord.getDataSchema({
        ...applicationContext,
        dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
      }).properties
    ).toHaveProperty('parentName')
    expect(
      currentRecord.getDataChunk(
        {
          ...applicationContext,
          dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
        },
        ['parentName']
      )
    ).toBe('Second')
    expect(
      currentRecord.getDataChunk(
        {
          ...applicationContext,
          dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
        },
        ['choiceName']
      )
    ).toBeNull()
  })

  test('data source context provider skips data sources without context data', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'data_source_context')

    const contextDataSchema = {
      type: 'object',
      properties: { 1: { type: 'object', title: 'Status' } },
    }
    const page = {
      id: 1,
      dataSources: [
        {
          id: 10,
          type: 'local_baserow_get_row',
          context_data_schema: contextDataSchema,
        },
        { id: 11, type: 'http_get', url: { formula: "'https://x'" } },
        {
          id: 12,
          type: 'http_get',
          url: { formula: "'https://x'" },
          returns_list: true,
        },
      ],
    }
    const sharedPage = { id: 2, shared: true, dataSources: [] }
    const applicationContext = {
      builder: { pages: [sharedPage, page] },
      page,
    }

    expect(dataProvider.getDataSchema(applicationContext)).toEqual({
      type: 'object',
      properties: { 10: { ...contextDataSchema, order: 0 } },
    })
  })
})
