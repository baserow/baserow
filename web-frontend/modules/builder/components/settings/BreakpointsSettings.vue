<template>
  <div>
    <h2 class="box__title">{{ $t('breakpointSettings.titleOverview') }}</h2>
    <Error :error="error" />
    <Alert v-if="success" type="success">
      <template #title>{{ $t('breakpointSettings.updatedTitle') }}</template>
      <p>{{ $t('breakpointSettings.updatedDescription') }}</p>
    </Alert>
    <BuilderBreakpointsSettingsForm
      ref="breakpointsForm"
      :default-values="breakpoints"
      @submitted="updateBreakpoints"
      @values-changed="onValuesChanged"
    />
    <div class="actions actions--right">
      <Button
        :loading="actionInProgress"
        :disabled="actionInProgress || invalidForm"
        size="large"
        @click="submit"
      >
        {{ $t('action.save') }}
      </Button>
    </div>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import BuilderBreakpointsSettingsForm from '@baserow/modules/builder/components/form/BuilderBreakpointsSettingsForm'
import { getBuilderBreakpoints } from '@baserow/modules/builder/utils/breakpoints'

export default {
  name: 'BreakpointsSettings',
  components: { BuilderBreakpointsSettingsForm },
  mixins: [error],
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      actionInProgress: false,
      invalidForm: true,
      success: false,
    }
  },
  computed: {
    breakpoints() {
      const { mobile, tablet } = getBuilderBreakpoints(this.builder)
      return {
        breakpoints: {
          ...this.builder.breakpoints,
          mobile,
          tablet,
        },
      }
    },
  },
  async mounted() {
    await this.$nextTick()
    this.onValuesChanged()
  },
  methods: {
    onValuesChanged() {
      this.success = false
      this.invalidForm = !this.$refs.breakpointsForm?.isFormValid()
    },
    submit() {
      if (this.actionInProgress || this.invalidForm) {
        return
      }

      this.$refs.breakpointsForm?.submit()
    },
    async updateBreakpoints(values) {
      if (this.actionInProgress) {
        return
      }

      this.hideError()
      this.success = false
      this.actionInProgress = true
      try {
        await this.$store.dispatch('application/update', {
          application: this.builder,
          values,
        })
        this.success = true
      } catch (error) {
        this.handleError(error)
      } finally {
        this.actionInProgress = false
      }
    },
  },
}
</script>
