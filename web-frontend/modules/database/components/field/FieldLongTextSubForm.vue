<template>
  <div>
    <div v-if="!primary" class="control">
      <div class="control__elements">
        <Checkbox v-model="values.long_text_enable_rich_text">{{
          $t('fieldLongTextSubForm.enableRichTextFormatting')
        }}</Checkbox>
        <Checkbox
          v-if="
            values.long_text_enable_rich_text &&
            $featureFlagIsEnabled(FF_IDENTITIES)
          "
          v-model="values.long_text_include_identities"
          >{{ $t('fieldLongTextSubForm.includeIdentities') }}</Checkbox
        >
      </div>
    </div>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import { FF_IDENTITIES } from '@baserow/modules/core/plugins/featureFlags'

export default {
  name: 'FieldLongTextSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      FF_IDENTITIES,
      allowedValues: [
        'long_text_enable_rich_text',
        'long_text_include_identities',
      ],
      values: {
        long_text_enable_rich_text: false,
        long_text_include_identities: false,
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
