<template>
  <section class="selector">
    <div class="selector-header">
      <h2>Choose a league</h2>
      <p>Select a league, then pick a team to view details.</p>
    </div>

    <div class="selector-grid">
      <div class="field">
        <label for="league">League</label>
        <select id="league" v-model="selectedLeague" :disabled="loadingLeagues || !!error">
          <option value="">Choose a league</option>
          <option
            v-for="league in leagues"
            :key="league.id"
            :value="league.id"
            :disabled="!league.available"
          >
            {{ league.name }}
          </option>
        </select>
      </div>

      <div class="field">
        <label for="team">Team</label>
        <select
          id="team"
          v-model="selectedTeamId"
          :disabled="!selectedLeague || loadingTeams || !!teamError || !!error"
        >
          <option value="">Choose a team</option>
          <option v-for="team in filteredTeams" :key="team.id" :value="team.id">
            {{ team.name }}
          </option>
        </select>
      </div>

      <button class="primary" :disabled="!selectedTeamId" @click="goToTeam">
        View Team
      </button>
    </div>

    <div class="status">
      <p v-if="loadingLeagues">Loading leagues...</p>
      <p v-else-if="error">{{ error }}</p>
      <p v-else-if="loadingTeams">Loading teams...</p>
      <p v-else-if="teamError">{{ teamError }}</p>
      <p v-else-if="selectedLeague && filteredTeams.length === 0">No teams found.</p>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const leagues = ref([])
const teams = ref([])
const loadingLeagues = ref(true)
const loadingTeams = ref(false)
const error = ref('')
const teamError = ref('')
const selectedLeague = ref('')
const selectedTeamId = ref('')

const filteredTeams = computed(() => teams.value)

const apiUrl = process.env.VUE_APP_API_URL || '/api'

  watch(selectedLeague, async (leagueId) => {
  selectedTeamId.value = ''
  teams.value = []
  teamError.value = ''
  if (!leagueId) {
    return
  }

  loadingTeams.value = true
  try {
    const response = await fetch(`${apiUrl}/leagues/${leagueId}/teams`)
    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `API error: ${response.status}`)
    }
    const data = await response.json()
    teams.value = data.teams || []
  } catch (err) {
    teamError.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loadingTeams.value = false
  }
})

const goToTeam = () => {
  if (selectedTeamId.value && selectedLeague.value) {
    router.push(`/teams/${selectedLeague.value}/${selectedTeamId.value}`)
  }
}

onMounted(async () => {
  try {
    const response = await fetch(`${apiUrl}/leagues`)
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }
    const data = await response.json()
    leagues.value = data.leagues || []
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loadingLeagues.value = false
  }
})
</script>

<style scoped>
.selector {
  background: #fff;
  border-radius: 20px;
  padding: 28px 32px;
  box-shadow: 0 18px 32px rgba(15, 23, 42, 0.08);
}

.selector-header h2 {
  margin: 0 0 6px;
  font-size: 24px;
}

.selector-header p {
  margin: 0 0 24px;
  color: #4b5563;
}

.selector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 18px;
  align-items: end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field label {
  font-weight: 600;
  color: #111827;
}

.field select {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  font-size: 15px;
  background: #f9fafb;
  color: #111827;
}

.field select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.primary {
  padding: 12px 18px;
  border-radius: 12px;
  border: none;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.25);
}

.primary:hover:enabled {
  transform: translateY(-1px);
  box-shadow: 0 16px 28px rgba(37, 99, 235, 0.3);
}

.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.status {
  margin-top: 16px;
  color: #6b7280;
}
</style>
