import { uuid } from '@baserow/modules/core/utils/string'

export class Task {
  constructor(uid, func) {
    this.uid = uid
    this.func = func
    // Store the resolvers to enable the resolution when the function is executed.
    this.resolve = null
    this.reject = null
    this.wait = new Promise((resolve, reject) => {
      this.resolve = resolve
      this.reject = reject
    })
  }

  async run() {
    try {
      const result = await this.func()
      this.resolve(result)
      return result
    } catch (e) {
      this.reject(e)
    }
  }
}
export class TaskQueue {
  constructor({ doneCallback = null }) {
    this.queue = []
    this.running = false
    this.locked = false
    this.doneCallback = doneCallback
  }

  add(func) {
    const task = new Task(uuid(), func)
    this.queue.push(task)
    return task.uid
  }

  async waitFor(taskId) {
    const task = this.queue.find((task) => task.uid === taskId)
    if (!task) {
      throw new Error(`Task with id ${taskId} not found`)
    }
    this.start()
    await task.wait
  }

  /**
   * waits for all queued tasks
   *
   * @returns {Promise<void>}
   */
  async waitAll() {
    const waitlist = Array.from(this.queue, (item) => {
      return item.wait
    })
    await Promise.all(waitlist)
  }

  start() {
    if (this.running) {
      return
    }
    this.running = true
    this.run()
  }

  async run() {
    while (this.queue.length > 0 && this.running && !this.locked) {
      // need to keep queue filled when task is running
      const task = this.queue[0]
      await task.run()
      this.queue.shift()
    }
    this.running = false
    this.done()
  }

  done() {
    if (this.doneCallback && this.queue.length === 0) {
      this.doneCallback()
    }
  }

  /**
   * Prevent queued or to be queued functions from executing by locking them.
   */
  lock() {
    this.locked = true
  }

  /**
   * Release the lock. This will immediately run the queued functions that were locked
   * before.
   */
  release() {
    this.locked = false
    this.start()
  }
}

export class GroupTaskQueue {
  constructor() {
    this.queues = {}
  }

  getOrCreateQueue(groupId) {
    if (!Object.prototype.hasOwnProperty.call(this.queues, groupId)) {
      // Delete the queue when it's empty to clear the memory.
      const doneCallback = () => {
        delete this.queues[groupId]
      }
      this.queues[groupId] = new TaskQueue({ doneCallback })
    }
    return this.queues[groupId]
  }

  /**
   * Add a function to the queue. If there are no other functions in the queue, it
   * will be executed immediately, otherwise it will wait until the other are
   * finished first.
   *
   * @param func the function that must be queued.
   * @param groupId indicates the queue group identifier. Function is only stacked
   * on the queue with the same ID.
   * @returns resolves when the queued function completes or rejects when an
   * exception was raised.
   */
  async add(func, groupId = null) {
    const queue = this.getOrCreateQueue(groupId)
    const taskId = queue.add(func)
    await queue.waitFor(taskId)
  }

  lock(groupId = null) {
    const queue = this.getOrCreateQueue(groupId)
    queue.lock()
  }

  release(groupId = null) {
    const queue = this.getOrCreateQueue(groupId)
    queue.release()
  }
}

/**
 * Helper function that resolves when the `checkFunction` returns true.
 */
export function waitFor(checkFunction, interval = 5, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now()

    const check = () => {
      const loaded = checkFunction()

      if (loaded) {
        resolve()
      } else if (Date.now() - startTime >= timeout) {
        reject(new Error('Timeout waiting.'))
      } else {
        setTimeout(check, interval)
      }
    }

    check()
  })
}
