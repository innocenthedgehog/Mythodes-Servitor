from collections import defaultdict
from enum import Enum
from typing import Optional
from constants import BOT_TOKEN, MY_GUILD

import discord
from discord import app_commands

import math
import random
import re


class Difficulty(Enum):
    IMPOSSIBLE = 0.0
    HERCULEAN = 0.1
    FORMIDABLE = 0.5
    HARD = 0.67
    STANDARD = 1.0
    EASY = 1.5
    VERY_EASY = 2.0
    AUTOMATIC = 100.0

class Tier(Enum):
    FUMBLE = 0
    FAILURE= 1
    PALTRY_SUCCESS = 2
    MODEST_SUCCESS = 3
    STANDARD_SUCCESS = 4
    SUPERB_SUCCESS = 5
    GRAND_SUCCESS = 6
    CRITICAL_SUCCESS = 7

class SpeciesLocationTable:
    def __init__(self, name, die_size=20):
        self.name = name
        self.die_size = die_size
        self._ranges = []

    def add_location(self, start, end, location):
        self._ranges.append((start, end, location))

    def get_location(self, roll):
        for start, end, loc_name in self._ranges:
            if start <= roll <= end:
                return loc_name
        return "Unknown"

human = SpeciesLocationTable("Human", die_size=20)
human.add_location(1, 3, "Right Leg")
human.add_location(4, 6, "Left Leg")
human.add_location(7, 9, "Abdomen")
human.add_location(10, 12, "Chest")
human.add_location(13, 15, "Right Arm")
human.add_location(16, 18, "Left Arm")
human.add_location(19, 20, "Head")

class MyClient(discord.Client):
    # Suppress error on the User attribute being None since it fills up later
    user: discord.ClientUser

    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


def roll_dice(formula: str):
    formula = formula.replace(" ", "").lower()
    pattern = r'([+-]?)(\d*d\d+|\d+)'
    matches = re.findall(pattern, formula)

    results = []
    total = 0

    for sign, term in matches:
        multiplier = -1 if sign == "-" else 1
        if 'd' in term:
            parts = term.split('d')
            num_dice = int(parts[0]) if parts[0] else 1
            sides = int(parts[1])
            rolls = [random.randint(1, sides) for _ in range(num_dice)]
            term_total = sum(rolls) * multiplier
            total += term_total
            results.append({"term": term, "rolls": rolls, "total": term_total})
        else:
            val = int(term) * multiplier
            total += val
            results.append({"term": "modifier", "value": val})

    return {"total": total, "breakdown": results}

def get_hit_location():
    roll = random.randint(1,20)
    if roll < 3:
        return 'right_leg'

def resolve_test(skill_rating: int, roll: int = None, tiered: bool = False) -> dict:
    if roll is None:
        roll = random.randint(1, 100)

    # Fixed values
    if roll == 100:
        return {"roll": roll, "result": Tier.FUMBLE, "success": False}
    
    if roll == 99:
        if skill_rating < 100:
            return {"roll": roll, "result": Tier.FUMBLE, "success": False}
        else:
            return {"roll": roll, "result": Tier.FAILURE, "success": False}

    if 96 <= roll <= 98:
        return {"roll": roll, "result": Tier.FAILURE, "success": False}

    # Calculate Tier Thresholds
    crit_thresh = math.ceil(skill_rating / 10)
    grand_thresh = math.ceil(skill_rating / 2)
    superb_thresh = math.ceil((skill_rating * 2) / 3)
    standard_thresh = skill_rating
    modest_thresh = math.ceil(skill_rating * 1.5)
    paltry_thresh = skill_rating * 2

    # Determine Result
    result_tier = Tier.FAILURE
    is_success = False

    if tiered == False:
        if roll <= crit_thresh:
            result_tier = Tier.CRITICAL_SUCCESS
            is_success = True
        elif roll <= standard_thresh:
            result_tier = Tier.STANDARD_SUCCESS
            is_success = True
        else:
            result_tier = Tier.FAILURE
            is_success = False
    else:
        if roll <= crit_thresh:
            result_tier = Tier.CRITICAL_SUCCESS
            is_success = True
        elif roll <= grand_thresh:
            result_tier = Tier.GRAND_SUCCESS
            is_success = True
        elif roll <= superb_thresh:
            result_tier = Tier.SUPERB_SUCCESS
            is_success = True
        elif roll <= standard_thresh:
            result_tier = Tier.STANDARD_SUCCESS
            is_success = True
        elif roll <= modest_thresh:
            result_tier = Tier.MODEST_SUCCESS
            is_success = True
        elif roll <= paltry_thresh:
            result_tier = Tier.PALTRY_SUCCESS
            is_success = True
        else:
            result_tier = Tier.FAILURE
            is_success = False

    return {"roll": roll, "result": result_tier, "success": is_success}

intents = discord.Intents.default()
client = MyClient(intents=intents)


@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')


@client.tree.command()
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'Pong! {round(interaction.client.latency * 1000)} ms')

