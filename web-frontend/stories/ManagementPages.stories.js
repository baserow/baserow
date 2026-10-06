import { computed, ref } from 'vue'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import TwoFactorAuthField from '@baserow/modules/core/components/crudTable/fields/TwoFactorAuthField'
import ManagementNameField from '@baserow/modules/core/components/settings/ManagementNameField'
import RoleSelectorButton from '@baserow/modules/core/components/settings/RoleSelectorButton'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import ManageAgentModal from '@baserow/modules/core/components/settings/agents/ManageAgentModal'
import AgentLastActiveField from '@baserow/modules/core/components/settings/agents/AgentLastActiveField'
import {
  GeneralAgentSettingsType,
  McpServerAgentSettingsType,
} from '@baserow/modules/core/agentSettingsTypes'
import AgentTeamsFormField from '@baserow_enterprise/components/agents/AgentTeamsFormField'
import UserTeamsField from '@baserow_enterprise/components/crudTable/fields/UserTeamsField'
import SubjectSampleField from '@baserow_enterprise/components/crudTable/fields/SubjectSampleField'
import Button from '@baserow/modules/core/components/Button'
import Tabs from '@baserow/modules/core/components/Tabs'
import Tab from '@baserow/modules/core/components/Tab'
import Context from '@baserow/modules/core/components/Context'

const teams = [
  { id: 1, name: 'Management' },
  { id: 2, name: 'Front-End Team' },
  { id: 3, name: 'Back-End Team' },
  { id: 4, name: 'Marketing Team' },
  { id: 5, name: 'Support Team' },
]
const roles = [
  { uid: 'ADMIN', name: 'Admin' },
  { uid: 'BUILDER', name: 'Builder' },
  { uid: 'EDITOR', name: 'Editor' },
  { uid: 'VIEWER', name: 'Viewer' },
  { uid: 'NO_ACCESS', name: 'No access' },
].map((role) => ({ ...role, isVisible: true, isDeactivated: false }))
const workspace = { id: 1, name: 'Widelab', _: { roles } }

// Keep previews independent of API state; production controls handle rendering.
const TeamsFormPreview = {
  ...AgentTeamsFormField,
  data: () => ({ loading: false, loadError: false, teams }),
  mounted() {},
}
const AgentModalPreview = {
  ...ManageAgentModal,
  computed: {
    ...ManageAgentModal.computed,
    registeredSettings() {
      const context = { app: { $i18n: { t: this.$t } } }
      return [
        new GeneralAgentSettingsType(context),
        {
          name: 'Teams',
          icon: 'iconoir-community',
          component: TeamsFormPreview,
          componentPadding: true,
          showInCreate: true,
          getType: () => 'teams',
          getInitialValues: (agent) => ({
            team_ids: (agent?.teams || []).map((team) => team.id),
          }),
          getSubmitValues: ({ team_ids: teamIds }) => ({ team_ids: teamIds }),
        },
        new McpServerAgentSettingsType(context),
      ]
    },
  },
  methods: {
    ...ManageAgentModal.methods,
    async submit() {
      Object.assign(
        this.initialValues,
        JSON.parse(JSON.stringify(this.isUpdate ? this.changedValues : this.values))
      )
      this.success = true
      if (!this.isUpdate) this.hide()
    },
  },
}

