import os
from elevenlabs import play
from elevenlabs.client import ElevenLabs
from openai import OpenAI

def generate_speech(chore_name: str, chore_person: str) -> str:
    client = OpenAI()
    intro_prompt = f"Announce the fact that {chore_person} has to do the {chore_name} chore today. Compoase a very very short speech composing of only the word turkey and once mention the chore and who has to do it. And add one thanksgiving related word."
    completion = client.chat.completions.create(
        model="gpt-4", 
        messages=[{"role": "user", "content": intro_prompt}]
    )
    speech_text = completion.choices[0].message.content
    print(speech_text)
    return speech_text

def generate_audio(text: str) -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    client = ElevenLabs(api_key=api_key)
    audio = client.generate(
        text=text,
        voice="Brian",
        model="eleven_multilingual_v2"
    )
    play(audio)

