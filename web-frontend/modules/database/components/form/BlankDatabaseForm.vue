<template>
  <form @submit.prevent="submit">
    <FormGroup :error="fieldHasErrors('name')" required small-label>
      <template #label>
        <i class="iconoir-text"></i>
        {{ $t('applicationForm.nameLabel') }}
      </template>

      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        :error="fieldHasErrors('name')"
        type="text"
        size="large"
        :placeholder="$t('applicationForm.namePlaceholder')"
        @focus.once="$event.target.select()"
        @blur="v$.values.name.$touch"
      ></FormInput>

      <template #error>
        {{ v$.values.name.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <div class="actions">
      <div class="align-right">
        <Button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="loading"
        >
          {{ $t('action.add') }}
          {{ databaseApplicationType.getName() | lowercase }}
        </Button>
      </div>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { required, helpers } from '@vuelidate/validators'

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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
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
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
