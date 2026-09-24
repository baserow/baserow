import { mountSuspended } from '@nuxt/test-utils/runtime'
import { vi } from 'vitest'

import TeamsTable from '@baserow_enterprise/components/teams/TeamsTable'

const showContext = vi.fn()

const CrudTableStub = {
  name: 'CrudTable',
  emits: ['row-context'],
  template: `
    <div>
      <button
        class="more-button"
        @click="$emit('row-context', {
          row: { id: 1, name: 'Writers' },
          event: $event,
          target: $event.currentTarget,
        })"
      />
      <slot name="menus" :delete-row="() => {}" />
    </div>
  `,
}

const EditTeamContextStub = {
  name: 'EditTeamContext',
  methods: {
    show(...args) {
      showContext(...args)
    },
    toggle(...args) {
      showContext(...args)
    },
  },
  template: '<div />',
}

describe('TeamsTable', () => {
  test('aligns the edit context with the right edge of the more button', async () => {
    showContext.mockClear()
    const wrapper = await mountSuspended(TeamsTable, {
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
      global: {
        stubs: {
          CrudTable: CrudTableStub,
          EditTeamContext: EditTeamContextStub,
          CreateTeamModal: true,
          UpdateTeamModal: true,
        },
      },
    })
    const button = wrapper.find('.more-button')

    await button.trigger('click')

    expect(showContext).toHaveBeenCalledWith(
      button.element,
      'bottom',
      'right',
      4
    )
  })
})
