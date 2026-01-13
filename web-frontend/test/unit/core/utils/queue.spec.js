import { GroupTaskQueue } from '@baserow/modules/core/utils/queue'
import flushPromises from 'flush-promises'

vi.useFakeTimers()

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

describe('test GroupTaskQueue when immediately filling the queue', () => {
  test('GroupTaskQueue when immediately filling the queue', async () => {
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

    vi.advanceTimersByTime(15)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)

    vi.advanceTimersByTime(10)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(false)

    vi.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
  })
})
describe('test GroupTaskQueue adding to queue on the fly', () => {
  test('GroupTaskQueue adding to queue on the fly', async () => {
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

    vi.advanceTimersByTime(15)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    queue.add(async () => {
      await sleep(20)
      executed2 = true
    })

    vi.advanceTimersByTime(15)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    queue.add(async () => {
      await sleep(20)
      executed3 = true
    })

    vi.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    vi.advanceTimersByTime(25)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(true)
  })
})
describe('test GroupTaskQueue with different ids', () => {
  test('GroupTaskQueue with different ids', async () => {
    let executed1 = false
    let executed2 = false
    let executed3 = false

    const queue = new GroupTaskQueue()
    queue.add(async () => {
      await sleep(20)
      executed1 = true
    }, 1)

    vi.advanceTimersByTime(10)
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

    vi.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    vi.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(true)
  })
})
describe('test GroupTaskQueue with waiting for add to resolve', () => {
  test('GroupTaskQueue with waiting for add to resolve', async () => {
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

    vi.advanceTimersByTime(30)
    await flushPromises()
    vi.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)
  })
})
describe('test GroupTaskQueue with exception during execution', () => {
  test('GroupTaskQueue with exception during execution', async () => {
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

    vi.advanceTimersByTime(50)
    await flushPromises()

    expect(failed1).toBe(true)
    expect(failed1Error.toString()).toBe('Error: test')
    expect(failed2).toBe(false)
  })
})
describe('test GroupTaskQueue with lock', () => {
  test('GroupTaskQueue with exception during execution', async () => {
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

    vi.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(false)
    expect(executed3).toBe(false)

    queue.release(2)

    vi.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(false)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    queue.release(1)

    vi.advanceTimersByTime(30)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(false)

    vi.advanceTimersByTime(20)
    await flushPromises()

    expect(executed1).toBe(true)
    expect(executed2).toBe(true)
    expect(executed3).toBe(true)
  })
})
describe('test queue deleted from GroupTaskQueue', () => {
  test('queue deleted from GroupTaskQueue', async () => {
    const queue = new GroupTaskQueue()
    queue.add(async () => {
      await sleep(20)
    }, 1)

    expect(Object.prototype.hasOwnProperty.call(queue.queues, 1)).toBe(true)

    vi.advanceTimersByTime(30)
    await flushPromises()

    expect(Object.prototype.hasOwnProperty.call(queue.queues, 1)).toBe(false)
  })
})
