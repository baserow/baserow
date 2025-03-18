<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.values.name.$error"
      small-label
      :label="$t('snapshotsModal.createLabel')"
      required
    >
      <slot name="input">
        <FormInput
          ref="name"
          v-model="v$.values.name.$model"
          size="large"
          :error="fieldHasErrors('name')"
          class="snapshots-modal__name-input"
          @blur="v$.values.name.$touch"
        />
      </slot>

      <template #error>
        {{ v$.values.name.$errors[0]?.$message }}
      </template>

      <template #after-input>
        <slot></slot>
      </template>
    </FormGroup>
    <slot name="cancel-action"></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import moment from '@baserow/modules/core/moment'

export default {
  name: 'CreateSnapshotForm',
  mixins: [form],
  props: {
    applicationName: {
      type: String,
      required: true,
    },
    snapshots: {
      type: Array,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: this.getDefaultName(),
      },
    }
  },

  methods: {
    getDefaultName() {
      const datetime = moment().format('YYYY-MM-DD HH:mm:ss')
      return `${this.applicationName} - ${datetime}`
    },
    resetName() {
      this.values.name = this.getDefaultName()
    },
    mustHaveUniqueName(param) {
      const names = this.snapshots.map((snapshot) => snapshot.name)
      return !names.includes(param)
    },
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          mustHaveUniqueName: helpers.withMessage(
            this.$t('snapshotsModal.nameAlreadyExists'),
            this.mustHaveUniqueName
          ),
        },
      },
    }
  },
}
</script>
