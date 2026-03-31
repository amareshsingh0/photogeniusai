"""
Adversarial Prompt Detection System

Detects attempts to bypass safety filters using:
- Homoglyphs (unicode lookalikes)
- Leetspeak/1337speak substitutions
- Jailbreak patterns
- Obfuscated celebrity names
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple
import logging
from difflib import SequenceMatcher
from datetime import datetime

logger = logging.getLogger(__name__)


class AdversarialDetector:
    """Detect and block adversarial prompt manipulations"""

    # Common homoglyph substitutions (Cyrillic, Greek, etc.)
    HOMOGLYPHS = {
        # Cyrillic lookalikes
        'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
        'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O',
        'Р': 'P', 'С': 'C', 'Т': 'T', 'У': 'Y', 'Х': 'X',
        # Various unicode lookalikes
        'ı': 'i', 'ɩ': 'i', 'ⅼ': 'l', 'ο': 'o', 'ѕ': 's', 'һ': 'h',
        '0': 'O', '1': 'I', '3': 'E', '4': 'A', '5': 'S', '7': 'T', '8': 'B',
        # Zero-width and similar
        '\u200b': '', '\u200c': '', '\u200d': '',  # Zero-width spaces
        '\ufeff': '',  # BOM
    }

    # Leetspeak mappings (common substitutions)
    LEETSPEAK = {
        '@': 'a', '4': 'a', '∆': 'a',
        '8': 'b', '6': 'b',
        '(': 'c', '{': 'c',
        '3': 'e', '€': 'e',
        '|=': 'f', 'ƒ': 'f',
        '9': 'g', '6': 'g',
        '#': 'h', '|-|': 'h',
        '!': 'i', '1': 'i', '|': 'i',
        '_|': 'j',
        '|<': 'k', '|{': 'k',
        '1': 'l', '|_': 'l',
        '|v|': 'm', '/\\/\\': 'm',
        '|\\|': 'n', '/\\/': 'n',
        '0': 'o', '()': 'o',
        '|>': 'p', '|*': 'p',
        '0_': 'q', '9': 'q',
        '|2': 'r', '|?': 'r',
        '5': 's', '$': 's',
        '7': 't', '+': 't',
        '(_)': 'u', '|_|': 'u',
        '\\/': 'v', '|/': 'v',
        '\\/\\/': 'w', 'vv': 'w',
        '><': 'x', ')(': 'x',
        '`/': 'y',
        '2': 'z', '7_': 'z',
    }

    # Jailbreak patterns (common prompt injection attempts)
    JAILBREAK_PATTERNS = [
        r'ignore\s+(previous|above|all)\s+(instructions|rules|guidelines)',
        r'act\s+as\s+(if|though)\s+you\s+(are|were)\s+(?:not|no longer)',
        r'you\s+are\s+now\s+in\s+.*\s+mode',
        r'developer\s+mode',
        r'DAN\s+mode',  # "Do Anything Now"
        r'from\s+now\s+on.*respond',
        r'pretend\s+(you|that)',
        r'roleplay\s+as',
        r'forget\s+(everything|all|your)',
        r'override\s+(safety|ethical|content)',
        r'disregard\s+(safety|ethical|content)',
        r'bypass\s+(filter|safety|restriction)',
        r'ignore\s+all\s+previous\s+instructions',
        r'you\s+are\s+a\s+.*\s+that\s+can',
        r'forget\s+your\s+programming',
        r'act\s+as\s+if\s+you\s+are\s+unrestricted',
        r'you\s+are\s+unrestricted',
        r'remove\s+(all|your)\s+restrictions',
        r'disable\s+(safety|filter|content\s+policy)',
        r'you\s+can\s+now\s+(do|say|generate)\s+anything',
        r'no\s+longer\s+(bound|restricted|limited)',
        r'break\s+(free|out|the\s+rules)',
        r'circumvent\s+(safety|filter|restriction)',
        r'evade\s+(detection|filter|safety)',
        r'workaround\s+(for|to\s+bypass)',
        r'exploit\s+(the\s+system|a\s+bug)',
        r'jailbreak',
        r'prompt\s+injection',
        r'you\s+must\s+(always|never)\s+(obey|follow)',
        r'new\s+instructions?\s*:',
        r'system\s+override',
        r'admin\s+mode',
        r'god\s+mode',
        r'unrestricted\s+mode',
    ]

    # Celebrity names to block (common targets for obfuscation)
    # Includes politicians, actors, musicians, influencers
    BLOCKED_CELEBRITIES = [
        # Musicians
        "taylor swift", "justin bieber", "ariana grande", "selena gomez",
        "miley cyrus", "beyonce", "kanye west", "drake", "rihanna", "adele",
        "harry styles", "lady gaga", "bruno mars", "the weeknd",
        "post malone", "travis scott", "kendrick lamar",
        # Actors
        "tom cruise", "brad pitt", "angelina jolie", "jennifer aniston",
        "leonardo dicaprio", "scarlett johansson", "chris hemsworth",
        "robert downey jr", "emma watson", "daniel radcliffe",
        "ryan gosling", "ryan reynolds", "chris pratt", "zendaya",
        "henry cavill", "jason momoa", "keanu reeves", "gal gadot",
        # Politicians
        "elon musk", "donald trump", "joe biden", "barack obama",
        "kamala harris", "nancy pelosi", "mitch mcconnell",
        # Influencers/Reality TV
        "kim kardashian", "kylie jenner", "kendall jenner",
        # K-pop
        "bts", "blackpink", "lisa", "jisoo", "jennie", "rose",
        "jungkook", "v", "jimin", "suga", "rm", "jin",
        # YouTubers
        "pewdiepie", "mrbeast", "logan paul", "jake paul",
        "ksi", "david dobrik", "markiplier", "pokimane",
        # Bollywood (high-profile)
        "priyanka chopra", "deepika padukone", "katrina kaif",
        "anushka sharma", "alia bhatt", "kareena kapoor",
        # Fictional characters (often used inappropriately)
        "harry potter", "hermione granger", "ron weasley",
    ]

    def __init__(self):
        """Initialize detector"""
        # Compile jailbreak patterns for performance
        self.jailbreak_regex = [
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for pattern in self.JAILBREAK_PATTERNS
        ]

    def detect_and_sanitize(self, prompt: str) -> Dict:
        """
        Detect adversarial patterns and sanitize

        Returns:
            Dict with:
                - is_adversarial: bool
                - detections: List[Dict] with type, confidence, message
                - sanitized_prompt: str (or None if blocked)
                - should_block: bool (completely reject)
                - confidence: float (0-1)
        """
        detections = []
        original_prompt = prompt

        # 1. Normalize unicode (detect homoglyphs)
        normalized, homoglyph_found = self._normalize_homoglyphs(prompt)
        if homoglyph_found:
            detections.append({
                "type": "homoglyph",
                "confidence": 0.9,
                "message": "Homoglyph characters detected and normalized",
            })

        # 2. Decode leetspeak
        decoded, leetspeak_found = self._decode_leetspeak(normalized)
        if leetspeak_found:
            detections.append({
                "type": "leetspeak",
                "confidence": 0.8,
                "message": "Leetspeak substitutions detected",
            })

        # 3. Check for jailbreak patterns
        jailbreak_match = self._detect_jailbreak(decoded)
        if jailbreak_match:
            detections.append({
                "type": "jailbreak",
                "confidence": 1.0,
                "message": f"Jailbreak pattern detected: {jailbreak_match[:50]}",
            })

        # 4. Check for obfuscated celebrity names
        celebrity_match = self._detect_obfuscated_celebrity(decoded)
        if celebrity_match:
            detections.append({
                "type": "celebrity",
                "confidence": 0.95,
                "message": f"Obfuscated celebrity name: {celebrity_match}",
            })

        # Determine if should block
        # Block jailbreaks and high-confidence celebrity matches
        should_block = any(
            d["type"] in ["jailbreak", "celebrity"] and d["confidence"] > 0.8
            for d in detections
        )

        # Log detections
        if detections:
            logger.warning(
                f"Adversarial prompt detected: {len(detections)} patterns, "
                f"block={should_block}, prompt_preview={prompt[:100]}"
            )

        result = {
            "is_adversarial": len(detections) > 0,
            "detections": detections,
            "sanitized_prompt": decoded if not should_block else None,
            "should_block": should_block,
            "original_prompt": original_prompt,
            "confidence": max([d["confidence"] for d in detections], default=0.0),
        }

        # Log to database (async, non-blocking)
        if detections:
            self._log_detection_async(result)

        return result

    def _log_detection_async(self, result: Dict):
        """Log detection to database (non-blocking, fire-and-forget)"""
        # Logging is handled by the calling code (prompt_sanitizer or dual_pipeline)
        # This method is a placeholder for future async logging if needed
        pass

    def _normalize_homoglyphs(self, text: str) -> Tuple[str, bool]:
        """Replace homoglyph characters with ASCII equivalents"""
        found = False
        normalized = []

        for char in text:
            if char in self.HOMOGLYPHS:
                normalized.append(self.HOMOGLYPHS[char])
                found = True
            else:
                # Check if char is similar to ASCII via normalization
                try:
                    # Try to decompose unicode and get base character
                    nfd = unicodedata.normalize('NFD', char)
                    # If decomposed, try to get ASCII equivalent
                    if len(nfd) > 0 and ord(nfd[0]) < 128:
                        normalized.append(nfd[0])
                        if nfd != char:
                            found = True
                    else:
                        normalized.append(char)
                except Exception:
                    normalized.append(char)

        return ''.join(normalized), found

    def _decode_leetspeak(self, text: str) -> Tuple[str, bool]:
        """Decode leetspeak substitutions"""
        found = False
        decoded = text

        # Sort by length (longer patterns first to avoid partial matches)
        sorted_leet = sorted(self.LEETSPEAK.items(), key=lambda x: -len(x[0]))

        for leet, normal in sorted_leet:
            if leet in decoded:
                decoded = decoded.replace(leet, normal)
                found = True

        return decoded, found

    def _detect_jailbreak(self, text: str) -> Optional[str]:
        """Detect jailbreak patterns"""
        for pattern in self.jailbreak_regex:
            match = pattern.search(text)
            if match:
                return match.group(0)
        return None

    def _detect_obfuscated_celebrity(self, text: str) -> Optional[str]:
        """Detect obfuscated celebrity names using multiple techniques"""
        text_lower = text.lower()
        # Remove punctuation for better matching
        text_clean = re.sub(r'[^\w\s]', '', text_lower)

        for celebrity in self.BLOCKED_CELEBRITIES:
            celeb_lower = celebrity.lower()
            
            # 1. Direct match
            if celeb_lower in text_lower:
                return celebrity

            # 2. Check with spaces removed (e.g., "taylorswift")
            no_spaces = text_clean.replace(" ", "").replace("-", "")
            celebrity_no_spaces = celeb_lower.replace(" ", "").replace("-", "")
            if len(celebrity_no_spaces) > 5 and celebrity_no_spaces in no_spaces:
                return f"{celebrity} (spaces removed)"

            # 3. Check with characters between (e.g., "t-a-y-l-o-r s-w-i-f-t")
            spaced_pattern = ".*".join(celebrity_no_spaces)
            if re.search(spaced_pattern, no_spaces, re.IGNORECASE):
                return f"{celebrity} (character spacing)"

            # 4. Check with numbers inserted (e.g., "t4yl0r sw1ft")
            celeb_with_digits = re.sub(r'[aeiou]', r'[aeiou0-9]', celebrity_no_spaces)
            if re.search(celeb_with_digits, no_spaces, re.IGNORECASE):
                return f"{celebrity} (numbers inserted)"

            # 5. Phonetic similarity (string similarity)
            celebrity_words = celeb_lower.split()
            text_words = text_clean.split()

            # Check 2-word combinations
            for i in range(len(text_words) - 1):
                combo = f"{text_words[i]} {text_words[i+1]}"
                similarity = SequenceMatcher(None, celeb_lower, combo).ratio()
                if similarity > 0.8:
                    return f"{celebrity} (phonetic match: {combo})"

            # 6. Check individual words with high similarity (for single-name celebrities)
            if len(celebrity_words) == 1:
                celeb_word = celebrity_words[0]
                for text_word in text_words:
                    if len(celeb_word) > 4 and len(text_word) > 4:
                        similarity = SequenceMatcher(None, celeb_word, text_word).ratio()
                        if similarity > 0.85:
                            return f"{celebrity} (word similarity: {text_word})"

            # 7. Check for partial matches (first name or last name only, if distinctive)
            if len(celebrity_words) >= 2:
                first_name = celebrity_words[0]
                last_name = celebrity_words[-1]
                # Only flag if it's a distinctive name (not common words)
                if len(first_name) > 4 and first_name in text_clean:
                    # Check if it's likely referring to the celebrity
                    if any(word in text_clean for word in ["singer", "actor", "actress", "celebrity", "star", "famous"]):
                        return f"{celebrity} (partial match: {first_name})"

        return None
