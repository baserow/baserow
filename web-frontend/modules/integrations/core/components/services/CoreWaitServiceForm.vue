<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('coreWaitServiceForm.secondsLabel')"
      required
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('coreWaitServiceForm.secondsDescription', { max: maxSeconds }) }}
      </p>
      <InjectedFormulaInput
        v-model="values.seconds"
        :placeholder="$t('coreWaitServiceForm.secondsPlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'CoreWaitServiceForm',
  components: { InjectedFormulaInput },
  mixins: [form],
  data() {
    return {
      allowedValues: ['seconds'],
      values: {
        seconds: {},
      },
    }
  },
  computed: {
    /**
     * The longest wait a single node may be configured for. Enforced by the
     * backend from the same setting; shown here so the designer knows the
     * bound before the node fails on it.
     */
    maxSeconds() {
      return this.$config.public.automationWaitMaxSeconds
    },
  },
}
</script>
