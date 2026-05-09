import { useLanguage } from '../../lib/i18n/useLanguage'

export function LanguageToggle() {
  const { language, toggleLanguage } = useLanguage()

  return (
    <button className="icon-button language-toggle" type="button" onClick={toggleLanguage} aria-label={language === 'en' ? 'Switch language to Vietnamese' : 'Switch language to English'}>
      {language === 'en' ? 'VI' : 'EN'}
    </button>
  )
}
