import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import ca from './locales/ca.json'
import es from './locales/es.json'
import en from './locales/en.json'

i18n.use(initReactI18next).init({
  resources: {
    ca: { translation: ca },
    es: { translation: es },
    en: { translation: en },
  },
  lng: 'ca',
  fallbackLng: 'ca',
  interpolation: { escapeValue: false },
})

export default i18n
