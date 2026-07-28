import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import FieldPermissionsModal from '@baserow_enterprise/components/fieldPermissions/FieldPermissionsModal'
import FieldPermissionService from '@baserow_enterprise/services/fieldPermissions'

vi.mock('@baserow_enterprise/services/fieldPermissions', () => ({
  default: vi.fn(),
}))

const MainModalStub = defineComponent({
  name: 'Modal',
  emits: ['show'],
  data() {
    return { visible: true }
  },
  mounted() {
    this.$emit('show')
  },
  methods: {
    show() {
      this.$emit('show')
    },
    hide() {
      this.visible = false
    },
  },
  template: '<div v-if="visible" class="modal-stub"><slot /></div>',
})

const SubjectsSelectorStub = defineComponent({
  name: 'FieldPermissionSubjectsSelector',
  props: ['fieldId'],
  emits: ['selection-change'],
  mounted() {
    this.$emit('selection-change', 1)
  },
  methods: {
    getSelectedSubjects() {
      return [{ subject_id: 2, subject_type: 'auth.User' }]
    },
  },
  template: '<div class="subjects-editor"></div>',
})

const DropdownStub = defineComponent({
  name: 'Dropdown',
  emits: ['input'],
  template:
    '<div><button class="choose-custom" @click="$emit(\'input\', \'CUSTOM\')">Custom</button><slot /></div>',
})

const simpleStub = (name) =>
  defineComponent({ name, template: '<div><slot /></div>' })

async function mountComponent() {
  return await mountSuspended(FieldPermissionsModal, {
    props: {
      field: { id: 10, name: 'Last name', type: 'text' },
      workspaceId: 20,
    },
    global: {
      stubs: {
        Modal: MainModalStub,
        FieldPermissionSubjectsSelector: SubjectsSelectorStub,
        Dropdown: DropdownStub,
        DropdownItem: simpleStub('DropdownItem'),
        FormGroup: defineComponent({
          name: 'FormGroup',
          template: '<div class="forms-toggle"><slot /></div>',
        }),
        SwitchInput: simpleStub('SwitchInput'),
        Alert: simpleStub('Alert'),
        Button: defineComponent({
          name: 'Button',
          template: '<button><slot /></button>',
        }),
      },
      mocks: {
        $client: {},
        $t: (key) => key,
        $bus: { $on: vi.fn(), $off: vi.fn() },
        $registry: {
          get: () => ({ updateWritePermissionsForField: vi.fn() }),
        },
      },
    },
  })
}

describe('FieldPermissionsModal', () => {
  let get
  let update

  beforeEach(() => {
    get = vi.fn().mockResolvedValue({
      data: { role: 'EDITOR', allow_in_forms: true, subjects: [] },
    })
    update = vi.fn().mockResolvedValue({
      data: {
        role: 'CUSTOM',
        allow_in_forms: false,
        can_write_values: true,
        subjects: [
          {
            subject_id: 2,
            subject_type: 'auth.User',
            subject: { id: 2, first_name: 'Alan Turing' },
          },
        ],
      },
    })
    FieldPermissionService.mockReturnValue({ get, update })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  test('shows the selector inline before persisting the custom permission', async () => {
    const wrapper = await mountComponent()
    await flushPromises()

    await wrapper.find('.choose-custom').trigger('click')

    expect(wrapper.find('.subjects-editor').exists()).toBe(true)
    expect(wrapper.find('.forms-toggle').element.nextElementSibling).toBe(
      wrapper.find('.subjects-editor').element
    )
    expect(update).not.toHaveBeenCalled()

    const saveButton = wrapper
      .findAll('button')
      .find((button) => button.text() === 'action.save')
    await saveButton.trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(10, {
      role: 'CUSTOM',
      allowInForms: false,
      subjects: [{ subject_id: 2, subject_type: 'auth.User' }],
    })
    expect(wrapper.find('.modal-stub').exists()).toBe(false)
  })
})
