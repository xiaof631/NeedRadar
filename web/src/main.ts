import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { VueQueryPlugin } from '@tanstack/vue-query';

import App from './App.vue';
import ElementPlusPlugin from './plugins/elementPlus';
import router from './router';
import { i18n } from './modules/i18n';
import './styles/main.css';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(i18n);
app.use(VueQueryPlugin);
app.use(ElementPlusPlugin);

app.mount('#app');
