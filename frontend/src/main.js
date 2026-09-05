import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Vuetify imports
import vuetify from './plugins/vuetify'

import App from './App.vue'
import router from './router'
import './assets/main.css'
import './styles/notes.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(vuetify)

app.mount('#app')
