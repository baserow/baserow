<template>
  <Modal
    ref="modal"
    :left-sidebar="isUpdate"
    :left-sidebar-scrollable="isUpdate"
    :content-padding="
      selectedSetting == null ? true : selectedSetting.componentPadding
    "
  >
    <template v-if="isUpdate" #sidebar>
      <div class="modal-sidebar__title">
        {{ $t('agents.updateTitle') }}
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="setting in registeredSettings" :key="setting.getType()">
          <a
            class="modal-sidebar__nav-link"
            :class="{
              active:
                selectedSetting &&
                setting.getType() === selectedSetting.getType(),
            }"
            @click="selectSetting(setting)"
          >
            <i class="modal-sidebar__nav-icon" :class="setting.icon"></i>
            {{ setting.name }}
          </a>
        </li>
      </ul>
    </template>
    <template #content>
      <h2 class="box__title">
        {{ isUpdate ? selectedSetting?.name : $t('agents.createTitle') }}
      </h2>
      <Error :error="error" />
      <form @submit.prevent="submit">
        <component
          :is="setting.component"
          v-for="setting in displayedSettings"
          :key="setting.getType()"
          :ref="`setting_${setting.getType()}`"
          v-model="values"
          :workspace="workspace"
          :agent="agent"
          :roles="roles"
        />
        <div class="actions">
          <Button type="secondary" @click="hide">{{
            $t('action.cancel')
          }}</Button>
          <Button type="primary" :loading="loading" :disabled="!values.name">
            {{ isUpdate ? $t('agents.save') : $t('agents.create') }}
          </Button>
        </div>
      </form>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'

export default {
  name: 'ManageAgentModal',
  mixins: [modal, error],
  props: {
    workspace: { type: Object, required: true },
    agent: { type: Object, default: null },
  },
  emits: ['saved'],
  data() {
    return {
      loading: false,
      values: { name: '', role_uid: 'MEMBER' },
      selectedSetting: null,
    }
  },
  computed: {
    isUpdate() {
      return !!this.agent?.id
    },
    roles() {
      return (this.workspace._?.roles || []).filter(
        (role) =>
          role.isVisible &&
          (!Array.isArray(role.allowedSubjectTypes) ||
            role.allowedSubjectTypes.includes('core.Agent'))
      )
    },
    registeredSettings() {
      return this.$registry
        .getOrderedList('agentSettings')
        .filter(
          (setting) => setting.isActive(this.workspace) && setting.component
        )
    },
    displayedSettings() {
      return this.isUpdate
        ? [this.selectedSetting].filter(Boolean)
        : this.createSettings
    },
    createSettings() {
      return this.registeredSettings.filter((setting) => setting.showInCreate)
    },
  },
  methods: {
    /** Initialize every registered setting so switching sidebar pages is lossless. */
    show(...args) {
      const defaultRole = this.roles.some((role) => role.uid === 'NO_ACCESS')
        ? 'NO_ACCESS'
        : 'MEMBER'
      this.values = {}
      for (const setting of this.registeredSettings) {
        Object.assign(
          this.values,
          setting.getInitialValues(this.agent, {
            workspace: this.workspace,
            defaultRole,
          })
        )
      }
      this.selectedSetting = this.registeredSettings[0] || null
      modal.methods.show.call(this, ...args)
      this.focusSelectedSetting()
    },
    selectSetting(setting) {
      this.selectedSetting = setting
      this.hideError()
      this.focusSelectedSetting()
    },
    focusSelectedSetting() {
      this.$nextTick(() => {
        const setting = this.selectedSetting || this.registeredSettings[0]
        this.$refs[`setting_${setting?.getType()}`]?.[0]?.focus?.()
      })
    },
    /** Submit only the active page while editing, or every page when creating. */
    async submit() {
      this.loading = true
      this.hideError()
      try {
        const values = this.isUpdate
          ? this.selectedSetting.getSubmitValues(this.values)
          : Object.assign(
              {},
              ...this.createSettings.map((setting) =>
                setting.getSubmitValues(this.values)
              )
            )
        const data = this.isUpdate
          ? await this.$store.dispatch('agent/update', {
              agentId: this.agent.id,
              values,
            })
          : await this.$store.dispatch('agent/create', {
              workspaceId: this.workspace.id,
              values,
            })
        this.$emit('saved', data)
        this.hide()
      } catch (error) {
        this.handleError(error, 'agent')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
