import { describe, test, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import SubDomainForm from '@baserow/modules/builder/components/domain/SubDomainForm'

describe('SubDomainForm', () => {
  const mountForm = () =>
    mountSuspended(SubDomainForm, { props: { domain: 'test.com' } })

  test('accepts a single label and builds the full domain name', async () => {
    const wrapper = await mountForm()

    await wrapper.find('input').setValue('hello')

    expect(wrapper.vm.values.domain_name).toBe('hello.test.com')
    expect(wrapper.vm.v$.domainPrefix.$error).toBe(false)
    expect(wrapper.vm.isFormValid()).toBe(true)
  })

  test('rejects a name that contains a dot', async () => {
    const wrapper = await mountForm()

    await wrapper.find('input').setValue('hello.world')

    expect(wrapper.vm.v$.domainPrefix.$error).toBe(true)
    expect(wrapper.vm.v$.domainPrefix.noDot.$invalid).toBe(true)
    expect(wrapper.text()).toContain('subDomainForm.noDotError')
    expect(wrapper.vm.isFormValid()).toBe(false)
  })
})
