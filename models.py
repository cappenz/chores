import os
import asyncio
from elevenlabs.play import play
from elevenlabs.client import ElevenLabs
from openai import OpenAI

ANNOUNCEMENT_VOICE_ID = "QvlD90AkjGTCqc9685Rq"

def generate_speech(chore_name: str, chore_person: str) -> str:
    client = OpenAI()

    intro_prompt = f"""
    Write a super short speech (two sentences max) to announce the fact that {chore_person} has to do the {chore_name} chore today.
    Start it by announcing that you are back!
    The speech should contain a joke about the person.
    """


    completion = client.chat.completions.create(
        model="gpt-5.4-mini", 
        messages=[{"role": "user", "content": intro_prompt}]
    )
    speech_text = completion.choices[0].message.content
    print(speech_text)
    return speech_text

def generate_audio(text: str) -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    client = ElevenLabs(api_key=api_key)
    audio = client.text_to_speech.convert(
        voice_id=ANNOUNCEMENT_VOICE_ID,
        text=text,
        model_id="eleven_multilingual_v2",
    )
    play(audio)

async def generate_and_play_audio_async(chore_name: str, chore_person: str) -> None:
    try:
        speech = await asyncio.to_thread(generate_speech, chore_name, chore_person)
        await asyncio.to_thread(generate_audio, speech)
    except Exception as e:
        print(f"Error generating or playing audio: {e}")

