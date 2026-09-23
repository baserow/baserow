import {
  ConcurrentPriorityTaskQueue,
  GroupTaskQueue,
} from '@baserow/modules/core/utils/queue'
import flushPromises from 'flush-promises'

vi.useFakeTimers()

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

describe('ConcurrentPriorityTaskQueue', () => {
  test('limits concurrency and starts higher-priority pending tasks first', async () => {
    const queue = new ConcurrentPriorityTaskQueue({ concurrency: 2 })
    const requests = [deferred(), deferred(), deferred(), deferred()]
    const started = []
    let active = 0
    let maximumActive = 0
    const addTask = (index, priority) =>
      queue.add(async () => {
        started.push(index)
        active += 1
        maximumActive = Math.max(maximumActive, active)
        await requests[index].promise
        active -= 1
      }, priority)

    const tasks = [addTask(0, 0), addTask(1, 0), addTask(2, 10), addTask(3, 1)]
    await flushPromises()

    expect(started).toEqual([0, 1])
    expect(maximumActive).toBe(2)

    requests[0].resolve()
    await flushPromises()
    expect(started).toEqual([0, 1, 3])

    requests[1].resolve()
    requests[2].resolve()
    requests[3].resolve()
    await Promise.all(tasks)
    expect(started).toEqual([0, 1, 3, 2])
    expect(maximumActive).toBe(2)
  })

  test('continues after a task rejects', async () => {
    const queue = new ConcurrentPriorityTaskQueue({ concurrency: 1 })
    const error = new Error('Failed')
    const first = queue.add(() => Promise.reject(error))
    const secondTask = vi.fn()
    const second = queue.add(secondTask)

    await expect(first).rejects.toBe(error)
    await second
    expect(secondTask).toHaveBeenCalledOnce()
  })
})

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
