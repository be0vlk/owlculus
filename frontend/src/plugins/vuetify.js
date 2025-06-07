import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { VTreeview } from 'vuetify/labs/VTreeview'

// Custom theme to match current Owlculus color scheme
const owlculusTheme = {
  dark: false,
  colors: {
    background: '#FFFFFF',
    surface: '#FFFFFF',
    'surface-bright': '#FFFFFF',
    'surface-light': '#EEEEEE',
    'surface-variant': '#424242',
    'on-surface-variant': '#EEEEEE',
    primary: '#00585f',
    'primary-darken-1': '#006064',
    secondary: '#424242',
    'secondary-darken-1': '#303030',
    error: '#B00020',
    info: '#00838F',
    success: '#26A69A',
    warning: '#FB8C00',
    // OSINT-specific colors
    'case-status': '#26A69A',
    'evidence': '#FF9800',
    'entity': '#9C27B0'
  }
}

const owlculusDarkTheme = {
  dark: true,
  colors: {
    background: '#121212',
    surface: '#1E1E1E',
    'surface-bright': '#2C2C2C',
    'surface-light': '#424242',
    'surface-variant': '#424242',
    'on-surface-variant': '#EEEEEE',
    primary: '#00585f',
    'primary-darken-1': '#006064',
    secondary: '#616161',
    'secondary-darken-1': '#424242',
    error: '#CF6679',
    info: '#00838F',
    success: '#26A69A',
    warning: '#FF9800',
    'case-status': '#26A69A',
    'evidence': '#FF9800',
    'entity': '#BA68C8'
  }
}

export default createVuetify({
  components: {
    ...components,
    VTreeview,
  },
  directives,
  theme: {
    defaultTheme: 'owlculusLight',
    themes: {
      owlculusLight: owlculusTheme,
      owlculusDark: owlculusDarkTheme
    }
  },
  defaults: {
    VBtn: {
      variant: 'flat',
      style: 'text-transform: none;'
    },
    VCard: {
      elevation: 2
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable'
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable'
    },
    VTextarea: {
      variant: 'outlined',
      density: 'comfortable'
    }
  }
})
