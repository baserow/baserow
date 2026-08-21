import { flushPromises } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'

import { TestApp } from '@baserow/test/helpers/testApp'
import ImportFileModal from '@baserow/modules/database/components/table/ImportFileModal'

let getDataHook = async () => {}

const ModalStub = defineComponent({
  name: 'Modal',
  methods: {
    show() {},
    hide() {},
  },
  template: '<div><slot name="content" /><slot name="sidebar" /></div>',
})

const CSVImporterStub = defineComponent({
  name: 'TableCSVImporter',
  emits: ['data', 'getData'],
  mounted() {
    this.$emit('data', {
      header: ['Name', 'Notes', 'Active'],
      previewData: [['Ada', 'Cannot write this', 'true']],
    })
    this.$emit('getData', async () => {
      await getDataHook()
      return [['Ada', 'Cannot write this', 'true']]
    })
  },
  template:
    '<div class="csv-importer-stub"><slot name="upsertMapping" /></div>',
})

const CheckboxStub = defineComponent({
  name: 'Checkbox',
  props: ['modelValue', 'disabled'],
  emits: ['update:modelValue'],
  template:
    '<button class="enable-upsert" :disabled="disabled" @click="$emit(\'update:modelValue\', true)"><slot /></button>',
})

const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: ['modelValue', 'disabled'],
  emits: ['update:modelValue'],
  template:
    '<div class="dropdown-stub" :data-model-value="modelValue"><button class="choose-name-field" :disabled="disabled" @click="$emit(\'update:modelValue\', 1)">Name</button><slot /></div>',
})

const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  props: ['name', 'value', 'disabled'],
  template:
    '<span class="dropdown-item-stub" :data-value="value">{{ name }}</span>',
})

