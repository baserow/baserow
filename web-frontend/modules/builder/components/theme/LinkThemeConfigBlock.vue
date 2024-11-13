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
          <FontFamilySelector v-model="v$.link_font_family.$model" />
          <template #after-input>
            <ResetButton
              v-model="v$.link_font_family.$model"
              :default-value="theme?.link_font_family"
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
          <HorizontalAlignmentsSelector
            v-model="v$.link_text_alignment.$model"
          />
          <template #after-input>
            <ResetButton
              v-model="v$.link_text_alignment.$model"
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
            v-model="v$.link_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.link_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.link_text_color.$model"
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
            v-model="v$.link_hover_text_color.$model"
            :color-variables="colorVariables"
            :default-value="theme?.link_hover_text_color"
            small
          />
          <template #after-input>
            <ResetButton
              v-model="v$.link_hover_text_color.$model"
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'
import ResetButton from '@baserow/modules/builder/components/theme/ResetButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'
import FontFamilySelector from '@baserow/modules/builder/components/FontFamilySelector'

export default {
  name: 'LinkThemeConfigBlock',
  components: {
    ThemeConfigBlockSection,
    ResetButton,
    HorizontalAlignmentsSelector,
    FontFamilySelector,
  },
  mixins: [themeConfigBlock],
  data() {
    return {
      v$: null,
      values: null,
    }
  },
  created() {
    const values = reactive({
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
      link_font_family: this.theme?.link_font_family,
    })

    const rules = computed(() => ({
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
      link_font_family: {},
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    isAllowedKey(key) {
      return key.startsWith('link_')
    },
  },
}
</script>
