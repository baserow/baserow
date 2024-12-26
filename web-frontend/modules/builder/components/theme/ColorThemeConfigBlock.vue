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
          v-for="(customColor, index) in values.custom_colors" :key="customColor.name"
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="customColor.name"
        >
          <ColorInput
            :value="values.custom_colors[index].color"
            @input="(newValue) => updateExistingColor(index, newValue)"
            small
          />
          <template #after-input>
            <ButtonIcon icon="iconoir-bin" @click="deleteCustomColor(index)" />
          </template>
        </FormGroup>
          <div class="color-theme-config-block__custom_color_container">
            <a class="color-theme-config-block__custom_color_link" @click="addCustomColor"">
              <i class="baserow-icon-plus"></i>
            </a>
          </div>
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'

const CUSTOM_COLOR_PREFIX = 'Custom '
// The same as the Primary color
const DEFAULT_CUSTOM_COLOR = '#5190efff'

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
    addCustomColor() {
      let newColorId = this.values.custom_colors.length + 1
      const existingNames = this.values.custom_colors.map(color => color.name)
    
      // If an earlier custom color is deleted, the size of the array has changed.
      // This ensures that the new name will never collide with an existing name.
      while (existingNames.includes(`${CUSTOM_COLOR_PREFIX} ${newColorId}`)) {
        newColorId++
      }

      const colorName = `${CUSTOM_COLOR_PREFIX} ${newColorId}`
      const newCustomColor = {
        name: colorName,
        value: colorName,
        color: DEFAULT_CUSTOM_COLOR,
      }
      const updatedCustomColors = [...this.values.custom_colors, newCustomColor]
      this.values.custom_colors = updatedCustomColors
    },
    deleteCustomColor(index) {
      const updatedCustomColors = [...this.values.custom_colors]
      updatedCustomColors.splice(index, 1)
      this.values.custom_colors = updatedCustomColors
    },
    updateExistingColor(index, newValue) {
      const updatedCustomColors = structuredClone(this.values.custom_colors)
      updatedCustomColors[index].color = newValue
      this.values.custom_colors = updatedCustomColors
    }
  },
}
</script>
