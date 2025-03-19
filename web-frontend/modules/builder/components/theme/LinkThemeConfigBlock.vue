<template>
  <form @submit.prevent @keydown.enter.prevent>
    <ThemeConfigBlockSection>
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.fontFamily')"
        >
          <FontFamilySelector v-model="v$.values.link_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.values.link_font_family.$model"
              :default-value="theme?.link_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.weight')"
        >
          <FontWeightSelector
            v-model="values.link_font_weight"
            :font="values.link_font_family"
          />
          <template #after-input>
            <ResetButton
              v-if="values.link_font_family === theme?.link_font_family"
              v-model="values.link_font_weight"
              :default-value="theme?.link_font_weight"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          :label="$t('linkThemeConfigBlock.size')"
          :error="v$.values.link_font_size.$error"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="v$.values.link_font_size.$model"
            :default-value-when-empty="defaultValuesWhenEmpty[`link_font_size`]"
          />
          <template #after-input>
            <ResetButton
              v-model="values.link_font_size"
              :default-value="theme?.link_font_size"
            />
          </template>

          <template #error>
            {{ v$.values.link_font_size.$errors[0].$message }}
          </template>
        </FormGroup>
        <FormGroup
          v-if="!extraArgs?.noAlignment"
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.alignment')"
        >
          <HorizontalAlignmentsSelector
            v-model="v$.values.link_text_alignment.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.link_text_alignment.$model"
              :default-value="theme?.link_text_alignment"
            />
          </template>
        </FormGroup>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('linkThemeConfigBlock.defaultState')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.color')"
        >
          <ColorInput
            v-model="v$.values.link_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.link_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.link_text_color.$model"
              :default-value="theme?.link_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.decoration')"
        >
          <TextDecorationSelector
            v-model="values.link_default_text_decoration"
          />
          <template #after-input>
            <ResetButton
              v-model="values.link_default_text_decoration"
              :default-value="theme?.link_default_text_decoration"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABLink url="">{{ $t('linkThemeConfigBlock.link') }}</ABLink>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('linkThemeConfigBlock.hoverState')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.color')"
        >
          <ColorInput
            v-model="v$.values.link_hover_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.link_hover_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.link_hover_text_color.$model"
              :default-value="theme?.link_hover_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.decoration')"
        >
          <TextDecorationSelector v-model="values.link_hover_text_decoration" />
          <template #after-input>
            <ResetButton
              v-model="values.link_hover_text_decoration"
              :default-value="theme?.link_hover_text_decoration"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABLink url="" class="ab-link--force-hover">
          {{ $t('linkThemeConfigBlock.link') }}
        </ABLink>
      </template>
    </ThemeConfigBlockSection>
    <ThemeConfigBlockSection :title="$t('linkThemeConfigBlock.activeState')">
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          required
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.color')"
        >
          <ColorInput
            v-model="v$.values.link_active_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.link_active_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.link_active_text_color.$model"
              :default-value="theme?.link_active_text_color"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('linkThemeConfigBlock.decoration')"
        >
          <TextDecorationSelector
            v-model="values.link_active_text_decoration"
          />
          <template #after-input>
            <ResetButton
              v-model="values.link_active_text_decoration"
              :default-value="theme?.link_active_text_decoration"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABLink url="" class="ab-link--force-active">
          {{ $t('linkThemeConfigBlock.link') }}
        </ABLink>
      </template>
    </ThemeConfigBlockSection>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import FontWeightSelector from '@baserow/modules/builder/components/FontWeightSelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import TextDecorationSelector from '@baserow/modules/builder/components/TextDecorationSelector'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'
import { DEFAULT_FONT_SIZE_PX } from '@baserow/modules/builder/defaultStyles'

const minMax = {
  link_font_size: {
    min: 1,
    max: 100,
  },
}

export default {
  name: 'LinkThemeConfigBlock',
  components: {
    ThemeConfigBlockSection,
    ResetButton,
    HorizontalAlignmentsSelector,
    FontFamilySelector,
    FontWeightSelector,
    PixelValueSelector,
    TextDecorationSelector,
  },
  mixins: [themeConfigBlock],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      defaultValuesWhenEmpty: {
        link_font_size: DEFAULT_FONT_SIZE_PX,
      },
      values: {
        primary_color: this.theme?.primary_color,
        secondary_color: this.theme?.secondary_color,
        border_color: this.theme?.border_color,
        main_success_color: this.theme?.main_success_color,
        main_warning_color: this.theme?.main_warning_color,
        main_error_color: this.theme?.main_error_color,
        text_color: this.theme?.text_color,
        hover_text_color: this.theme?.hover_text_color,
        font_family: this.theme?.font_family,
        link_text_color: this.theme?.link_text_color,
        link_text_alignment: this.theme?.link_text_alignment,
        link_hover_text_color: this.theme?.link_hover_text_color,
        link_active_text_color: this.theme?.link_active_text_color,
        link_font_family: this.theme?.link_font_family,
        link_font_weight: this.theme?.link_font_weight,
        link_font_size: this.theme?.link_font_size,
        link_default_text_decoration: this.theme?.link_default_text_decoration,
        link_hover_text_decoration: this.theme?.link_hover_text_decoration,
        link_active_text_decoration: this.theme?.link_active_text_decoration,
      },
    }
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('link_')
    },
  },
  validations() {
    return {
      values: {
        link_font_size: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minMaxValueField', minMax.link_font_size),
            minValue(minMax.link_font_size.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.minMaxValueField', minMax.link_font_size),
            maxValue(minMax.link_font_size.max)
          ),
        },
        primary_color: {},
        secondary_color: {},
        border_color: {},
        main_success_color: {},
        main_warning_color: {},
        main_error_color: {},
        text_color: {},
        hover_text_color: {},
        font_family: {},
        link_text_color: {},
        link_text_alignment: {},
        link_hover_text_color: {},
        link_active_text_color: {},
        link_font_family: {},
        link_font_weight: {},
        link_default_text_decoration: {},
        link_hover_text_decoration: {},
        link_active_text_decoration: {},
      },
    }
  },
}
</script>
