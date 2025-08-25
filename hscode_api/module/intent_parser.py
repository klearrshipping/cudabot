#!/usr/bin/env python3
"""
Intent Parser for Trade Classification System
============================================

Analyzes user queries to:
1. Extract the actual product name
2. Determine the user's intent (classification, duties, permits, etc.)
3. Provide confidence scoring for the extraction

Supported intents:
- classify: HS/commodity code classification
- duties: Import/export duties and taxes
- permits: Import/export permit requirements
- restrictions: Trade restrictions and regulations
- general: General trade information
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Import LLM functionality
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from module.hs_code import chat_completion

logger = logging.getLogger("IntentParser")

class IntentType(Enum):
    CLASSIFY = "classify"
    DUTIES = "duties" 
    PERMITS = "permits"
    RESTRICTIONS = "restrictions"
    GENERAL = "general"
    UNKNOWN = "unknown"

@dataclass
class ParsedIntent:
    product_name: str
    intent: IntentType
    confidence: str  # "high", "medium", "low"
    original_query: str
    extracted_keywords: List[str]
    additional_context: Dict[str, Any]

class IntentParser:
    """Parses user queries to extract product names and determine trade-related intents"""
    
    def __init__(self):
        # Regex patterns for different intent types
        self.classification_patterns = [
            r"what is the (?:hs code|commodity code|tariff code|classification) for (.+?)[\?\.]?$",
            r"(?:classify|find (?:the )?(?:hs code|commodity code|classification) for) (.+?)[\?\.]?$",
            r"(?:hs code|commodity code|tariff code) (?:for|of) (.+?)[\?\.]?$",
            r"can you classify (.+?)[\?\.]?$",
            r"help me classify (.+?)[\?\.]?$",
            r"what code (?:is|does) (.+?) (?:have|fall under)[\?\.]?$",
        ]
        
        self.duties_patterns = [
            r"what (?:are the|is the) (?:import duty|import duties|customs duty|duties|tax|taxes) (?:for|on) (.+?)[\?\.]?$",
            r"how much (?:duty|tax|taxes) (?:do i pay|to pay) (?:for|on) (.+?)[\?\.]?$",
            r"(?:import|customs|duty) (?:rates?|charges?) (?:for|on) (.+?)[\?\.]?$",
            r"what will it cost to import (.+?)[\?\.]?$",
            r"customs charges (?:for|on) (.+?)[\?\.]?$",
            r"(?:duty|tax) calculation (?:for|on) (.+?)[\?\.]?$",
        ]
        
        self.permits_patterns = [
            r"do (?:i|we) need (?:a |an )?(?:import|export) (?:permit|license|authorization) (?:for|to import|to export) (.+?)[\?\.]?$",
            r"(?:import|export) (?:permit|license|authorization) (?:required )?(?:for|on) (.+?)[\?\.]?$",
            r"what (?:permits|licenses|authorizations) (?:are required|do i need) (?:for|to import|to export) (.+?)[\?\.]?$",
            r"is (?:a |an )?(?:permit|license|authorization) needed (?:for|to import|to export) (.+?)[\?\.]?$",
            r"licensing requirements (?:for|on) (.+?)[\?\.]?$",
        ]
        
        self.restrictions_patterns = [
            r"(?:are there |what are the )?(?:restrictions|prohibitions|bans) (?:on|for) (?:importing|exporting) (.+?)[\?\.]?$",
            r"is (.+?) (?:restricted|prohibited|banned) (?:for import|for export|from import|from export)[\?\.]?$",
            r"can (?:i|we) (?:import|export) (.+?)[\?\.]?$",
            r"(?:trade restrictions|import restrictions|export restrictions) (?:on|for) (.+?)[\?\.]?$",
            r"is it legal to (?:import|export) (.+?)[\?\.]?$",
        ]
        
        self.general_patterns = [
            r"tell me about (?:importing|exporting) (.+?)[\?\.]?$",
            r"(?:information|details) (?:about|on) (?:importing|exporting) (.+?)[\?\.]?$",
            r"how to (?:import|export) (.+?)[\?\.]?$",
            r"what do i need to know about (.+?)[\?\.]?$",
        ]
        
        # Keywords for intent classification
        self.intent_keywords = {
            IntentType.CLASSIFY: [
                "hs code", "commodity code", "tariff code", "classification", 
                "classify", "code", "harmonized system"
            ],
            IntentType.DUTIES: [
                "duty", "duties", "tax", "taxes", "customs", "charges", 
                "cost", "rates", "import duty", "customs duty"
            ],
            IntentType.PERMITS: [
                "permit", "license", "authorization", "licensing", 
                "required", "need", "permit required"
            ],
            IntentType.RESTRICTIONS: [
                "restrictions", "restricted", "prohibited", "banned", 
                "legal", "allowed", "prohibitions", "bans"
            ],
            IntentType.GENERAL: [
                "information", "details", "tell me", "how to", 
                "what do i need", "about importing", "about exporting"
            ]
        }
    
    def parse_with_patterns(self, query: str) -> Optional[ParsedIntent]:
        """Try to parse using regex patterns first (faster)"""
        query_lower = query.lower().strip()
        
        # Try classification patterns
        for pattern in self.classification_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                product = match.group(1).strip()
                return ParsedIntent(
                    product_name=product,
                    intent=IntentType.CLASSIFY,
                    confidence="high",
                    original_query=query,
                    extracted_keywords=["classification"],
                    additional_context={"pattern_matched": True}
                )
        
        # Try duties patterns
        for pattern in self.duties_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                product = match.group(1).strip()
                return ParsedIntent(
                    product_name=product,
                    intent=IntentType.DUTIES,
                    confidence="high",
                    original_query=query,
                    extracted_keywords=["duties", "import"],
                    additional_context={"pattern_matched": True}
                )
        
        # Try permits patterns
        for pattern in self.permits_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                product = match.group(1).strip()
                return ParsedIntent(
                    product_name=product,
                    intent=IntentType.PERMITS,
                    confidence="high",
                    original_query=query,
                    extracted_keywords=["permits", "license"],
                    additional_context={"pattern_matched": True}
                )
        
        # Try restrictions patterns
        for pattern in self.restrictions_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                product = match.group(1).strip()
                return ParsedIntent(
                    product_name=product,
                    intent=IntentType.RESTRICTIONS,
                    confidence="high",
                    original_query=query,
                    extracted_keywords=["restrictions"],
                    additional_context={"pattern_matched": True}
                )
        
        # Try general patterns
        for pattern in self.general_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                product = match.group(1).strip()
                return ParsedIntent(
                    product_name=product,
                    intent=IntentType.GENERAL,
                    confidence="medium",
                    original_query=query,
                    extracted_keywords=["general"],
                    additional_context={"pattern_matched": True}
                )
        
        return None
    
    def parse_with_llm(self, query: str) -> ParsedIntent:
        """Use LLM for complex queries that don't match patterns"""
        
        intent_prompt = f"""
        Analyze this trade-related user query and extract the product name and intent.
        
        User query: "{query}"
        
        Intent types:
        - classify: User wants HS/commodity code classification
        - duties: User wants import/export duty information  
        - permits: User wants permit/license requirements
        - restrictions: User wants trade restriction information
        - general: General trade information request
        
        Return ONLY valid JSON with:
        {{
            "product_name": "the actual product being asked about",
            "intent": "classify|duties|permits|restrictions|general",
            "confidence": "high|medium|low",
            "keywords": ["relevant", "keywords", "found"]
        }}
        
        Examples:
        "What is the HS code for fresh apples?" → {{"product_name": "fresh apples", "intent": "classify", "confidence": "high", "keywords": ["hs code"]}}
        "How much duty do I pay on importing cars?" → {{"product_name": "cars", "intent": "duties", "confidence": "high", "keywords": ["duty", "importing"]}}
        "Do I need a permit for exporting wheat?" → {{"product_name": "wheat", "intent": "permits", "confidence": "high", "keywords": ["permit", "exporting"]}}
        """
        
        try:
            response = chat_completion([
                {"role": "system", "content": "You are an expert intent parser for international trade queries. Return only valid JSON."},
                {"role": "user", "content": intent_prompt}
            ])
            
            # Clean the response to extract JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            parsed = json.loads(response)
            
            return ParsedIntent(
                product_name=parsed.get("product_name", query),
                intent=IntentType(parsed.get("intent", "unknown")),
                confidence=parsed.get("confidence", "medium"),
                original_query=query,
                extracted_keywords=parsed.get("keywords", []),
                additional_context={"llm_parsed": True}
            )
            
        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}")
            # Fallback: treat as classification request
            return ParsedIntent(
                product_name=query,
                intent=IntentType.CLASSIFY,
                confidence="low",
                original_query=query,
                extracted_keywords=[],
                additional_context={"fallback": True, "error": str(e)}
            )
    
    def parse(self, query: str) -> ParsedIntent:
        """Main parsing method - tries patterns first, then LLM"""
        if not query or not query.strip():
            return ParsedIntent(
                product_name="",
                intent=IntentType.UNKNOWN,
                confidence="low",
                original_query=query,
                extracted_keywords=[],
                additional_context={"error": "Empty query"}
            )
        
        # Try pattern matching first (faster and more reliable for common cases)
        pattern_result = self.parse_with_patterns(query)
        if pattern_result:
            logger.info(f"Pattern matched: {pattern_result.intent.value} for '{pattern_result.product_name}'")
            return pattern_result
        
        # Fall back to LLM for complex queries
        logger.info(f"Using LLM parsing for: {query}")
        return self.parse_with_llm(query)
    
    def get_response_template(self, intent: IntentType) -> str:
        """Get appropriate response template based on intent"""
        templates = {
            IntentType.CLASSIFY: "I'll help you classify {product} and find its HS/commodity code.",
            IntentType.DUTIES: "I'll help you find the import duties and taxes for {product}.",
            IntentType.PERMITS: "I'll check the permit and licensing requirements for {product}.",
            IntentType.RESTRICTIONS: "I'll check for any trade restrictions on {product}.",
            IntentType.GENERAL: "I'll provide general trade information about {product}.",
            IntentType.UNKNOWN: "I'll help you with information about {product}."
        }
        return templates.get(intent, templates[IntentType.UNKNOWN])

# Convenience function for easy import
def parse_user_intent(query: str) -> ParsedIntent:
    """Parse user query and return intent information"""
    parser = IntentParser()
    return parser.parse(query)

# Test function
def test_intent_parser():
    """Test the intent parser with various queries"""
    parser = IntentParser()
    
    test_queries = [
        "What is the commodity code for fresh apples?",
        "How much duty do I pay on importing cars?",
        "Do I need a permit to export wheat?",
        "Are there restrictions on importing electronics?",
        "Tell me about importing textiles",
        "fresh apples",  # Direct product name
        "Can you classify wireless headphones?",
        "What are the import charges for steel pipes?",
        "Is an export license required for machinery?",
    ]
    
    for query in test_queries:
        result = parser.parse(query)
        print(f"Query: {query}")
        print(f"  Product: {result.product_name}")
        print(f"  Intent: {result.intent.value}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Keywords: {result.extracted_keywords}")
        print()

if __name__ == "__main__":
    test_intent_parser() 