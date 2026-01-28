<template>
  <div>
    <h2 class="box__title">{{ $t('generalSettings.titleOverview') }}</h2>

    <FormGroup
      small-label
      :label="$t('generalSettings.nameLabel')"
      :error="fieldHasErrors('name')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        v-model="v$.values.name.$model"
        :error="fieldHasErrors('name')"
        size="large"
      ></FormInput>
      <template #error>
        {{ v$.values.name.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <div class="separator"></div>

    <FormGroup
      small-label
      :label="$t('generalSettings.notificationLabel')"
      :error="fieldHasErrors('notification')"
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.values.notification.$model" class="margin-top-1">{{
        $t('generalSettings.notificationCheckboxLabel')
      }}</Checkbox>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { isSubObject } from '@baserow/modules/core/utils/object'

export default {
  name: 'GeneralSettings',
  mixins: [form],
  props: {
    automation: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: '',
        notification: false,
      },
    }
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
        notification: {},
      },
    }
  },
  methods: {
    emitChange(newValues) {
      this.updateAutomation(newValues)
    },
    async updateAutomation(updatedValues) {
      if (isSubObject(this.automation, updatedValues)) {
        return
      }

      try {
        await this.$store.dispatch('application/update', {
          application: this.automation,
          values: updatedValues,
        })
      } catch (error) {
        const title = this.$t('generalSettings.cantUpdateAutomationTitle')
        const message = this.$t(
          'generalSettings.cantUpdateAutomationDescription'
        )
        this.$store.dispatch('toast/error', { title, message })
        this.reset()
      }
    },
  },
}
</script>
