<template>
  <div>
    <FormGroup :label="$t('localBaserowForm.user')" required small-label>
      <div class="local-baserow-form__user">
        <Presentation
          v-if="values.authorized_user"
          :title="values.authorized_user.first_name"
          :subtitle="values.authorized_user.username"
          :initials="
            $filters.nameAbbreviation(values.authorized_user.first_name)
          "
          avatar-color="blue"
        />
        <div>{{ $t('localBaserowForm.userMessage') }}</div>
      </div>
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
      values: {
        authorized_user: {},
      },
      allowedValues: ['authorized_user'],
    }
  },
}
</script>
