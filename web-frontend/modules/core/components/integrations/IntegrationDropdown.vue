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
    <DropdownItem
      v-for="integrationItem in integrations"
      :key="integrationItem.id"
      :name="integrationItem.name"
      :value="integrationItem.id"
      :image="integrationType?.image"
    />
    <template #emptyState>
      {{ $t('integrationDropdown.noIntegrations') }}
    </template>
    <template #footer>
      <button
        v-if="allowEditing && selectedIntegration"
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
        create
        @created="select($event.id)"
      />
      <IntegrationCreateEditModal
        v-if="allowEditing && selectedIntegration"
        ref="IntegrationEditModal"
        :application="application"
        :integration="selectedIntegration"
      />
    </template>
  </Dropdown>
</template>

<script>
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'

export default {
  name: 'IntegrationDropdown',
  components: { IntegrationCreateEditModal },
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
     * If there is only one integration available, it will be
     * automatically selected if this property is true.
     */
    autoSelectFirst: {
      type: Boolean,
      required: false,
      default: false,
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
    selectedIntegration() {
      return this.integrations.find(({ id }) => id === this.currentValue)
    },
  },
  watch: {
    integrations: {
      handler(newValue) {
        if (
          this.autoSelectFirst &&
          newValue.length === 1 &&
          this.currentValue === null
        ) {
          this.$nextTick(() => {
            this.select(newValue[0].id)
          })
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
