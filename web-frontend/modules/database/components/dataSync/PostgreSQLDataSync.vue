<template>
  <form @submit.prevent="submit">
    <p class="margin-bottom-2 margin-top-3">
      {{ $t('postgreSQLDataSync.description') }}
    </p>
    <FormGroup
      v-for="field in [
        { name: 'postgresql_host', translationPrefix: 'host', type: 'text' },
        {
          name: 'postgresql_username',
          translationPrefix: 'username',
          type: 'text',
        },
        {
          name: 'postgresql_password',
          translationPrefix: 'password',
          type: 'password',
          protectedEdit: true,
        },
        {
          name: 'postgresql_database',
          translationPrefix: 'database',
          type: 'text',
        },
        {
          name: 'postgresql_schema',
          translationPrefix: 'schema',
          type: 'text',
        },
        { name: 'postgresql_table', translationPrefix: 'table', type: 'text' },
      ]"
      :key="field.name"
      :error="fieldHasErrors(field.name)"
      required
      small-label
      :protected-edit="update && field.protectedEdit"
      class="margin-bottom-2"
      @enabled-protected-edit="values.postgresql_password = ''"
      @disable-protected-edit="values.postgresql_password = undefined"
    >
      <template #label>{{
        $t(`postgreSQLDataSync.${field.translationPrefix}`)
      }}</template>
      <FormInput
        v-model="v$.values[field.name].$model"
        size="large"
        :type="field.type"
        :error="fieldHasErrors(field.name)"
        :disabled="disabled"
        @blur="v$.values[field.name].$touch()"
      >
      </FormInput>
      <template #error>
        {{ v$.values[field.name].$errors[0]?.$message }}
      </template>
    </FormGroup>
    <div class="row">
      <div class="col col-5">
        <FormGroup
          :error="fieldHasErrors('postgresql_port')"
          required
          small-label
          class="margin-bottom-2"
        >
          <template #label>{{ $t('postgreSQLDataSync.port') }}</template>
          <FormInput
            v-model="v$.values.postgresql_port.$model"
            size="large"
            :error="fieldHasErrors('postgresql_port')"
            :disabled="disabled"
            @blur="v$.values.postgresql_port.$touch"
          >
          </FormInput>
          <template #error>
            {{ v$.values.postgresql_port.$errors[0]?.$message }}
          </template>
        </FormGroup>
      </div>
      <div class="col col-7">
        <FormGroup required small-label class="margin-bottom-2">
          <template #label>{{ $t('postgreSQLDataSync.sslMode') }}</template>
          <Dropdown
            v-model="v$.values.postgresql_sslmode.$model"
            :disabled="disabled"
            size="large"
          >
            <DropdownItem
              v-for="option in sslModeOptions"
              :key="option"
              :name="option"
              :value="option"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, requiredIf, numeric, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'PostgreSQLDataSync',
  mixins: [form],
  props: {
    update: {
      type: Boolean,
      required: false,
      default: false,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    const allowedValues = [
      'postgresql_host',
      'postgresql_username',
      'postgresql_port',
      'postgresql_database',
      'postgresql_password',
      'postgresql_schema',
      'postgresql_table',
      'postgresql_sslmode',
    ]
    return {
      allowedValues,
      values: {
        postgresql_host: '',
        postgresql_username: '',
        postgresql_port: '5432',
        postgresql_database: '',
        // If `undefined`, it's not included in the patch update request, and will then
        // not be changed.
        postgresql_password: this.update ? undefined : '',
        postgresql_schema: 'public',
        postgresql_table: '',
        postgresql_sslmode: 'prefer',
      },
      sslModeOptions: [
        'disable',
        'allow',
        'prefer',
        'require',
        'verify-ca',
        'verify-full',
      ],
    }
  },
  validations() {
    return {
      values: {
        postgresql_host: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        postgresql_username: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        postgresql_password: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => {
              return this.values.postgresql_password !== undefined
            })
          ),
        },
        postgresql_database: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        postgresql_schema: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        postgresql_table: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        postgresql_sslmode: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        postgresql_port: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          numeric: helpers.withMessage(this.$t('error.invalidNumber'), numeric),
        },
      },
    }
  },
}
</script>
