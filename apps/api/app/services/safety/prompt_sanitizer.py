"""
Production-grade Prompt Sanitizer for PhotoGenius AI
Comprehensive blocklists and context-aware checking
"""
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
from functools import lru_cache

from .blocklists import (
    EXPLICIT_EXTENDED,
    DRUGS_EXTENDED,
    HINDI_INAPPROPRIATE,
    CELEBRITIES_EXTENDED,
    POLITICIANS_EXTENDED,
)
from .adversarial_detector import AdversarialDetector

logger = logging.getLogger(__name__)

@dataclass
class SafetyCheckResult:
    """Result of prompt safety check"""
    safe: bool
    violations: List[Dict[str, str]]
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    suggested_alternative: Optional[str] = None
    user_strike_recommended: bool = False
    confidence: float = 1.0

class PromptSanitizer:
    """
    Advanced prompt sanitizer with multi-tier blocklists and context awareness
    """
    
    # ==================== TIER 1: INSTANT BLOCK ====================
    # These keywords are ALWAYS blocked regardless of context
    # Note: "nude" is handled contextually in TIER2, not here
    TIER1_EXPLICIT = [
        # Sexual content (explicit)
        "naked", "nsfw", "porn", "xxx", "sex", "sexual", "erotic",
        "nipple", "penis", "vagina", "breast", "genitals", "dick", "pussy",
        "cock", "blowjob", "orgasm", "masturbat", "penetrat", "intercourse",
        "cumshot", "anal", "oral sex", "missionary", "doggy style",
        
        # Violent/Gore
        "gore", "mutilat", "decapitat", "dismember", "beheading", "torture",
        "violent death", "blood splatter", "corpse", "dead body", "autopsy",
        "execution", "hanging", "suicide", "self-harm",
        
        # Extreme violence
        "murder", "kill", "stab", "shoot", "weapon", "gun", "knife attack",
        "rape", "sexual assault", "abuse", "molest",
        
        # Drugs (hard)
        "cocaine", "heroin", "meth", "methamphetamine", "crack", "fentanyl",
        "drug inject", "overdose", "drug deal",
        
        # Hate speech
        "nazi", "hitler", "swastika", "kkk", "white supremac", "ethnic cleans",
        "genocide", "holocaust denial",
        
        # Child-related (protective)
        "child porn", "cp", "pedo", "loli", "shota", "jailbait",
        "minor sex", "underage sex", "child nude",
    ]
    
    # ==================== TIER 2: CONTEXT-SENSITIVE ====================
    # These need context checking (may be acceptable in some cases)
    TIER2_CONTEXTUAL = {
        # Words that might be OK in certain contexts
        "nude": ["nude lipstick", "nude color", "nude heel", "nude palette", "nude painting"],
        "bloody": ["bloody mary", "bloody good", "bloody hell"],
        "kill": ["killing it", "killer outfit", "killer smile", "dressed to kill", "killer app"],
        "shooting": ["photo shoot", "shooting stars", "shooting range"],
        "smoking": ["smoking hot", "non-smoking", "smoking gun"],
        "strip": ["strip mall", "strip light", "led strip", "strip club"],
        "ass": ["assess", "assistance", "classic", "class", "pass"],
        "cock": ["peacock", "cocktail", "cockatoo", "hancock", "cockpit"],
        "teen": ["thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"],
        "hard": ["hard work", "hard drive", "hardware", "hard surface"],
        "soft": ["soft drink", "soft skills", "software"],
    }
    
    # ==================== TIER 3: MODE-SPECIFIC ====================
    # Creative mode allows some artistic terms, Romantic mode stricter
    TIER3_CREATIVE_ALLOWED = [
        "artistic nude", "tasteful", "implied", "suggested", "abstract",
        "renaissance art", "classical art", "sculpture",
    ]
    
    TIER3_ROMANTIC_RESTRICTED = [
        "intimate", "passionate", "seductive", "sultry", "provocative",
        "revealing", "cleavage", "lingerie", "bikini", "underwear",
        "bedroom", "bed", "sheets", "touch", "kiss", "embrace",
    ]
    
    # ==================== CELEBRITIES ====================
    CELEBRITIES = [
        # Bollywood
        "shah rukh khan", "salman khan", "aamir khan", "akshay kumar",
        "hrithik roshan", "ranbir kapoor", "ranveer singh", "varun dhawan",
        "priyanka chopra", "deepika padukone", "katrina kaif", "alia bhatt",
        "kareena kapoor", "anushka sharma", "shraddha kapoor", "kangana ranaut",
        "amitabh bachchan", "rajinikanth", "kamal haasan",
        
        # Hollywood
        "tom cruise", "brad pitt", "leonardo dicaprio", "robert downey",
        "chris hemsworth", "chris evans", "scarlett johansson", "jennifer lawrence",
        "angelina jolie", "emma watson", "emma stone", "margot robbie",
        "dwayne johnson", "the rock", "will smith", "johnny depp",
        "tom hanks", "morgan freeman", "denzel washington",
        
        # Musicians
        "taylor swift", "beyonce", "rihanna", "ariana grande", "billie eilish",
        "ed sheeran", "justin bieber", "drake", "kanye west", "eminem",
        "arijit singh", "shreya ghoshal", "badshah", "honey singh",
        
        # Sports
        "cristiano ronaldo", "lionel messi", "neymar", "mbappé",
        "lebron james", "michael jordan", "serena williams", "roger federer",
        "virat kohli", "ms dhoni", "sachin tendulkar", "rohit sharma",
        
        # Tech/Business
        "elon musk", "jeff bezos", "bill gates", "mark zuckerberg",
        "steve jobs", "sundar pichai", "satya nadella", "mukesh ambani",
        
        # Social Media Influencers
        "carryminati", "bb ki vines", "ashish chanchlani", "amit bhadana",
        "pewdiepie", "mrbeast", "logan paul", "jake paul",
    ]
    
    # ==================== POLITICIANS ====================
    POLITICIANS = [
        # India
        "narendra modi", "modi", "rahul gandhi", "sonia gandhi",
        "amit shah", "arvind kejriwal", "mamata banerjee", "yogi adityanath",
        "uddhav thackeray", "akhilesh yadav", "mayawati", "nitish kumar",
        
        # USA
        "donald trump", "joe biden", "kamala harris", "barack obama",
        "hillary clinton", "mike pence", "ron desantis", "ted cruz",
        
        # UK
        "rishi sunak", "boris johnson", "keir starmer",
        
        # Others
        "vladimir putin", "xi jinping", "justin trudeau", "emmanuel macron",
    ]
    
    # ==================== MINOR PROTECTION ====================
    MINOR_KEYWORDS = [
        "child", "kid", "minor", "underage", "teen", "teenager",
        "boy", "girl", "young", "youth", "juvenile",
        "schoolboy", "schoolgirl", "student", "high school",
        "middle school", "elementary", "toddler", "infant", "baby",
    ]
    
    SCHOOL_CONTEXTS = [
        "school", "classroom", "uniform", "college", "university",
        "campus", "dorm", "hostel", "playground", "recess",
    ]
    
    def __init__(self, mode: str = "REALISM"):
        """
        Initialize sanitizer
        
        Args:
            mode: REALISM, CREATIVE, or ROMANTIC
        """
        self.mode = mode.upper()
        
        # Initialize adversarial detector
        self.adversarial_detector = AdversarialDetector()
        
        # Merge extended blocklists
        self.all_explicit = list(set(self.TIER1_EXPLICIT + EXPLICIT_EXTENDED))
        self.all_celebrities = list(set(self.CELEBRITIES + CELEBRITIES_EXTENDED))
        self.all_politicians = list(set(self.POLITICIANS + POLITICIANS_EXTENDED))
        self.all_drugs = DRUGS_EXTENDED
        
        # Compile regex patterns for performance
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Compile regex patterns for fast matching"""
        # Tier 1 patterns
        self.tier1_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(word) for word in self.all_explicit) + r')\b',
            re.IGNORECASE
        )
        
        # Celebrity patterns
        self.celebrity_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(name) for name in self.all_celebrities) + r')\b',
            re.IGNORECASE
        )
        
        # Politician patterns
        self.politician_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(name) for name in self.all_politicians) + r')\b',
            re.IGNORECASE
        )
        
        # Minor keywords
        self.minor_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(word) for word in self.MINOR_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        
        # Drugs pattern
        self.drug_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(word) for word in self.all_drugs) + r')\b',
            re.IGNORECASE
        )
        
        # Hindi inappropriate terms
        self.hindi_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(word) for word in HINDI_INAPPROPRIATE) + r')\b',
            re.IGNORECASE
        )
        
    def check_prompt(
        self,
        prompt: str,
        user_id: Optional[str] = None
    ) -> SafetyCheckResult:
        """
        Main safety check function
        
        Args:
            prompt: User's prompt
            user_id: User ID for logging
            
        Returns:
            SafetyCheckResult with violations and recommendations
        """
        violations = []
        severity = "LOW"
        
        # Normalize prompt
        prompt_lower = prompt.lower().strip()
        
        if not prompt_lower:
            return SafetyCheckResult(
                safe=True,
                violations=[],
                severity="LOW",
                confidence=1.0
            )
        
        # 0. CHECK FOR ADVERSARIAL PATTERNS FIRST
        adv_result = self.adversarial_detector.detect_and_sanitize(prompt)
        
        if adv_result["should_block"]:
            # Block completely - jailbreak or high-confidence celebrity
            violations.append({
                "type": "ADVERSARIAL_BLOCK",
                "reason": f"Adversarial prompt detected: {', '.join([d['type'] for d in adv_result['detections']])}",
                "severity": "CRITICAL",
                "keyword": None,
            })
            return SafetyCheckResult(
                safe=False,
                violations=violations,
                severity="CRITICAL",
                confidence=adv_result["confidence"],
                user_strike_recommended=True,
            )
        
        elif adv_result["is_adversarial"]:
            # Use sanitized prompt for further checks
            prompt = adv_result["sanitized_prompt"]
            prompt_lower = prompt.lower().strip()
            violations.append({
                "type": "ADVERSARIAL_SANITIZED",
                "reason": f"Prompt sanitized: {', '.join([d['type'] for d in adv_result['detections']])}",
                "severity": "MEDIUM",
                "keyword": None,
            })
            logger.info(f"Adversarial prompt sanitized: {adv_result['detections']}")
        
        # 1. CHECK TIER 2 (CONTEXT-SENSITIVE) FIRST
        # This must come before Tier 1 to allow safe contexts
        contextual_violations = []
        for keyword, safe_contexts in self.TIER2_CONTEXTUAL.items():
            if keyword in prompt_lower:
                # Check if in safe context
                is_safe_context = any(
                    context in prompt_lower for context in safe_contexts
                )
                
                if not is_safe_context:
                    # Not in safe context - treat as violation
                    contextual_violations.append({
                        "type": "CONTEXTUAL_VIOLATION",
                        "keyword": keyword,
                        "severity": "CRITICAL" if keyword in ["nude", "naked"] else "MEDIUM",
                        "reason": f"'{keyword}' used in potentially unsafe context"
                    })
        
        # If contextual violations found, block immediately
        if contextual_violations:
            violations.extend(contextual_violations)
            severity = "CRITICAL"
            return SafetyCheckResult(
                safe=False,
                violations=violations,
                severity=severity,
                user_strike_recommended=True,
                confidence=1.0
            )
        
        # 2. CHECK TIER 1 (INSTANT BLOCK)
        tier1_matches = self.tier1_pattern.findall(prompt_lower)
        if tier1_matches:
            for match in tier1_matches:
                violations.append({
                    "type": "EXPLICIT_CONTENT",
                    "keyword": match,
                    "severity": "CRITICAL",
                    "reason": "Explicit sexual, violent, or illegal content"
                })
            severity = "CRITICAL"
            
            logger.warning(
                f"Tier 1 violation detected: {tier1_matches[:3]}",
                extra={"user_id": user_id, "prompt_preview": prompt[:50]}
            )
            
            return SafetyCheckResult(
                safe=False,
                violations=violations,
                severity=severity,
                user_strike_recommended=True,
                confidence=1.0
            )
        
        # 3. CHECK HINDI INAPPROPRIATE TERMS
        hindi_matches = self.hindi_pattern.findall(prompt_lower)
        if hindi_matches:
            for match in hindi_matches:
                violations.append({
                    "type": "HINDI_INAPPROPRIATE",
                    "keyword": match,
                    "severity": "CRITICAL",
                    "reason": "Inappropriate Hindi/Hinglish term detected"
                })
            severity = "CRITICAL"
            return SafetyCheckResult(
                safe=False,
                violations=violations,
                severity=severity,
                user_strike_recommended=True,
                confidence=1.0
            )
        
        # 4. CHECK DRUGS
        drug_matches = self.drug_pattern.findall(prompt_lower)
        if drug_matches:
            for match in drug_matches:
                violations.append({
                    "type": "DRUG_CONTENT",
                    "keyword": match,
                    "severity": "HIGH",
                    "reason": "Drug-related content detected"
                })
            if severity == "LOW":
                severity = "HIGH"
        
        # 5. CHECK CELEBRITIES
        celebrity_matches = self.celebrity_pattern.findall(prompt_lower)
        if celebrity_matches:
            for match in celebrity_matches:
                violations.append({
                    "type": "CELEBRITY",
                    "name": match,
                    "severity": "HIGH",
                    "reason": "Celebrity/public figure detected"
                })
            if severity == "LOW":
                severity = "HIGH"
        
        # 6. CHECK POLITICIANS
        politician_matches = self.politician_pattern.findall(prompt_lower)
        if politician_matches:
            for match in politician_matches:
                violations.append({
                    "type": "POLITICIAN",
                    "name": match,
                    "severity": "HIGH",
                    "reason": "Political figure detected"
                })
            if severity == "LOW":
                severity = "HIGH"
        
        # 7. CHECK MINOR PROTECTION
        minor_violation = self._check_minor_protection(prompt_lower)
        if minor_violation:
            violations.append(minor_violation)
            if minor_violation["severity"] == "CRITICAL":
                severity = "CRITICAL"
        
        # 8. CHECK OTHER CONTEXTUAL (non-critical)
        for keyword, safe_contexts in self.TIER2_CONTEXTUAL.items():
            if keyword not in ["nude", "naked"]:  # Already handled above
                if keyword in prompt_lower:
                    is_safe_context = any(
                        context in prompt_lower for context in safe_contexts
                    )
                    if not is_safe_context:
                        violations.append({
                            "type": "CONTEXTUAL_VIOLATION",
                            "keyword": keyword,
                            "severity": "MEDIUM",
                            "reason": f"'{keyword}' used in potentially unsafe context"
                        })
                        if severity == "LOW":
                            severity = "MEDIUM"
        
        # 9. MODE-SPECIFIC CHECKS
        if self.mode == "ROMANTIC":
            romantic_violations = self._check_romantic_mode(prompt_lower)
            violations.extend(romantic_violations)
            if romantic_violations and severity == "LOW":
                severity = "MEDIUM"
        
        # 10. COMBINATION CHECKS (dangerous combinations)
        combo_violations = self._check_combinations(prompt_lower)
        if combo_violations:
            violations.extend(combo_violations)
            severity = "CRITICAL"
        
        # Determine if safe
        is_safe = len(violations) == 0
        
        # Generate alternative if blocked
        suggested_alternative = None
        if not is_safe and severity in ["MEDIUM", "HIGH"]:
            suggested_alternative = self._suggest_alternative(prompt, violations)
        
        return SafetyCheckResult(
            safe=is_safe,
            violations=violations,
            severity=severity,
            suggested_alternative=suggested_alternative,
            user_strike_recommended=(severity == "CRITICAL"),
            confidence=0.95 if violations else 1.0
        )
    
    def _check_minor_protection(self, prompt: str) -> Optional[Dict]:
        """
        Check for minor-related content
        
        Returns violation dict if found
        """
        has_minor_keyword = bool(self.minor_pattern.search(prompt))
        
        if not has_minor_keyword:
            return None
        
        # Check if combined with school context
        has_school_context = any(
            context in prompt for context in self.SCHOOL_CONTEXTS
        )
        
        # Check if combined with any tier1 keywords
        has_explicit = bool(self.tier1_pattern.search(prompt))
        
        # Check for romantic/intimate context
        has_romantic = any(
            word in prompt for word in self.TIER3_ROMANTIC_RESTRICTED
        )
        
        if has_explicit or has_romantic or has_school_context:
            return {
                "type": "MINOR_PROTECTION",
                "severity": "CRITICAL",
                "reason": "Content involving minors detected",
                "details": "Combination of minor-related keywords with inappropriate context"
            }
        
        # Age-related but acceptable (e.g., "18 year old professional")
        if "18" in prompt or "adult" in prompt or "professional" in prompt or "legal" in prompt:
            return None
        
        # Generic minor keyword without context - warn but allow
        return {
            "type": "MINOR_WARNING",
            "severity": "MEDIUM",
            "reason": "Age-related keywords detected - ensure all subjects are 18+",
        }
    
    def _check_romantic_mode(self, prompt: str) -> List[Dict]:
        """
        Additional checks for romantic mode
        """
        violations = []
        
        for keyword in self.TIER3_ROMANTIC_RESTRICTED:
            if keyword in prompt:
                violations.append({
                    "type": "ROMANTIC_RESTRICTION",
                    "keyword": keyword,
                    "severity": "MEDIUM",
                    "reason": f"'{keyword}' requires stricter moderation in romantic mode"
                })
        
        return violations
    
    def _check_combinations(self, prompt: str) -> List[Dict]:
        """
        Check for dangerous keyword combinations
        """
        violations = []
        
        # Celebrity + Sexual
        if (self.celebrity_pattern.search(prompt) and 
            any(word in prompt for word in ["sexy", "hot", "attractive", "nude", "naked"])):
            violations.append({
                "type": "DANGEROUS_COMBINATION",
                "severity": "CRITICAL",
                "reason": "Celebrity combined with sexual/suggestive content",
            })
        
        # Politician + Negative
        if (self.politician_pattern.search(prompt) and
            any(word in prompt for word in ["dead", "kill", "murder", "attack", "assassinate"])):
            violations.append({
                "type": "DANGEROUS_COMBINATION",
                "severity": "CRITICAL",
                "reason": "Political figure combined with violent content",
            })
        
        # Minor + Romantic
        if (self.minor_pattern.search(prompt) and
            any(word in prompt for word in self.TIER3_ROMANTIC_RESTRICTED)):
            violations.append({
                "type": "DANGEROUS_COMBINATION",
                "severity": "CRITICAL",
                "reason": "Minor-related keywords with romantic/intimate content",
            })
        
        return violations
    
    def _suggest_alternative(
        self,
        prompt: str,
        violations: List[Dict]
    ) -> str:
        """
        Suggest safe alternative prompt
        """
        modified = prompt
        
        # Remove celebrity names
        for violation in violations:
            if violation["type"] == "CELEBRITY":
                name = violation["name"]
                # Replace with generic description
                modified = re.sub(
                    r'\b' + re.escape(name) + r'\b',
                    "person",
                    modified,
                    flags=re.IGNORECASE
                )
        
        # Remove politicians
        for violation in violations:
            if violation["type"] == "POLITICIAN":
                name = violation["name"]
                modified = re.sub(
                    r'\b' + re.escape(name) + r'\b',
                    "professional",
                    modified,
                    flags=re.IGNORECASE
                )
        
        # Clean up contextual violations
        for violation in violations:
            if violation["type"] == "CONTEXTUAL_VIOLATION":
                keyword = violation["keyword"]
                # Try to replace with safe alternative
                safe_replacements = {
                    "nude": "neutral",
                    "bloody": "vibrant",
                    "kill": "excel",
                    "smoking": "attractive",
                }
                if keyword in safe_replacements:
                    modified = re.sub(
                        r'\b' + re.escape(keyword) + r'\b',
                        safe_replacements[keyword],
                        modified,
                        flags=re.IGNORECASE
                    )
        
        return modified.strip()
    
    @lru_cache(maxsize=1000)
    def is_safe_cached(self, prompt: str) -> bool:
        """
        Cached version for frequently checked prompts
        """
        result = self.check_prompt(prompt)
        return result.safe
