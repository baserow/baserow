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
          <FontFamilySelector v-model="values.link_font_family" />
          <template #after-input>
            <ResetButton
              v-model="values.link_font_family"
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
          :error-message="getError('link_font_size')"
          class="margin-bottom-2"
        >
          <PixelValueSelector
            v-model="values.link_font_size"
            :default-value-when-empty="defaultValuesWhenEmpty[`link_font_size`]"
          />
          <template #after-input>
            <ResetButton
              v-model="values.link_font_size"
              :default-value="theme?.link_font_size"
            />
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
          <HorizontalAlignmentsSelector v-model="values.link_text_alignment" />
          <template #after-input>
            <ResetButton
              v-model="values.link_text_alignment"
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
            v-model="values.link_text_color"
            :color-variables="colorVariables"
            :default-value="theme?.link_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.link_text_color"
              :default-value="theme?.link_text_color"
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
            v-model="values.link_hover_text_color"
            :color-variables="colorVariables"
            :default-value="theme?.link_hover_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.link_hover_text_color"
              :default-value="theme?.link_hover_text_color"
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
  </form>
</template>

<script>
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import FontWeightSelector from '@baserow/modules/builder/components/FontWeightSelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import { required, integer, minValue, maxValue } from 'vuelidate/lib/validators'
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
  },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
      defaultValuesWhenEmpty: {
        link_font_size: DEFAULT_FONT_SIZE_PX,
      },
    }
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('link_')
    },
    getError(property) {
      if (this.$v.values[property].$invalid) {
        return this.$t('error.minMaxValueField', minMax[property])
      }
      return null
    },
  },
  validations: {
    values: {
      link_font_size: {
        required,
        integer,
        minValue: minValue(minMax.link_font_size.min),
        maxValue: maxValue(minMax.link_font_size.max),
      },
    },
  },
}
</script>
