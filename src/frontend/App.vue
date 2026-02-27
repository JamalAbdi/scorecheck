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

          <transition name="menu-fade">
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
                <img v-if="team.logo" :src="team.logo" :alt="`${team.name} logo`" class="team-link-logo" />
                <span>{{ team.name }}</span>
              </router-link>
            </div>
          </transition>
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
  background: transparent;
  color: #111827;
  padding: 20px 32px 16px;
}

.header-top {
  display: flex;
  justify-content: center;
  align-items: center;
}

.header h1 {
  margin: 0;
  font-size: 34px;
  font-family: "Avenir Next", "Montserrat", "Segoe UI", system-ui, sans-serif;
  letter-spacing: 0.6px;
  font-weight: 800;
}

.brand-link {
  color: #111827;
  text-decoration: none;
}

.league-bar {
  margin-top: 18px;
  display: flex;
  justify-content: center;
  padding: 0 24px;
}

.league-nav {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}

.league-item {
  position: relative;
  padding-bottom: 8px;
}

.league-button {
  border: 1px solid #dbe3f0;
  background: #fff;
  color: #0f172a;
  padding: 12px 20px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 16px;
  letter-spacing: 0.2px;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.1);
  transition: transform 0.15s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.league-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: #bfdbfe;
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.16);
}

.league-button.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.28);
}

.league-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.team-menu {
  position: absolute;
  top: calc(100% - 2px);
  left: 0;
  z-index: 20;
  min-width: 250px;
  max-height: 320px;
  overflow-y: auto;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.97);
  backdrop-filter: blur(8px);
  border: 1px solid #dbe3f0;
  box-shadow: 0 18px 32px rgba(15, 23, 42, 0.18);
  padding: 10px;
}

.menu-fade-enter-active {
  transition: opacity 0.16s ease-out, transform 0.16s ease-out;
}

.menu-fade-leave-active {
  transition: opacity 0.1s ease-in, transform 0.1s ease-in;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.team-link {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0f172a;
  text-decoration: none;
  border-radius: 10px;
  padding: 9px 10px;
  font-size: 14px;
  transition: background-color 0.15s ease, transform 0.15s ease;
}

.team-link-logo {
  width: 18px;
  height: 18px;
  object-fit: contain;
}

.team-link:hover {
  background: #eef4ff;
  transform: translateX(1px);
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

