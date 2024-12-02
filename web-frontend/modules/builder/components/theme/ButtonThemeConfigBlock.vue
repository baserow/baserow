<template>
  <div>
    <ThemeConfigBlockSection>
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          :label="$t('buttonThemeConfigBlock.width')"
          class="margin-bottom-2"
        >
          <WidthSelector v-model="buttonWidth" />
          <template #after-input>
            <ResetButton
              v-model="values.button_width"
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
          <HorizontalAlignmentsSelector v-model="values.button_alignment" />
          <template #after-input>
            <ResetButton
              v-model="values.button_alignment"
              :default-value="theme?.button_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          v-if="values.button_width === 'full'"
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.textAlignment')"
        >
          <HorizontalAlignmentsSelector
            v-model="values.button_text_alignment"
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_text_alignment"
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
          <FontFamilySelector v-model="values.button_font_family" />
          <template #after-input>
            <ResetButton
              v-model="values.button_font_family"
              :default-value="theme?.button_font_family"
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
            v-model="values.button_font_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`button_font_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_font_size"
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
            v-model="values.button_border_size"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`button_border_size`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_border_size"
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
            v-model="values.button_border_radius"
            :default-value-when-empty="
              defaultValuesWhenEmpty[`button_border_radius`]
            "
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_border_radius"
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
              v-model="padding"
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
            v-model="values.button_background_color"
            :color-variables="colorVariables"
            :default-value="theme?.button_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_background_color"
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
            v-model="values.button_text_color"
            :color-variables="colorVariables"
            :default-value="theme?.button_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_text_color"
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
            v-model="values.button_border_color"
            :color-variables="colorVariables"
            :default-value="theme?.button_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_border_color"
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
            v-model="values.button_hover_background_color"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_hover_background_color"
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
            v-model="values.button_hover_text_color"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_hover_text_color"
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
            v-model="values.button_hover_border_color"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.button_hover_border_color"
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
  </div>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import WidthSelector from '@baserow/modules/builder/components/WidthSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { required, integer, minValue, maxValue } from 'vuelidate/lib/validators'
import { DEFAULT_FONT_SIZE_PX } from '@baserow/modules/builder/defaultStyles'

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
    PixelValueSelector,
    PaddingSelector,
  },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
      defaultValuesWhenEmpty: {
        button_font_size: DEFAULT_FONT_SIZE_PX,
        button_border_size: minMax.button_border_size.min,
        button_border_radius: minMax.button_border_size.min,
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
        this.values.button_width = value
        if (value === 'auto') {
          this.values.button_alignment = this.values.button_text_alignment
        } else {
          this.values.button_text_alignment = this.values.button_alignment
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
        this.values.button_vertical_padding = newValue.vertical
        this.values.button_horizontal_padding = newValue.horizontal
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
      if (this.$v.values[property].$invalid) {
        return this.$t('error.minMaxValueField', minMax[property])
      }
      return null
    },
    getPaddingError() {
      return (
        this.getError('button_vertical_padding') ||
        this.getError('button_horizontal_padding')
      )
    },
  },
  validations: {
    values: {
      button_font_size: {
        required,
        integer,
        minValue: minValue(minMax.button_font_size.min),
        maxValue: maxValue(minMax.button_font_size.max),
      },
      button_border_size: {
        integer,
        minValue: minValue(minMax.button_border_size.min),
        maxValue: maxValue(minMax.button_border_size.max),
      },
      button_border_radius: {
        integer,
        minValue: minValue(minMax.button_border_radius.min),
        maxValue: maxValue(minMax.button_border_radius.max),
      },
      button_horizontal_padding: {
        required,
        integer,
        minValue: minValue(minMax.button_horizontal_padding.min),
        maxValue: maxValue(minMax.button_horizontal_padding.max),
      },
      button_vertical_padding: {
        required,
        integer,
        minValue: minValue(minMax.button_vertical_padding.min),
        maxValue: maxValue(minMax.button_vertical_padding.max),
      },
    },
  },
}
</script>