const RolePreviewField = {
  components: { RoleSelectorButton, EditRoleContext },
  props: ['row'],
  emits: ['row-update'],
  setup: () => ({ roles, workspace }),
  template: `<div>
    <RoleSelectorButton :role-uid="row.role" :role-name="roles.find(role => role.uid === row.role)?.name || row.role"
      :read-only="row.user_id === 1" @click="$refs.menu.toggle($event.currentTarget)" />
    <EditRoleContext ref="menu" :subject="row" :roles="roles" :workspace="workspace" role-value-column="role"
      @update-role="$emit('row-update', { ...row, role: $event.uid })" />
  </div>`,
}
const members = [
  {
    id: 1,
    user_id: 1,
    name: 'Michal Roszyk',
    email: 'michal@example.com',
    role: 'ADMIN',
    teams: [teams[0]],
    highest_role: 'Admin',
    two_factor_auth: { is_enabled: true },
  },
  {
    id: 2,
    user_id: 2,
    name: 'Arlene McCoy',
    email: 'arlene@example.com',
    role: 'EDITOR',
    teams: [teams[1], teams[2], teams[3]],
    highest_role: 'Builder',
    two_factor_auth: { is_enabled: false },
  },
  {
    id: 3,
    user_id: 3,
    name: 'Marvin McKinney',
    email: 'marvin@example.com',
    role: 'VIEWER',
    teams: [],
    highest_role: 'Viewer',
    two_factor_auth: { is_enabled: true },
  },
]
const agents = [
  {
    id: 1,
    name: 'Weekly Report Writer',
    role: 'EDITOR',
    role_uid: 'EDITOR',
    last_active: '2026-10-05T12:00:00Z',
    teams: [teams[1]],
  },
  {
    id: 2,
    name: 'Data Sync Agent',
    role: 'VIEWER',
    role_uid: 'VIEWER',
    last_active: null,
    teams: [],
  },
]
const pages = ['Members', 'Invites', 'Teams', 'Agents']

function columnsFor(page) {
  const name = new CrudTableColumn(
    'name',
    'Name',
    ManagementNameField,
    true,
    true,
    false,
    page === 'Agents'
      ? { icon: 'baserow-icon-agent', color: 'purple' }
      : page === 'Teams'
        ? { icon: 'iconoir-community', color: 'neutral' }
        : { userId: 1 }
  )
  const email = new CrudTableColumn('email', 'Email', SimpleField, true)
  const role = new CrudTableColumn('role', 'Default role', RolePreviewField)
  const team = new CrudTableColumn('teams', 'Teams', UserTeamsField)
  const more = new CrudTableColumn('more', '', MoreField, false, false, true)
  if (page === 'Agents')
    return [
      name,
      new CrudTableColumn(
        'last_active',
        'Last active',
        AgentLastActiveField,
        true
      ),
      role,
      team,
      more,
    ]
  if (page === 'Invites') return [email, role, more]
  if (page === 'Teams')
    return [
      name,
      role,
      new CrudTableColumn('subject_sample', 'Members', SubjectSampleField),
      more,
    ]
  return [
    name,
    email,
    role,
    team,
    new CrudTableColumn('highest_role', 'Highest role', SimpleField),
    new CrudTableColumn('two_factor_auth', '2FA', TwoFactorAuthField),
    more,
  ]
}

