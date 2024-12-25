import { GroupTaskQueue } from '@baserow/modules/core/utils/queue'
import flushPromises from 'flush-promises'

jest.useFakeTimers()

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

describe('test GroupTaskQueue when immediately filling the queue', () => {
  test('test GroupTaskQueue when immediately filling the queue', async () => {
    let executed1 = false
    let executed2 = false

    const queue = new GroupTaskQueue()
    queue.add(async () => {
      await sleep(20)
      executed1 = true
    })
    queue.add(async () => {
      await sleep(20)
      executed2 = true
    })

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)

    jest.advanceTimersByTime(15)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)

    jest.advanceTimersByTime(10)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(false)

    jest.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
  })
})
describe('test GroupTaskQueue adding to queue on the fly', () => {
  test('test GroupTaskQueue adding to queue on the fly', async () => {
    let executed1 = false
    let executed2 = false
    let executed3 = false

    const queue = new GroupTaskQueue()
    queue.add(async () => {
      await sleep(20)
      executed1 = true
    })

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    jest.advanceTimersByTime(15)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    queue.add(async () => {
      await sleep(20)
      executed2 = true
    })

    jest.advanceTimersByTime(15)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    queue.add(async () => {
      await sleep(20)
      executed3 = true
    })

    jest.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    jest.advanceTimersByTime(25)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(true)
  })
})
describe('test GroupTaskQueue with different ids', () => {
  test('test GroupTaskQueue with different ids', async () => {
    let executed1 = false
    let executed2 = false
    let executed3 = false

    const queue = new GroupTaskQueue()
    queue.add(async () => {
      await sleep(20)
      executed1 = true
    }, 1)

    jest.advanceTimersByTime(10)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    queue.add(async () => {
      await sleep(20)
      executed2 = true
    }, 2)
    queue.add(async () => {
      await sleep(30)
      executed3 = true
    }, 1)

    jest.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    jest.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(true)
  })
})
describe('test GroupTaskQueue with waiting for add to resolve', () => {
  test('test GroupTaskQueue with waiting for add to resolve', async () => {
    let executed1 = false
    let executed2 = false
    let executed3 = false

    const queue = new GroupTaskQueue()
    queue
      .add(async () => {
        await sleep(20)
      })
      .then(() => {
        executed1 = true
      })
    queue
      .add(async () => {
        await sleep(20)
      })
      .then(() => {
        executed2 = true
      })
    queue
      .add(async () => {
        await sleep(20)
      })
      .then(() => {
        executed3 = true
      })

    jest.advanceTimersByTime(30)
    await flushPromises()
    jest.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)
  })
})
describe('test GroupTaskQueue with exception during execution', () => {
  test('test GroupTaskQueue with exception during execution', async () => {
    let failed1 = false
    let failed1Error = null
    let failed2 = false

    const queue = new GroupTaskQueue()
    queue
      .add(async () => {
        await sleep(20)
        throw new Error('test')
      })
      .then(() => {
        failed1 = false
      })
      .catch((error) => {
        failed1Error = error
        failed1 = true
      })
    queue
      .add(async () => {
        await sleep(20)
      })
      .then(() => {
        failed2 = false
      })
      .catch(() => {
        failed2 = true
      })

    jest.advanceTimersByTime(50)
    await flushPromises()

    expect(failed1).toBe(true)
    expect(failed1Error.toString()).toBe('Error: test')
    expect(failed2).toBe(false)
  })
})
describe('test GroupTaskQueue with lock', () => {
  test('test GroupTaskQueue with exception during execution', async () => {
    let executed1 = false
    let executed2 = false
    let executed3 = false

    const queue = new GroupTaskQueue()
    queue.lock(1)
    queue.lock(2)

    queue.add(async () => {
      await sleep(20)
      executed1 = true
    }, 1)
    queue.add(async () => {
      await sleep(20)
      executed2 = true
    }, 2)
    queue.add(async () => {
      await sleep(20)
      executed3 = true
    }, 1)

    jest.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    queue.release(2)

    jest.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    queue.release(1)

    jest.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    jest.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(true)
  })
})
describe('test queue deleted from GroupTaskQueue', () => {
  test('test queue deleted from GroupTaskQueue', async () => {
    const queue = new GroupTaskQueue()
    queue.add(async () => {
      await sleep(20)
    }, 1)

    expect(Object.prototype.hasOwnProperty.call(queue.queues, 1)).toBe(true)

    jest.advanceTimersByTime(30)
    await flushPromises()

    expect(Object.prototype.hasOwnProperty.call(queue.queues, 1)).toBe(false)
  })
})
