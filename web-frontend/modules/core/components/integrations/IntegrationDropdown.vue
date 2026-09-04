<template>
  <Dropdown
    :value="value"
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
    @input="$emit('input', $event)"
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
        v-if="selectedIntegration"
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
      <!--
        An export strips a credential, so an imported integration arrives
        named but unusable. Without this there is no way to repair it from a
        database, which has no integration settings page of its own.
      -->
      <IntegrationCreateEditModal
        v-if="selectedIntegration"
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
     * What the parent has selected. A `v-model` binding sends `modelValue`,
     * which falls through to the dropdown below rather than arriving as a
     * prop here, so it is read off the attributes.
     */
    currentValue() {
      const bound = this.$attrs.modelValue
      return bound === undefined ? this.value : bound
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
          this.value === null
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
     * Chosen somewhere other than the list below, which reaches the parent on
     * its own. A parent binds this with `v-model` and so listens for
     * `update:modelValue`; `input` is kept for anything still written the
     * Vue 2 way.
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
