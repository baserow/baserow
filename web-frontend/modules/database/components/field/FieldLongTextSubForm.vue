<template>
  <div>
    <div v-if="!primary" class="control">
      <div class="control__elements">
        <Checkbox v-model="values.long_text_enable_rich_text">{{
          $t('fieldLongTextSubForm.enableRichTextFormatting')
        }}</Checkbox>
      </div>
    </div>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldLongTextSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['long_text_enable_rich_text'],
      values: {
        long_text_enable_rich_text: false,
      },
    }
  },
  methods: {
    isFormValid() {
      return true
    },
  },
}
</script>
