// Ignore responses superseded by a newer request, selection, or disconnected component.
export function latestRequest() {
  let version = 0
  return {
    invalidate: () => { version += 1 },
    async run(fetch, accept, reject = () => {}) {
      const current = ++version
      try {
        const value = await fetch()
        if (current === version) accept(value)
      } catch (error) {
        if (current === version) reject(error)
        throw error
      }
    },
  }
}
