<template>
  <form @submit.prevent="submit">
    <div class="row margin-bottom-2">
      <div class="col col-6">
        <FormGroup
          required
          small-label
          :label="$t('pageForm.nameTitle')"
          :error-message="getFirstErrorMessage('name')"
          :helper-text="$t('pageForm.nameSubtitle')"
        >
          <FormInput
            ref="name"
            v-model="v$.values.name.$model"
            size="large"
            :placeholder="$t('pageForm.namePlaceholder')"
            :disabled="!hasPermission"
            @blur="v$.values.name.$touch"
            @focus.once="isCreation && $event.target.select()"
          />
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          required
          small-label
          :label="$t('pageForm.pathTitle')"
          :error="fieldHasErrors('path')"
          :error-message="getFirstErrorMessage('path')"
          :helper-text="$t('pageForm.pathSubtitle')"
        >
          <FormInput
            v-model="v$.values.path.$model"
            size="large"
            :placeholder="$t('pageForm.pathPlaceholder')"
            :disabled="!hasPermission"
            @blur="onPathBlur"
          />
        </FormGroup>
      </div>
    </div>
    <div class="row">
      <div class="col col-6">
        <PageSettingsQueryParamsFormElement
          :disabled="!hasPermission"
          :query-params="localQueryParams"
          :has-errors="fieldHasErrors('query_params')"
          :validation-state="v$.values.query_params"
          @update="onQueryParamUpdate"
          @add="addQueryParam"
        />
      </div>
      <div class="col col-6">
        <PageSettingsPathParamsFormElement
          :disabled="!hasPermission"
          :path-params="values.path_params"
          @update="onPathParamUpdate"
        />
      </div>
    </div>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { maxLength, required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import PageSettingsPathParamsFormElement from '@baserow/modules/builder/components/page/settings/PageSettingsPathParamsFormElement'
import PageSettingsQueryParamsFormElement from '@baserow/modules/builder/components/page/settings/PageSettingsQueryParamsFormElement'
import {
  getPathParams,
  PATH_PARAM_REGEX,
  ILLEGAL_PATH_SAMPLE_CHARACTER,
  VALID_PATH_CHARACTERS,
} from '@baserow/modules/builder/utils/path'
import { QUERY_PARAM_REGEX } from '@baserow/modules/builder/utils/params'
import {
  getNextAvailableNameInSequence,
  slugify,
} from '@baserow/modules/core/utils/string'

export default {
  name: 'PageSettingsForm',
  components: {
    PageSettingsPathParamsFormElement,
    PageSettingsQueryParamsFormElement,
  },
  mixins: [form],
  inject: ['workspace', 'builder'],
  props: {
    page: {
      type: Object,
      required: false,
      default: null,
    },
    isCreation: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: '',
        path: '',
        path_params: [],
        query_params: [],
      },
      localQueryParams: [],
      hasPathBeenEdited: false,
    }
  },
  computed: {
    hasPermission() {
      if (this.isCreation) {
        return this.$hasPermission(
          'builder.create_page',
          this.builder,
          this.workspace.id
        )
      } else {
        return this.$hasPermission(
          'builder.page.update',
          this.page,
          this.workspace.id
        )
      }
    },
    defaultPathParamType() {
      return this.$registry.getOrderedList('pathParamType')[0].getType()
    },
    defaultName() {
      const baseName = this.$t('pageForm.defaultName')
      return getNextAvailableNameInSequence(baseName, this.pageNames)
    },
    pages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
    pageNames() {
      return this.pages.map((page) => page.name)
    },
    otherPagePaths() {
      return this.pages
        .filter((page) => page.id !== this.page?.id)
        .map((page) => page.path)
    },
    currentPathParams() {
      if (this.values.path) return getPathParams(this.values.path)
      return []
    },
  },
  watch: {
    // When the path change we want to update the value.path_params value
    // but try to keep the previous configuration as much as possible
    currentPathParams(paramNames, oldParamNames) {
      const result = paramNames.map((param) => ({
        name: param,
        type: 'text',
      }))

      const pathParamIndexesByName = this.values.path_params.reduce(
        (prev, { name }, index) => {
          if (!prev[name]) {
            prev[name] = []
          }
          prev[name].push(index)
          return prev
        },
        {}
      )

      // List of used index of existing params to use them once only.
      const usedIndex = []
      // An index is ok if it has already been associated with an existing param
      // to prevent double association.
      const okIndex = []

      // First match same names at same position
      paramNames.forEach((paramName, index) => {
        if (paramName === oldParamNames[index]) {
          Object.assign(result[index], this.values.path_params[index])
          pathParamIndexesByName[paramName] = pathParamIndexesByName[
            paramName
          ].filter((i) => i !== index)
          usedIndex.push(index)
          okIndex.push(index)
        }
      })

      // Then match previously existing names at another position
      paramNames.forEach((paramName, index) => {
        if (okIndex.includes(index)) {
          return
        }
        if (pathParamIndexesByName[paramName]?.length) {
          const paramIndex = pathParamIndexesByName[paramName].shift()
          Object.assign(result[index], this.values.path_params[paramIndex])
          usedIndex.push(paramIndex)
          okIndex.push(index)
        }
      })

      // Then match remaining existing params in same relative order
      paramNames.forEach((paramName, index) => {
        if (okIndex.includes(index)) {
          return
        }
        const freeIndex = this.values.path_params.findIndex(
          (_, index) => !usedIndex.includes(index)
        )
        if (freeIndex !== -1) {
          Object.assign(result[index], this.values.path_params[freeIndex], {
            name: paramName,
          })
          usedIndex.push(freeIndex)
        }
      })

      this.values.path_params = result
    },
    'values.name': {
      handler(value) {
        if (!this.hasPathBeenEdited && this.isCreation) {
          this.values.path = `/${slugify(value)}`
        }
      },
      immediate: true,
    },
    'values.query_params': {
      handler(newQueryParams) {
        this.localQueryParams = [...newQueryParams]
        // Touch the validation when params change
        if (this.v$.values && this.v$.values.query_params) {
          this.v$.values.query_params.$touch()
        }
      },
      immediate: true,
    },
  },
  created() {
    if (this.isCreation) {
      this.values.name = this.defaultName
    }
  },
  mounted() {
    if (this.isCreation) {
      this.$refs.name.$refs.input.focus()
    }
  },
  methods: {
    generalisePath(path) {
      return path.replace(PATH_PARAM_REGEX, ILLEGAL_PATH_SAMPLE_CHARACTER)
    },
    onPathBlur() {
      this.v$.values.path.$touch()
      this.hasPathBeenEdited = true
    },
    onPathParamUpdate(paramTypeName, paramType) {
      this.values.path_params.forEach((pathParam) => {
        if (pathParam.name === paramTypeName) {
          pathParam.type = paramType
        }
      })
    },
    onQueryParamUpdate(updatedQueryParams) {
      this.localQueryParams = updatedQueryParams
      this.values.query_params = updatedQueryParams
      if (this.v$.values.query_params) {
        this.v$.values.query_params.$touch()
      }
    },
    getFormValues() {
      return Object.assign({}, this.values, this.getChildFormsValues(), {
        query_params: this.localQueryParams,
      })
    },
    addQueryParam(newParam) {
      this.localQueryParams.push(newParam)
    },
    isNameUnique(name) {
      return !this.pageNames.includes(name) || name === this.page?.name
    },
    isPathUnique(path) {
      const pathGeneralised = this.generalisePath(path)
      return (
        !this.otherPagePaths.some(
          (pathCurrent) => this.generalisePath(pathCurrent) === pathGeneralised
        ) || path === this.page?.path
      )
    },
    pathStartsWithSlash(path) {
      return path[0] === '/'
    },
    pathHasValidCharacters(path) {
      return !path
        .split('')
        .some((letter) => !VALID_PATH_CHARACTERS.includes(letter))
    },
    arePathParamsUnique(path) {
      const pathParams = getPathParams(path)
      return new Set(pathParams).size === pathParams.length
    },
    areQueryParamsUnique(queryParams) {
      const uniqueParams = new Set()

      // First check if all query param names match the regex pattern
      for (const param of queryParams) {
        // Create a regex with ^ and $ to ensure full string match
        const fullMatchRegex = new RegExp(`^${QUERY_PARAM_REGEX.source}$`)
        if (!fullMatchRegex.test(param.name)) {
          return false
        }
      }

      // Then check for uniqueness against path params and other query params
      for (const pathParam of this.values.path_params) {
        uniqueParams.add(pathParam.name)
      }

      for (const param of queryParams) {
        if (uniqueParams.has(param.name)) {
          return false
        }
        uniqueParams.add(param.name)
      }

      return true
    },
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          isUnique: helpers.withMessage(
            this.$t('pageErrors.errorNameNotUnique'),
            this.isNameUnique
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(225)
          ),
        },
        query_params: {
          uniqueQueryParams: this.areQueryParamsUnique,
        },
        path: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          isUnique: helpers.withMessage(
            this.$t('pageErrors.errorPathNotUnique'),
            this.isPathUnique
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(225)
          ),
          startingSlash: helpers.withMessage(
            this.$t('pageErrors.errorStartingSlash'),
            this.pathStartsWithSlash
          ),
          validPathCharacters: helpers.withMessage(
            this.$t('pageErrors.errorValidPathCharacters'),
            this.pathHasValidCharacters
          ),
          uniquePathParams: helpers.withMessage(
            this.$t('pageErrors.errorUniquePathParams'),
            this.arePathParamsUnique
          ),
        },
      },
    }
  },
}
</script>
