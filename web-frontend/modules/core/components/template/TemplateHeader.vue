<template>
  <div class="templates__header">
    <template v-if="template !== null">
      <div class="templates__icon">
        <i :class="template.icon"></i>
      </div>
      <div class="templates__header-title">
        {{ template.name }}
        <small v-if="category !== null">{{ category.name }}</small>
      </div>
      <div class="templates__install">
        <Dropdown
          v-if="workspace === null"
          v-model="selectedWorkspaceId"
          class="templates__install-workspace"
          :placeholder="$t('templateHeader.selectWorkspace')"
          :fixed-items="true"
        >
          <DropdownItem
            v-for="workspaceItem in workspaces"
            :key="workspaceItem.id"
            :name="workspaceItem.name"
            :value="workspaceItem.id"
          ></DropdownItem>
        </Dropdown>
        <Button
          :loading="installing"
          :disabled="installing || targetWorkspaceId === null"
          @click="install(template)"
          >{{ $t('templateHeader.use') }}</Button
        >
      </div>
    </template>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import TemplateService from '@baserow/modules/core/services/template'

export default {
  name: 'TemplateHeader',
  props: {
    // When no workspace is provided, a dropdown is shown so that the user can choose
    // the workspace to install the template into.
    workspace: {
      type: Object,
      required: false,
      default: null,
    },
    template: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
    category: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
  },
  emits: ['installed'],
  data() {
    return {
      job: null,
      installing: false,
      selectedWorkspaceId: null,
    }
  },
  computed: {
    // Deliberately not filtered by the `workspace.create_application` permission
    // because the granular permissions are only fetched for the selected workspace,
    // and fetching them for all workspaces is too expensive. The backend rejects the
    // install if the user doesn't have permission.
    workspaces() {
      return this.$store.getters['workspace/getAll']
    },
    targetWorkspaceId() {
      return this.workspace !== null
        ? this.workspace.id
        : this.selectedWorkspaceId
    },
  },
  watch: {
    'job.state'(newState) {
      if (['finished', 'failed'].includes(newState)) {
        this.installing = false
      }
    },
  },
  methods: {
    async install(template) {
      this.installing = true
      const workspaceId = this.targetWorkspaceId

      try {
        const { data: job } = await TemplateService(this.$client).asyncInstall(
          workspaceId,
          template.id
        )
        this.job = job
        this.$store.dispatch('job/create', job)
        this.$emit('installed')

        // If the user explicitly chose the workspace via the dropdown, they're not
        // on a page of that workspace, so redirect to its homepage where they can
        // see the template being installed.
        if (this.workspace === null) {
          await this.$router.push({
            name: 'workspace',
            params: { workspaceId },
          })
        }
      } catch (error) {
        notifyIf(error, 'template')
        this.installing = false
      }
    },
  },
}
</script>
