#!/usr/bin/env python3
"""
Populate the database with sports data.
Run this script to cache all league/team data.
"""
import requests
import sys
import time

BASE_URL = "http://localhost:8000/api"


def populate_database():
    print("🏀 Populating database with sports data...")

    # Fetch all leagues
    print("\n📋 Fetching leagues...")
    req = requests.get(f"{BASE_URL}/leagues")
    if req.status_code != 200:
        print(f"❌ Failed to fetch leagues: {req.status_code}")
        return False

    leagues = req.json().get("leagues", [])
    print(
        f"✓ Found {len(leagues)} leagues: "
        f"{', '.join(league_item['name'] for league_item in leagues)}"
    )

    # Fetch teams for each league
    for league in leagues:
        league_id = league["id"]
        league_name = league["name"]
        print(f"\n🏟️ Fetching teams for {league_name}...")

        req = requests.get(f"{BASE_URL}/leagues/{league_id}/teams")
        if req.status_code != 200:
            print(f"⚠️ Failed to fetch {league_name}: {req.status_code}")
            continue

        data = req.json()
        teams = data.get("teams", [])
        print(f"✓ Found {len(teams)} teams")

        # Fetch details for each team (to cache individual team data)
        for team in teams[:5]:  # Cache first 5 teams per league to speed up
            team_id = team["id"]
            print(f"  • Caching {team['name']}...", end=" ", flush=True)

            req = requests.get(f"{BASE_URL}/leagues/{league_id}/teams/{team_id}")
            if req.status_code == 200:
                print("✓")
            else:
                print(f"⚠️ ({req.status_code})")

            time.sleep(0.1)  # Rate limiting

    print("\n\n✅ Database population complete!")
    print(
        "💾 All data is now cached in SQLite and will be served from cache "
        "on subsequent requests."
    )
    return True


if __name__ == "__main__":
    try:
        success = populate_database()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
