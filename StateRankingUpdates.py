import os
import discord
from discord.ext import commands, tasks
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
state = 'Oklahoma'
json_file = f"{state}Data.json" 

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!', flush=True)
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    check_data.start()  # Start the loop to check data every 20 minutes

async def fetch_data():
    print("Fetching data from osu! World API...")
    base_url = "https://osuworld.octo.moe/api/US/US-OK/top/osu?page={}"
    page = 1
    data_list = []

    while True:
        url = base_url.format(page)
        response = requests.get(url)
        if response.status_code != 200:
            break
        data = response.json()
        players = data.get("top", [])
        if not players:
            break  # No more data

        for player in players:
            playerData = {
                "PlayerID": str(player.get("id", "")),
                "PlayerName": player.get("username", ""),
                "PlayerState": "Oklahoma",
                "StateRank": "",
                "GlobalRank": str(player.get("rank", "")),
                "Total PP": str(player.get("pp", "")),
                "Gamemode": player.get("mode", "osu")
            }
            data_list.append(playerData)

        page += 1
        if page > data.get("pages", 1):
            break

    # Sort and assign StateRank as before
    data_list = [p for p in data_list if p["GlobalRank"].isdigit()]
    data_list.sort(key=lambda x: int(x["GlobalRank"]))
    for idx, player in enumerate(data_list, start=1):
        player["StateRank"] = f"#{idx}"

    print(f"Fetched {len(data_list)} players.")
    return data_list

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            content = file.read().strip()
            if not content:
                return []
            return json.loads(content)
    return []

def save_json(filepath, data):
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=7)

def data_has_changed(new_data, old_data):
    return new_data != old_data

async def notify_rank_changes(channel, new_data, old_data):
    old_rankings = {player['PlayerID']: player['StateRank'] for player in old_data}
    old_Gamemode = {player['PlayerID']: player['Gamemode'] for player in old_data}
    new_Gamemode = {player['PlayerID']: player['Gamemode'] for player in new_data}
    for new_player in new_data:
        player_id = new_player['PlayerID']
        new_rank = int(new_player['StateRank'].replace('#', ''))
        if player_id in old_rankings and new_rank < int(old_rankings[player_id].replace('#', '')) and new_Gamemode == old_Gamemode:
            print(f"Rank change detected for player {new_player['PlayerName']}!")
            beaten_players = []
            beater_player = new_player

        
            # Finding the players who were beaten
            for old_player in old_data:
                old_rank = int(old_player['StateRank'].replace('#', ''))
                if old_rank == new_rank or old_rank == new_rank + 1 and old_player['PlayerName'] != new_player['PlayerName']:
                    beaten_players = [old_player] + beaten_players

            if beaten_players:
                for beaten_player in beaten_players:
                    if beaten_player['Gamemode'] == beater_player['Gamemode']:
                        beater_link = f"[{beater_player['PlayerName']}](https://osu.ppy.sh/users/{beater_player['PlayerID']})"
                        beaten_link = f"[{beaten_player['PlayerName']}](https://osu.ppy.sh/users/{beaten_player['PlayerID']})"
                        embed = discord.Embed(
                            title="🏆 Leaderboard Update Detected!",
                            description=(f"{beater_link} is one step closer to #1 in Oklahoma!"),
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Player", value=beater_link, inline=True)
                        embed.add_field(name="New State Rank", value=beaten_player['StateRank'], inline=True)
                        embed.add_field(name="Passed Player", value=beaten_link, inline=False)
                        embed.set_footer(text="Rank updates")
                        embed.set_thumbnail(url= f"https://a.ppy.sh/{beater_player['PlayerID']}")
                        await channel.send(embed=embed)

@client.tree.command(name="nextpass", description="Shows who the specified user is about to pass.")
async def Next_Pass(interaction: discord.Interaction, username: str):
    data = load_json(json_file)
    user = next((p for p in data if p["PlayerName"].lower() == username.lower()), None)
    if not user:
        await interaction.response.send_message(f"User '{username}' not found.", ephemeral=True)
        return
    user_rank = int(user["StateRank"].replace("#", ""))
    next_user = next((p for p in data if int(p["StateRank"].replace("#", "")) == user_rank - 1), None)
    if next_user:
        user_link = f"[{user['PlayerName']}](https://osu.ppy.sh/users/{user['PlayerID']})"
        next_link = f"[{next_user['PlayerName']}](https://osu.ppy.sh/users/{next_user['PlayerID']})"
        rank_diff = int(next_user["GlobalRank"]) - int(user["GlobalRank"])
        pp_diff = float(next_user["Total PP"]) - float(user["Total PP"])
        embed = discord.Embed(
            title="🚀 Next Pass Prediction",
            description=f"{user_link} is closest to passing {next_link}!\n"
                        f"{next_user['PlayerName']} is {abs(rank_diff)} ranks and {abs(pp_diff):.2f}pp ahead. Better get to farming O.O",
            color=discord.Color.blue()
        )
        embed.add_field(name=f"{user['PlayerName']}'s State Rank", value=user["StateRank"], inline=True)
        embed.add_field(name=f"{next_user['PlayerName']}'s State Rank", value=next_user["StateRank"], inline=True)
        embed.add_field(name=f"{next_user['PlayerName']}'s PP", value=next_user["Total PP"], inline=True)
        embed.add_field(name="PP Difference", value=f"{abs(pp_diff):.2f}pp", inline=True)
        embed.set_thumbnail(url=f"https://a.ppy.sh/{user['PlayerID']}")
        embed.set_footer(text="osu! Oklahoma Leaderboard")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"{user['PlayerName']} is already #1!")

