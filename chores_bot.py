import discord
from discord.ext import tasks
import os
import datetime

token = os.getenv("DISCORD_TOKEN")
print(token)
if token is None:
    print("No token found")
    exit()  

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

chore_people = ["Isabelle, <@663405556312047633>", "Guido, <@339570174451646469>", "Daniel, <@341262399531122689>", "Charlotte, <@340964475135983618>", "Thomas,<@869351880155885600>"]

@client.event
async def on_ready():
    global window
    if not myLoop.is_running():
        myLoop.start()
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    global window, chores

    if message.author == client.user:
        return

    if 'dish' in message.content.lower():
        chores.dishwasher_status = chores.dishwasher_status + 1
        if chores.dishwasher_status >= len(chore_people):
            chores.dishwasher_status = 0
        await message.channel.send(f"It's {chore_people[chores.dishwasher_status]}'s turn to do the dishwasher")
        chores.make_intro("dishwasher", chores.chore_people[chores.dishwasher_status])

    elif 'wednesday'in message.content.lower() or 'outside' in message.content.lower():
        chores.wednesday_status = chores.wednesday_status + 1
        if chores.wednesday_status >= len(chore_people):
            chores.wednesday_status = 0
        await message.channel.send(f"It's {chore_people[chores.wednesday_status]}'s turn to do Wednesday trash")
        chores.make_intro("wednesday trash", chores.chore_people[chores.wednesday_status])

    elif 'kitchen' in message.content.lower():
        chores.kitchen_status = chores.kitchen_status + 1
        if chores.kitchen_status >= len(chore_people):
            chores.kitchen_status = 0
        await message.channel.send(f"It's {chore_people[chores.kitchen_status]}'s turn to do kitchen trash")
        chores.make_intro("kitchen trash", chores.chore_people[chores.kitchen_status])

    elif 'info'in message.content.lower() or 'status' in message.content.lower():
        await message.channel.send(f"It's {chore_people[chores.dishwasher_status]}'s turn to do the dishwasher,\n"
                                   f"It's {chore_people[chores.kitchen_status]}'s turn to do the kitchen trash,\n"
                                   f"It's {chore_people[chores.wednesday_status]}'s turn to do the Wednesday trash.")

    else:
        await message.channel.send("Please use the words 'dishwasher', 'wednesday' or 'kitchen' to talk about what you need.")

    chores.save_status()
    chores.refresh_labels()    
    window.update_idletasks()
    window.update()

@tasks.loop(seconds = 1) # repeat after every 1 seconds
async def myLoop():
    global window, chores
    window.update_idletasks()
    chores.refresh_labels()
    window.update()
    

def run_chores_bot(window_arg, chores_arg):
    global window
    global chores
    window = window_arg
    chores = chores_arg
    
    # Set window to fullscreen mode
    window.wm_attributes('-fullscreen', True)
    
    window.update_idletasks()
    window.update()
    client.run(token)





