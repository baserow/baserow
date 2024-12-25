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
      @enabled-protected-edit="allowedValues.push(field.name)"
      @disable-protected-edit="
        ;[
          allowedValues.splice(allowedValues.indexOf(field.name), 1),
          delete values[field.name],
        ]
      "
    >
      <template #label>{{
        $t(`postgreSQLDataSync.${field.translationPrefix}`)
      }}</template>
      <FormInput
        v-model="values[field.name]"
        size="large"
        :type="field.type"
        :error="fieldHasErrors(field.name)"
        :disabled="disabled"
        @blur="$v.values[field.name].$touch()"
      >
      </FormInput>
      <template #error>
        <div
          v-if="$v.values[field.name].$dirty && !$v.values[field.name].required"
        >
          {{ $t('error.requiredField') }}
        </div>
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
            v-model="values.postgresql_port"
            size="large"
            :error="fieldHasErrors('postgresql_port')"
            :disabled="disabled"
            @blur="$v.values.postgresql_port.$touch()"
          >
          </FormInput>
          <template #error>
            <div
              v-if="
                $v.values.postgresql_port.$dirty &&
                !$v.values.postgresql_port.required
              "
            >
              {{ $t('error.requiredField') }}
            </div>
            <div
              v-else-if="
                $v.values.postgresql_port.$dirty &&
                !$v.values.postgresql_port.numeric
              "
            >
              {{ $t('error.invalidNumber') }}
            </div>
          </template>
        </FormGroup>
      </div>
      <div class="col col-7">
        <FormGroup required small-label class="margin-bottom-2">
          <template #label>{{ $t('postgreSQLDataSync.sslMode') }}</template>
          <Dropdown
            v-model="values.postgresql_sslmode"
            size="large"
            :disabled="disabled"
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
import { required, numeric, requiredIf } from 'vuelidate/lib/validators'

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
  data() {
    const allowedValues = [
      'postgresql_host',
      'postgresql_username',
      'postgresql_port',
      'postgresql_database',
      'postgresql_schema',
      'postgresql_table',
      'postgresql_sslmode',
    ]
    if (!this.update) {
      allowedValues.push('postgresql_password')
    }
    return {
      allowedValues,
      values: {
        postgresql_host: '',
        postgresql_username: '',
        postgresql_port: '5432',
        postgresql_database: '',
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
        postgresql_host: { required },
        postgresql_username: { required },
        postgresql_password: {
          required: requiredIf(() => {
            return this.allowedValues.includes('postgresql_password')
          }),
        },
        postgresql_database: { required },
        postgresql_schema: { required },
        postgresql_table: { required },
        postgresql_sslmode: { required },
        postgresql_port: { required, numeric },
      },
    }
  },
}
</script>
