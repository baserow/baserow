<template>
  <fieldset class="application-access">
    <legend class="control__label control__label--small">
      {{ $t('personalApplication.access') }}
    </legend>
    <div class="application-access__options">
      <template v-for="option in options" :key="option.value">
        <button
          v-if="option.locked"
          type="button"
          class="application-access__option"
          aria-haspopup="dialog"
          :title="$t('personalApplication.unlock')"
          :aria-label="$t('personalApplication.unlock')"
          :aria-describedby="groupName + '-' + option.value"
          @click="$refs.upgrade.show()"
        >
          <i class="iconoir-lock" aria-hidden="true"></i>
          <span class="application-access__label">{{ option.label }}</span>
          <span
            :id="groupName + '-' + option.value"
            class="application-access__description"
          >
            {{ option.description }}
          </span>
        </button>
        <label v-else class="application-access__option">
          <input
            type="radio"
            :name="groupName"
            :value="option.value"
            :checked="selected === option.value"
            :aria-label="option.label"
            :aria-describedby="groupName + '-' + option.value"
            @change="select(option.value)"
          />
          <span class="application-access__label">{{ option.label }}</span>
          <span
            :id="groupName + '-' + option.value"
            class="application-access__description"
          >
            {{ option.description }}
          </span>
        </label>
      </template>
    </div>
    <PaidFeaturesModal
      v-if="!licensed"
      ref="upgrade"
      initial-selected-type="rbac"
      :workspace="workspace"
    />
  </fieldset>
</template>

<script>
import { useId } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  components: { PaidFeaturesModal },
  mixins: [form],
  props: { workspace: { type: Object, required: true } },
  setup() {
    return { groupName: useId() }
  },
  data() {
    return { values: {} }
  },
  computed: {
    licensed() {
      return this.$hasFeature(EnterpriseFeatures.RBAC, this.workspace.id)
    },
    selected() {
      return this.values.access_policy || 'collaborative'
    },
    options() {
      return [
        {
          value: 'collaborative',
          label: this.$t('personalApplication.collaborative'),
          description: this.$t('personalApplication.workspaceRoles'),
        },
        {
          value: 'personal',
          label: this.$t('personalApplication.personal'),
          description: this.$t('personalApplication.initialAccess'),
          locked: !this.licensed,
        },
      ]
    },
  },
  methods: {
    select(mode) {
      this.values = mode === 'personal' ? { access_policy: mode } : {}
    },
  },
}
</script>
