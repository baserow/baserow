<template>
  <Dropdown
    :value="currentValue"
    fixed-items
    class="integration-dropdown"
    :size="size"
    :disabled="disabled || !integrationType"
    :placeholder="
      !integrationType
        ? $t('integrationDropdown.selectTypeFirst')
        : placeholder || $t('integrationDropdown.integrationPlaceholder')
    "
    show-footer
    @input="select($event)"
  >
    <template v-if="workspaceIntegrations.length">
      <DropdownSection
        v-if="applicationIntegrations.length"
        :title="$t('integrationDropdown.applicationIntegrations')"
      >
        <DropdownItem
          v-for="integrationItem in applicationIntegrations"
          :key="integrationItem.id"
          :name="integrationItem.name"
          :value="integrationItem.id"
          :image="integrationType?.image"
        />
      </DropdownSection>
      <DropdownSection :title="$t('integrationDropdown.workspaceIntegrations')">
        <DropdownItem
          v-for="integrationItem in workspaceIntegrations"
          :key="integrationItem.id"
          :name="integrationItem.name"
          :value="integrationItem.id"
          :image="integrationType?.image"
          :description="integrationType?.getWorkspaceHint(integrationItem)"
        />
      </DropdownSection>
    </template>
    <template v-else>
      <DropdownItem
        v-for="integrationItem in integrations"
        :key="integrationItem.id"
        :name="integrationItem.name"
        :value="integrationItem.id"
        :image="integrationType?.image"
      />
    </template>
    <template #emptyState>
      {{ $t('integrationDropdown.noIntegrations') }}
    </template>
    <template #footer>
      <button
        v-if="editableIntegration"
        type="button"
        class="select__footer-button"
        @click="$refs.IntegrationEditModal.show()"
      >
        <i class="iconoir-edit-pencil"></i>
        {{ $t('integrationDropdown.editIntegration') }}
      </button>
      <button
        type="button"
        class="select__footer-button"
        @click="$refs.IntegrationCreateEditModal.show()"
      >
        <i class="iconoir-plus"></i>
        {{ $t('integrationDropdown.addIntegration') }}
      </button>
      <IntegrationCreateEditModal
        v-if="integrationType"
        ref="IntegrationCreateEditModal"
        :application="application"
        :integration-type="integrationType"
        :service-types="serviceTypes"
        create
        @created="select($event.id)"
      />
      <IntegrationCreateEditModal
        v-if="editableIntegration"
        ref="IntegrationEditModal"
        :application="application"
        :integration="editableIntegration"
        :service-types="serviceTypes"
      />
    </template>
  </Dropdown>
</template>

<script>
import { getDefaultIntegration } from '@baserow/modules/core/utils/integration'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import DropdownSection from '@baserow/modules/core/components/DropdownSection'

export default {
  name: 'IntegrationDropdown',
  components: { IntegrationCreateEditModal, DropdownSection },
  props: {
    value: {
      type: Number,
      required: false,
      default: null,
    },
    /**
     * What a `v-model` parent binds. Declared rather than read out of
     * `$attrs`, so this component passes one resolved value down instead of
     * relying on the attribute also falling through to the dropdown below.
     */
    modelValue: {
      type: Number,
      required: false,
      default: undefined,
    },
    application: {
      type: Object,
      required: true,
    },
    integrationType: {
      type: Object,
      required: false,
      default: null,
    },
    /**
     * The integrations that can be chosen, usually what the
     * `integration/getUsableIntegrations` getter returns: the application's own
     * and the workspace ones, which are listed apart.
     */
    integrations: {
      type: Array,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    size: {
      type: String,
      required: false,
      default: 'regular',
    },
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * Whether the selected integration can be edited from here. An imported
     * integration arrives named but unusable, and a database has no
     * integration settings page to repair it from. Everything else does, so
     * they keep the one route.
     */
    allowEditing: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Select an unambiguous default, preferring the application's own
     * integrations. Callers opt in for creation forms.
     */
    autoSelectFirst: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The service types the integration is picked for. An integration that
     * connects an account by signing in asks for what they need.
     */
    serviceTypes: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    /**
     * What the parent has selected, whichever way it bound it: `v-model`
     * sends `modelValue`, older callers send `value`.
     */
    currentValue() {
      return this.modelValue === undefined ? this.value : this.modelValue
    },
    /**
     * The integrations of another application, which can only be the shared
     * application of the workspace.
     */
    workspaceIntegrations() {
      return this.integrations.filter(
        ({ application_id: applicationId }) =>
          applicationId !== this.application.id
      )
    },
    applicationIntegrations() {
      return this.integrations.filter(
        ({ application_id: applicationId }) =>
          applicationId === this.application.id
      )
    },
    /**
     * The selected integration, when it can be edited from here. A workspace
     * integration can't: it's changed for every application from the
     * Integrations page of the workspace settings.
     */
    editableIntegration() {
      if (!this.allowEditing) {
        return null
      }
      return (
        this.applicationIntegrations.find(
          ({ id }) => id === this.currentValue
        ) || null
      )
    },
  },
  watch: {
    integrations: {
      handler(newValue) {
        if (this.autoSelectFirst && this.currentValue === null) {
          const integration = getDefaultIntegration(newValue, this.application)
          if (integration) {
            this.$nextTick(() => {
              if (this.currentValue === null) {
                this.select(integration.id)
              }
            })
          }
        }
      },
      immediate: true,
    },
  },
  methods: {
    /**
     * Every way of choosing one goes through here. Declaring
     * `update:modelValue` keeps a parent's listener out of `$attrs`, so it no
     * longer falls through to the dropdown below and this is the only thing
     * that reaches a `v-model` parent. `input` is kept for anything still
     * bound the Vue 2 way.
     *
     * @param {Number|null} integrationId The integration that was chosen.
     */
    select(integrationId) {
      this.$emit('input', integrationId)
      this.$emit('update:modelValue', integrationId)
    },
  },
}
</script>
