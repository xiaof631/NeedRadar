import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('../pages/DashboardPage.vue') },
    { path: '/sources', component: () => import('../pages/RssSourcesPage.vue') },
    { path: '/marketplace', component: () => import('../pages/MarketplaceLeadsPage.vue') },
    { path: '/customer-radar', component: () => import('../pages/CustomerRadarPage.vue') },
    { path: '/entries', component: () => import('../pages/RawEntriesPage.vue') },
    { path: '/filter', component: () => import('../pages/FilterMonitorPage.vue') },
    { path: '/candidates', component: () => import('../pages/CandidateNeedsPage.vue') },
    { path: '/alerts', component: () => import('../pages/SystemAlertsPage.vue') },
    { path: '/:pathMatch(.*)*', component: () => import('../pages/NotFoundPage.vue') }
  ]
});

export default router;
