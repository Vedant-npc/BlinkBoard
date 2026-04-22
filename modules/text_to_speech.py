"""
Text-to-Speech Module
Converts typed text to speech using pyttsx3.
"""

import pyttsx3
import threading


class TextToSpeech:
    """
    Text-to-Speech converter using pyttsx3.
    Supports multiple voices, rates, and volumes.
    """
    
    def __init__(self):
        """Initialize text-to-speech engine."""
        self.engine = pyttsx3.init()
        self.is_speaking = False
        self.engine.setProperty('rate', 150)  # Speed of speech
        self.engine.setProperty('volume', 1.0)  # Volume level
        
        # Get available voices
        self.voices = self.engine.getProperty('voices')
        self.current_voice_index = 0
        
        if self.voices:
            self.engine.setProperty('voice', self.voices[0].id)
    
    def speak(self, text):
        """
        Speak the given text synchronously.
        
        Args:
            text: Text to speak
        """
        if not text:
            return
        
        try:
            self.is_speaking = True
            self.engine.say(text)
            self.engine.runAndWait()
            self.is_speaking = False
        except Exception as e:
            print(f"Error in text-to-speech: {e}")
            self.is_speaking = False
    
    def speak_async(self, text):
        """
        Speak the given text asynchronously in a separate thread.
        
        Args:
            text: Text to speak
        """
        if not text:
            return
        
        thread = threading.Thread(target=self.speak, args=(text,))
        thread.daemon = True
        thread.start()
    
    def stop(self):
        """Stop current speech."""
        try:
            self.engine.stop()
            self.is_speaking = False
        except:
            pass
    
    def set_rate(self, rate):
        """
        Set speech rate (speed).
        
        Args:
            rate: Speech rate in words per minute (50-300, default 150)
        """
        rate = max(50, min(300, rate))  # Clamp between 50 and 300
        self.engine.setProperty('rate', rate)
    
    def set_volume(self, volume):
        """
        Set speech volume.
        
        Args:
            volume: Volume level (0.0 to 1.0)
        """
        volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        self.engine.setProperty('volume', volume)
    
    def set_voice(self, voice_index=None):
        """
        Set the voice to use.
        
        Args:
            voice_index: Index of voice to use (0 = first available)
        """
        if not self.voices:
            print("No voices available")
            return
        
        voice_index = voice_index if voice_index is not None else 0
        voice_index = max(0, min(len(self.voices) - 1, voice_index))
        
        self.current_voice_index = voice_index
        self.engine.setProperty('voice', self.voices[voice_index].id)
    
    def get_voices(self):
        """
        Get list of available voices.
        
        Returns:
            list: List of voice objects with 'name' and 'id' properties
        """
        voice_info = []
        for i, voice in enumerate(self.voices):
            voice_info.append({
                'index': i,
                'name': voice.name,
                'id': voice.id,
                'languages': voice.languages if hasattr(voice, 'languages') else []
            })
        return voice_info
    
    def get_current_settings(self):
        """
        Get current TTS settings.
        
        Returns:
            dict: Dictionary with current settings
        """
        return {
            'rate': self.engine.getProperty('rate'),
            'volume': self.engine.getProperty('volume'),
            'voice_index': self.current_voice_index,
            'is_speaking': self.is_speaking
        }
    
    def speak_character(self, char):
        """
        Speak a single character (useful for feedback).
        
        Args:
            char: Character to speak
        """
        # Map some special characters to words
        char_map = {
            ' ': 'space',
            '\n': 'new line',
            '.': 'period',
            ',': 'comma',
            '!': 'exclamation',
            '?': 'question',
            '-': 'dash',
            '1': 'one',
            '2': 'two',
            '3': 'three',
            '4': 'four',
            '5': 'five',
            '6': 'six',
            '7': 'seven',
            '8': 'eight',
            '9': 'nine',
            '0': 'zero',
        }
        
        text = char_map.get(char, char)
        self.speak(text)
    
    def close(self):
        """Close and release TTS engine."""
        try:
            self.engine.stop()
        except:
            pass
