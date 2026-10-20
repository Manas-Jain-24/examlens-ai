import re
from typing import Tuple, Optional

# Comprehensive Bloom's Taxonomy Verb Ontology
BLOOMS_LEXICON = {
    "Remember": [
        "define", "list", "recall", "state", "name", "identify", "mention", 
        "quote", "label", "recite", "record", "match", "tabulate", "who", "when", 
        "where", "which", "what is", "what are", "write short notes on"
    ],
    "Understand": [
        "explain", "describe", "discuss", "outline", "summarize", "distinguish", 
        "clarify", "interpret", "paraphrase", "exemplify", "rephrase", "translate",
        "illustrate the concept", "elucidate", "give example", "give an example",
        "how does", "why is", "why does"
    ],
    "Apply": [
        "implement", "solve", "calculate", "compute", "demonstrate", "show how", 
        "use", "execute", "construct", "determine", "simulate", "operate", 
        "write a program", "write an algorithm", "apply", "trace", "find the output",
        "perform", "derive", "convert", "model"
    ],
    "Analyze": [
        "compare", "contrast", "differentiate", "examine", "investigate", "break down",
        "categorize", "debate", "deduce", "inspect", "dissect", "analyze", 
        "time complexity", "space complexity", "compare and contrast", "trade-offs",
        "tradeoff", "asymptotic analysis", "distinguish between"
    ],
    "Evaluate": [
        "evaluate", "justify", "critique", "assess", "judge", "defend", "prioritize",
        "rate", "recommend", "argue", "validate", "verify", "appraise", "choose the best",
        "which one is more suitable", "prove"
    ],
    "Create": [
        "design", "formulate", "compose", "devise", "synthesize", "develop", 
        "invent", "generate", "propose", "architect", "construct a framework",
        "create", "build a system", "modify to support"
    ]
}

# Hierarchy of weights for complexity
BLOOMS_ORDER = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]

def extract_command_verb(text: str) -> Optional[str]:
    """Extracts leading action verb or prominent command keyword."""
    cleaned = re.sub(r'^[Q0-9\.\(\)\s\-a-zA-Z]+?:\s*', '', text).strip()
    words = re.findall(r'\b[a-zA-Z\-]+\b', cleaned.lower())
    
    # Check multi-word command phrases first
    lowered = text.lower()
    multi_word_checks = [
        "compare and contrast", "write a program", "write an algorithm",
        "what is", "what are", "time complexity", "space complexity",
        "give an example", "give example", "distinguish between",
        "write short notes on", "how does", "why does"
    ]
    for phrase in multi_word_checks:
        if phrase in lowered:
            return phrase

    # Scan the first few words for matching command verbs
    for word in words[:6]:
        for level, verbs in BLOOMS_LEXICON.items():
            if word in verbs:
                return word
                
    return words[0] if words else None

def classify_blooms_taxonomy(question_text: str) -> Tuple[str, Optional[str], float]:
    """
    Classifies a question into Bloom's Taxonomy cognitive level.
    Returns: (blooms_level, command_verb, confidence_score)
    """
    cleaned = question_text.lower().strip()
    cmd_verb = extract_command_verb(question_text)
    
    # Check multi-word phrases first
    for level, verbs in BLOOMS_LEXICON.items():
        for verb in verbs:
            if " " in verb and verb in cleaned:
                # Direct match for phrases like 'compare and contrast' or 'what is'
                return level, verb, 0.92

    # Score each cognitive level based on verb presence and contextual cues
    scores = {level: 0.0 for level in BLOOMS_ORDER}
    
    words = set(re.findall(r'\b[a-zA-Z\-]+\b', cleaned))
    
    for level, verbs in BLOOMS_LEXICON.items():
        for verb in verbs:
            if verb in words:
                # Higher weight if it is the leading command verb
                if cmd_verb and verb == cmd_verb:
                    scores[level] += 3.0
                else:
                    scores[level] += 1.2
                    
    # Heuristics based on question phrasing
    if any(k in cleaned for k in ["time complexity", "space complexity", "big-o", "worst-case", "best-case"]):
        scores["Analyze"] += 2.0
    if any(k in cleaned for k in ["implement", "code", "pseudo-code", "algorithm", "simulate"]):
        scores["Apply"] += 2.0
    if any(k in cleaned for k in ["design", "devise", "architect", "new data structure"]):
        scores["Create"] += 2.5
    if any(k in cleaned for k in ["justify", "why should we choose", "critique", "prove that"]):
        scores["Evaluate"] += 2.2
    if any(k in cleaned for k in ["what is", "define", "state the properties", "list"]):
        scores["Remember"] += 2.0
    if any(k in cleaned for k in ["explain", "describe", "discuss", "how it works"]):
        scores["Understand"] += 1.8
        
    # Get level with maximum score
    best_level = max(scores, key=scores.get)
    max_score = scores[best_level]
    
    if max_score > 0:
        confidence = min(0.95, 0.65 + (max_score * 0.07))
        return best_level, cmd_verb, round(confidence, 2)
        
    # Fallback default heuristic if no keywords caught
    if "?" in question_text and len(question_text.split()) < 10:
        return "Remember", cmd_verb or "inquire", 0.60
    return "Understand", cmd_verb or "explain", 0.55
