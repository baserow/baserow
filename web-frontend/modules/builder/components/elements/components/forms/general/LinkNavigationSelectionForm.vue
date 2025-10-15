<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('linkNavigationSelection.navigateTo')"
      small-label
      class="margin-bottom-2"
      required
    >
      <Dropdown v-model="navigateTo" :show-search="false">
        <template #selectedValue>
          <template v-if="destinationPage">
            <span
              v-tooltip:[tooltipOptions]="destinationPagePathWithParams"
              class="link-navigation-selection-form__navigate-option-page-name"
            >
              {{ destinationPage.name }}
            </span>
            <span
              v-tooltip:[tooltipOptions]="destinationPagePathWithParams"
              class="link-navigation-selection-form__navigate-option-page-path"
            >
              {{ destinationPagePathWithParams }}
            </span>
          </template>
          <span v-else>{{
            $t('linkNavigationSelection.navigateToCustom')
          }}</span>
        </template>

        <DropdownItem
          v-for="pageItem in pages"
          :key="pageItem.id"
          :value="pageItem.id"
          :name="pageItem.name"
        >
          {{ pageItem.name }} {{ getPagePathWithParams(pageItem) }}
        </DropdownItem>
        <DropdownItem
          :name="$t('linkNavigationSelection.navigateToCustom')"
          value="custom"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      v-if="navigateTo === 'custom'"
      class="margin-bottom-2"
      :label="$t('linkNavigationSelection.url')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.navigate_to_url"
        :placeholder="$t('linkNavigationSelection.urlPlaceholder')"
      />
    </FormGroup>
    <FormGroup v-if="destinationPage" class="margin-bottom-2" required>
      <template v-if="parametersInError">
        <Alert type="error">
          <p>
            {{ $t('linkNavigationSelection.paramsInErrorDescription') }}
          </p>
          <template #actions>
            <button
              class="alert__actions-button-text"
              @click.prevent="updatePageParameters"
            >
              {{ $t('linkNavigationSelection.paramsInErrorButton') }}
            </button>
          </template>
        </Alert>
      </template>
      <div v-else>
        <FormGroup
          v-for="param in values.page_parameters"
          :key="param.name"
          small-label
          :label="param.name"
          class="margin-bottom-2"
          required
          horizontal
        >
          <InjectedFormulaInput
            v-model="param.value"
            :placeholder="$t('linkNavigationSelection.paramPlaceholder')"
          />
        </FormGroup>
        <FormGroup
          v-for="param in values.query_parameters"
          :key="param.name"
          small-label
          :label="param.name"
          class="margin-bottom-2"
          required
          horizontal
        >
          <InjectedFormulaInput
            v-model="param.value"
            :placeholder="$t('linkNavigationSelection.paramPlaceholder')"
          />
        </FormGroup>
      </div>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('linkNavigationSelection.target')"
      class="margin-bottom-2"
      required
    >
      <RadioGroup
        v-model="values.target"
        type="button"
        :options="linkNavigationSelectionTargetOptions"
      ></RadioGroup>
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { pathParametersInError } from '@baserow/modules/builder/utils/params'

export default {
  name: 'LinkNavigationSelectionForm',
  components: {
    InjectedFormulaInput,
  },
  mixins: [elementForm],
  data() {
    return {
      parametersInError: false,
      navigateTo: '',
      allowedValues: [
        'navigation_type',
        'navigate_to_page_id',
        'navigate_to_url',
        'page_parameters',
        'query_parameters',
        'target',
      ],
      values: {
        navigation_type: 'page',
        navigate_to_page_id: null,
        navigate_to_url: {},
        page_parameters: [],
        query_parameters: [],
        target: 'self',
      },
      linkNavigationSelectionTargetOptions: [
        { value: 'self', label: this.$t('linkNavigationSelection.targetSelf') },
        {
          value: 'blank',
          label: this.$t('linkNavigationSelection.targetNewTab'),
        },
      ],
      tooltipOptions: {
        contentClasses: ['tooltip__content--expandable'],
      },
    }
  },
  computed: {
    pages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
    destinationPage() {
      if (!isNaN(this.navigateTo)) {
        return this.pages.find(({ id }) => id === this.navigateTo)
      }
      return null
    },
    destinationPagePathWithParams() {
      if (!this.destinationPage) return ''
      return this.getPagePathWithParams(this.destinationPage)
    },
  },
  watch: {
    'destinationPage.path_params': {
      handler(value) {
        this.updatePageParameters()
        this.refreshParametersInError()
      },
      deep: true,
    },
    navigateTo(value) {
      if (value === '') {
        this.values.navigation_type = 'page'
        this.values.navigate_to_page_id = null
        this.values.navigate_to_url = ''
      } else if (value === 'custom') {
        this.values.navigation_type = 'custom'
      } else if (!isNaN(value)) {
        this.values.navigation_type = 'page'
        this.values.navigate_to_page_id = value
        this.updatePageParameters()
      }
    },
    destinationPage(value) {
      this.updatePageParameters()
      // This means that the page select does not exist anymore
      if (value === undefined) {
        this.values.navigate_to_page_id = null
      }
    },
  },
  mounted() {
    if (typeof this.defaultValues.navigation_type !== 'undefined') {
      let navigateTo = ''
      if (this.defaultValues.navigation_type === 'page') {
        if (this.defaultValues.navigate_to_page_id) {
          navigateTo = this.defaultValues.navigate_to_page_id
        }
      } else {
        navigateTo = 'custom'
      }
      this.navigateTo = navigateTo
    }
    this.updatePageParameters()
    this.refreshParametersInError()
  },
  methods: {
    getPagePathWithParams(page) {
      const shortTypes = {
        text: '*',
        numeric: '#',
      }
      let path = page.path
      if (page.query_params.length) {
        path += `?${page.query_params
          .map((p) => `${p.name}=${shortTypes[p.type]}`)
          .join('&')}`
      }
      return path
    },
    refreshParametersInError() {
      this.parametersInError = pathParametersInError(this.values, this.pages)
    },
    updatePageParameters() {
      // Update path parameters
      this.values.page_parameters = (
        this.destinationPage?.path_params || []
      ).map(({ name }, index) => {
        const previousValue = this.values.page_parameters[index]?.value || {}
        return { name, value: previousValue }
      })

      // Update query parameters
      this.values.query_parameters = (
        this.destinationPage?.query_params || []
      ).map(({ name }, index) => {
        const previousValue = this.values.query_parameters[index]?.value || {}
        return { name, value: previousValue }
      })

      this.parametersInError = false
    },
  },
}
</script>
