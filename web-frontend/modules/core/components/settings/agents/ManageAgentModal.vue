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
      <Alert v-if="success" type="success">
        <template #title>{{ $t('agents.saved') }}</template>
      </Alert>
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
          <Button type="secondary" @click.prevent="hide">{{
            isUpdate ? $t('action.close') : $t('action.cancel')
          }}</Button>
          <Button
            v-if="!isUpdate || hasSubmitFields"
            type="primary"
            :loading="loading"
            :disabled="loading || (isUpdate ? !hasChanges : !values.name)"
          >
            {{ isUpdate ? $t('agents.save') : $t('agents.create') }}
          </Button>
        </div>
      </form>
    </template>
  </Modal>
</template>

<script>
import _ from 'lodash'

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
      success: false,
      initialValues: {},
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
    hasSubmitFields() {
      return (
        Object.keys(this.selectedSetting?.getSubmitValues(this.values) || {})
          .length > 0
      )
    },
    changedValues() {
      const values = this.selectedSetting?.getSubmitValues(this.values) || {}
      return Object.fromEntries(
        Object.entries(values).filter(
          ([key, value]) => !_.isEqual(value, this.initialValues[key])
        )
      )
    },
    hasChanges() {
      return Object.keys(this.changedValues).length > 0
    },
    createSettings() {
      return this.registeredSettings.filter((setting) => setting.showInCreate)
    },
  },
  watch: {
    values: {
      deep: true,
      handler() {
        this.success = false
      },
    },
  },
  methods: {
    /** Initialize every registered setting so switching sidebar pages is lossless. */
    show(...args) {
      const defaultRole = this.roles.some(
        (role) => role.uid === 'NO_ACCESS' && !role.isDeactivated
      )
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
      this.initialValues = _.cloneDeep(this.values)
      this.success = false
      this.hideError()
      this.selectedSetting = this.registeredSettings[0] || null
      modal.methods.show.call(this, ...args)
      this.focusSelectedSetting()
    },
    selectSetting(setting) {
      if (this.loading) return
      this.success = false
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
      if (this.loading || (this.isUpdate && !this.hasChanges)) return
      this.loading = true
      this.success = false
      this.hideError()
      try {
        const values = this.isUpdate
          ? _.cloneDeep(this.changedValues)
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
        if (this.isUpdate) {
          // Only advance the saved page baseline; other pages keep their drafts.
          Object.assign(this.initialValues, _.cloneDeep(values))
          this.success = true
        } else {
          this.hide()
        }
      } catch (error) {
        this.handleError(error, 'agent')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
