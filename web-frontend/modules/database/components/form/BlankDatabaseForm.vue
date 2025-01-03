<template>
  <form @submit.prevent="submit">
    <FormGroup :error="fieldHasErrors('name')" required small-label>
      <template #label>
        <i class="iconoir-text"></i>
        {{ $t('applicationForm.nameLabel') }}
      </template>

      <FormInput
        ref="name"
        v-model="values.name"
        :error="fieldHasErrors('name')"
        type="text"
        size="large"
        :placeholder="$t('applicationForm.namePlaceholder')"
        @focus.once="$event.target.select()"
        @blur="$v.values.name.$touch()"
      ></FormInput>

      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { required } from 'vuelidate/lib/validators'

export default {
  name: 'BlankDatabaseForm',
  mixins: [form],
  props: {
    defaultName: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      values: {
        name: this.defaultName,
      },
    }
  },
  computed: {
    databaseApplicationType() {
      return this.$registry.get('application', 'database')
    },
  },
  mounted() {
    this.$refs.name.focus()
  },
  validations: {
    values: {
      name: { required },
    },
  },
}
</script>
