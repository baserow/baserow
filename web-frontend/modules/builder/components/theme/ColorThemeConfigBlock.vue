<template>
  <ThemeConfigBlockSection>
    <template #default>
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('colorThemeConfigBlock.primaryColor')"
      >
        <ColorInput v-model="v$.primary_color.$model" small />
      </FormGroup>
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('colorThemeConfigBlock.secondaryColor')"
      >
        <ColorInput v-model="v$.secondary_color.$model" small />
      </FormGroup>
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('colorThemeConfigBlock.borderColor')"
      >
        <ColorInput v-model="v$.border_color.$model" small />
      </FormGroup>
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('colorThemeConfigBlock.successColor')"
      >
        <ColorInput v-model="v$.main_success_color.$model" small />
      </FormGroup>
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('colorThemeConfigBlock.warningColor')"
      >
        <ColorInput v-model="v$.main_warning_color.$model" small />
      </FormGroup>
      <FormGroup
        horizontal-narrow
        small-label
        class="margin-bottom-2"
        :label="$t('colorThemeConfigBlock.errorColor')"
      >
        <ColorInput v-model="v$.main_error_color.$model" small />
      </FormGroup>
    </template>
  </ThemeConfigBlockSection>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import themeConfigBlock from '@baserow/modules/builder/mixins/themeConfigBlock'
import ThemeConfigBlockSection from '@baserow/modules/builder/components/theme/ThemeConfigBlockSection'

export default {
  name: 'ColorThemeConfigBlock',
  components: { ThemeConfigBlockSection },
  mixins: [themeConfigBlock],
  data() {
    return {
      values: null,
      v$: null,
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
    })

    const rules = computed(() => ({
      primary_color: {},
      secondary_color: {},
      border_color: {},
      main_success_color: {},
      main_warning_color: {},
      main_error_color: {},
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    isAllowedKey(key) {
      return (
        key.startsWith('main_') ||
        ['primary_color', 'secondary_color', 'border_color'].includes(key)
      )
    },
  },
}
</script>
