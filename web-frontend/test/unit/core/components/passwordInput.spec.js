import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'
import { bootstrapVueContext } from '@baserow/test/helpers/components'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { passwordValidation } from '@baserow/modules/core/validators'

describe('Password Input Tests', () => {
  let vueContext = null

  beforeEach(() => {
    vueContext = bootstrapVueContext()
  })

  afterEach(() => {
    vueContext.teardownVueContext()
  })

  function mountPasswordInputWithParentState() {
    const parent = {
      data() {
        return { v$: null }
      },
      created() {
        const values = reactive({
          password: '',
        })

        const rules = computed(() => ({
          password: passwordValidation,
        }))
        this.v$ = useVuelidate(rules, values, { $lazy: true })
        this.values = values
      },
      template:
        '<div> <password-input v-model="v$.password.$model" :validation-state="v$.password"></password-input> </div>',
      components: { 'password-input': PasswordInput },
    }
    return vueContext.vueTestUtils.mount(parent, {
      localVue: vueContext.vue,
    })
  }

  async function changePassword(wrapper, passwordValue) {
    const passwordInputComponent = wrapper.findComponent(PasswordInput)
    const passwordInputs = passwordInputComponent.findAll('input')

    passwordInputs.at(0).element.value = passwordValue
    await passwordInputs.at(0).trigger('input')
  }

  test('Correct password does not render error div', async () => {
    const password = 'thisIsAValidPassword'
    const wrapper = mountPasswordInputWithParentState()
    await changePassword(wrapper, password)
    await wrapper.vm.v$.password.$touch()
    const inputInvalid = wrapper.vm.v$.$invalid
    expect(inputInvalid).toBeFalsy()
  })

  test('Password must be minimum of 8 characters', async () => {
    const password = 'short'
    const wrapper = mountPasswordInputWithParentState()
    await changePassword(wrapper, password)

    await wrapper.vm.v$.password.$touch()
    const inputInvalid = wrapper.vm.v$.$invalid
    expect(inputInvalid).toBeTruthy()
  })

  test('Password cannot be empty', async () => {
    const password = ''
    const wrapper = mountPasswordInputWithParentState()
    await changePassword(wrapper, password)

    await wrapper.vm.v$.password.$touch()
    const inputInvalid = wrapper.vm.v$.$invalid
    expect(inputInvalid).toBeTruthy()
  })

  test('Password cannot be more than 256 characters', async () => {
    const password = 't'.repeat(257)
    const wrapper = mountPasswordInputWithParentState()
    await changePassword(wrapper, password)

    await wrapper.vm.v$.password.$touch()
    const inputInvalid = wrapper.vm.v$.$invalid
    expect(inputInvalid).toBeTruthy()
  })

  test('Password can be exactly 256 characters', async () => {
    const password = 't'.repeat(256)
    const wrapper = mountPasswordInputWithParentState()
    await changePassword(wrapper, password)

    await wrapper.vm.v$.password.$touch()
    const inputInvalid = wrapper.vm.v$.$invalid
    expect(inputInvalid).toBeFalsy()
  })

  test('Password can be exactly 8 characters', async () => {
    const password = 't'.repeat(8)
    const wrapper = mountPasswordInputWithParentState()
    await changePassword(wrapper, password)

    await wrapper.vm.v$.password.$touch()
    const inputInvalid = wrapper.vm.v$.$invalid
    expect(inputInvalid).toBeFalsy()
  })
})