describe('ImportFileModal', () => {
  let testApp
  let notesFieldType
  let originalNotesFieldTypeApp
  let notesWritable

  const table = { id: 5, name: 'People' }
  const database = {
    id: 1,
    workspace: { id: 10 },
    tables: [table],
  }
  const fields = [
    {
      id: 1,
      name: 'Name',
      type: 'text',
      primary: true,
      order: 0,
      read_only: false,
      workspace_id: 10,
      _: { type: { iconClass: 'iconoir-text' } },
    },
    {
      id: 2,
      name: 'Notes',
      type: 'long_text',
      primary: false,
      order: 1,
      read_only: false,
      workspace_id: 10,
      _: { type: { iconClass: 'iconoir-align-left' } },
    },
    {
      id: 3,
      name: 'Active',
      type: 'boolean',
      primary: false,
      order: 2,
      read_only: false,
      workspace_id: 10,
      _: { type: { iconClass: 'iconoir-check-circle' } },
    },
  ]

  beforeEach(() => {
    testApp = new TestApp()
    getDataHook = async () => {}
    notesWritable = ref(false)
    notesFieldType = testApp.$registry.get('field', 'long_text')
    originalNotesFieldTypeApp = notesFieldType.app
    notesFieldType.app = new Proxy(notesFieldType.app, {
      get(target, property) {
        return property === '$hasPermission'
          ? () => notesWritable.value
          : Reflect.get(target, property)
      },
    })
  })

  afterEach(async () => {
    notesFieldType.app = originalNotesFieldTypeApp
    await testApp.afterEach()
  })

  test.each([
    ['normal import', false],
    ['upsert', true],
  ])(
    'omits a denied middle field from the mapping and %s payload',
    async (_, useUpsert) => {
      let requestBody
      testApp.mock
        .onPost(`/database/tables/${table.id}/import/async/`)
        .reply((request) => {
          requestBody = JSON.parse(request.data)
          return [
            200,
            {
              id: useUpsert ? 2 : 1,
              type: 'file_import',
              state: 'finished',
              progress_percentage: 100,
              table_id: table.id,
              database_id: database.id,
              report: { failing_rows: {} },
            },
          ]
        })

      const wrapper = await testApp.mount(ImportFileModal, {
        props: { database, table, fields },
        global: {
          stubs: {
            Modal: ModalStub,
            TableCSVImporter: CSVImporterStub,
            Checkbox: CheckboxStub,
            Dropdown: DropdownStub,
            DropdownItem: DropdownItemStub,
            SimpleGrid: true,
            ImportErrorReport: true,
          },
        },
      })

      await wrapper.find('.choice-items__link').trigger('click')
      await flushPromises()

      const mappingPanel = wrapper.find('.import-modal__field-mapping-body')
      const availableFieldNames = mappingPanel
        .findAll('.dropdown-item-stub')
        .map((item) => item.text())
      expect(availableFieldNames).not.toContain('Notes')
      expect(availableFieldNames).toContain('Name')
      expect(availableFieldNames).toContain('Active')
      expect(
        mappingPanel
          .findAll('.dropdown-stub')
          .map((dropdown) => Number(dropdown.attributes('data-model-value')))
      ).toStrictEqual([1, 0, 3])

      if (useUpsert) {
        const importer = wrapper.find('.csv-importer-stub')
        await importer.find('.enable-upsert').trigger('click')
        await importer.find('.choose-name-field').trigger('click')
      }

      await wrapper.find('.modal-progress__primary-button').trigger('click')
      await vi.waitFor(() => expect(requestBody).toBeDefined())

      expect(requestBody.data).toStrictEqual([['Ada', true]])
      if (useUpsert) {
        expect(requestBody.configuration).toStrictEqual({
          import_fields: [1, 3],
          upsert_fields: [1],
          upsert_values: [['Ada']],
        })
      } else {
        expect(requestBody.configuration).toStrictEqual({
          import_fields: [1, 3],
        })
      }
    }
  )

  test('uses one field snapshot while preparing import data', async () => {
    notesWritable.value = true
    let requestBody
    testApp.mock
      .onPost(`/database/tables/${table.id}/import/async/`)
      .reply((request) => {
        requestBody = JSON.parse(request.data)
        return [
          200,
          {
            id: 1,
            type: 'file_import',
            state: 'finished',
            progress_percentage: 100,
            table_id: table.id,
            database_id: database.id,
            report: { failing_rows: {} },
          },
        ]
      })

    const wrapper = await testApp.mount(ImportFileModal, {
      props: { database, table, fields },
      global: {
        stubs: {
          Modal: ModalStub,
          TableCSVImporter: CSVImporterStub,
          Checkbox: CheckboxStub,
          Dropdown: DropdownStub,
          DropdownItem: DropdownItemStub,
          SimpleGrid: true,
          ImportErrorReport: true,
        },
      },
    })

    await wrapper.find('.choice-items__link').trigger('click')
    await flushPromises()
    expect(wrapper.vm.writableFields.map(({ id }) => id)).toStrictEqual([
      1, 2, 3,
    ])

    getDataHook = async () => {
      notesWritable.value = false
      await nextTick()
      expect(wrapper.vm.writableFields.map(({ id }) => id)).toStrictEqual([
        1, 3,
      ])
    }

    await wrapper.find('.modal-progress__primary-button').trigger('click')
    await vi.waitFor(() => expect(requestBody).toBeDefined())

    expect(requestBody.data).toStrictEqual([['Ada', 'Cannot write this', true]])
    expect(requestBody.configuration).toStrictEqual({
      import_fields: [1, 2, 3],
    })
  })

  test('rejects a stale mapping when its field becomes denied', async () => {
    notesWritable.value = true
    const wrapper = await testApp.mount(ImportFileModal, {
      props: { database, table, fields },
      global: {
        stubs: {
          Modal: ModalStub,
          TableCSVImporter: CSVImporterStub,
          Checkbox: CheckboxStub,
          Dropdown: DropdownStub,
          DropdownItem: DropdownItemStub,
          SimpleGrid: true,
          ImportErrorReport: true,
        },
      },
    })

    await wrapper.find('.choice-items__link').trigger('click')
    await flushPromises()
    wrapper.vm.useUpsertField = true
    wrapper.vm.upsertField = 2
    await nextTick()
    expect(wrapper.vm.canBeSubmitted).toBe(true)

    notesWritable.value = false
    await nextTick()

    expect(wrapper.vm.fieldMapping).toStrictEqual([
      ['0', 0],
      ['2', 1],
    ])
    expect(wrapper.vm.availableUpsertFields.map(({ id }) => id)).not.toContain(
      2
    )
    expect(wrapper.vm.canBeSubmitted).toBe(false)
  })
})
