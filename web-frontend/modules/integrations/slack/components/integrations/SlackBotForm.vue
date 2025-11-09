<template>
  <div>
    <FormGroup required :label="$t('slackBotForm.tokenLabel')" small-label>
      <FormInput
        v-model="values.token"
        type="password"
        :placeholder="$t('slackBotForm.tokenPlaceholder')"
      />
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: { token: '' },
      allowedValues: ['token'],
    }
  },
}
</script>