@client.tree.command(name="closestthreat", description="Shows who is closest to passing the specified user.")
async def Closest_Threat(interaction: discord.Interaction, username: str):
    data = load_json(json_file)
    user = next((p for p in data if p["PlayerName"].lower() == username.lower()), None)
    if not user:
        await interaction.response.send_message(f"User '{username}' not found.", ephemeral=True)
        return
    user_rank = int(user["StateRank"].replace("#", ""))
    threat_user = next((p for p in data if int(p["StateRank"].replace("#", "")) == user_rank + 1), None)
    if threat_user:
        user_link = f"[{user['PlayerName']}](https://osu.ppy.sh/users/{user['PlayerID']})"
        threat_link = f"[{threat_user['PlayerName']}](https://osu.ppy.sh/users/{threat_user['PlayerID']})"
        rank_diff = int(user["GlobalRank"]) - int(threat_user["GlobalRank"])
        pp_diff = float(user["Total PP"]) - float(threat_user["Total PP"])
        embed = discord.Embed(
            title="⚠️ Closest Threat",
            description=f"{threat_link} is closest to passing {user_link}!\n"
                        f"{threat_user['PlayerName']} is {abs(rank_diff)} ranks and {abs(pp_diff):.2f}pp behind you. Keep farming to stay ahead!",
            color=discord.Color.red()
        )
        embed.add_field(name=f"{user['PlayerName']}'s State Rank", value=user["StateRank"], inline=True)
        embed.add_field(name=f"{threat_user['PlayerName']}'s State Rank", value=threat_user["StateRank"], inline=True)
        embed.add_field(name=f"{threat_user['PlayerName']}'s PP", value=threat_user["Total PP"], inline=True)
        embed.add_field(name="PP Difference", value=f"{abs(pp_diff):.2f}pp", inline=True)
        embed.set_thumbnail(url=f"https://a.ppy.sh/{threat_user['PlayerID']}")
        embed.set_footer(text="osu! Oklahoma Leaderboard")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"{user['PlayerName']} is at the bottom of the leaderboard!", ephemeral=True)

@tasks.loop(minutes=20)
async def check_data():
    old_data = load_json(json_file)
    new_data = await fetch_data()
    
    if data_has_changed(new_data, old_data):
        save_json(json_file, new_data)
        print("Data has changed and updated the JSON file.")

        channel = client.get_guild(GUILD_ID).get_channel(CHANNEL_ID)
        await notify_rank_changes(channel, new_data, old_data)
    else:
        print("Data has not changed.")

def main():
    client.run(TOKEN)

if __name__ == "__main__":
    main()