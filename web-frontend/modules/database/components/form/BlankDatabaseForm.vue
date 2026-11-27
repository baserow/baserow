<template>
  <form @submit.prevent="submit">
    <FormGroup
      data-kuma-scope
      :error="fieldHasErrors('name')"
      required
      small-label
    >
      <template #label>
        <i class="iconoir-text"></i>
        {{ $t('applicationForm.nameLabel') }}
      </template>

      <template #label-action>
        <CreateDatabaseStructurePrompt
          v-if="!loading"
          :workspace="workspace"
          :name="values.name === defaultName ? '' : values.name"
          @created="$emit('created')"
        />
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
          {{ $filters.lowercase(databaseApplicationType.getName()) }}
        </Button>
      </div>
    </div>
  </form>
</template>

<script>
import CreateDatabaseStructurePrompt from '@baserow/modules/database/components/CreateDatabaseStructurePrompt'

import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { required, helpers } from '@vuelidate/validators'

export default {
  name: 'BlankDatabaseForm',
  components: { CreateDatabaseStructurePrompt },
  mixins: [form],
  props: {
    workspace: { type: Object, required: true },
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
  emits: ['created', 'submitted'],
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
