<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-if="v$.level.$model"
      v-model="v$.styles.$model"
      style-key="typography"
      :config-block-types="['typography']"
      :theme="builder.theme"
      :extra-args="{ headingLevel: values.level }"
    />
    <FormGroup
      small-label
      required
      :label="$t('headingElementForm.levelTitle')"
      class="margin-bottom-2"
    >
      <Dropdown v-model="v$.level.$model" :show-search="false">
        <DropdownItem
          v-for="level in levels"
          :key="level.value"
          :name="level.name"
          :value="level.value"
        >
          {{ level.name }}
        </DropdownItem>
      </Dropdown>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('headingElementForm.textTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="v$.value.$model"
        :placeholder="$t('elementForms.textInputPlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'

export default {
  name: 'HeaderElementForm',
  components: {
    InjectedFormulaInput,
    CustomStyle,
  },
  mixins: [elementForm],
  data() {
    return {
      v$: null,
      values: null,
      levels: [...Array(6).keys()].map((level) => ({
        name: this.$t('headingElementForm.headingName', { level: level + 1 }),
        value: level + 1,
      })),
      allowedValues: ['value', 'level', 'styles'],
    }
  },
  created() {
    const values = reactive({
      styles: {},
      level: 1,
      value: '',
    })

    const rules = computed(() => ({
      styles: {},
      level: {},
      value: {},
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
