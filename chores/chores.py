import tkinter as tk
import os
import datetime
from dotenv import load_dotenv
from chores_bot import run_chores_bot
from chores_bot import dishwasher_status, kitchen_status, wednesday_status

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

chore_people_2 = ["Isabelle", "Guido", "Daniel", "Charlotte", "Thomas"]
dishwasher_name = chore_people_2[dishwasher_status]
kitchen_name = chore_people_2[kitchen_status]
wednesday_name = chore_people_2[wednesday_status]

class Table:

    def __init__(self, window):
        global tk
        self.window = window
        self.labels = [
            tk.Label(window, text=f"Dishwasher: {dishwasher_name}", font=('Arial', 30, 'bold')),
            tk.Label(window, text=f"Kitchen Trash: {kitchen_name}", font=('Arial', 30, 'bold')),
            tk.Label(window, text=f"Wednesday Trash: {wednesday_name}", font=('Arial', 30, 'bold')),
            tk.Label(window, text=f"Today is {datetime.datetime.now().strftime('%a,\n %b %d,\n %H:%M:%S')}", font=('Arial', 30, 'bold')),

        ]
        # Make the time in the top left and everything else centered below
        self.labels[3].pack(anchor="nw", pady=(0, 20))  # Time label at the top left
        for label in self.labels[0:3]:
            label.pack(pady=20, anchor="center")  # Center the other labels below

    def update_labels(self, dishwasher_status, kitchen_status, wednesday_status):
        dishwasher_name = chore_people_2[dishwasher_status]
        kitchen_name = chore_people_2[kitchen_status]
        wednesday_name = chore_people_2[wednesday_status]
        self.labels[0].config(text=f"Dishwasher: {dishwasher_name}")
        self.labels[1].config(text=f"Kitchen Trash: {kitchen_name}")
        self.labels[2].config(text=f"Wednesday Trash: {wednesday_name}")
        self.labels[3].config(text=f"Today is {datetime.datetime.now().strftime('%a,\n %b %d,\n %H:%M:%S')}")


    
def chores():
    window = tk.Tk()
    t = Table(window)
    run_chores_bot(window,t)

if __name__ == "__main__":
    chores()

 




    