const renderPage =
  (initialPage = 'Members', empty = false, width = '100%') =>
  () => ({
    components: { CrudTable, Tabs, Tab, Button, Context, AgentModalPreview },
    setup() {
      const selected = ref(pages.indexOf(initialPage))
      const page = computed(() => pages[selected.value])
      const columns = computed(() => columnsFor(page.value))
      const action = computed(() =>
        page.value === 'Agents'
          ? 'Create agent'
          : page.value === 'Teams'
            ? 'Create team'
            : 'Invite members'
      )
      const service = computed(() => {
        const allRows = empty
          ? []
          : page.value === 'Agents'
            ? agents
            : page.value === 'Teams'
              ? teams.map((team) => ({
                  ...team,
                  role: 'EDITOR',
                  subject_count: 2,
                  subject_sample: [
                    { subject_type: 'auth.User', subject_label: 'Alex Morgan' },
                    {
                      subject_type: 'core.Agent',
                      subject_label: 'Weekly Report Writer',
                    },
                  ],
                }))
              : members
        return {
          options: { isPaginated: false, baseUrl: '/storybook/management/' },
          async fetch(_url, _page, search, sorts) {
            const rows = allRows.filter((row) =>
              `${row.name} ${row.email || ''}`
                .toLowerCase()
                .includes((search || '').toLowerCase())
            )
            rows.sort((a, b) => {
              for (const { key, direction } of sorts) {
                const result = String(a[key] || '').localeCompare(
                  String(b[key] || '')
                )
                if (result) return direction === 'asc' ? result : -result
              }
              return 0
            })
            return { data: rows }
          },
        }
      })
      const emptyPrefix = computed(() =>
        page.value === 'Agents'
          ? 'agents'
          : page.value === 'Teams'
            ? 'teamsTable'
            : page.value === 'Invites'
              ? 'membersSettings.invitesTable'
              : 'membersSettings.membersTable'
      )
      const context = ref(null)
      const focused = ref(null)
      const openContext = ({ row, target }) => {
        focused.value = row
        context.value.toggle(target)
      }
      return {
        pages,
        selected,
        page,
        columns,
        action,
        service,
        width,
        workspace,
        emptyPrefix,
        context,
        focused,
        openContext,
      }
    },
    template: `<div :style="{ position: 'relative', height: '700px', width, maxWidth: '100%' }" class="management-pages">
    <Tabs :selected-index="selected" full-height large-offset @update:selected-index="selected = $event">
      <Tab v-for="name in pages" :key="name" :title="name" :badge="name === 'Agents' ? 'New' : null">
        <CrudTable :key="page" :service="service" :columns="columns" row-id-key="id" :search-placeholder="'Search ' + page.toLowerCase()" @row-context="openContext">
          <template #title="{ count }">{{ count }} {{ page.toLowerCase() }} in Widelab</template>
          <template #primary-action><Button icon="iconoir-plus" @click="page === 'Agents' && $refs.create.show()">{{ action }}</Button></template>
          <template #empty><div class="placeholder"><div class="placeholder__icon"><i :class="page === 'Agents' ? 'baserow-icon-agent' : 'iconoir-group'" /></div><h2 class="placeholder__header">{{ $t(emptyPrefix + '.emptyTitle') }}</h2><p class="placeholder__content">{{ $t(emptyPrefix + '.emptyDescription') }}</p></div></template>
        </CrudTable>
      </Tab>
    </Tabs>
    <Context ref="context"><ul class="context__menu"><li class="context__menu-item"><a class="context__menu-item-link" @click="context.hide(); page === 'Agents' && $refs.edit.show()">{{ page === 'Agents' ? 'Edit agent' : 'Manage ' + (focused?.name || focused?.email) }}</a></li></ul></Context>
    <AgentModalPreview ref="create" :workspace="workspace" />
    <AgentModalPreview v-if="focused && page === 'Agents'" ref="edit" :workspace="workspace" :agent="focused" />
  </div>`,
  })

export default {
  title: 'Baserow/Management pages',
  parameters: {
    layout: 'fullscreen',
    design: {
      type: 'figma',
      url: 'https://www.figma.com/design/nINWJ2KPHfg2Aes5kleK4n?node-id=2199-48386',
    },
    docs: {
      description: {
        component:
          'Isolated UI previews with in-memory data. Role changes and agent dialogs are local to the story; invitation and team actions do not call the API.',
      },
    },
  },
}
export const Members = { render: renderPage('Members') }
export const Invites = { render: renderPage('Invites') }
export const Teams = { render: renderPage('Teams') }
export const Agents = { render: renderPage('Agents') }
export const EmptyAgents = { render: renderPage('Agents', true) }
export const NarrowMembers = { render: renderPage('Members', false, '390px') }

const renderModal = (editing) => () => ({
  components: { AgentModalPreview, Button },
  setup: () => ({ workspace, agent: editing ? agents[0] : null }),
  mounted() {
    this.$refs.modal.show()
  },
  template:
    '<div><Button @click="$refs.modal.show()">Open agent dialog</Button><AgentModalPreview ref="modal" :workspace="workspace" :agent="agent" /></div>',
})
export const CreateAgent = { render: renderModal(false) }
export const EditAgent = { render: renderModal(true) }
