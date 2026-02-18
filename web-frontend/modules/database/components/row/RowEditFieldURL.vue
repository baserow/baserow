<template>
  <FormGroup :error="touched && !valid">
    <div class="url-input">
      <FormInput
        ref="input"
        v-model="copy"
        size="large"
        :error="touched && !valid"
        :disabled="readOnly"
        :text-invisible="!editing"
        @keyup.enter="$refs.input?.$el?.blur()"
        @focus="select()"
        @blur="unselect()"
      />
      <a
        v-if="!editing"
        :href="getHref(copy)"
        target="_blank"
        rel="nofollow noopener noreferrer"
        class="url-input__link"
        >{{ value }}</a
      >
    </div>
    <template #error>
      <span v-show="touched && !valid">
        {{ error }}
      </span>
    </template>
  </FormGroup>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'
import { ensureUrlProtocol } from '@baserow/modules/core/utils/url'

export default {
  mixins: [rowEditField, rowEditFieldInput],
  methods: {
    getHref(value) {
      return ensureUrlProtocol(value)
    },
  },
}
</script>
