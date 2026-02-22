import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/Home.vue'
import TeamView from './views/Team.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/teams/:id', name: 'team', component: TeamView, props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
