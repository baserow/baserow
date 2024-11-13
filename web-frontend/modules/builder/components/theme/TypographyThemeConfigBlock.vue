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
          <FontFamilySelector v-model="v$.body_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.body_font_family.$model"
              :default-value="theme?.body_font_family"
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
          <HorizontalAlignmentsSelector
            v-model="v$.body_text_alignment.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.body_text_alignment.$model"
              :default-value="theme?.body_text_alignment"
            />
          </template>
        </FormGroup>
        <FormGroup
          horizontal-narrow
          small-label
          class="margin-bottom-2"
          :label="$t('typographyThemeConfigBlock.size')"
          :error-message="
            v$[`body_font_size`].$invalid
              ? $t('error.minMaxValueField', {
                  min: fontSizeMin,
                  max: bodyFontSizeMax,
                })
              : ''
          "
        >
          <PixelValueSelector
            v-model="v$.body_font_size.$model"
            class="typography-theme-config-block__input-number"
            @blur="v$[`body_font_size`].$touch"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.body_font_size.$model"
              :default-value="theme?.body_font_size"
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
            v-model="v$['body_text_color'].$value"
            :color-variables="colorVariables"
            :default-value="theme ? theme['body_text_color'] : null"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.body_text_color.$model"
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
              v-model="v$[`heading_${level}_font_family`].$model"
            />
            <template #after-input>
              <ResetButton
                v-model="v$[`heading_${level}_font_family`].$model"
                :default-value="theme?.[`heading_${level}_font_family`]"
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
              v-model="v$[`heading_${level}_text_alignment`].$model"
            />
            <template #after-input>
              <ResetButton
                v-model="v$[`heading_${level}_text_alignment`].$model"
                :default-value="theme?.[`heading_${level}_text_alignment`]"
              />
            </template>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.size')"
            :error="v$[`heading_${level}_font_size`].$error"
          >
            <PixelValueSelector
              v-model="v$[`heading_${level}_font_size`].$model"
              class="typography-theme-config-block__input-number"
              @blur="v$[`heading_${level}_font_size`].$touch()"
            />
            <template #after-input>
              <ResetButton
                v-model="v$[`heading_${level}_font_size`].$model"
                :default-value="theme?.[`heading_${level}_font_size`]"
              />
            </template>
            <template #error>
              <span
                v-if="
                  v$[`heading_${level}_font_size`].minValue.$invalid ||
                  v$[`heading_${level}_font_size`].maxValue.$invalid
                "
              >
                {{
                  $t('error.minMaxValueField', {
                    min: fontSizeMin,
                    max: fontSizeMax,
                  })
                }}
              </span>
            </template>
          </FormGroup>
          <FormGroup
            horizontal-narrow
            small-label
            class="margin-bottom-2"
            :label="$t('typographyThemeConfigBlock.color')"
          >
            <ColorInput
              v-model="v$[`heading_${level}_text_color`].$model"
              :color-variables="colorVariables"
              :default-value="
                theme ? theme[`heading_${level}_text_color`] : null
              "
              small
            />
            <template #after-input>
              <ResetButton
                v-model="v$[`heading_${level}_text_color`].$model"
                :default-value="theme?.[`heading_${level}_text_color`]"
              />
            </template>
          </FormGroup>
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
import { reactive, computed } from 'vue'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'

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
    PixelValueSelector,
  },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: {},
      v$: null,
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
  created() {
    const values = reactive({
      body_font_size: 0,
      body_text_color: '',
      body_font_family: '',
      body_text_alignment: '',
      ...headings.reduce((o, i) => {
        o[`heading_${i}_font_size`] = 0
        o[`heading_${i}_text_color`] = ''
        o[`heading_${i}_font_family`] = ''
        o[`heading_${i}_text_alignment`] = ''
        return o
      }, {}),
    })

    const rules = computed(() => ({
      body_font_size: {
        required,
        integer,
        minValue: minValue(fontSizeMin),
        maxValue: maxValue(bodyFontSizeMax),
      },
      body_text_color: {
        required,
      },
      body_font_family: {
        required,
      },
      body_text_alignment: {
        required,
      },
      ...headings.reduce((o, i) => {
        o[`heading_${i}_font_size`] = {
          required,
          integer,
          minValue: minValue(fontSizeMin),
          maxValue: maxValue(fontSizeMax),
        }
        o[`heading_${i}_text_color`] = {
          required,
        }
        o[`heading_${i}_font_family`] = {
          required,
        }
        o[`heading_${i}_text_alignment`] = {
          required,
        }
        return o
      }, {}),
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('heading_') || key.startsWith('body_')
    },
  },
}
</script>
