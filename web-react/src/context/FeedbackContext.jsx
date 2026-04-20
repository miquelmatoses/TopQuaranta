/**
 * FeedbackContext — lets content pages tell the Layout footer what
 * the page is "about" so the shared "Corregir" button in the footer
 * can address it properly.
 *
 * Usage (in an artist/album/canco page):
 *
 *   import { useFeedbackTarget } from '../context/FeedbackContext'
 *   ...
 *   useFeedbackTarget({
 *     targetType: 'artista',
 *     targetPk: data.pk,
 *     targetSlug: data.slug,
 *     targetLabel: data.nom,
 *   })
 *
 * The hook clears on unmount so navigating to a page that doesn't
 * call it hides the button again.
 */
import { createContext, useContext, useEffect, useState } from 'react'

const FeedbackContext = createContext({
  target: null,
  setTarget: () => {},
})

export function FeedbackProvider({ children }) {
  const [target, setTarget] = useState(null)
  return (
    <FeedbackContext.Provider value={{ target, setTarget }}>
      {children}
    </FeedbackContext.Provider>
  )
}

export function useFeedbackContext() {
  return useContext(FeedbackContext)
}

/** Call from a page component to publish its target. Clears on unmount. */
export function useFeedbackTarget(target) {
  const { setTarget } = useContext(FeedbackContext)
  useEffect(() => {
    setTarget(target)
    return () => setTarget(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    target?.targetType,
    target?.targetPk,
    target?.targetSlug,
    target?.targetLabel,
  ])
}
