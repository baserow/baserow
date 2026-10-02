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
  name: 'FieldAIRichTextSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['long_text_enable_rich_text'],
      values: {
        // Only fields becoming AI fields start rich; stored values override this.
        long_text_enable_rich_text:
          !this.primary && this.defaultValues.type !== this.fieldType,
      },
    }
  },
  methods: {
    getFormValues() {
      return {
        long_text_enable_rich_text:
          !this.primary && this.values.long_text_enable_rich_text,
      }
    },
  },
}
</script>
