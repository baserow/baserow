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
        <CustomColorInput
          v-for="(customColor, index) in values.custom_colors"
          :key="customColor.value"
          :value="customColor"
          @input="updateCustomColor(index, $event)"
          @deleteCustomColor="deleteCustomColor(index)"
        />

        <div class="color-theme-config-block__custom-color-container">
          <ButtonText
            type="primary"
            icon="iconoir-plus"
            size="small"
            @click="addCustomColor"
          >
            {{ $t('colorThemeConfigBlock.addCustomColor') }}
          </ButtonText>
        </div>
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import CustomColorInput from '@baserow/modules/builder/components/theme/CustomColorInput'
import {
  smallUID,
  getNextAvailableNameInSequence,
} from '@baserow/modules/core/utils/string'

const COLOR_ID_LENGTH = 5

export default {
  name: 'ColorThemeConfigBlock',

  components: { ThemeConfigBlockSection, CustomColorInput },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
    }
  },
  methods: {
    updateCustomColor(index, updatedValue) {
      const updatedColors = [...this.values.custom_colors]
      updatedColors[index] = { ...updatedValue }
      this.values.custom_colors = updatedColors
    },
    isAllowedKey(key) {
      return (
        key.startsWith('main_') ||
        ['primary_color', 'secondary_color', 'border_color'].includes(key)
      )
    },
    /**
     * Create a new custom color.
     *
     * A new custom color object is generated and added to the custom_colors
     * array.
     *
     * The color name is a short name like "Custom 1", "Custom 2", etc. To
     * derive the correct number to use, `1` is added to the size of the
     * current array of custom colors.
     *
     * There is some additional logic that ensures a new custom color's name
     * doesn't duplicate the name of an existing custom color.
     */
    addCustomColor() {
      // To avoid duplicating names, newColorId is incremented until an unused
      // value is found.
      const existingNames = this.values.custom_colors.map((color) => color.name)

      const colorName = getNextAvailableNameInSequence(
        this.$t('colorThemeConfigBlock.customColorPrefix'),
        existingNames
      )

      const newCustomColor = {
        name: colorName,
        value: smallUID(COLOR_ID_LENGTH),
        // Initializes the color to a predictable default.
        color: this.values.primary_color,
      }

      const updatedCustomColors = [...this.values.custom_colors, newCustomColor]
      this.values.custom_colors = updatedCustomColors
    },

    /**
     * Delete a specific custom color.
     *
     * When a custom color is deleted, we need to remove it from the array of
     * custom colors.
     */
    deleteCustomColor(index) {
      const updatedCustomColors = [...this.values.custom_colors]
      updatedCustomColors.splice(index, 1)
      this.values.custom_colors = updatedCustomColors
    },

    /**
     * Update a specific custom color's hex value.
     */
    updateExistingColor(index, newValue) {
      const updatedCustomColors = structuredClone(this.values.custom_colors)
      updatedCustomColors[index].color = newValue
      this.values.custom_colors = updatedCustomColors
    },
  },
}
</script>
