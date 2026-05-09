import { useEffect, useState } from 'react'

const THEME_STORAGE_KEY = 'agtech-theme'

type Theme = 'dark' | 'light'

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === 'undefined') {
      return 'dark'
    }
    return window.localStorage.getItem(THEME_STORAGE_KEY) === 'light' ? 'light' : 'dark'
  })

  useEffect(() => {
    document.body.dataset.theme = theme
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  return (
    <button className="icon-button" type="button" onClick={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">
      {theme === 'dark' ? '☾' : '☀'}
    </button>
  )
}
