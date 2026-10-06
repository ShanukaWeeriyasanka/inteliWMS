import { useSyncExternalStore } from 'react'
import { createThreadNavigator } from './threadRoute'

// One navigator for the app: the URL is the source of truth for the active conversation
export const threadNavigator = createThreadNavigator(window)

export function useThreadRoute() {
  return useSyncExternalStore(threadNavigator.subscribe, threadNavigator.current)
}
