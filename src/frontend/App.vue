<template>
  <div class="app">
    <header class="header">
      <div class="header-top">
        <h1><router-link to="/" class="brand-link">Scorecheck</router-link></h1>
      </div>
    </header>

    <section class="league-bar" v-if="leagues.length">
      <nav class="league-nav" aria-label="Leagues">
        <div
          v-for="league in leagues"
          :key="league.id"
          class="league-item"
          @mouseenter="openLeagueMenu(league)"
          @focusin="openLeagueMenu(league)"
          @mouseleave="closeLeagueMenu"
        >
          <button
            type="button"
            class="league-button"
            :class="{ active: activeLeague === league.id }"
            :disabled="!league.available"
            @click="goToLeague(league.id)"
          >
            {{ league.name }}
          </button>

          <div
            v-if="openLeague === league.id && league.available"
            class="team-menu"
            :aria-label="`${league.name} teams`"
          >
            <p v-if="loadingTeamsByLeague[league.id]" class="team-menu-status">Loading teams...</p>
            <p v-else-if="!teamsByLeague[league.id]?.length" class="team-menu-status">No teams available.</p>
            <router-link
              v-else
              v-for="team in teamsByLeague[league.id]"
              :key="team.id"
              class="team-link"
              :to="`/teams/${league.id}/${team.id}`"
              @click="closeLeagueMenu"
            >
              {{ team.name }}
            </router-link>
          </div>
        </div>
      </nav>
    </section>

    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const leagues = ref([])
const teamsByLeague = ref({})
const loadingTeamsByLeague = ref({})
const openLeague = ref('')
const apiUrl = process.env.VUE_APP_API_URL || '/api'

const activeLeague = computed(() => {
  if (route.params?.league) {
    return String(route.params.league)
  }
  if (route.query?.league) {
    return String(route.query.league)
  }
  return ''
})

const goToLeague = (leagueId) => {
  router.push({ path: '/', query: { league: leagueId } })
}

const openLeagueMenu = async (league) => {
  if (!league.available) {
    return
  }

  openLeague.value = league.id

  if (teamsByLeague.value[league.id] || loadingTeamsByLeague.value[league.id]) {
    return
  }

  loadingTeamsByLeague.value = { ...loadingTeamsByLeague.value, [league.id]: true }

  try {
    const response = await fetch(`${apiUrl}/leagues/${league.id}/teams`)
    if (!response.ok) {
      teamsByLeague.value = { ...teamsByLeague.value, [league.id]: [] }
      return
    }
    const data = await response.json()
    teamsByLeague.value = { ...teamsByLeague.value, [league.id]: data.teams || [] }
  } catch {
    teamsByLeague.value = { ...teamsByLeague.value, [league.id]: [] }
  } finally {
    loadingTeamsByLeague.value = { ...loadingTeamsByLeague.value, [league.id]: false }
  }
}

const closeLeagueMenu = () => {
  openLeague.value = ''
}

onMounted(async () => {
  try {
    const response = await fetch(`${apiUrl}/leagues`)
    if (!response.ok) {
      return
    }
    const data = await response.json()
    leagues.value = data.leagues || []
  } catch {
    leagues.value = []
  }
})
</script>

<style>
:root {
  color-scheme: light;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #1d1d1f;
  background: #f5f6f8;
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background: #111827;
  color: #fff;
  padding: 20px 32px 42px;
}

.header-top {
  display: flex;
  justify-content: center;
  align-items: center;
}

.header h1 {
  margin: 0;
  font-size: 30px;
}

.brand-link {
  color: #fff;
  text-decoration: none;
}

.league-bar {
  margin-top: -26px;
  display: flex;
  justify-content: center;
  padding: 0 24px;
}

.league-nav {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14px;
}

.league-item {
  position: relative;
}

.league-button {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #111827;
  padding: 14px 20px;
  border-radius: 14px;
  font-weight: 600;
  font-size: 18px;
  cursor: pointer;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.12);
}

.league-button.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.league-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.team-menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 20;
  min-width: 220px;
  max-height: 320px;
  overflow-y: auto;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.2);
  padding: 8px;
}

.team-link {
  display: block;
  color: #111827;
  text-decoration: none;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 14px;
}

.team-link:hover {
  background: #f3f4f6;
}

.team-menu-status {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
  padding: 8px 10px;
}

.content {
  flex: 1;
  padding: 24px 32px 48px;
}
</style>

