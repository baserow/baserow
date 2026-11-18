<template>
  <FormGroup
    :label="$t('personalApplication.access')"
    small-label
    class="margin-bottom-2"
  >
    <Radio
      :name="groupName"
      :model-value="selected"
      value="collaborative"
      @update:model-value="select"
    >
      {{ $t('personalApplication.collaborative') }}
    </Radio>
    <div class="margin-bottom-1">
      {{ $t('personalApplication.workspaceRoles') }}
    </div>
    <Radio
      v-if="licensed"
      :name="groupName"
      :model-value="selected"
      value="personal"
      @update:model-value="select"
    >
      {{ $t('personalApplication.personal') }}
    </Radio>
    <Button
      v-else
      type="secondary"
      size="small"
      button-type="button"
      icon="iconoir-lock"
      @click="$refs.upgrade.show()"
    >
      {{ $t('personalApplication.personal') }}
    </Button>
    <div>{{ $t('personalApplication.initialAccess') }}</div>
    <PaidFeaturesModal
      v-if="!licensed"
      ref="upgrade"
      initial-selected-type="rbac"
      :workspace="workspace"
    />
  </FormGroup>
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
  },
  methods: {
    select(mode) {
      this.values = mode === 'personal' ? { access_policy: mode } : {}
    },
  },
}
</script>
