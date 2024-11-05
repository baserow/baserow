<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('name')"
      small-label
      :label="$t('snapshotsModal.createLabel')"
      required
    >
      <slot name="input">
        <FormInput
          ref="name"
          v-model="values.name"
          size="large"
          :error="fieldHasErrors('name')"
          class="snapshots-modal__name-input"
          @blur="v$.values.name.$touch()"
        />
      </slot>

      <template #after-input>
        <slot></slot>
      </template>
    </FormGroup>
    <slot name="cancel-action"></slot>
  </form>
</template>

<script>
import { required } from '@vuelidate/validators'
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
          required,
          mustHaveUniqueName: this.mustHaveUniqueName,
        },
      },
    }
  },
}
</script>
