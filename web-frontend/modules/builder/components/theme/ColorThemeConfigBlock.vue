<template>
  <div>
    <ThemeConfigBlockSection>
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('colorThemeConfigBlock.primaryColor')"
        >
          <ColorInput v-model="values.primary_color" small />
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('colorThemeConfigBlock.secondaryColor')"
        >
          <ColorInput v-model="values.secondary_color" small />
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('colorThemeConfigBlock.borderColor')"
        >
          <ColorInput v-model="values.border_color" small />
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('colorThemeConfigBlock.successColor')"
        >
          <ColorInput v-model="values.main_success_color" small />
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('colorThemeConfigBlock.warningColor')"
        >
          <ColorInput v-model="values.main_warning_color" small />
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('colorThemeConfigBlock.errorColor')"
        >
          <ColorInput v-model="values.main_error_color" small />
        </FormGroup>
      </template>
    </ThemeConfigBlockSection>

    <ThemeConfigBlockSection :title="$t('colorThemeConfigBlock.customColors')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('colorThemeConfigBlock.primaryColor')"
        >
          <ColorInput v-model="values.primary_color" small />
        </FormGroup>
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'

export default {
  name: 'ColorThemeConfigBlock',

  components: { ThemeConfigBlockSection },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
    }
  },
  methods: {
    isAllowedKey(key) {
      return (
        key.startsWith('main_') ||
        ['primary_color', 'secondary_color', 'border_color'].includes(key)
      )
    },
  },
}
</script>
