<template>
  <div>
    <ThemeConfigBlockSection>
      <template #default>
        <FormGroup
          v-if="!extraArgs?.noWidth"
          horizontal-narrow
          small-label
          required
          :label="$t('buttonThemeConfigBlock.width')"
          class="margin-bottom-2"
        >
          <WidthSelector v-model="buttonWidth" />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_width.$model"
              :default-value="theme?.button_width"
            />
          </template>
        </FormGroup>

        <FormGroup
          v-if="values.button_width === 'auto' && !extraArgs?.noAlignment"
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.alignment')"
        >
          <HorizontalAlignmentsSelector
            v-model="v$.values.button_alignment.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_alignment.$model"
              :default-value="theme?.button_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          v-if="
            v$.values.button_width.$model === 'full' && !extraArgs?.noAlignment
          "
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.textAlignment')"
        >
          <HorizontalAlignmentsSelector
            v-model="v$.values.button_text_alignment.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_text_alignment.$model"
              :default-value="theme?.button_text_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('buttonThemeConfigBlock.fontFamily')"
          class="margin-bottom-2"
        >
          <FontFamilySelector v-model="v$.values.button_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_font_family.$model"
              :default-value="theme?.button_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.weight')"
        >
          <FontWeightSelector
            v-model="v$.values.button_font_weight.$model"
            :font="values.button_font_family"
          />
          <template #after-input>
            <ResetButton
              v-if="values.button_font_family === theme?.button_font_family"
              v-model="values.button_font_weight"
              :default-value="theme?.button_font_weight"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('buttonThemeConfigBlock.size')"
          :error-message="getError('button_font_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="v$.values.button_font_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`button_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_font_size.$model"
              :default-value="theme?.button_font_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('buttonThemeConfigBlock.borderSize')"
          :error-message="getError('button_border_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="v$.values.button_border_size.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`button_border_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_border_size.$model"
              :default-value="theme?.button_border_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('buttonThemeConfigBlock.borderRadius')"
          :error-message="getError('button_border_radius')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="v$.values.button_border_radius.$model"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`button_border_radius`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_border_radius.$model"
              :default-value="theme?.button_border_radius"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('buttonThemeConfigBlock.padding')"
          :error-message="getPaddingError()"
          class="margin-bottom-2"
        >
          <PaddingSelector
            v-model="padding"
            :default-values-when-empty="paddingDefaults"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.padding.$model"
              :default-value="
                theme
                  ? {
                      vertical: theme['button_vertical_padding'],
                      horizontal: theme['button_horizontal_padding'],
                    }
                  : undefined
              "
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABButton>{{ $t('buttonThemeConfigBlock.button') }}</ABButton>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('buttonThemeConfigBlock.defaultState')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.backgroundColor')"
        >
          <ColorInput
            v-model="v$.values.button_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_background_color.$model"
              :default-value="theme?.button_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.textColor')"
        >
          <ColorInput
            v-model="v$.values.button_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_text_color.$model"
              :default-value="theme?.button_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.borderColor')"
        >
          <ColorInput
            v-model="v$.values.button_border_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_border_color.$model"
              :default-value="theme?.button_border_color"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABButton>{{ $t('buttonThemeConfigBlock.button') }}</ABButton>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('buttonThemeConfigBlock.hoverState')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.backgroundColor')"
        >
          <ColorInput
            v-model="v$.values.button_hover_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_hover_background_color.$model"
              :default-value="theme?.button_hover_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.textColor')"
        >
          <ColorInput
            v-model="v$.values.button_hover_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_hover_text_color.$model"
              :default-value="theme?.button_hover_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.borderColor')"
        >
          <ColorInput
            v-model="v$.values.button_hover_border_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_hover_border_color.$model"
              :default-value="theme?.button_hover_border_color"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABButton class="ab-button--force-hover">
          {{ $t('buttonThemeConfigBlock.button') }}
        </ABButton>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('buttonThemeConfigBlock.activeState')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.backgroundColor')"
        >
          <ColorInput
            v-model="v$.values.button_active_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_active_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_active_background_color.$model"
              :default-value="theme?.button_active_background_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.textColor')"
        >
          <ColorInput
            v-model="v$.values.button_active_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_active_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_active_text_color.$model"
              :default-value="theme?.button_active_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.borderColor')"
        >
          <ColorInput
            v-model="v$.values.button_active_border_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_active_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.button_active_border_color.$model"
              :default-value="theme?.button_active_border_color"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABButton class="ab-button--force-active">
          {{ $t('buttonThemeConfigBlock.button') }}
        </ABButton>
      </template>
    </ThemeConfigBlockSection>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import WidthSelector from '@baserow/modules/builder/components/WidthSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import FontWeightSelector from '@baserow/modules/builder/components/FontWeightSelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { DEFAULT_FONT_SIZE_PX } from '@baserow/modules/builder/defaultStyles'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'

const pixelSizeMin = 1
const pixelSizeMax = 100

