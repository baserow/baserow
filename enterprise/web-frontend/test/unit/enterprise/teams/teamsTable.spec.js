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

describe('TeamsTable role assignments', () => {
  test('expands the teams with roles into their roles', async () => {
    const team = { id: 3, name: 'Sales', role_assignment_count: 2 }
    // Renders what the table asks of the expandable rows, for one team with
    // roles and one without.
    const ExpandingCrudTableStub = {
      name: 'CrudTable',
      props: ['rowExpandable', 'expandColumnKey'],
      data: () => ({ rows: [team, { id: 4, role_assignment_count: 0 }] }),
      template: `
        <div>
          <div class="expand-column">{{ expandColumnKey }}</div>
          <div class="expandable">{{ rows.map(rowExpandable).join(',') }}</div>
          <div class="toggle">
            <slot name="row-expansion-toggle" :row="rows[0]" />
          </div>
          <table>
            <slot
              name="expanded-row"
              :row="rows[0]"
              :columns="[]"
              :update-row="() => {}"
            />
          </table>
        </div>
      `,
    }
    const wrapper = await mountSuspended(TeamsTable, {
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
      global: {
        stubs: {
          CrudTable: ExpandingCrudTableStub,
          CreateTeamModal: true,
          UpdateTeamModal: true,
          SubjectRoleAssignmentRows: {
            props: ['subjectType', 'subjectId', 'roleColumnKey', 'readOnly'],
            template:
              '<tr class="rows"><td>{{ subjectType }}:{{ subjectId }}:{{ roleColumnKey }}:{{ readOnly }}</td></tr>',
          },
        },
      },
    })

    expect(wrapper.get('.expand-column').text()).toBe('default_role')
    expect(wrapper.get('.expandable').text()).toBe('true,false')
    expect(wrapper.get('.toggle').text()).toBe('+2')
    expect(wrapper.get('.rows').text()).toBe(
      'baserow_enterprise.Team:3:default_role:false'
    )
  })
})
