<template>
  <form @submit.prevent="submit">
    <FormGroup :error="fieldHasErrors('name')" required small-label>
      <template #label>
        <i class="iconoir-text"></i>
        {{ $t('applicationForm.nameLabel') }}
      </template>

      <FormInput
        ref="name"
        v-model="v$.name.$model"
        :error="fieldHasErrors('name')"
        type="text"
        size="large"
        :placeholder="$t('applicationForm.namePlaceholder')"
        @focus.once="$event.target.select()"
        @blur="v$.name.$touch"
      ></FormInput>

      <template #error>
        {{ $t('error.requiredField') }}
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
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import { required } from '@vuelidate/validators'

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
      values: null,
      v$: null,
    }
  },
  computed: {
    databaseApplicationType() {
      return this.$registry.get('application', 'database')
    },
  },
  created() {
    const values = reactive({
      name: this.defaultName,
    })

    const rules = computed(() => ({
      name: {
        required,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  mounted() {
    this.$refs.name.focus()
  },
}
</script>
