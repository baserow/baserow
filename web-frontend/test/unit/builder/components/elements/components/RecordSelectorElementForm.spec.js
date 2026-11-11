import { mountSuspended } from '@nuxt/test-utils/runtime'
import '@baserow/modules/builder/enums'
import RecordSelectorElementForm from '@baserow/modules/builder/components/elements/components/forms/general/RecordSelectorElementForm.vue'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput.vue'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField.vue'
import { DATA_SCOPES } from '@baserow/modules/builder/constants'

describe('RecordSelectorElementForm formula scopes', () => {
  test('offers the current option row only in the option suffix formula editor', async () => {
    const element = {
      id: 20,
      page_id: 1,
      type: 'record_selector',
      data_source_id: 1,
      items_per_page: 5,
      option_name_suffix: { formula: '' },
      label: { formula: '' },
      default_value: { formula: '' },
      placeholder: { formula: '' },
      styles: {},
    }
    const page = {
      id: 1,
      _: { dataSourceLoading: false, dataSourceContentLoading: false },
      dataSources: [
        {
          id: 1,
          type: 'local_baserow_list_rows',
          table_id: 1,
          schema: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                field_1: { type: 'string', title: 'Name' },
              },
            },
          },
        },
      ],
      graph: { 0: 20, 20: {} },
    }
    const sharedPage = { id: 2, shared: true, dataSources: [], graph: {} }
    const builder = {
      id: 1,
      pages: [sharedPage, page],
      selectedElement: element,
      theme: {},
    }
    useNuxtApp().$store.commit('element/SET_ITEMS', {
      builder,
      page,
      elements: [element],
    })
    builder.selectedElement = element

    const wrapper = await mountSuspended(RecordSelectorElementForm, {
      props: { defaultValues: element },
      global: {
        provide: {
          workspace: { id: 1 },
          builder,
          currentPage: page,
          elementPage: page,
          mode: 'editing',
          formulaComponent: ApplicationBuilderFormulaInput,
          applicationContext: {
            builder,
            page,
            element,
            mode: 'editing',
            dataScope: DATA_SCOPES.EXCLUDE_TARGET_SUBTREE,
          },
        },
        stubs: {
          CustomStyleButton: true,
          DataSourceDropdown: true,
          PropertyOptionForm: true,
        },
      },
    })

    const formulaInputs = wrapper.findAllComponents(FormulaInputField)
    const providerNames = (input) =>
      input
        .props('nodesHierarchy')
        .flatMap((group) => group.nodes || [])
        .map((node) => node.identifier)

    expect(formulaInputs).toHaveLength(4)
    expect(providerNames(formulaInputs[0])).toContain('current_record')
    const currentRecordNode = formulaInputs[0]
      .props('nodesHierarchy')
      .flatMap((group) => group.nodes || [])
      .find((node) => node.identifier === 'current_record')
    expect(currentRecordNode.nodes.map((node) => node.identifier)).toContain(
      'field_1'
    )
    const fieldNode = currentRecordNode.nodes.find(
      (node) => node.identifier === 'field_1'
    )
    formulaInputs[0].vm.handleNodeSelected({
      path: 'current_record.field_1',
      node: fieldNode,
    })
    expect(formulaInputs[0].emitted('input').at(-1)).toEqual([
      "get('current_record.field_1')",
    ])
    expect(providerNames(formulaInputs[1])).not.toContain('current_record')
    expect(providerNames(formulaInputs[2])).not.toContain('current_record')
    expect(providerNames(formulaInputs[3])).not.toContain('current_record')
    wrapper.unmount()
  })
})
