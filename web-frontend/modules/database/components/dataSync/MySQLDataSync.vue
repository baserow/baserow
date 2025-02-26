<template>
  <form @submit.prevent="submit">
    <p class="margin-bottom-2 margin-top-3">
      {{ $t('mySQLDataSync.description') }}
    </p>
    <FormGroup
      v-for="field in [
        { name: 'mysql_host', translationPrefix: 'host', type: 'text' },
        {
          name: 'mysql_username',
          translationPrefix: 'username',
          type: 'text',
        },
        {
          name: 'mysql_password',
          translationPrefix: 'password',
          type: 'password',
          protectedEdit: true,
        },
        {
          name: 'mysql_database',
          translationPrefix: 'database',
          type: 'text',
        },
        { name: 'mysql_table', translationPrefix: 'table', type: 'text' },
      ]"
      :key="field.name"
      :error="fieldHasErrors(field.name)"
      required
      small-label
      :protected-edit="update && field.protectedEdit"
      class="margin-bottom-2"
      @enabled-protected-edit="allowedValues.push(field.name)"
      @disable-protected-edit="
        ;[
          allowedValues.splice(allowedValues.indexOf(field.name), 1),
          delete values[field.name],
        ]
      "
    >
      <template #label>{{
        $t(`mySQLDataSync.${field.translationPrefix}`)
      }}</template>
      <FormInput
        v-model="v$.values[field.name].$model"
        size="large"
        :type="field.type"
        :error="fieldHasErrors(field.name)"
        :disabled="disabled"
      >
      </FormInput>
      <template #error>
        {{ v$.values[field.name].$errors[0]?.$message }}
      </template>
    </FormGroup>
    <div class="row">
      <div class="col col-5">
        <FormGroup
          :error="fieldHasErrors('mysql_port')"
          required
          small-label
          class="margin-bottom-2"
        >
          <template #label>{{ $t('mySQLDataSync.port') }}</template>
          <FormInput
            v-model="v$.values.mysql_port.$model"
            size="large"
            :error="fieldHasErrors('mysql_port')"
            :disabled="disabled"
          >
          </FormInput>
          <template #error>
            {{ v$.values.mysql_port.$errors[0]?.$message }}
          </template>
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
  name: 'MySQLDataSync',
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
      'mysql_host',
      'mysql_username',
      'mysql_port',
      'mysql_database',
      'mysql_table',
    ]
    if (!this.update) {
      allowedValues.push('mysql_password')
    }
    return {
      allowedValues,
      values: {
        mysql_host: '',
        mysql_username: '',
        mysql_port: '3306',
        mysql_database: '',
        mysql_table: '',
        mysql_password: '',
      },
    }
  },
  validations() {
    return {
      values: {
        mysql_host: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        mysql_username: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        mysql_password: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            requiredIf(() => {
              return this.allowedValues.includes('mysql_password')
            })
          ),
        },
        mysql_database: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        mysql_table: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        mysql_port: {
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
