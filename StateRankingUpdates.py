import os
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
from typing import Final
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = 
CHANNEL_ID = 
state = ''
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
    check_data.start()  # Start the loop to check data every hour

def fetch_data():
    print("Fetching data...")
    r = requests.get(f'https://states.osutools.com/states/{state}') # Start getting the data from the website
    soup = BeautifulSoup(r.content, 'html.parser')
    s = soup.find('div', class_='players-container')

    playerState = s.find_all_next('h6') # Get specific text for certain statistics
    stateRank = s.find_all_next('h4')
    playerName = s.find_all_next('h2')
    playerID = s.find_all_next('a')
    gameMode = s.find_all_next('h5')
    data_list = []
    index = 0
    gmIndex=0
    for i in range(0, len(stateRank), 5):
        dataString = [
            f'{playerName[index]}',
            f'{stateRank[i]}',
            f'{playerState[index]}',
            f'{stateRank[i+2]}',
            f'{stateRank[i+1]}',
            f'{playerID[index]}',
            f'{gameMode[gmIndex]}'
        ]
        # Add formatted information into the JSON file
        playerData = {
            "PlayerID": dataString[5].replace('<a href="https://osu.ppy.sh/users/', '').replace('" target="_blank"><h2>', '').replace(dataString[0].replace('<h2>', '').replace('</h2>', ''), '').replace('</h2></a>', ''),
            "PlayerName": dataString[0].replace('<h2>', '').replace('</h2>', ''),
            "PlayerState": dataString[2].replace('<h6>', '').replace('</h6>', '').replace('\u2713', ''),
            "StateRank": dataString[1].replace('<h4>', '').replace('</h4>', ''),
            "GlobalRank": dataString[3].replace('<h4>', '').replace('</h4>', ''),
            "Total PP": dataString[4].replace('<h4>', '').replace('</h4>', ''),
            "Gamemode": dataString[6].replace('<h5>Mode: ','').replace('</h5>', '')
        }
        data_list.append(playerData)
        index += 1
        gmIndex += 3

    print("Data fetched successfully.")
    return data_list

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            return json.load(file)
    return []

def save_json(filepath, data):
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=7)

def data_has_changed(new_data, old_data):
    return new_data != old_data

async def notify_rank_changes(channel, new_data, old_data):
    old_rankings = {player['PlayerID']: player['StateRank'] for player in old_data}
    new_rankings = {player['PlayerID']: player['StateRank'] for player in new_data}

    for new_player in new_data:
        player_id = new_player['PlayerID']
        new_rank = int(new_player['StateRank'].replace('#', ''))
        if player_id in old_rankings and new_rank < int(old_rankings[player_id].replace('#', '')) and new_player['Gamemode'] == old_player['Gamemode']:
            print(f"Rank change detected for player {new_player['PlayerName']}!")
            beaten_player = None
            beater_player = None

            # Finding the player who was beaten
            for old_player in old_data:
                old_rank = int(old_player['StateRank'].replace('#', ''))
                if old_rank == new_rank + 1:
                    beaten_player = old_player
                    break

            # Finding the player who moved up in rank
            for old_player in old_data:
                old_rank = int(old_player['StateRank'].replace('#', ''))
                if old_rank == new_rank and old_player['PlayerName'] != new_player['PlayerName']:
                    beater_player = old_player
                    break

            if beaten_player and beater_player:
                embed = discord.Embed(
                    title="Leaderboard Update Detected!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Player", value=beaten_player['PlayerName'], inline=True)
                embed.add_field(name="New State Rank", value=beater_player['StateRank'], inline=True)
                embed.add_field(name="Passed Player", value=beater_player['PlayerName'], inline=False)
                embed.set_footer(text="Rank updates")
                await channel.send(embed=embed)

@tasks.loop(minutes=20)
async def check_data():
    new_data = fetch_data()
    old_data = load_json(json_file)
    
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