import formDataStore from '@baserow/modules/builder/store/formData'

describe('formData store', () => {
  test('removeFormData deletes a repeated form data entry by unique element id', () => {
    const page = {}
    const commit = (mutation, payload) => {
      formDataStore.mutations[mutation](formDataStore.state, payload)
    }

    formDataStore.actions.setFormData(
      { commit },
      {
        page,
        uniqueElementId: '42.0',
        payload: {
          value: 'first',
          elementId: 42,
        },
      }
    )
    formDataStore.actions.setFormData(
      { commit },
      {
        page,
        uniqueElementId: '42.1',
        payload: {
          value: 'second',
          elementId: 42,
        },
      }
    )

    formDataStore.actions.removeFormData(
      { commit },
      {
        page,
        uniqueElementId: '42.0',
      }
    )

    expect(page.formData).toStrictEqual({
      42: [
        {
          value: 'second',
          elementId: 42,
        },
      ],
    })
  })

  test('removeFormData deletes all form data for an element', () => {
    const page = {
      formData: {
        42: [
          {
            value: 'first',
            elementId: 42,
          },
        ],
        43: {
          value: 'other',
          elementId: 43,
        },
      },
    }
    const commit = (mutation, payload) => {
      formDataStore.mutations[mutation](formDataStore.state, payload)
    }

    formDataStore.actions.removeFormData(
      { commit },
      {
        page,
        uniqueElementId: '42',
      }
    )

    expect(page.formData).toStrictEqual({
      43: {
        value: 'other',
        elementId: 43,
      },
    })
  })
})
