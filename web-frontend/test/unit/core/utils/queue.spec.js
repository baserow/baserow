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

  test('releases its worker slot while a retry is delayed', async () => {
    const queue = new ConcurrentPriorityTaskQueue({ concurrency: 1 })
    const order = []
    const retryingTask = vi
      .fn()
      .mockImplementationOnce(() => {
        order.push('first attempt')
        return Promise.reject(new Error('Throttled'))
      })
      .mockImplementationOnce(() => {
        order.push('retry')
      })

    const retrying = queue.add(retryingTask, 0, {
      maxRetries: 1,
      shouldRetry: () => true,
      retryDelay: () => 1000,
    })
    const other = queue.add(() => order.push('other task'), 0)

    await flushPromises()
    expect(order).toEqual(['first attempt', 'other task'])

    await vi.advanceTimersByTimeAsync(1000)
    await Promise.all([retrying, other])
    expect(order).toEqual(['first attempt', 'other task', 'retry'])
  })

  test('rejects after the maximum number of retries', async () => {
    const queue = new ConcurrentPriorityTaskQueue()
    const error = new Error('Throttled')
    const task = vi.fn().mockRejectedValue(error)

    const queued = queue.add(task, 0, {
      maxRetries: 2,
      shouldRetry: () => true,
    })
    queued.catch(() => {})
    await vi.runAllTimersAsync()

    await expect(queued).rejects.toBe(error)
    expect(task).toHaveBeenCalledTimes(3)
  })

  test('cancels pending tasks without starting them', async () => {
    const queue = new ConcurrentPriorityTaskQueue({ concurrency: 1 })
    const activeRequest = deferred()
    const pendingTask = vi.fn()
    const active = queue.add(() => activeRequest.promise)
    const pending = queue.add(pendingTask)
    await flushPromises()

    queue.cancelPending()

    await expect(pending).resolves.toBeUndefined()
    expect(pendingTask).not.toHaveBeenCalled()
    activeRequest.resolve()
    await active
  })

  test('cancels a delayed retry', async () => {
    const queue = new ConcurrentPriorityTaskQueue()
    const task = vi.fn().mockRejectedValue(new Error('Throttled'))
    const queued = queue.add(task, 0, {
      maxRetries: 1,
      shouldRetry: () => true,
      retryDelay: () => 1000,
    })
    await flushPromises()

    queue.cancelPending()
    await vi.advanceTimersByTimeAsync(1000)

    await expect(queued).resolves.toBeUndefined()
    expect(task).toHaveBeenCalledOnce()
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
