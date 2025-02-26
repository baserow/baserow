<template>
  <ThemeConfigBlockSection>
    <template #default>
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('fontThemeConfigBlock.googleFontFamily')"
      >
        <GoogleFontFamilySelector
          v-model="values.customFont"
        />
        <template #after-input>
          TODO: Add Button to install the font
        </template>
      </FormGroup>
    </template>
  </ThemeConfigBlockSection>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import GoogleFontFamilySelector from '@baserow/modules/builder/components/GoogleFontFamilySelector'

export default {
  name: 'FontThemeConfigBlock',
  components: { ThemeConfigBlockSection, GoogleFontFamilySelector },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
    }
  },
}
</script>
