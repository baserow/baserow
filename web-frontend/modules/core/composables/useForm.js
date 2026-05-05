import {
  inject,
  nextTick,
  onBeforeUnmount,
  provide,
  ref,
  unref,
  watch,
} from 'vue'
import get from 'lodash/get'

import { clone } from '@baserow/modules/core/utils/object'

const formParentKey = Symbol('formParentKey')

export function useForm({
  defaultValues,
  values,
  allowedValues = null,
  emit,
  v$ = null,
  emitChange = null,
  root = null,
  selectedFieldIsDeactivated = false,
}) {
  const parentForm = inject(formParentKey, null)
  const emitValues = ref(true)
  const skipFirstValuesEmit = ref(false)
  const registeredChildForms = ref([])

  const getVuelidateField = (fieldName) => {
    const vuelidate = unref(v$)
    if (!vuelidate) {
      return null
    }

    return (
      get(vuelidate, fieldName) ?? get(vuelidate, `values.${fieldName}`) ?? null
    )
  }

  const isAllowedKey = (key) => {
    const currentAllowedValues = unref(allowedValues)
    if (currentAllowedValues !== null) {
      return currentAllowedValues.includes(key)
    }
    return true
  }

  const getCurrentDefaultValues = () => {
    const currentDefaultValues = unref(defaultValues) ?? {}

    return Object.keys(currentDefaultValues).reduce((result, key) => {
      if (isAllowedKey(key)) {
        let value = currentDefaultValues[key]

        if (
          Array.isArray(value) ||
          (typeof value === 'object' && value !== null)
        ) {
          value = clone(value)
        }

        result[key] = value
      }
      return result
    }, {})
  }

  Object.assign(values, getCurrentDefaultValues())

  const formApi = {
    emitValues,
    skipFirstValuesEmit,
    registeredChildForms,
    registerChildForm(childForm) {
      if (!registeredChildForms.value.includes(childForm)) {
        registeredChildForms.value.push(childForm)
      }
    },
    unregisterChildForm(childForm) {
      const index = registeredChildForms.value.indexOf(childForm)
      if (index !== -1) {
        registeredChildForms.value.splice(index, 1)
      }
    },
    isAllowedKey,
    getDefaultValues: getCurrentDefaultValues,
    focusOnFirstError() {
      const element = unref(root)?.$el ?? unref(root)
      const firstError = element?.querySelector?.('[data-form-error]')
      if (firstError) {
        firstError.scrollIntoView({ behavior: 'smooth' })
      }
    },
    getChildForms(predicate = (child) => 'isFormValid' in child, deep = false) {
      const children = []

      const processChildren = (forms, depth = 0) => {
        for (const form of unref(forms) ?? []) {
          if (predicate(form)) {
            children.push(form)
          }

          if (deep && depth < 10 && form.registeredChildForms) {
            processChildren(form.registeredChildForms, depth + 1)
          }
        }
      }

      processChildren(registeredChildForms.value)
      return children
    },
    touch(deep = false) {
      unref(v$)?.$touch()

      for (const child of formApi.getChildForms(
        (child) => 'touch' in child,
        deep
      )) {
        child.touch(deep)
      }
    },
    submit(deep = false) {
      if (unref(selectedFieldIsDeactivated)) {
        return
      }

      formApi.touch(deep)

      if (formApi.isFormValid(deep)) {
        emit?.('submitted', formApi.getFormValues(deep))
      } else {
        nextTick(() => formApi.focusOnFirstError())
      }
    },
    fieldHasErrors(fieldName) {
      return getVuelidateField(fieldName)?.$error || false
    },
    getFirstErrorMessage(fieldName) {
      return getVuelidateField(fieldName)?.$errors?.[0]?.$message
    },
    isFormValid(deep = false) {
      const thisFormInvalid = Boolean(unref(v$)?.$invalid)
      return !thisFormInvalid && formApi.areChildFormsValid(deep)
    },
    areChildFormsValid(deep = false) {
      return formApi
        .getChildForms((child) => 'isFormValid' in child, deep)
        .every((child) => child.isFormValid())
    },
    getFormValues(deep = false) {
      return Object.assign({}, values, formApi.getChildFormsValues(deep))
    },
    getChildFormsValues(deep = false) {
      const children = formApi.getChildForms(
        (child) => 'getChildFormsValues' in child,
        deep
      )
      return Object.assign(
        {},
        ...children.map((child) => child.getFormValues(deep))
      )
    },
    isDirty() {
      for (const [key, value] of Object.entries(getCurrentDefaultValues())) {
        if (values[key] !== value) {
          return true
        }
      }
      return false
    },
    async reset(deep = false) {
      Object.assign(values, getCurrentDefaultValues())

      unref(v$)?.$reset()

      await nextTick()

      formApi
        .getChildForms((child) => 'reset' in child, deep)
        .forEach((child) => child.reset())
    },
    setEmitValues(value) {
      emitValues.value = value
      formApi
        .getChildForms((child) => 'setEmitValues' in child, true)
        .forEach((child) => child.setEmitValues(value))
    },
    handleErrorByForm(error, deep = false) {
      let childHandledIt = false
      const children = formApi.getChildForms(
        (child) => 'handleErrorByForm' in child,
        deep
      )
      for (const child of children) {
        if (child.handleErrorByForm(error)) {
          childHandledIt = true
        }
      }
      return childHandledIt
    },
    emitChange(newValues) {
      if (emitChange) {
        emitChange(newValues)
        return
      }

      emit?.('values-changed', newValues)
    },
  }

  provide(formParentKey, formApi)

  if (typeof parentForm?.registerChildForm === 'function') {
    parentForm.registerChildForm(formApi)
  }

  onBeforeUnmount(() => {
    if (typeof parentForm?.unregisterChildForm === 'function') {
      parentForm.unregisterChildForm(formApi)
    }
  })

  watch(
    values,
    (newValues) => {
      if (skipFirstValuesEmit.value) {
        skipFirstValuesEmit.value = false
        return
      }

      if (emitValues.value) {
        formApi.emitChange(newValues)
      }
    },
    { deep: true }
  )

  return formApi
}
