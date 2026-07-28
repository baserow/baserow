import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import FieldPermissionSubjectsSelector from '@baserow_enterprise/components/fieldPermissions/FieldPermissionSubjectsSelector'
import FieldPermissionService from '@baserow_enterprise/services/fieldPermissions'

vi.mock('@baserow_enterprise/services/fieldPermissions', () => ({
  default: vi.fn(),
}))

const ButtonIconStub = defineComponent({
  name: 'ButtonIcon',
  props: ['disabled', 'icon'],
  template:
    '<button class="remove-subject" :disabled="disabled"><i v-if="icon" :class="icon"></i><slot /></button>',
})

const AvatarStub = defineComponent({
  name: 'Avatar',
  props: ['initials'],
  template: '<div class="avatar-stub">{{ initials }}</div>',
})

const simpleStub = (name) =>
  defineComponent({ name, template: '<div><slot /></div>' })

const selectedUser = {
  subject_id: 1,
  subject_type: 'auth.User',
  subject: {
    id: 1,
    first_name: 'Ada Lovelace',
    username: 'ada@example.com',
    email: 'ada@example.com',
  },
}

async function mountComponent() {
  return await mountSuspended(FieldPermissionSubjectsSelector, {
    props: {
      fieldId: 10,
      subjects: [selectedUser],
    },
    global: {
      stubs: {
        ButtonIcon: ButtonIconStub,
        Avatar: AvatarStub,
        Alert: simpleStub('Alert'),
      },
      mocks: {
        $client: {},
        $t: (key, params = {}) =>
          `${key}${params.subject ? `:${params.subject}` : ''}`,
      },
    },
  })
}

describe('FieldPermissionSubjectsSelector', () => {
  let fetchSubjectOptions

  beforeEach(() => {
    vi.useFakeTimers()
    fetchSubjectOptions = vi.fn().mockResolvedValue({
      data: {
        count: 2,
        results: [
          {
            subject_id: 2,
            subject_type: 'auth.User',
            name: 'Alan Turing',
            email: 'alan@example.com',
            subject_count: null,
          },
          {
            subject_id: 3,
            subject_type: 'baserow_enterprise.Team',
            name: 'Development team',
            email: null,
            subject_count: 4,
          },
        ],
      },
    })
    FieldPermissionService.mockReturnValue({ fetchSubjectOptions })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  test('loads the first page on open and renders collaborator-style options', async () => {
    const wrapper = await mountComponent()

    const sections = wrapper.findAll('.field-permission-subjects__section')
    expect(sections[0].find('.dropdown').exists()).toBe(true)
    expect(sections[1].text()).toContain('Ada Lovelace')
    expect(wrapper.text()).not.toContain('ada@example.com')
    expect(fetchSubjectOptions).not.toHaveBeenCalled()

    await wrapper.find('.dropdown__selected').trigger('click')
    await flushPromises()

    expect(fetchSubjectOptions).toHaveBeenCalledWith(10, {
      page: 1,
      size: 20,
      search: '',
      exclude_user_ids: '1',
      exclude_team_ids: '',
    })
    const options = wrapper.findAll(
      '.field-permission-subjects__dropdown-option'
    )
    expect(options).toHaveLength(2)
    expect(options[0].text()).toContain('Alan Turing')
    expect(options[0].text()).not.toContain('alan@example.com')
    expect(options[0].find('.avatar-stub').text()).toBe('AT')
    expect(options[1].find('.iconoir-group').exists()).toBe(true)

    expect(wrapper.find('.remove-subject .iconoir-cancel').exists()).toBe(true)
    expect(wrapper.find('.remove-subject .iconoir-bin').exists()).toBe(false)
    await wrapper.find('.remove-subject').trigger('click')
    expect(wrapper.text()).not.toContain('Ada Lovelace')
    expect(wrapper.emitted('selection-change').at(-1)).toEqual([0])
  })

  test('paginates server search and adds the selected dropdown result', async () => {
    const wrapper = await mountComponent()

    await wrapper.find('.dropdown__selected').trigger('click')
    await flushPromises()
    await wrapper.find('.select__search-input').setValue('al')
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()

    expect(fetchSubjectOptions).toHaveBeenCalledWith(10, {
      page: 1,
      size: 20,
      search: 'al',
      exclude_user_ids: '1',
      exclude_team_ids: '',
    })
    expect(wrapper.find('.dropdown__items').text()).toContain('Alan Turing')
    expect(wrapper.find('.dropdown__items').text()).toContain(
      'Development team'
    )

    await wrapper.findAll('.select__item-link')[0].trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.field-permission-subjects__item')).toHaveLength(2)
    expect(wrapper.text()).toContain('Alan Turing')
    expect(wrapper.find('.dropdown__items').classes()).toContain('hidden')
    expect(wrapper.emitted('selection-change').at(-1)).toEqual([2])
  })
})
