export function initDatabase(databaseName, storeName) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(databaseName, 1)

    request.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(storeName)) {
        db.createObjectStore(storeName, { keyPath: 'key' })
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = (event) => reject(event.target.error)
  })
}

export async function setData(databaseName, storeName, key, value) {
  const db = await initDatabase(databaseName, storeName)
  const transaction = db.transaction(storeName, 'readwrite')
  const store = transaction.objectStore(storeName)
  return new Promise((resolve, reject) => {
    const request = store.put({ key, value })
    request.onsuccess = () => resolve()
    request.onerror = (event) => reject(event.target.error)
  })
}

export async function getData(databaseName, storeName, key) {
  const db = await initDatabase(databaseName, storeName)
  const transaction = db.transaction(storeName, 'readonly')
  const store = transaction.objectStore(storeName)
  return new Promise((resolve, reject) => {
    const request = store.get(key)
    request.onsuccess = (event) => resolve(event.target.result?.value || null)
    request.onerror = (event) => reject(event.target.error)
  })
}
