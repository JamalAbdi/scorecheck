<template>
  <section class="dashboard">
    <div class="dashboard-header">
      <h2>All Sports Dashboard</h2>
      <p>Team records and last 30 completed games.</p>
    </div>

    <p v-if="loading" class="status">Loading teams...</p>
    <p v-else-if="error" class="status">{{ error }}</p>

    <div v-else class="league-sections">
      <section class="league-section" v-for="section in sections" :key="section.league">
        <h3>{{ section.league }}</h3>

        <div class="team-card" v-for="team in section.teams" :key="team.id">
          <div class="team-header">
            <router-link class="team-link" :to="team.link">{{ team.name }}</router-link>
            <span class="record">Record: {{ team.record }}</span>
          </div>

          <div class="games">
            <div class="game" v-for="game in team.games" :key="`${team.id}-${game.date}-${game.opponent}`">
              <span>{{ game.date }}</span>
              <span>{{ game.home ? 'vs' : '@' }} {{ game.opponent }}</span>
              <strong>{{ game.score }}</strong>
            </div>
            <p v-if="team.games.length === 0" class="status">No completed games available.</p>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const loading = ref(true)
const error = ref('')
const teams = ref([])
const apiUrl = process.env.VUE_APP_API_URL || '/api'

const parseRecord = (games) => {
  let wins = 0
  let losses = 0
  let ties = 0

  for (const game of games) {
    if (!game?.score || typeof game.score !== 'string') {
      continue
    }
    const [homeScoreText, awayScoreText] = game.score.split('-')
    const homeScore = Number(homeScoreText)
    const awayScore = Number(awayScoreText)
    if (!Number.isFinite(homeScore) || !Number.isFinite(awayScore)) {
      continue
    }

    const teamScore = game.home ? homeScore : awayScore
    const opponentScore = game.home ? awayScore : homeScore

    if (teamScore > opponentScore) {
      wins += 1
    } else if (teamScore < opponentScore) {
      losses += 1
    } else {
      ties += 1
    }
  }

  return ties > 0 ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`
}

const sections = computed(() => {
  const grouped = {}
  for (const team of teams.value) {
    const league = team.league || 'Other'
    if (!grouped[league]) {
      grouped[league] = []
    }
    grouped[league].push(team)
  }

  return Object.entries(grouped)
    .sort(([leagueA], [leagueB]) => leagueA.localeCompare(leagueB))
    .map(([league, leagueTeams]) => ({
      league,
      teams: leagueTeams.slice(0, 3),
    }))
})

const loadDashboard = async () => {
  try {
    const teamsResponse = await fetch(`${apiUrl}/teams`)
    if (!teamsResponse.ok) {
      throw new Error(`API error: ${teamsResponse.status}`)
    }
    const teamsData = await teamsResponse.json()
    const baseTeams = teamsData.teams || []

    const details = await Promise.all(
      baseTeams.map(async (team) => {
        const response = await fetch(`${apiUrl}/teams/${team.id}`)
        if (!response.ok) {
          return {
            ...team,
            games: [],
            record: '0-0',
            link: '/',
          }
        }

        const detail = await response.json()
        const lastThirtyGames = (detail.games || [])
          .filter((game) => game?.status === 'played')
          .sort((first, second) => {
            const firstDate = Date.parse(first?.date || '')
            const secondDate = Date.parse(second?.date || '')
            return (Number.isFinite(secondDate) ? secondDate : 0) - (Number.isFinite(firstDate) ? firstDate : 0)
          })
          .slice(0, 30)

        return {
          id: team.id,
          name: detail.name || team.name,
          league: detail.league || team.league,
          games: lastThirtyGames,
          record: parseRecord(lastThirtyGames),
          link: `/teams/${String(team.league || '').toLowerCase()}/${team.id}`,
        }
      })
    )

    teams.value = details
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard {
  background: #fff;
  border-radius: 20px;
  padding: 28px 32px;
  box-shadow: 0 18px 32px rgba(15, 23, 42, 0.08);
}

.dashboard-header h2 {
  margin: 0 0 6px;
  font-size: 24px;
}

.dashboard-header p {
  margin: 0 0 20px;
  color: #4b5563;
}

.league-sections {
  display: grid;
  gap: 20px;
}

.league-section h3 {
  margin: 0 0 10px;
}

.team-card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 10px;
}

.team-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.team-link {
  color: #2563eb;
  font-weight: 700;
  text-decoration: none;
}

.record {
  font-weight: 700;
  color: #111827;
}

.games {
  display: grid;
  gap: 8px;
}

.game {
  display: grid;
  grid-template-columns: 110px 1fr auto;
  gap: 12px;
  align-items: center;
  border-radius: 10px;
  background: #f9fafb;
  padding: 8px 10px;
  font-size: 14px;
}

.status {
  color: #6b7280;
}
</style>
