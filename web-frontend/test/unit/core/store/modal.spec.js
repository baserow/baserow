import { TestApp } from '@baserow/test/helpers/testApp'

describe('Modal store', () => {
  let testApp = null
  let store = null
  let mockBusEmit = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store

    // Mock the $bus.$emit method
    mockBusEmit = jest.fn()
    store.$bus = { $emit: mockBusEmit }

    store.dispatch('modal/removeEscListener')
  })

  afterEach(() => {
    testApp.afterEach()
    jest.clearAllMocks()
  })

  describe('State', () => {
    test('should initialize with empty modalStack', () => {
      expect(store.state.modal.modalStack).toEqual([])
    })
  })

  describe('Mutations', () => {
    test('PUSH_MODAL should add modal to stack', () => {
      const modal = { id: 'test-modal-1', canClose: true }
      store.commit('modal/PUSH_MODAL', modal)

      expect(store.state.modal.modalStack).toHaveLength(1)
      expect(store.state.modal.modalStack[0]).toEqual(modal)
    })

    test('PUSH_MODAL should maintain order when adding multiple modals', () => {
      const modal1 = { id: 'modal-1', canClose: true }
      const modal2 = { id: 'modal-2', canClose: false }

      store.commit('modal/PUSH_MODAL', modal1)
      store.commit('modal/PUSH_MODAL', modal2)

      expect(store.state.modal.modalStack).toHaveLength(2)
      expect(store.state.modal.modalStack[0]).toEqual(modal1)
      expect(store.state.modal.modalStack[1]).toEqual(modal2)
    })

    test('POP_MODAL should remove specific modal by id', () => {
      const modal1 = { id: 'modal-1', canClose: true }
      const modal2 = { id: 'modal-2', canClose: true }
      const modal3 = { id: 'modal-3', canClose: true }

      store.commit('modal/PUSH_MODAL', modal1)
      store.commit('modal/PUSH_MODAL', modal2)
      store.commit('modal/PUSH_MODAL', modal3)

      store.commit('modal/POP_MODAL', 'modal-2')

      expect(store.state.modal.modalStack).toHaveLength(2)
      expect(store.state.modal.modalStack[0]).toEqual(modal1)
      expect(store.state.modal.modalStack[1]).toEqual(modal3)
    })

    test('POP_MODAL should handle non-existent modal id', () => {
      const modal = { id: 'modal-1', canClose: true }
      store.commit('modal/PUSH_MODAL', modal)

      store.commit('modal/POP_MODAL', 'non-existent')

      expect(store.state.modal.modalStack).toHaveLength(1)
      expect(store.state.modal.modalStack[0]).toEqual(modal)
    })
  })

  describe('Actions', () => {
    describe('pushModal', () => {
      test('should add modal to stack and add ESC listener for first modal', async () => {
        const addEscListenerSpy = jest.spyOn(
          store._actions['modal/addEscListener'],
          '0'
        )
        const modal = { id: 'modal-1', canClose: true }

        await store.dispatch('modal/pushModal', modal)

        expect(store.state.modal.modalStack).toHaveLength(1)
        expect(store.state.modal.modalStack[0]).toEqual(modal)
        expect(addEscListenerSpy).toHaveBeenCalled()
      })

      test('should not add ESC listener for subsequent modals', async () => {
        const modal1 = { id: 'modal-1', canClose: true }
        const modal2 = { id: 'modal-2', canClose: true }

        await store.dispatch('modal/pushModal', modal1)

        const addEscListenerSpy = jest.spyOn(
          store._actions['modal/addEscListener'],
          '0'
        )

        await store.dispatch('modal/pushModal', modal2)

        expect(store.state.modal.modalStack).toHaveLength(2)
        expect(addEscListenerSpy).not.toHaveBeenCalled()
      })
    })

    describe('popModal', () => {
      test('should remove modal and keep ESC listener if other modals exist', async () => {
        const modal1 = { id: 'modal-1', canClose: true }
        const modal2 = { id: 'modal-2', canClose: true }

        await store.dispatch('modal/pushModal', modal1)
        await store.dispatch('modal/pushModal', modal2)

        const removeEscListenerSpy = jest.spyOn(
          store._actions['modal/removeEscListener'],
          '0'
        )

        await store.dispatch('modal/popModal', 'modal-2')

        expect(store.state.modal.modalStack).toHaveLength(1)
        expect(removeEscListenerSpy).not.toHaveBeenCalled()
      })

      test('should remove modal and remove ESC listener when last modal is popped', async () => {
        const modal = { id: 'modal-1', canClose: true }

        await store.dispatch('modal/pushModal', modal)

        const removeEscListenerSpy = jest.spyOn(
          store._actions['modal/removeEscListener'],
          '0'
        )

        await store.dispatch('modal/popModal', 'modal-1')

        expect(store.state.modal.modalStack).toHaveLength(0)
        expect(removeEscListenerSpy).toHaveBeenCalled()
      })
    })

    describe('addEscListener and removeEscListener', () => {
      test('should add and remove event listener', async () => {
        const addEventListenerSpy = jest.spyOn(window, 'addEventListener')
        const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener')

        await store.dispatch('modal/addEscListener')

        expect(addEventListenerSpy).toHaveBeenCalledWith(
          'keyup',
          expect.any(Function)
        )

        await store.dispatch('modal/removeEscListener')

        expect(removeEventListenerSpy).toHaveBeenCalledWith(
          'keyup',
          expect.any(Function)
        )

        addEventListenerSpy.mockRestore()
        removeEventListenerSpy.mockRestore()
      })

      test('should not add duplicate event listeners', async () => {
        const addEventListenerSpy = jest.spyOn(window, 'addEventListener')

        await store.dispatch('modal/addEscListener')
        await store.dispatch('modal/addEscListener')

        expect(addEventListenerSpy).toHaveBeenCalledTimes(1)

        addEventListenerSpy.mockRestore()
      })

      test('should handle ESC key press', async () => {
        const modal = { id: 'modal-1', canClose: true }
        await store.dispatch('modal/pushModal', modal)

        const closeTopmostModalSpy = jest.spyOn(
          store._actions['modal/closeTopmostModal'],
          '0'
        )

        // Simulate ESC key press
        const escapeEvent = new KeyboardEvent('keyup', { key: 'Escape' })
        window.dispatchEvent(escapeEvent)

        expect(closeTopmostModalSpy).toHaveBeenCalled()
      })

      test('should not respond to non-ESC keys', async () => {
        const modal = { id: 'modal-1', canClose: true }
        await store.dispatch('modal/pushModal', modal)

        const closeTopmostModalSpy = jest.spyOn(
          store._actions['modal/closeTopmostModal'],
          '0'
        )

        // Simulate Enter key press
        const enterEvent = new KeyboardEvent('keyup', { key: 'Enter' })
        window.dispatchEvent(enterEvent)

        expect(closeTopmostModalSpy).not.toHaveBeenCalled()
      })
    })

    describe('closeTopmostModal', () => {
      test('should emit close event for topmost modal when canClose is true', async () => {
        const modal1 = { id: 'modal-1', canClose: true }
        const modal2 = { id: 'modal-2', canClose: true }

        await store.dispatch('modal/pushModal', modal1)
        await store.dispatch('modal/pushModal', modal2)

        await store.dispatch('modal/closeTopmostModal')

        expect(mockBusEmit).toHaveBeenCalledWith('modal:close:modal-2')
        expect(mockBusEmit).toHaveBeenCalledTimes(1)
      })

      test('should not emit close event when canClose is false', async () => {
        const modal1 = { id: 'modal-1', canClose: true }
        const modal2 = { id: 'modal-2', canClose: false }

        await store.dispatch('modal/pushModal', modal1)
        await store.dispatch('modal/pushModal', modal2)

        await store.dispatch('modal/closeTopmostModal')

        expect(mockBusEmit).not.toHaveBeenCalled()
      })

      test('should handle empty modal stack', async () => {
        await store.dispatch('modal/closeTopmostModal')

        expect(mockBusEmit).not.toHaveBeenCalled()
      })
    })
  })

  describe('Integration tests', () => {
    test('complete modal lifecycle with ESC key', async () => {
      const modal1 = { id: 'modal-1', canClose: true }
      const modal2 = { id: 'modal-2', canClose: true }

      // Push first modal - should add ESC listener
      await store.dispatch('modal/pushModal', modal1)
      expect(store.state.modal.modalStack).toHaveLength(1)

      // Push second modal - should not add another ESC listener
      await store.dispatch('modal/pushModal', modal2)
      expect(store.state.modal.modalStack).toHaveLength(2)

      // Press ESC - should emit close for modal-2
      const escapeEvent = new KeyboardEvent('keyup', { key: 'Escape' })
      window.dispatchEvent(escapeEvent)
      expect(mockBusEmit).toHaveBeenCalledWith('modal:close:modal-2')

      // Manually pop modal-2 (simulating modal close handler)
      await store.dispatch('modal/popModal', 'modal-2')
      expect(store.state.modal.modalStack).toHaveLength(1)

      // Press ESC again - should emit close for modal-1
      mockBusEmit.mockClear()
      window.dispatchEvent(escapeEvent)
      expect(mockBusEmit).toHaveBeenCalledWith('modal:close:modal-1')

      // Pop last modal - should remove ESC listener
      await store.dispatch('modal/popModal', 'modal-1')
      expect(store.state.modal.modalStack).toHaveLength(0)

      // Press ESC with no modals - should not emit anything
      mockBusEmit.mockClear()
      window.dispatchEvent(escapeEvent)
      expect(mockBusEmit).not.toHaveBeenCalled()
    })

    test('mixed canClose values in modal stack', async () => {
      const modal1 = { id: 'modal-1', canClose: true }
      const modal2 = { id: 'modal-2', canClose: false }
      const modal3 = { id: 'modal-3', canClose: true }

      await store.dispatch('modal/pushModal', modal1)
      await store.dispatch('modal/pushModal', modal2)
      await store.dispatch('modal/pushModal', modal3)

      // First ESC - should close modal-3
      const escapeEvent = new KeyboardEvent('keyup', { key: 'Escape' })
      window.dispatchEvent(escapeEvent)
      expect(mockBusEmit).toHaveBeenCalledWith('modal:close:modal-3')

      // Remove modal-3
      await store.dispatch('modal/popModal', 'modal-3')

      // Second ESC - should not close modal-2 (canClose: false)
      mockBusEmit.mockClear()
      window.dispatchEvent(escapeEvent)
      expect(mockBusEmit).not.toHaveBeenCalled()

      // Remove modal-2
      await store.dispatch('modal/popModal', 'modal-2')

      // Third ESC - should close modal-1
      mockBusEmit.mockClear()
      window.dispatchEvent(escapeEvent)
      expect(mockBusEmit).toHaveBeenCalledWith('modal:close:modal-1')
    })
  })
})