@client.tree.command()
@app_commands.describe(
    skill_rating='Your unmodified skill value',
    difficulty='The difficulty of your test',
    modifier='Your flat modifier',
    roll='Force a specific roll')
async def test(
    interaction: discord.Interaction,
    skill_rating: int,
    difficulty: Optional[Difficulty] = Difficulty.STANDARD,
    modifier: Optional[int] = 0,
    roll: Optional[int] = None):
    skill_rating = math.ceil((skill_rating + modifier) * difficulty.value)
    results = resolve_test(skill_rating, roll, False)

    results_str = f"""
{interaction.user.nick} rolled: **{results['roll']}** with a target of **{skill_rating}**
**{results['result'].name.capitalize().replace("_", " ")}**!"""

    await interaction.response.send_message(results_str)

@client.tree.command()
@app_commands.describe(
    your_skill_rating='Your unmodified skill value',
    your_difficulty='The difficulty of your test',
    your_modifier='Your flat modifier',
    your_roll='Force a specific roll',
    opponent_skill_rating='Opponent\'s unmodified skill value',
    opponent_difficulty='Opponent\'s test difficulty',
    opponent_modifier='Opponent\'s flat modifier',
    opponent_roll='Force a specific roll')
async def tiered(
    interaction: discord.Interaction,
    your_skill_rating: int,
    your_difficulty: Optional[Difficulty] = Difficulty.STANDARD,
    your_modifier: Optional[int] = 0,
    your_roll: Optional[int] = None,
    opponent_skill_rating: int = None,
    opponent_difficulty: Optional[Difficulty] = Difficulty.STANDARD,
    opponent_modifier: Optional[int] = 0,
    opponent_roll: Optional[int] = None):
    
    # If opposed, make opponent's roll
    if opponent_skill_rating is not None:
        opponent_skill_rating = math.ceil((opponent_skill_rating + opponent_modifier) * opponent_difficulty.value)
        opponent_results = resolve_test(opponent_skill_rating, opponent_roll, True)
        opponent_results_str = f"""
Your oponent rolled: **{opponent_results['roll']}** with a target of **{opponent_skill_rating}**
**{opponent_results['result'].name.capitalize().replace("_", " ")}**!"""
    else:
        opponent_results_str = ""
    
    your_skill_rating = math.ceil((your_skill_rating + your_modifier) * your_difficulty.value)
    your_results = resolve_test(your_skill_rating, your_roll, True)

    if opponent_skill_rating is not None:
        differential = your_results["result"].value - opponent_results["result"].value
        if your_results["success"] == False and opponent_results["success"] == False:
            winner_str = f'You both fail.'
        elif differential > 0:
            winner_str = f'You win by **{differential} degrees**!'
        elif differential < 0:
            winner_str = f'Your opponent wins by **{abs(differential)} degrees**!'
        else:
            if your_results["roll"] > opponent_results["roll"]:
                winner_str = f'You win with a **marginal success**.'
            elif your_results["roll"] < opponent_results["roll"]:
                winner_str = f'Your opponent wins with a **marginal success**.'
            elif your_skill_rating > opponent_skill_rating:
                winner_str = f'You win with a **marginal success**.'
            elif your_skill_rating < opponent_skill_rating:
                winner_str = f'Your opponent wins with a **marginal success**.'
            else:
                winner_str = f'A true tie!!!'
    else:
        winner_str = ''

    your_results_str = f"""
{interaction.user.nick} rolled: **{your_results['roll']}** with a target of **{your_skill_rating}**
**{your_results['result'].name.capitalize().replace("_", " ")}**!"""

    final_output = your_results_str + "\n" + opponent_results_str + "\n\n" + winner_str

    await interaction.response.send_message(final_output)

@client.tree.command()
@app_commands.describe(
    damage_roll='Your damage roll',
    hits='The number of hits',
    species_placeholder='The target\'s species')
async def damage(
    interaction: discord.Interaction,
    damage_roll: str,
    hits: Optional[int] = 1,
    species_placeholder: Optional[str] = 'human'):
    totals = []
    damage_tracker = defaultdict(int) 
    species_table = human

    output = f"{interaction.user.name} rolled {hits} hit(s) of: `{damage_roll}`\n\n"
    for hit in range(hits):
        result = roll_dice(damage_roll)
        loc_roll = random.randint(1, species_table.die_size)
        location = species_table.get_location(loc_roll)
        damage_tracker[location] += result['total']
    
        all_random_numbers = [str(roll) for entry in result['breakdown'] if 'rolls' in entry for roll in entry['rolls']]
        output += f"- Hit {hit + 1}: Rolled {', '.join(all_random_numbers)} ({location})\n"

        #totals.append(str(result['total']))
    output += "\nTotal Damage:\n"

    damage_tracker = dict(damage_tracker)
    for location, total in damage_tracker.items():
        output += f"- {location}: **{total}**\n"
    
    #output += f"\nTotals: **{", ".join(totals)}**"
    
    await interaction.response.send_message(output)

if __name__ == '__main__':
    client.run(BOT_TOKEN)