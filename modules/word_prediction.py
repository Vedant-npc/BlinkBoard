"""
Word Prediction Module
Provides word suggestions based on typed characters.
"""

from collections import defaultdict


class WordPredictor:
    """
    Simple word predictor that suggests words based on typed prefix.
    Uses a basic dictionary and frequency-based ranking.
    """
    
    # Common English words with frequency scores
    COMMON_WORDS = {
        # Most common words
        'the': 100, 'be': 95, 'to': 90, 'of': 88, 'and': 87,
        'a': 85, 'in': 84, 'that': 82, 'have': 80, 'i': 78,
        'it': 76, 'for': 75, 'not': 74, 'on': 73, 'with': 72,
        'he': 71, 'as': 70, 'you': 69, 'do': 68, 'at': 67,
        'this': 66, 'but': 65, 'his': 64, 'by': 63, 'from': 62,
        'they': 61, 'we': 60, 'say': 59, 'her': 58, 'she': 57,
        'or': 56, 'an': 55, 'will': 54, 'my': 53, 'one': 52,
        'all': 51, 'would': 50, 'there': 49, 'their': 48, 'what': 47,
        
        # Common phrases and words
        'hello': 45, 'yes': 44, 'no': 43, 'please': 42, 'thank': 41,
        'thanks': 40, 'sorry': 39, 'help': 38, 'water': 37, 'food': 36,
        'pain': 35, 'medicine': 34, 'doctor': 33, 'hospital': 32, 'family': 31,
        'friend': 30, 'love': 29, 'home': 28, 'time': 27, 'day': 26,
        'good': 25, 'bad': 24, 'better': 23, 'best': 22, 'more': 21,
        'less': 20, 'come': 19, 'go': 18, 'give': 17, 'take': 16,
        'know': 15, 'think': 14, 'feel': 13, 'want': 12, 'need': 11,
        'make': 10, 'see': 9, 'hear': 8, 'talk': 7, 'walk': 6,
        'run': 5, 'sit': 4, 'stand': 3, 'sleep': 2, 'wake': 1,
        
        # Customizable common communication phrases
        'communication': 50, 'care': 49, 'able': 48, 'comfortable': 47,
        'tired': 46, 'happy': 45, 'sad': 44, 'frustrated': 43,
    }
    
    def __init__(self, custom_words=None):
        """
        Initialize word predictor.
        
        Args:
            custom_words: Dictionary of custom words with frequencies
        """
        self.words = self.COMMON_WORDS.copy()
        
        if custom_words:
            self.words.update(custom_words)
        
        # Build prefix lookup for faster searching
        self._rebuild_prefix_index()
    
    def _rebuild_prefix_index(self):
        """Build prefix index for efficient word lookup."""
        self.prefix_index = defaultdict(list)
        
        for word, frequency in self.words.items():
            # Add all prefixes of the word
            for i in range(1, len(word) + 1):
                prefix = word[:i]
                self.prefix_index[prefix].append((word, frequency))
            
            # Sort by frequency
            self.prefix_index[prefix].sort(key=lambda x: x[1], reverse=True)
    
    def predict(self, prefix, max_suggestions=5):
        """
        Get word predictions based on prefix.
        
        Args:
            prefix: Typed prefix (can be partial word)
            max_suggestions: Maximum number of suggestions to return
        
        Returns:
            list: List of suggested words, sorted by frequency
        """
        if not prefix:
            # Return top words if no prefix
            sorted_words = sorted(self.words.items(), key=lambda x: x[1], reverse=True)
            return [word for word, _ in sorted_words[:max_suggestions]]
        
        prefix_lower = prefix.lower()
        
        # Get suggestions from prefix index
        suggestions = self.prefix_index.get(prefix_lower, [])
        
        if not suggestions:
            return []
        
        # Return top suggestions
        return [word for word, _ in suggestions[:max_suggestions]]
    
    def get_top_word(self, prefix):
        """
        Get the top suggested word for a prefix.
        
        Args:
            prefix: Typed prefix
        
        Returns:
            str: Top suggested word, or None if no suggestions
        """
        predictions = self.predict(prefix, max_suggestions=1)
        return predictions[0] if predictions else None
    
    def add_word(self, word, frequency=10):
        """
        Add a custom word to the predictor.
        
        Args:
            word: Word to add
            frequency: Frequency score (higher = more common)
        """
        word_lower = word.lower()
        self.words[word_lower] = frequency
        self._rebuild_prefix_index()
    
    def add_words(self, words_dict):
        """
        Add multiple custom words.
        
        Args:
            words_dict: Dictionary of {word: frequency}
        """
        for word, frequency in words_dict.items():
            self.add_word(word, frequency)
    
    def remove_word(self, word):
        """
        Remove a word from predictor.
        
        Args:
            word: Word to remove
        """
        word_lower = word.lower()
        if word_lower in self.words:
            del self.words[word_lower]
            self._rebuild_prefix_index()
    
    def update_frequency(self, word, frequency):
        """
        Update frequency of a word.
        
        Args:
            word: Word to update
            frequency: New frequency score
        """
        word_lower = word.lower()
        if word_lower in self.words:
            self.words[word_lower] = frequency
            self._rebuild_prefix_index()
    
    def get_similar_words(self, typed_text):
        """
        Get suggestions considering user might type uncompleted text.
        
        Args:
            typed_text: Text typed so far
        
        Returns:
            list: List of word suggestions
        """
        words = typed_text.strip().split()
        
        if not words:
            return self.predict("", max_suggestions=10)
        
        # Use last word as prefix
        current_word = words[-1]
        return self.predict(current_word, max_suggestions=10)
    
    def correct_word(self, word):
        """
        Simple spell correction - finds closest match.
        
        Args:
            word: Word to correct
        
        Returns:
            str: Best matched word from dictionary
        """
        word_lower = word.lower()
        
        # If word exists, return it
        if word_lower in self.words:
            return word_lower
        
        # Find closest match using prefix matching
        for i in range(len(word_lower), 0, -1):
            prefix = word_lower[:i]
            suggestions = self.predict(prefix, max_suggestions=1)
            if suggestions:
                return suggestions[0]
        
        return word_lower
