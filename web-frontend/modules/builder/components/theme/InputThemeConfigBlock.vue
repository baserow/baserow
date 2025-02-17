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
          <FontFamilySelector v-model="v$.values.label_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.values.label_font_family.$model"
              :default-value="theme?.label_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('inputThemeConfigBlock.weight')"
        >
          <FontWeightSelector
            v-model="v$.values.label_font_weight.$model"
            :font="values.label_font_family"
          />
          <template #after-input>
            <ResetButton
              v-if="values.label_font_family === theme?.label_font_family"
              v-model="v$.values.label_font_weight.$model"
              :default-value="theme?.label_font_weight"
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
            v-model="v$.values.label_font_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`label_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.label_font_size.$model"
              :default-value="theme?.label_font_size"
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
            v-model="v$.values.label_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.label_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.label_text_color.$model"
              :default-value="theme?.label_text_color"
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
          <FontFamilySelector v-model="v$.values.input_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.values.input_font_family.$model"
              :default-value="theme?.input_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('inputThemeConfigBlock.weight')"
        >
          <FontWeightSelector
            v-model="v$.values.input_font_weight.$model"
            :font="values.input_font_family"
          />
          <template #after-input>
            <ResetButton
              v-if="values.input_font_family === theme?.input_font_family"
              v-model="v$.values.input_font_weight.$model"
              :default-value="theme?.input_font_weight"
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
            v-model="v$.values.input_font_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`input_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.input_font_size.$model"
              :default-value="theme?.input_font_size"
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
            v-model="v$.values.input_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.input_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.input_text_color.$model"
              :default-value="theme?.input_text_color"
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
            v-model="v$.values.input_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.input_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.input_background_color.$model"
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
            v-model="v$.values.input_border_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.input_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.input_border_color.$model"
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
            v-model="v$.values.input_border_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`input_border_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.input_border_size.$model"
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
            v-model="v$.values.input_border_radius.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`input_border_radius`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.input_border_radius.$model"
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
import { useVuelidate } from '@vuelidate/core'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import FontWeightSelector from '@baserow/modules/builder/components/FontWeightSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'
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
    FontWeightSelector,
    PixelValueSelector,
    PaddingSelector,
  },
  mixins: [themeConfigBlock],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        label_font_family: this.theme?.label_font_family,
        label_text_color: this.theme?.label_text_color,
        label_font_size: this.theme?.label_font_size,
        label_font_weight: this.theme?.label_font_weight,
        input_font_family: this.theme?.input_font_family,
        input_text_color: this.theme?.input_text_color,
        input_font_size: this.theme?.input_font_size,
        input_font_weight: this.theme?.input_font_weight,
        input_background_color: this.theme?.input_background_color,
        input_border_color: this.theme?.input_border_color,
        input_border_radius: this.theme?.input_border_radius,
        input_border_size: this.theme?.input_border_size,
        input_horizontal_padding: this.theme?.input_horizontal_padding,
        input_vertical_padding: this.theme?.input_vertical_padding,
      },
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
      if (this.v$.values[property].$invalid) {
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
  validations() {
    return {
      values: {
        ...Object.fromEntries(
          Object.entries(minMax).map(([key, limits]) => [
            key,
            {
              required: helpers.withMessage(
                this.$t('error.requiredField'),
                required
              ),
              integer: helpers.withMessage(
                this.$t('error.integerField'),
                integer
              ),
              minValue: helpers.withMessage(
                this.$t('error.minValueField', { min: limits.min }),
                minValue(limits.min)
              ),
              maxValue: helpers.withMessage(
                this.$t('error.maxValueField', { max: limits.max }),
                maxValue(limits.max)
              ),
            },
          ])
        ),
        label_font_family: {},
        label_text_color: {},
        label_font_size: {},
        label_font_weight: {},
        input_font_family: {},
        input_text_color: {},
        input_font_size: {},
        input_background_color: {},
        input_font_weight: {},
        input_border_color: {},
        input_border_radius: {},
        input_border_size: {},
        input_horizontal_padding: {},
        input_vertical_padding: {},
      },
    }
  },
}
</script>