const minMax = {
  button_font_size: {
    min: 1,
    max: 100,
  },
  button_border_size: {
    min: 0,
    max: 100,
  },
  button_border_radius: {
    min: 0,
    max: 100,
  },
  button_horizontal_padding: {
    min: 0,
    max: 200,
  },
  button_vertical_padding: {
    min: 0,
    max: 200,
  },
}

export default {
  name: 'ButtonThemeConfigBlock',
  components: {
    ThemeConfigBlockSection,
    ResetButton,
    WidthSelector,
    HorizontalAlignmentsSelector,
    FontFamilySelector,
    FontWeightSelector,
    PixelValueSelector,
    PaddingSelector,
  },
  mixins: [themeConfigBlock],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      defaultValuesWhenEmpty: {
        button_font_size: DEFAULT_FONT_SIZE_PX,
        button_border_size: minMax.button_border_size.min,
        button_border_radius: minMax.button_border_size.min,
      },
      values: {
        button_font_size: this.theme?.button_font_size,
        button_border_size: this.theme?.button_border_size,
        button_border_radius: this.theme?.button_border_radius,
        button_border_color: this.theme?.button_border_color,
        button_horizontal_padding: this.theme?.button_horizontal_padding,
        button_vertical_padding: this.theme?.button_vertical_padding,
        button_font_family: this.theme?.button_font_family,
        button_font_weight: this.theme?.button_font_weight,
        button_text_alignment: this.theme?.button_text_alignment,
        button_alignment: this.theme?.button_alignment,
        button_text_color: this.theme?.button_text_color,
        button_width: this.theme?.button_width,
        button_background_color: this.theme?.button_background_color,
        button_hover_background_color:
          this.theme?.button_hover_background_color,
        button_hover_text_color: this.theme?.button_hover_text_color,
        button_hover_border_color: this.theme?.button_hover_border_color,
        button_active_background_color:
          this.theme?.button_active_background_color,
        button_active_text_color: this.theme?.button_active_text_color,
        button_active_border_color: this.theme?.button_active_border_color,
      },
    }
  },
  computed: {
    buttonWidth: {
      get() {
        return this.values.button_width
      },
      set(value) {
        // When we change the button width we want to keep the same alignment,
        // it's less confusing to the user.
        this.v$.values.button_width.$model = value
        if (value === 'auto') {
          this.v$.values.button_alignment.$model =
            this.values.button_text_alignment
        } else {
          this.v$.values.button_text_alignment.$model =
            this.values.button_alignment
        }
      },
    },
    padding: {
      get() {
        return {
          vertical: this.values.button_vertical_padding,
          horizontal: this.values.button_horizontal_padding,
        }
      },
      set(newValue) {
        this.v$.values.button_vertical_padding.$model = newValue.vertical
        this.v$.values.button_horizontal_padding.$model = newValue.horizontal
      },
    },
    paddingDefaults() {
      return {
        vertical: minMax.button_vertical_padding.min,
        horizontal: minMax.button_horizontal_padding.min,
      }
    },
    pixedSizeMin() {
      return pixelSizeMin
    },
    pixedSizeMax() {
      return pixelSizeMax
    },
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('button_')
    },
    getError(property) {
      return this.v$.values[property].$errors[0]?.$message
    },
    getPaddingError() {
      return (
        this.getError('button_vertical_padding') ||
        this.getError('button_horizontal_padding')
      )
    },
  },
  validations() {
    return {
      values: {
        button_font_size: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.button_font_size.min,
            }),
            minValue(minMax.button_font_size.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: minMax.button_font_size.max,
            }),
            maxValue(minMax.button_font_size.max)
          ),
        },
        button_border_size: {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.button_border_size.min,
            }),
            minValue(minMax.button_border_size.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: minMax.button_border_size.max,
            }),
            maxValue(minMax.button_border_size.max)
          ),
        },
        button_border_radius: {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.button_border_radius.min,
            }),
            minValue(minMax.button_border_radius.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: minMax.button_border_radius.max,
            }),
            maxValue(minMax.button_border_radius.max)
          ),
        },
        button_horizontal_padding: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.button_horizontal_padding.min,
            }),
            minValue(minMax.button_horizontal_padding.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: minMax.button_horizontal_padding.max,
            }),
            maxValue(minMax.button_horizontal_padding.max)
          ),
        },
        button_vertical_padding: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', {
              min: minMax.button_vertical_padding.min,
            }),
            minValue(minMax.button_vertical_padding.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', {
              max: minMax.button_vertical_padding.max,
            }),
            maxValue(minMax.button_vertical_padding.max)
          ),
        },
        button_background_color: {},
        button_hover_background_color: {},
        button_hover_text_color: {},
        button_border_color: {},
        button_hover_border_color: {},
        button_active_background_color: {},
        button_active_text_color: {},
        button_active_border_color: {},
        button_font_family: {},
        button_font_weight: {},
        button_text_color: {},
        button_text_alignment: {},
        button_alignment: {},
        button_width: {},
        padding: {},
      },
    }
  },
}
</script>
