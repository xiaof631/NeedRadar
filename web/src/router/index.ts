import { createRouter, createWebHistory } from 'vue-router';
import DashboardPage from '../pages/DashboardPage.vue';
import RssSourcesPage from '../pages/RssSourcesPage.vue';
import RawEntriesPage from '../pages/RawEntriesPage.vue';
import FilterMonitorPage from '../pages/FilterMonitorPage.vue';
import CandidateNeedsPage from '../pages/CandidateNeedsPage.vue';
import SystemAlertsPage from '../pages/SystemAlertsPage.vue';
import NotFoundPage from '../pages/NotFoundPage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: DashboardPage },
    { path: '/sources', component: RssSourcesPage },
    { path: '/entries', component: RawEntriesPage },
    { path: '/filter', component: FilterMonitorPage },
    { path: '/candidates', component: CandidateNeedsPage },
    { path: '/alerts', component: SystemAlertsPage },
    { path: '/:pathMatch(.*)*', component: NotFoundPage }
  ]
});

export default router;
