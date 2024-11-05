import discord
from discord.ext import tasks
import os
from dotenv import load_dotenv
import datetime
load_dotenv()
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

chore_people = ["Isabelle, <@663405556312047633>", "Guido, <@339570174451646469>", "Daniel, <@341262399531122689>", "Charlotte, <@340964475135983618>", "Thomas,<@869351880155885600>"]
dishwasher_status = 0
kitchen_status = 0 
wednesday_status = 0
gone_status = 0

@client.event
async def on_ready():
    global window
    if not myLoop.is_running():
        myLoop.start()
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    global window, table
    global chore_people, dishwasher_status, kitchen_status, wednesday_status, gone_status
    if message.author == client.user:
        return

    if 'dish' in message.content.lower():
        dishwasher_status = dishwasher_status + 1
        if dishwasher_status >= len(chore_people):
            dishwasher_status = 0
        await message.channel.send(f"It's {chore_people[dishwasher_status]}'s turn to do the dishwasher")

    elif 'wednesday'in message.content.lower() or 'outside' in message.content.lower():
        wednesday_status = wednesday_status + 1
        if wednesday_status >= len(chore_people):
            wednesday_status = 0
        await message.channel.send(f"It's {chore_people[wednesday_status]}'s turn to do Wednesday trash")

    elif 'kitchen' in message.content.lower():
        kitchen_status = kitchen_status + 1
        if kitchen_status >= len(chore_people):
            kitchen_status = 0
        await message.channel.send(f"It's {chore_people[kitchen_status]}'s turn to do kitchen trash")

    elif 'gone' in message.content.lower():
        gone_status = gone_status + 1
        if gone_status >= len(chore_people):
            gone_status = 0
        await message.channel.send(f"It's {chore_people[gone_status]}'s turn to do the chore instead")

    elif 'info'in message.content.lower() or 'status' in message.content.lower():
        await message.channel.send(f"It's {chore_people[dishwasher_status]}'s turn to do the dishwasher,\n"
                                   f"It's {chore_people[kitchen_status]}'s turn to do the kitchen trash,\n"
                                   f"It's {chore_people[wednesday_status]}'s turn to do the Wednesday trash.")

    else:
        await message.channel.send("Please use the words 'dishwasher', 'wednesday', 'kitchen', or 'gone' to talk about what you need.")


    table.update_labels(dishwasher_status, kitchen_status, wednesday_status)    
    window.update_idletasks()
    window.update()

@tasks.loop(seconds = 1) # repeat after every 10 seconds
async def myLoop():
    global window
    window.update_idletasks()
    table.labels[3].config(text=f"Today is {datetime.datetime.now().strftime('%a,\n %b %d,\n %H:%M:%S')}")
    window.update()
    

def run_chores_bot(window_arg, table_arg):
    global window
    global table
    window = window_arg
    table = table_arg
    window.update_idletasks()
    window.update()
    client.run(token)





