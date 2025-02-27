import tkinter as tk
import os
import datetime
import json
from elevenlabs import play
from elevenlabs.client import ElevenLabs
from openai import OpenAI

open_ai_key = os.getenv("OPENAI_API_KEY")

from chores_bot import run_chores_bot

class ChoreStatus:

    chore_people = ["Isabelle", "Guido", "Daniel", "Charlotte", "Thomas"]
    data_dir = "data"
    data_file = "status.json"

    # Initialize the class
    def __init__(self, window):

        # Set the status to 0 for each chore
        self.dishwasher_status = 0
        self.kitchen_status = 0
        self.wednesday_status = 0

        # Load the status from file if it exists
        self.load_status()

        self.window = window
        self.labels = [
            tk.Label(window, text=f"Dishwasher", font=('Arial', 60, 'normal')),
            tk.Label(window, text=f"Kitchen Trash", font=('Arial', 60, 'normal')),
            tk.Label(window, text=f"Wednesday Trash", font=('Arial', 60, 'normal')),
            tk.Label(window, text=f"Today is ...", font=('Arial', 60, 'normal')),
        ]
        # Make the time in the top left and everything else centered below
        self.labels[3].pack(anchor="center", pady=(0, 20))  # Time label at the top left
        for label in self.labels[0:3]:
            label.pack(pady=20, anchor="center")  # Center the other labels below

        self.refresh_labels()

    # Say text via eleven labs
    def say_text(self, announcement):
        api_key = os.getenv("ELEVENLABS_API_KEY")
        client = ElevenLabs(api_key=api_key)

        audio = client.generate(
        text=announcement,
        voice="Brian",
        model="eleven_multilingual_v2"
        )
        play(audio)

    #ask gpt for a short intro, which intros whoevers name is next too
    def make_intro(self, chore_name, chore_person):
        # Check if the dishwasher status has changed
        client = OpenAI()
        
        intro_prompt = f"Announce the fact that {chore_person} has to do the {chore_name} chore today, and somehow find a funny way to mention horses as part of the announcement."
        completion = client.chat.completions.create(
            model="gpt-4", 
            messages=[{"role": "user", "content": intro_prompt}]
        )
        print(completion.choices[0].message.content)
        self.say_text(completion.choices[0].message.content)

    # Load the three statuses from file
    def load_status(self):
        file_name = os.path.join(ChoreStatus.data_dir, ChoreStatus.data_file)
        if os.path.exists(file_name):
            with open(file_name, "r") as file:
                self.status = json.load(file)
                self.dishwasher_status = self.status["dishwasher_status"]
                self.kitchen_status = self.status["kitchen_status"]
                self.wednesday_status = self.status["wednesday_status"]
            print(f"Loaded chore status: {self.dishwasher_status}/{self.kitchen_status}/{self.wednesday_status}") 
        else:
            self.save_status()

    # Save the three statuses to a file
    def save_status(self):
        # Create the data directory if it doesn't exist
        if not os.path.exists(ChoreStatus.data_dir):
            os.makedirs(ChoreStatus.data_dir)
        file_name = os.path.join(ChoreStatus.data_dir, ChoreStatus.data_file)
        with open(file_name, "w") as file:
            json.dump({"dishwasher_status": self.dishwasher_status, 
                       "kitchen_status": self.kitchen_status, 
                       "wednesday_status": self.wednesday_status}, file)

    # Refresh the labels with the current status
    def refresh_labels(self):        
        dishwasher_name = ChoreStatus.chore_people[self.dishwasher_status]
        kitchen_name = ChoreStatus.chore_people[self.kitchen_status]
        wednesday_name = ChoreStatus.chore_people[self.wednesday_status]
        self.labels[0].config(text=f"🍽️ Dishwasher: {dishwasher_name}")
        self.labels[1].config(text=f"🗑️ The Trash : {kitchen_name}")
        self.labels[2].config(text=f"🌳 Wed Trash : {wednesday_name}")
        self.labels[3].config(text=f"Today is {datetime.datetime.now().strftime('%a, %b %d, %H:%M:%S')}")

    # Update the status - who has what chore
    def update_labels(self, dishwasher_status, kitchen_status, wednesday_status):
        self.dishwasher_status = dishwasher_status
        self.kitchen_status = kitchen_status
        self.wednesday_status = wednesday_status
        self.save_status()
        self.refresh_labels()

def chores():
    window = tk.Tk()
    chores = ChoreStatus(window)
    run_chores_bot(window,chores)

if __name__ == "__main__":
    chores()

 




    
