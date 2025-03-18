<template>
  <form @submit.prevent @keydown.enter.prevent>
    <ThemeConfigBlockSection
      v-if="showBody"
      :title="$t('typographyThemeConfigBlock.bodyLabel')"
    >
      <template #default>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('typographyThemeConfigBlock.fontFamily')"
        >
          <FontFamilySelector v-model="v$.values.body_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.values.body_font_family.$model"
              :default-value="theme?.body_font_family"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('typographyThemeConfigBlock.weight')"
        >
          <FontWeightSelector
            v-model="v$.values.body_font_weight.$model"
            :font="v$.values.body_font_family.$model"
          />
          <template #after-input>
            <ResetButton
              v-if="values.body_font_family === theme?.body_font_family"
              v-model="v$.values.body_font_weight.$model"
              :default-value="theme?.body_font_weight"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('typographyThemeConfigBlock.size')"
          :error-message="v$.values[`body_font_size`].$errors[0]?.$message"
        >
          <PixelValueSelector
            v-model="v$.values.body_font_size.$model"
            :default-value-when-empty="defaultValuesWhenEmpty[`body_font_size`]"
            class="typography-theme-config-block__input-number"
            @blur="v$.values[`body_font_size`].$touch"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.values.body_font_size.$model"
              :default-value="theme?.body_font_size"
            />
          </template>
        </FormGroup>
        <FormGroup
          v-if="!extraArgs?.noAlignment"
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('typographyThemeConfigBlock.textAlignment')"
        >
          <HorizontalAlignmentsSelector v-model="values.body_text_alignment" />
          <template #after-input>
            <ResetButton
              v-model="values.body_text_alignment"
              :default-value="theme?.body_text_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('typographyThemeConfigBlock.color')"
        >
          <ColorInput
            v-model="values['body_text_color']"
            :color-variables="colorVariables"
            :default-value="theme ? theme['body_text_color'] : null"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="values.body_text_color"
              :default-value="theme?.body_text_color"
            />
          </template>
        </FormGroup>
      </template>
      <template #preview>
        <ABParagraph>
          Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
          eiusmod tempor incididunt ut labore et dolore magna aliqua.
        </ABParagraph>
      </template>
    </ThemeConfigBlockSection>
    <template v-if="showHeadings">
      <ThemeConfigBlockSection
        v-for="level in headings"
        :key="level"
        :title="$t('typographyThemeConfigBlock.headingLabel', { i: level })"
      >
        <template #default>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.fontFamily')"
          >
            <FontFamilySelector
              v-model="values[`heading_${level}_font_family`]"
            />
            <template #after-input>
              <ResetButton
                v-model="values[`heading_${level}_font_family`]"
                :default-value="theme?.[`heading_${level}_font_family`]"
              />
            </template>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.weight')"
          >
            <FontWeightSelector
              v-model="values[`heading_${level}_font_weight`]"
              :font="values[`heading_${level}_font_family`]"
            />
            <template #after-input>
              <ResetButton
                v-if="
                  values[`heading_${level}_font_family`] ===
                  theme?.[`heading_${level}_font_family`]
                "
                v-model="values[`heading_${level}_font_weight`]"
                :default-value="theme?.[`heading_${level}_font_weight`]"
              />
            </template>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.size')"
            :error-message="
              v$.values[`heading_${level}_font_size`].$errors[0]?.$message
            "
          >
            <PixelValueSelector
              v-model="v$.values[`heading_${level}_font_size`].$model"
              :default-value-when-empty="
                defaultValuesWhenEmpty[`heading_${level}_font_size`]
              "
              class="typography-theme-config-block__input-number"
              @blur="v$.values[`heading_${level}_font_size`].$touch()"
            />
            <template #after-input>
              <ResetButton
                v-model="v$.values[`heading_${level}_font_size`].$model"
                :default-value="theme?.[`heading_${level}_font_size`]"
              />
            </template>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.textAlignment')"
          >
            <HorizontalAlignmentsSelector
              v-model="values[`heading_${level}_text_alignment`]"
            />
            <template #after-input>
              <ResetButton
                v-model="values[`heading_${level}_text_alignment`]"
                :default-value="theme?.[`heading_${level}_text_alignment`]"
              />
            </template>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.color')"
          >
            <ColorInput
              v-model="values[`heading_${level}_text_color`]"
              :color-variables="colorVariables"
              :default-value="
                theme ? theme[`heading_${level}_text_color`] : null
              "
              small
            />
            <template #after-input>
              <ResetButton
                v-model="values[`heading_${level}_text_color`]"
                :default-value="theme?.[`heading_${level}_text_color`]"
              />
            </template>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.decoration')"
          >
            <TextDecorationSelector
              v-model="values[`heading_${level}_text_decoration`]" />
            <template #after-input>
              <ResetButton
                v-model="values[`heading_${level}_text_decoration`]"
                :default-value="theme?.[`heading_${level}_text_decoration`]"
              /> </template
          ></FormGroup>
        </template>
        <template #preview>
          <ABHeading
            class="typography-theme-config-block__heading-preview"
            :level="level"
          >
            {{ $t('typographyThemeConfigBlock.headingValue', { i: level }) }}
          </ABHeading>
        </template>
      </ThemeConfigBlockSection>
    </template>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import FontWeightSelector from '@baserow/modules/builder/components/FontWeightSelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'
