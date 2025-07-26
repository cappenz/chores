import tkinter as tk
import os
import datetime
import json
from elevenlabs import play
from elevenlabs.client import ElevenLabs
from openai import OpenAI
import sys
from PIL import Image, ImageTk

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
        window.configure(bg="#f5f5f5")  # Light gray background
        
        # Create a main frame to hold everything
        main_frame = tk.Frame(window, bg="#f5f5f5", padx=40, pady=70)
        main_frame.pack(expand=True, fill="both")
        
        # Date/time display at the top
        self.time_label = tk.Label(
            main_frame, 
            text="Today is ...", 
            font=('Helvetica', 48, 'bold'),
            bg="#f5f5f5",
            fg="#333333"
        )
        self.time_label.pack(anchor="center", pady=(0, 100))
        
        # Create a horizontal frame for the chores with proper spacing
        chores_row = tk.Frame(main_frame, bg="#f5f5f5")
        chores_row.pack(fill="x", expand=True)
        
        # Configure the grid to distribute columns evenly
        chores_row.columnconfigure(0, weight=1)
        chores_row.columnconfigure(1, weight=1)
        chores_row.columnconfigure(2, weight=1)
        
        # Create frames for each chore column
        self.chore_frames = []
        self.chore_titles = []
        self.chore_images = []
        self.chore_photos = {}  # Dictionary to store photo references
        self.chore_names = []
        
        # Load all person images
        self.load_person_images()
        
        chore_data = [
            ("🍽️ Dishwasher", self.dishwasher_status),
            ("🗑️ Kitchen Trash", self.kitchen_status),
            ("🌳 Wed Trash", self.wednesday_status)
        ]
        
        # Create three columns for the chores
        for i, (chore_name, status) in enumerate(chore_data):
            # Create a frame for this chore column
            chore_frame = tk.Frame(chores_row, bg="#f5f5f5")
            chore_frame.grid(row=0, column=i, sticky="nsew")  # Use sticky to expand in all directions
            self.chore_frames.append(chore_frame)
            
            # Add the chore title
            title_label = tk.Label(
                chore_frame,
                text=chore_name,
                font=('Helvetica', 32, 'bold'),
                bg="#f5f5f5",
                fg="#555555"
            )
            title_label.pack(pady=(0, 15))
            self.chore_titles.append(title_label)
            
            # Add the person's image
            person_name = self.chore_people[status].lower()
            image_label = tk.Label(
                chore_frame,
                image=self.chore_photos[person_name],
                bg="#f5f5f5"
            )
            image_label.pack(pady=(0, 10))
            self.chore_images.append(image_label)
            
            # Add the person's name
            name_label = tk.Label(
                chore_frame,
                text=self.chore_people[status],
                font=('Helvetica', 30, 'normal'),
                bg="#f5f5f5",
                fg="#000000"
            )
            name_label.pack()
            self.chore_names.append(name_label)
        
        self.refresh_labels()

    # Load all person images
    def load_person_images(self):
        for person in self.chore_people:
            person_lower = person.lower()
            try:
                # Open the image file with the correct path
                image_path = f"data/{person_lower}.png"
                image = Image.open(image_path)
                
                # Crop the image to a square (centered)
                width, height = image.size
                
                # Determine the crop dimensions
                if width > height:
                    # Landscape image - crop the sides
                    left = (width - height) // 2
                    top = 0
                    right = left + height
                    bottom = height
                else:
                    # Portrait image - crop the top/bottom
                    left = 0
                    top = (height - width) // 2
                    right = width
                    bottom = top + width
                
                # Crop to square
                image = image.crop((left, top, right, bottom))
                
                # Resize to target size
                image = image.resize((300, 300), Image.LANCZOS)
                
                # Convert the PIL image to a format Tkinter can use
                photo = ImageTk.PhotoImage(image)
                self.chore_photos[person_lower] = photo
            except Exception as e:
                print(f"Error loading image for {person}: {e}")
                # Create a fallback image (gray square)
                fallback = Image.new('RGB', (300, 300), color='gray')
                self.chore_photos[person_lower] = ImageTk.PhotoImage(fallback)

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
        
        intro_prompt = f"Announce the fact that {chore_person} has to do the {chore_name} chore today. Find a funny way to mention how charlotte is the best member of the family. Be funny and short."
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
        
        # Format date in Japanese style with Kanji for year, month, day
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute
        second = now.second
        japanese_date = f"{year}年{month}月{day}日 {hour}時{minute}分{second}秒"
        
        self.time_label.config(text=japanese_date)
        
        # Update names
        self.chore_names[0].config(text=dishwasher_name)
        self.chore_names[1].config(text=kitchen_name)
        self.chore_names[2].config(text=wednesday_name)
        
        # Update images
        self.chore_images[0].config(image=self.chore_photos[dishwasher_name.lower()])
        self.chore_images[1].config(image=self.chore_photos[kitchen_name.lower()])
        self.chore_images[2].config(image=self.chore_photos[wednesday_name.lower()])

    # Update the status - who has what chore
    def update_labels(self, dishwasher_status, kitchen_status, wednesday_status):
        self.dishwasher_status = dishwasher_status
        self.kitchen_status = kitchen_status
        self.wednesday_status = wednesday_status
        self.save_status()
        self.refresh_labels()

def chores():
    window = tk.Tk()
    
    # Check for WINDOWMODE environment variable
    window_mode = os.getenv("WINDOWMODE")
    if window_mode:
        try:
            # Parse dimensions from the format like "1280 x 800"
            dimensions = window_mode.replace(" ", "").split("x")
            width = int(dimensions[0])
            height = int(dimensions[1])
            
            # Set window size
            window.geometry(f"{width}x{height}")
            # Ensure fullscreen is disabled when using window mode
            window.attributes('-fullscreen', False)
        except (ValueError, IndexError):
            print("Invalid WINDOWMODE format. Expected format: '1280 x 800'")
            # Exit the application if WINDOWMODE is incorrect
            sys.exit(1)
    else:
        # Default to fullscreen
        window.attributes('-fullscreen', True)
    
    chores = ChoreStatus(window)
    run_chores_bot(window, chores)

if __name__ == "__main__":
    chores()

 




    
