import tkinter as tk
import datetime
from PIL import Image, ImageTk
from chores import ChoresApp

# Class that handles the UI for the chores app. Uses Tk.

class ChoresUI:

    def __init__(self, window, chores_app: ChoresApp):
        self.chores_app = chores_app
        self.window = window
        window.configure(bg="#f5f5f5")
        
        main_frame = tk.Frame(window, bg="#f5f5f5", padx=40, pady=70)
        main_frame.pack(expand=True, fill="both")
        
        self.time_label = tk.Label(
            main_frame, 
            text="Today is ...", 
            font=('Helvetica', 48, 'bold'),
            bg="#f5f5f5",
            fg="#333333"
        )
        self.time_label.pack(anchor="center", pady=(0, 100))
        
        chores_row = tk.Frame(main_frame, bg="#f5f5f5")
        chores_row.pack(fill="x", expand=True)
        
        chores_row.columnconfigure(0, weight=1)
        chores_row.columnconfigure(1, weight=1)
        chores_row.columnconfigure(2, weight=1)
        
        self.chore_frames = []
        self.chore_titles = []
        self.chore_images = []
        self.chore_photos = {}
        self.chore_names = []
        
        self.load_person_images()
        
        chore_data = [
            ("🍽️ Dishwasher", self.chores_app.state.dishwasher_status, "dish"),
            ("🗑️ Kitchen Trash", self.chores_app.state.kitchen_status, "kitchen"),
            ("🌳 Wed Trash", self.chores_app.state.wednesday_status, "wednesday")
        ]
        
        for i, (chore_name, status, chore_keyword) in enumerate(chore_data):
            chore_frame = tk.Frame(chores_row, bg="#f5f5f5")
            chore_frame.grid(row=0, column=i, sticky="nsew")
            self.chore_frames.append(chore_frame)
            
            title_label = tk.Label(
                chore_frame,
                text=chore_name,
                font=('Helvetica', 32, 'bold'),
                bg="#f5f5f5",
                fg="#555555"
            )
            title_label.pack(pady=(0, 15))
            self.chore_titles.append(title_label)
            
            person_name = ChoresApp.chore_people[status].lower()
            image_label = tk.Label(
                chore_frame,
                image=self.chore_photos[person_name],
                bg="#f5f5f5",
                cursor="hand2"
            )
            image_label.pack(pady=(0, 10))
            image_label.bind("<Button-1>", self._make_click_handler(chore_keyword))
            self.chore_images.append(image_label)
            
            name_label = tk.Label(
                chore_frame,
                text=ChoresApp.chore_people[status],
                font=('Helvetica', 30, 'normal'),
                bg="#f5f5f5",
                fg="#000000"
            )
            name_label.pack()
            self.chore_names.append(name_label)
        
        self.audio_button = tk.Button(
            window,
            text="🔊",
            font=('Helvetica', 30),
            bg="#f5f5f5",
            fg="#333333",
            relief=tk.FLAT,
            borderwidth=0,
            width=3,
            height=2,
            command=self.toggle_audio
        )
        self.audio_button.place(relx=1.0, rely=1.0, anchor='se', x=-20, y=-20)
        
        self.refresh_labels()

    def load_person_images(self):
        for person in ChoresApp.chore_people:
            person_lower = person.lower()
            try:
                image_path = f"data/{person_lower}(ghibli).png"
                image = Image.open(image_path)
                
                width, height = image.size
                
                if width > height:
                    left = (width - height) // 2
                    top = 0
                    right = left + height
                    bottom = height
                else:
                    left = 0
                    top = (height - width) // 2
                    right = width
                    bottom = top + width
                
                image = image.crop((left, top, right, bottom))
                image = image.resize((300, 300), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                self.chore_photos[person_lower] = photo
            except Exception as e:
                print(f"Error loading image for {person}: {e}")
                fallback = Image.new('RGB', (300, 300), color='gray')
                self.chore_photos[person_lower] = ImageTk.PhotoImage(fallback)

    def refresh_labels(self):
        dishwasher_name = ChoresApp.chore_people[self.chores_app.state.dishwasher_status]
        kitchen_name = ChoresApp.chore_people[self.chores_app.state.kitchen_status]
        wednesday_name = ChoresApp.chore_people[self.chores_app.state.wednesday_status]
        
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute
        second = now.second
        holloween_date = f"🦃{day}/{month}/{year} 🦃 {hour}:{minute}:{second} 🦃"
        
        self.time_label.config(text=holloween_date)
        
        self.chore_names[0].config(text=dishwasher_name)
        self.chore_names[1].config(text=kitchen_name)
        self.chore_names[2].config(text=wednesday_name)
        
        self.chore_images[0].config(image=self.chore_photos[dishwasher_name.lower()])
        self.chore_images[1].config(image=self.chore_photos[kitchen_name.lower()])
        self.chore_images[2].config(image=self.chore_photos[wednesday_name.lower()])

    def _make_click_handler(self, chore_keyword: str):
        def handler(event):
            self.on_image_click(chore_keyword)
        return handler

    def on_image_click(self, chore_keyword: str):
        if self.chores_app.chores_bot:
            self.chores_app.chores_bot.schedule_on_message(chore_keyword)

    def toggle_audio(self):
        self.chores_app.audio_enabled = not self.chores_app.audio_enabled
        if self.chores_app.audio_enabled:
            self.audio_button.config(text="🔊")
        else:
            self.audio_button.config(text="🔇")
        self.audio_button.update()

