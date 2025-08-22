import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from threading import Thread
import re
from songwriter import generate_package, to_markdown  # your existing songwriter.py

import pretty_midi 
from pychord import Chord 
import hashlib 

from dotenv import load_dotenv
load_dotenv()

# Globals
pkg = None
tempo = 120


def download_midi_file():
    global pkg, tempo
    if not pkg:
        song_text.delete("1.0", tk.END)
        song_text.insert(tk.END, "⚠️ Generate a song first to create MIDI.\n")
        return

    chords_str = pkg.get("musical_ideas", {}).get("chord_progression", "")
    if not chords_str.strip():
        song_text.delete("1.0", tk.END)
        song_text.insert(tk.END, "⚠️ No chord progression found in this song.\n")
        return

    # Clean and split chords
    VALID_CHORD_RE = re.compile(r'^[A-G][#b]?(maj|min|dim|aug|m|sus|7|9|11|13|6)?\d*$', re.IGNORECASE)
    raw_chords = [
        re.sub(r'[^\w#b]+', '', ch.strip())
        for ch in re.sub(r'[|;&]', ',', chords_str).split(",")
        if ch.strip() and VALID_CHORD_RE.match(re.sub(r'[^\w#b]+', '', ch.strip()))
    ]

    if not raw_chords:
        song_text.delete("1.0", tk.END)
        song_text.insert(tk.END, "⚠️ No valid chords found in the progression.\n")
        return

    # Ask user where to save
    filename = filedialog.asksaveasfilename(
        defaultextension=".mid",
        filetypes=[("MIDI files", "*.mid")],
        initialfile=f"{pkg.get('title','untitled')}.mid"
    )
    if not filename:
        return

    # Create PrettyMIDI object
    midi_data = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    piano_program = pretty_midi.instrument_name_to_program("Acoustic Grand Piano")
    piano = pretty_midi.Instrument(program=piano_program)

    # Add chords
    for n, ch_name in enumerate(raw_chords):
        try:
            chord_obj = Chord(ch_name)
            for note_name in chord_obj.components_with_pitch(root_pitch=4):
                note_number = pretty_midi.note_name_to_number(note_name)
                note = pretty_midi.Note(
                    velocity=100,
                    pitch=note_number,
                    start=n * 2,         # 2 beats per chord
                    end=n * 2 + 2
                )
                piano.notes.append(note)
        except Exception as e:
            print(f"⚠️ Could not parse chord '{ch_name}': {e}")

    midi_data.instruments.append(piano)

    # Save MIDI
    midi_data.write(filename)
    song_text.insert(tk.END, f"✅ MIDI saved to {filename}\n")

def reset_form():
    global pkg
    pkg = None
    for entry in [genre_entry, mood_entry, topic_entry, key_entry, tempo_entry, structure_entry, rhyme_entry, syllables_entry]:
        entry.delete(0, tk.END)
    song_text.delete("1.0", tk.END)
    new_song_btn.config(state="disabled")
    download_midi_btn.config(state="disabled")

def clean_filename(name: str) -> str:
    name = re.sub(r'[\\/:"*?<>|]+', '_', name)
    return name.strip().replace(" ", "_")

def generate_song_thread():
    progress_bar.start()
    generate_btn.config(state="disabled")
    try:
        global pkg, tempo

        class Args:
            genre = genre_entry.get()
            mood = mood_entry.get()
            topic = topic_entry.get()
            key = key_entry.get()
            tempo = int(tempo_entry.get() or 120)
            structure = structure_entry.get() or "verse, chorus, verse, chorus, bridge, chorus"
            rhyme = rhyme_entry.get() or None
            syllables = syllables_entry.get() or None
            language = "English"
            model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
            max_tokens = 1200
            outdir = Path("songs")
            basename = None
            force = True

        args = Args()
        tempo = args.tempo
        pkg = generate_package(args)

        # Save JSON and Markdown
        args.outdir.mkdir(exist_ok=True)
        base_title = clean_filename(pkg.get('title', 'untitled'))
        base = args.basename or base_title
        json_path = args.outdir / f"{base}.json"
        md_path = args.outdir / f"{base}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(pkg, f, ensure_ascii=False, indent=2)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(to_markdown(pkg))

        # Display song
        song_text.delete("1.0", tk.END)
        title = pkg.get("title", "Untitled")
        lyrics = pkg.get("lyrics", {})
        lyrics_str = ""
        if isinstance(lyrics, dict):
            for section, text in lyrics.items():
                text = text.strip()
                if text:
                    lyrics_str += f"{section.capitalize()}:\n{text}\n\n"
        else:
            lyrics_str = str(lyrics)

        chords_str = pkg.get("musical_ideas", {}).get("chord_progression", "")
        
        mdfile = to_markdown(pkg)
        md_nolyrics = re.sub(
            r'## Lyrics[\s\S]*?(?=## Production Notes|$)',  # match from "## Lyrics" to "## Production Notes" or end of file
            '',
            mdfile,
            flags=re.IGNORECASE
        )

        display_text = f"✅ Song Generated!\n\nTitle: {title}\n\n"
        display_text += "Chord Progression:\n" + chords_str + "\n\n"
        display_text += "Lyrics:\n" + lyrics_str
        display_text += md_nolyrics
        song_text.insert(tk.END, display_text)

        new_song_btn.config(state="normal")
        download_midi_btn.config(state="normal")

    except Exception as e:
        song_text.delete("1.0", tk.END)
        song_text.insert(tk.END, f"❌ Error: {e}\n")
    finally:
        progress_bar.stop()
        generate_btn.config(state="normal")

def generate_song():
    Thread(target=generate_song_thread, daemon=True).start()

# Build GUI
root = tk.Tk()
root.title("🎶 Song Writing Helper 🎶")

# Inputs
labels = ["Genre", "Mood", "Topic", "Key", "Tempo", "Structure", "Rhyme", "Syllables"]
entries = []
for i, text in enumerate(labels):
    tk.Label(root, text=f"{text}:").grid(row=i, column=0, sticky="e")
    entry = tk.Entry(root)
    entry.grid(row=i, column=1)
    entries.append(entry)

genre_entry, mood_entry, topic_entry, key_entry, tempo_entry, structure_entry, rhyme_entry, syllables_entry = entries

# Buttons
generate_btn = tk.Button(root, text="Generate Song", command=generate_song)
generate_btn.grid(row=8, column=0, columnspan=2, pady=5)

new_song_btn = tk.Button(root, text="Generate New Song", command=reset_form, state="disabled")
new_song_btn.grid(row=9, column=0, columnspan=2, pady=5)

download_midi_btn = tk.Button(root, text="Download MIDI File", command=download_midi_file, state="disabled")
download_midi_btn.grid(row=10, column=0, columnspan=2, pady=5)

# Song text display
song_text = tk.Text(root, height=20, width=70, wrap="word")
song_text.grid(row=11, column=0, columnspan=2, pady=5)
scroll = tk.Scrollbar(root, command=song_text.yview)
scroll.grid(row=11, column=2, sticky="ns")
song_text.config(yscrollcommand=scroll.set)

# Progress bar
progress_bar = ttk.Progressbar(root, mode="indeterminate")
progress_bar.grid(row=12, column=0, columnspan=2, sticky="ew", pady=5)

root.mainloop()
