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
              v-model="v$.button_width.$model"
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
          <HorizontalAlignmentsSelector v-model="v$.button_alignment.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.button_alignment.$model"
              :default-value="theme?.button_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          v-if="v$.button_width.$model === 'full'"
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('buttonThemeConfigBlock.textAlignment')"
        >
          <HorizontalAlignmentsSelector
            v-model="v$.button_text_alignment.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.button_text_alignment.$model"
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
          <FontFamilySelector v-model="v$.button_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.button_font_family.$model"
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
          <PixelValueSelector v-model="v$.button_font_size.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.button_font_size.$model"
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
          <PixelValueSelector v-model="v$.button_border_size.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.button_border_size.$model"
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
          <PixelValueSelector v-model="v$.button_border_radius.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.button_border_radius.$model"
              :default-value="theme?.button_border_radius"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('buttonThemeConfigBlock.padding')"
          :error="
            v$.button_vertical_padding.$error ||
            v$.button_horizontal_padding.$error
          "
          class="margin-bottom-2"
        >
          <PaddingSelector v-model="padding" />
          <template #after-input>
            <ResetButton
              v-model="v$.padding.$model"
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

          <template #error>
            {{ getPaddingError() }}
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
            v-model="v$.button_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.button_background_color.$model"
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
            v-model="v$.button_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.button_text_color.$model"
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
            v-model="v$.button_hover_background_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_background_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.button_hover_background_color.$model"
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
            v-model="v$.button_hover_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.button_hover_text_color.$model"
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
            v-model="v$.button_hover_border_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.button_hover_border_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.button_hover_border_color.$model"
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import WidthSelector from '@baserow/modules/builder/components/WidthSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import PaddingSelector from '@baserow/modules/builder/components/PaddingSelector'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'

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
      values: null,
      v$: null,
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
        this.v$.button_width.$model = value
        if (value === 'auto') {
          this.v$.button_alignment.$model = this.values.button_text_alignment
        } else {
          this.v$.button_text_alignment.$model = this.values.button_alignment
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
        this.v$.button_vertical_padding.$model = newValue.vertical
        this.v$.button_horizontal_padding.$model = newValue.horizontal
      },
    },
    pixedSizeMin() {
      return pixelSizeMin
    },
    pixedSizeMax() {
      return pixelSizeMax
    },
  },
  created() {
    const values = reactive({
      button_font_size: this.theme?.button_font_size,
      button_border_size: this.theme?.button_border_size,
      button_border_radius: this.theme?.button_border_radius,
      button_horizontal_padding: this.theme?.button_horizontal_padding,
      button_vertical_padding: this.theme?.button_vertical_padding,
      button_font_family: this.theme?.button_font_family,
      button_text_alignment: this.theme?.button_text_alignment,
      button_alignment: this.theme?.button_alignment,
      button_text_color: this.theme?.button_text_color,
      button_width: this.theme?.button_width,
      button_background_color: this.theme?.button_background_color,
      button_hover_background_color: this.theme?.button_hover_background_color,
      button_hover_text_color: this.theme?.button_hover_text_color,
      button_hover_border_color: this.theme?.button_hover_border_color,
    })

    const rules = computed(() => ({
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
      button_background_color: {
        required,
      },
      button_hover_background_color: {
        required,
      },
      button_hover_text_color: {
        required,
      },
      button_hover_border_color: {
        required,
      },
      button_font_family: {
        required,
      },
      button_text_color: {
        required,
      },
      button_text_alignment: {
        required,
      },
      button_alignment: {
        required,
      },
      button_width: {
        required,
      },
      padding: {
        required,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('button_')
    },
    getError(property) {
      if (
        this.v$[property].minValue.$invalid ||
        this.v$[property].maxValue.$invalid
      ) {
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
}
</script>
