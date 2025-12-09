import os
import asyncio
from elevenlabs import play
from elevenlabs.client import ElevenLabs
from openai import OpenAI

def generate_speech(chore_name: str, chore_person: str) -> str:
    client = OpenAI()
    intro_prompt = f"Announce the fact that {chore_person} has to do the {chore_name} chore today. Compoase a very very short speech composing of winter holiday or decemeber joke, a the name of who has to do what chore"
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

async def generate_and_play_audio_async(chore_name: str, chore_person: str) -> None:
    try:
        speech = await asyncio.to_thread(generate_speech, chore_name, chore_person)
        await asyncio.to_thread(generate_audio, speech)
    except Exception as e:
        print(f"Error generating or playing audio: {e}")

