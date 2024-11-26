<template>
  <div>
    <ThemeConfigBlockSection
      v-if="showLabel"
      :title="$t('inputThemeConfigBlock.label')"
    >
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.fontFamily')"
          class="margin-bottom-2"
        >
          <FontFamilySelector v-model="values.label_font_family" />
          <template #after-input>
            <ResetButton
              v-model="values.label_font_family"
              :default-value="theme?.label_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.textColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.label_text_color"
            :color-variables="colorVariables"
            :default-value="theme?.label_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.label_text_color"
              :default-value="theme?.label_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.size')"
          :error-message="getError('label_font_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.label_font_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`label_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.label_font_size"
              :default-value="theme?.label_font_size"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABFormGroup :label="$t('inputThemeConfigBlock.label')">
          <ABInput value="" />
        </ABFormGroup>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('inputThemeConfigBlock.input')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.fontFamily')"
          class="margin-bottom-2"
        >
          <FontFamilySelector v-model="values.input_font_family" />
          <template #after-input>
            <ResetButton
              v-model="values.input_font_family"
              :default-value="theme?.input_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.textColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.input_text_color"
            :color-variables="colorVariables"
            :default-value="theme?.input_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.input_text_color"
              :default-value="theme?.input_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.size')"
          :error-message="getError('input_font_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.input_font_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`input_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.input_font_size"
              :default-value="theme?.input_font_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.backgroundColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.input_background_color"
            :color-variables="colorVariables"
            :default-value="theme?.input_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.input_background_color"
              :default-value="theme?.input_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.borderColor')"
          class="margin-bottom-2"
        >
          <ColorInput
            v-model="values.input_border_color"
            :color-variables="colorVariables"
            :default-value="theme?.input_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.input_border_color"
              :default-value="theme?.input_border_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.borderSize')"
          :error-message="getError('input_border_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.input_border_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`input_border_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.input_border_size"
              :default-value="theme?.input_border_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.borderRadius')"
          :error-message="getError('input_border_radius')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.input_border_radius"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`input_border_radius`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.input_border_radius"
              :default-value="theme?.input_border_radius"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('inputThemeConfigBlock.padding')"
          :error-message="getInputPaddingError()"
          class="margin-bottom-2"
        >
          <PaddingSelector
            v-model="inputPadding"
            :default-values-when-empty="paddingDefaults"
          />
          <template #after-input>
            <ResetButton
              v-model="inputPadding"
              :default-value="
                theme
                  ? {
                      vertical: theme['input_vertical_padding'],
                      horizontal: theme['input_horizontal_padding'],
                    }
                  : undefined
              "
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABFormGroup>
          <ABInput
            :value="$t('inputThemeConfigBlock.input')"
            class="margin-bottom-2"
          />
          <ABDropdown
            :value="$t('inputThemeConfigBlock.input')"
            :show-search="false"
            class="margin-bottom-2"
          >
            <ABDropdownItem
              v-for="option in options"
              :key="option.value"
              :name="option.name"
              :value="option.value"
            />
          </ABDropdown>
          <div class="margin-bottom-2">
            <ABCheckbox
              v-for="(option, index) in options"
              :key="option.value"
              :name="option.name"
              :value="index === 1"
            >
              {{ option.name }}
            </ABCheckbox>
          </div>
          <div class="margin-bottom-2">
            <ABRadio
              v-for="(option, index) in options"
              :key="option.value"
              :value="index === 1"
            >
              {{ option.name }}
            </ABRadio>
          </div>
        </ABFormGroup>
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { required, integer, minValue, maxValue } from 'vuelidate/lib/validators'
import { DEFAULT_FONT_SIZE_PX } from '@baserow/modules/builder/defaultStyles'

const minMax = {
  label_font_size: {
    min: 1,
    max: 100,
  },
  input_font_size: {
    min: 1,
    max: 100,
  },
  input_border_size: {
    min: 0,
    max: 100,
  },
  input_border_radius: {
    min: 0,
    max: 100,
  },
  input_horizontal_padding: {
    min: 0,
    max: 200,
  },
  input_vertical_padding: {
    min: 0,
    max: 200,
  },
}

export default {
  name: 'LinkThemeConfigBlock',
  components: {
    ThemeConfigBlockSection,
    ResetButton,
    FontFamilySelector,
    PixelValueSelector,
    PaddingSelector,
  },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
      options: [
        { name: 'Option 1', value: 1 },
        { name: 'Option 2', value: 2 },
        { name: 'Option 3', value: 3 },
      ],
      defaultValuesWhenEmpty: {
        label_font_size: DEFAULT_FONT_SIZE_PX,
        input_font_size: DEFAULT_FONT_SIZE_PX,
        input_border_size: minMax.input_border_size.min,
        input_border_radius: minMax.input_border_radius.min,
      },
    }
  },
  computed: {
    inputPadding: {
      get() {
        return {
          vertical: this.values.input_vertical_padding,
          horizontal: this.values.input_horizontal_padding,
        }
      },
      set(newValue) {
        this.values.input_vertical_padding = newValue.vertical
        this.values.input_horizontal_padding = newValue.horizontal
      },
    },
    showLabel() {
      return !this.extraArgs?.onlyInput
    },
    paddingDefaults() {
      return {
        vertical: minMax.input_vertical_padding.min,
        horizontal: minMax.input_horizontal_padding.min,
      }
    },
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('input_') || key.startsWith('label_')
    },
    getError(property) {
      if (this.$v.values[property].$invalid) {
        return this.$t('error.minMaxValueField', minMax[property])
      }
      return null
    },
    getInputPaddingError() {
      return (
        this.getError('input_vertical_padding') ||
        this.getError('input_horizontal_padding')
      )
    },
  },
  validations: {
    values: Object.fromEntries(
      Object.entries(minMax).map(([key, limits]) => [
        key,
        {
          required,
          integer,
          minValue: minValue(limits.min),
          maxValue: maxValue(limits.max),
        },
      ])
    ),
  },
}
</script>
