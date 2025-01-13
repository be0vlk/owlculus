import './assets/main.css'
import { library } from '@fortawesome/fontawesome-svg-core'
import { faItalic, faBold, faUnderline, faStrikethrough, faListUl, faListOl, faQuoteRight } from '@fortawesome/free-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import '@fortawesome/fontawesome-svg-core/styles.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// Add FontAwesome icons to the library
library.add(faItalic, faBold, faUnderline, faStrikethrough, faListUl, faListOl, faQuoteRight)

// Initialize dark mode from stored preference
const darkMode = localStorage.getItem('color-scheme') === 'dark'
if (darkMode) {
  document.documentElement.classList.add('dark')
}

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.component('font-awesome-icon', FontAwesomeIcon)

app.mount('#app')
