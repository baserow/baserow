import { shallowMount } from '@vue/test-utils'
import TrashEntry from '@baserow/modules/core/components/trash/TrashEntry'

describe('TrashEntry', () => {
  const trashEntry = {
    id: 1,
    user_who_trashed: 'Ada',
    trash_item_type: 'application',
    trash_item_id: 20,
    trashed_at: '2026-11-04T09:00:00Z',
    name: 'My automation',
    names: null,
    parent_name: null,
  }

  const mountEntry = (props = {}) =>
    shallowMount(TrashEntry, {
      props: { trashEntry, ...props },
      global: {
        mocks: {
          $t: (key, values) => (values ? `${key} ${values.type}` : key),
          $filters: { nameAbbreviation: () => 'A' },
        },
      },
    })

  it('names the type after the trash item type by default', () => {
    expect(mountEntry().vm.typeName).toBe('trashType.application')
  })

  it('names the type with the provided trash item type name', () => {
    const wrapper = mountEntry({ trashItemTypeName: 'automation' })

    expect(wrapper.vm.typeName).toBe('automation')
    expect(wrapper.find('.trash-entry__name').text()).toBe(
      'trashEntry.name automation'
    )
  })
})