import TextDecorationSelector from '@baserow/modules/builder/components/TextDecorationSelector'
import { DEFAULT_FONT_SIZE_PX } from '@baserow/modules/builder/defaultStyles'

const fontSizeMin = 1
const fontSizeMax = 100
const bodyFontSizeMax = 30
const headings = [1, 2, 3, 4, 5, 6]

export default {
  name: 'TypographyThemeConfigBlock',
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
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        body_font_size: 0,
        body_text_color: '',
        body_font_weight: '',
        body_font_family: '',
        body_text_alignment: '',
        ...headings.reduce((o, i) => {
          o[`heading_${i}_font_size`] = 0
          o[`heading_${i}_text_color`] = ''
          o[`heading_${i}_font_family`] = ''
          o[`heading_${i}_font_weight`] = ''
          o[`heading_${i}_text_alignment`] = ''
          o[`heading_${i}_text_decoration`] = [false, false, false]
          return o
        }, {}),
      },
      defaultValuesWhenEmpty: {
        body_font_size: DEFAULT_FONT_SIZE_PX,
        heading_1_font_size: 24,
        heading_2_font_size: 20,
        heading_3_font_size: 16,
        heading_4_font_size: 16,
        heading_5_font_size: 14,
        heading_6_font_size: 14,
      },
    }
  },
  computed: {
    headings() {
      if (this.extraArgs?.headingLevel) {
        return [this.extraArgs.headingLevel]
      } else {
        return headings
      }
    },
    showBody() {
      return !this.extraArgs?.headingLevel
    },
    showHeadings() {
      return !this.extraArgs?.onlyBody
    },
    fontSizeMin() {
      return fontSizeMin
    },
    fontSizeMax() {
      return fontSizeMax
    },
    bodyFontSizeMax() {
      return bodyFontSizeMax
    },
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('heading_') || key.startsWith('body_')
    },
  },
  validations() {
    return {
      values: {
        ...headings.reduce((o, i) => {
          o[`heading_${i}_font_size`] = {
            required: helpers.withMessage(
              this.$t('error.requiredField'),
              required
            ),
            integer: helpers.withMessage(
              this.$t('error.integerField'),
              integer
            ),
            minValue: helpers.withMessage(
              this.$t('error.minValueField', { min: fontSizeMin }),
              minValue(fontSizeMin)
            ),
            maxValue: helpers.withMessage(
              this.$t('error.maxValueField', { max: fontSizeMax }),
              maxValue(fontSizeMax)
            ),
          }
          return o
        }, {}),
        body_font_size: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: fontSizeMin }),
            minValue(fontSizeMin)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: bodyFontSizeMax }),
            maxValue(bodyFontSizeMax)
          ),
        },
        body_font_family: {},
        body_font_weight: {},
      },
    }
  },
}
</script>
