#!/usr/bin/env python3
"""
HS Code Classification API with Enhanced Response Structures
===========================================================

A FastAPI-based REST API for HS code classification that provides:
1. Initial HS code classification using multiple AI models
2. Reconciliation against databases
3. Commodity code lookup with clarification questions

API Endpoints:
- POST /classify - Classify a product and get complete results
- POST /classify/continue - Continue classification with clarification answers
- GET /health - Health check endpoint
"""

import sys
import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import asyncio
import time

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import functions from our pipeline modules
from module.hs_code import classify_product
from module.confirm_hs_code import HSCodeReconciler, reason_with_llm_fn
from module.commodity_code import lookup_commodity_code, lookup_commodity_code_with_answers
from module.intent_parser import parse_user_intent, IntentType
from supabase import create_client
# Import config from the hscode_api directory
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
hscode_api_dir = current_dir
sys.path.insert(0, hscode_api_dir)

from config import SUPABASE_URL, SUPABASE_KEY

# Session storage (in production, use Redis or database)
classification_sessions = {}
classification_tasks = {}

class HSCodeOrchestrator:
    """Orchestrates the complete HS code classification pipeline"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.reconciler = HSCodeReconciler(self.supabase, reason_with_llm_fn, verbose=verbose)
    
    def classify_complete_pipeline(self, product_name: str, additional_context: Dict[str, Any] = None, 
                                 order_id: str = None, original_query: str = None, 
                                 contextual_data: Dict[str, Any] = None, user_answers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Run the complete HS code classification pipeline with flexible context handling
        
        Args:
            product_name: The product to classify
            additional_context: Additional context from clarification answers
            order_id: Order ID for database context lookup
            original_query: Original user query for context extraction
            contextual_data: Direct contextual data from request
            
        Returns:
            Complete results from all three stages
        """
        print(f"\n🚀 STARTING HS CODE CLASSIFICATION PIPELINE")
        print(f"{'='*60}")
        print(f"Product: {product_name}")
        print(f"{'='*60}")
        
        results = {
            "metadata": {
                "product_name": product_name,
                "timestamp": datetime.now().isoformat(),
                "pipeline_version": "1.0"
            },
            "stage1_classification": None,
            "stage2_reconciliation": None,
            "stage3_commodity_lookup": None,
            "final_results": None,
            "errors": []
        }
        
        try:
            # ────────────────────── STAGE 1: Initial Classification ──────────────────────
            print(f"\n📊 STAGE 1: Initial HS Code Classification")
            print(f"─────────────────────────────────────────")
            
            stage1_results = classify_product(product_name, contextual_data)
            results["stage1_classification"] = stage1_results
            
            # Check for None first, then check for consensus_codes
            if stage1_results is None:
                error_msg = "Stage 1 failed: classify_product returned None"
                results["errors"].append(error_msg)
                return results
            
            if not stage1_results.get("consensus_codes"):
                error_msg = "Stage 1 failed: No HS codes generated"
                results["errors"].append(error_msg)
                return results
            
            hs_codes = stage1_results["consensus_codes"]
            product_info = stage1_results.get("product_information", "")
            
            print(f"✅ Generated {len(hs_codes)} HS codes: {', '.join(hs_codes)}")
            
            # ────────────────────── STAGE 2: Reconciliation ──────────────────────────────
            print(f"\n🔍 STAGE 2: HS Code Reconciliation")
            print(f"─────────────────────────────────────")
            
            reconciliation_results = []
            for hs_code in hs_codes:
                result = self.reconciler.reconcile_hs_code(hs_code, product_name, product_info)
                reconciliation_results.append(result)
                
                # DEBUG: Print individual reconciliation result
                print(f"🔍 DEBUG: Reconciliation result for {hs_code}:")
                print(f"   resolved_hs_code: {result.get('resolved_hs_code')}")
                print(f"   resolved_source: {result.get('resolved_source')}")
                print(f"   match_score: {result.get('match_score')}")
                print(f"   errors: {result.get('errors', [])}")
            
            # Determine final consensus
            final_determination = self.reconciler.determine_final_hs_code(reconciliation_results, product_name)
            
            results["stage2_reconciliation"] = {
                "individual_results": reconciliation_results,
                "final_determination": final_determination
            }
            
            confirmed_hs_code = final_determination.get("confirmed_hs_code")
            if not confirmed_hs_code or confirmed_hs_code == "NO_MATCH":
                error_msg = "Stage 2 failed: No valid HS code confirmed"
                results["errors"].append(error_msg)
                # Continue to stage 3 with original codes if reconciliation failed
                final_hs_codes = hs_codes
            else:
                print(f"✅ Confirmed HS code: {confirmed_hs_code}")
                final_hs_codes = [confirmed_hs_code]
            
            # ────────────────────── Commodity Code Lookup ───────────────────────
            
            # Use answers if provided, otherwise do initial lookup
            try:
                print(f"🔍 DEBUG: Pipeline parameters:")
                print(f"   product_name: '{product_name}'")
                print(f"   original_query: '{original_query}'")
                print(f"   additional_context: {bool(additional_context)}")
                
                if additional_context:
                    print(f"🔍 DEBUG: Calling lookup_commodity_code_with_answers with {len(final_hs_codes)} HS codes")
                    print(f"   Using query: 'Classify {product_name}'")
                    commodity_results = lookup_commodity_code_with_answers(
                        final_hs_codes, product_name, product_info, 
                        f"Classify {product_name}", additional_context, order_id
                    )
                else:
                    print(f"🔍 DEBUG: Calling lookup_commodity_code with {len(final_hs_codes)} HS codes: {final_hs_codes}")
                    # Use original query if available, otherwise fall back to generic query
                    query_for_lookup = original_query if original_query else f"Classify {product_name}"
                    print(f"   Using query_for_lookup: '{query_for_lookup}'")
                    commodity_results = lookup_commodity_code(
                        final_hs_codes, product_name, product_info, query_for_lookup, order_id, contextual_data, stage1_results, user_answers
                    )
                
                print(f"🔍 DEBUG: Commodity lookup returned: {type(commodity_results)}")
                if commodity_results is None:
                    print(f"🔍 DEBUG: commodity_results is None - this indicates an error in the commodity lookup")
                    commodity_results = {}
                elif isinstance(commodity_results, dict):
                    print(f"🔍 DEBUG: commodity_results keys: {list(commodity_results.keys())}")
                else:
                    print(f"🔍 DEBUG: commodity_results is not a dict: {commodity_results}")
                    commodity_results = {}
                
                # Debug: Print detailed structure of commodity_results
                print(f"🔍 DEBUG: Detailed commodity_results structure:")
                for hs_code, result in commodity_results.items():
                    print(f"   HS Code {hs_code}: {type(result)}")
                    if isinstance(result, dict):
                        print(f"      Keys: {list(result.keys())}")
                        if result.get('requires_clarification'):
                            print(f"      REQUIRES CLARIFICATION: {result.get('requires_clarification')}")
                            print(f"      Questions: {len(result.get('questions', []))}")
                    elif isinstance(result, list):
                        print(f"      List length: {len(result)}")
                
            except Exception as e:
                print(f"❌ ERROR: Commodity lookup failed: {str(e)}")
                import traceback
                traceback.print_exc()
                commodity_results = {}
            
            results["stage3_commodity_lookup"] = commodity_results
            
            # Count total commodity codes found
            total_codes = 0
            needs_clarification = False
            clarification_questions = []
            
            
            for hs_code, result in commodity_results.items():
                print(f"🔍 DEBUG: Processing HS Code {hs_code}: {type(result)}")
                if isinstance(result, dict) and result.get('requires_clarification'):
                    print(f"   ✅ FOUND CLARIFICATION NEEDED: {result.get('requires_clarification')}")
                    needs_clarification = True
                    questions = result.get('questions', [])
                    print(f"   Questions found: {len(questions)}")
                    clarification_questions.extend(questions)
                elif isinstance(result, list):
                    print(f"   List result with {len(result)} items")
                    total_codes += len(result)
                else:
                    print(f"   Other result type: {type(result)}")
            
            print(f"✅ Found {total_codes} total commodity codes")
            
            # Show clarification status if needed
            if needs_clarification:
                clarification_count = len(clarification_questions)
                print(f"❓ Clarification needed: {clarification_count} questions generated")
            
            # ────────────────────── FINAL RESULTS SUMMARY ────────────────────────────────
            results["final_results"] = self._generate_final_summary(
                stage1_results, final_determination, commodity_results, product_name
            )
            
            # Add clarification info to results
            results["needs_clarification"] = needs_clarification
            results["clarification_questions"] = clarification_questions
            
            print(f"🔍 DEBUG: Final clarification status:")
            print(f"   needs_clarification: {needs_clarification}")
            print(f"   clarification_questions count: {len(clarification_questions)}")
            print(f"   clarification_questions: {clarification_questions}")
            
            return results
            
        except Exception as e:
            error_msg = f"Pipeline failed with error: {str(e)}"
            results["errors"].append(error_msg)
            return results
    
    def _generate_final_summary(self, stage1_results: Dict, final_determination: Dict, 
                              commodity_results: Dict, product_name: str) -> Dict[str, Any]:
        """Generate a final summary of all results"""
        
        # Extract key information
        initial_codes = stage1_results.get("consensus_codes", [])
        confirmed_code = final_determination.get("confirmed_hs_code")
        quality_score = final_determination.get("quality_score", 0)
        
        # Count commodity codes
        commodity_counts = {}
        total_commodity_codes = 0
        for hs_code, codes in commodity_results.items():
            if codes and isinstance(codes, list):
                count = len(codes)
                commodity_counts[hs_code] = count
                total_commodity_codes += count
        
        # Determine recommendation status
        if confirmed_code and confirmed_code != "NO_MATCH":
            if quality_score >= 8:
                recommendation_status = "high_confidence"
            elif quality_score >= 6:
                recommendation_status = "medium_confidence"
            else:
                recommendation_status = "low_confidence"
        else:
            recommendation_status = "no_match"
        
        # Determine if manual review is required
        requires_manual_review = (
            recommendation_status == "low_confidence" or
            total_commodity_codes == 0 or
            final_determination.get("requires_manual_review", False)
        )
        
        return {
            "product_name": product_name,
            "recommendation_status": recommendation_status,
            "initial_hs_codes": initial_codes,
            "confirmed_hs_code": confirmed_code,
            "quality_score": quality_score,
            "commodity_code_counts": commodity_counts,
            "total_commodity_codes": total_commodity_codes,
            "requires_manual_review": requires_manual_review,
            "key_warnings": final_determination.get("overall_warnings", []),
            "critical_errors": final_determination.get("overall_errors", [])
        }

# Initialize FastAPI app
app = FastAPI(
    title="HS Code Classification API",
    description="API for classifying products with HS codes and commodity codes",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize the orchestrator
orchestrator = HSCodeOrchestrator(verbose=False)

# Enhanced Pydantic models for request/response
class ClarificationQuestion(BaseModel):
    id: str
    question: str
    type: str  # "choice", "number", "text"
    help_text: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None
    unit: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None

class ContextualData(BaseModel):
    """Streamlined contextual data for enhanced classification"""
    # Clean flat structure (preferred)
    consignee_name: Optional[str] = None
    consignee_address: Optional[str] = None
    shipper: Optional[str] = None
    shipper_address: Optional[str] = None
    port_of_origin: Optional[str] = None
    port_of_destination: Optional[str] = None
    weight: Optional[str] = None
    commodity: Optional[str] = None
    vessel: Optional[str] = None
    bill_of_lading: Optional[str] = None
    extraction_confidence: Optional[str] = None
    
    # Legacy nested structure (for backward compatibility)
    buyer_info: Optional[Dict[str, Any]] = None
    supplier_info: Optional[Dict[str, Any]] = None
    product_details: Optional[Dict[str, Any]] = None
    shipping_info: Optional[Dict[str, Any]] = None
    document_metadata: Optional[Dict[str, Any]] = None

class ClassificationRequest(BaseModel):
    product_name: str
    verbose: Optional[bool] = False
    order_id: Optional[str] = None
    contextual_data: Optional[ContextualData] = None
    user_answers: Optional[Dict[str, str]] = None

class ClarificationRequest(BaseModel):
    session_id: str
    additional_context: Dict[str, Any]

class SimplifiedResponse(BaseModel):
    product_name: str
    hs_code: Optional[str]
    commodity_code: Optional[str]
    description: Optional[str]
    requires_clarification: Optional[bool] = False
    clarification_questions: Optional[List[ClarificationQuestion]] = None
    session_id: Optional[str] = None

class ClassificationResponse(BaseModel):
    metadata: Dict[str, Any]
    stage1_classification: Optional[Dict[str, Any]]
    stage2_reconciliation: Optional[Dict[str, Any]]
    stage3_commodity_lookup: Optional[Dict[str, Any]]
    final_results: Optional[Dict[str, Any]]
    errors: List[str]

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str

class APIInfo(BaseModel):
    name: str
    version: str
    description: str
    endpoints: List[str]

class StreamChunk(BaseModel):
    id: str
    object: str = "classification.chunk"
    created: int
    choices: List[Dict[str, Any]]

class StreamChoice(BaseModel):
    index: int = 0
    delta: Dict[str, Any]
    finish_reason: Optional[str] = None

# Response generation functions
def build_classification_response(results: Dict[str, Any], product_name: str) -> str:
    """Build a clean, structured classification response"""
    
    # Extract key data
    stage2_results = results.get("stage2_reconciliation", {})
    final_determination = stage2_results.get("final_determination", {})
    confirmed_code = final_determination.get("confirmed_hs_code")
    quality_score = final_determination.get("quality_score", 0)
    
    # Get commodity code
    commodity_results = results.get("stage3_commodity_lookup", {})
    selected_commodity = None
    for hs_code, codes in commodity_results.items():
        if codes and isinstance(codes, list) and len(codes) > 0:
            # Take the first code since commodity lookup returns [best_match] with selected=True
            selected_commodity = codes[0]
            break
    
    # Clean up product name for title
    clean_product_name = product_name.replace("what is the commodity code for", "").replace("what is the hs code for", "").strip()
    if clean_product_name.lower().startswith("the "):
        clean_product_name = clean_product_name[4:]
    
    # Detect if user asked about commodity codes specifically
    asked_about_commodity = "commodity code" in product_name.lower()
    
    # Build response following the exact structure
    response = []
    
    if confirmed_code and confirmed_code != "NO_MATCH":
        # Query hs_codes_2022 table for proper descriptions
        try:
            hs_query_response = supabase.table('hs_codes_2022') \
                .select('hs_code, heading, heading_description, subcategory, description') \
                .eq('hs_code', confirmed_code) \
                .execute()
            
            hs_data = None
            if hs_query_response.data and len(hs_query_response.data) > 0:
                hs_data = hs_query_response.data[0]
            else:
                # If exact match not found, try to find by heading
                heading_code = confirmed_code.replace(".", "")[:4]
                heading_formatted = f"{heading_code[:2]}.{heading_code[2:]}"
                
                heading_response = supabase.table('hs_codes_2022') \
                    .select('hs_code, heading, heading_description, subcategory, description') \
                    .eq('heading', heading_formatted) \
                    .limit(1) \
                    .execute()
                
                if heading_response.data and len(heading_response.data) > 0:
                    hs_data = heading_response.data[0]
        except Exception as e:
            print(f"Error querying hs_codes_2022: {str(e)}")
            hs_data = None
        
        # Format response based on what the user asked for
        if asked_about_commodity and selected_commodity:
            # User asked about commodity code - lead with that
            response.append(f"**The commodity code for {clean_product_name} is {selected_commodity.get('tariff_code')}.**")
            response.append("")
            response.append(f"This 10-digit commodity code is based on HS code {confirmed_code}.")
            response.append("")
        else:
            # User asked about HS code - lead with that
            response.append(f"**The HS code for {clean_product_name} is {confirmed_code}.**")
            response.append("")
        
        # Product type and heading description
        heading_code = confirmed_code.replace(".", "")[:4]
        
        # Try to infer product type from product name
        product_type = clean_product_name
        if "tesla" in clean_product_name.lower() or "model" in clean_product_name.lower() or "electric vehicle" in clean_product_name.lower():
            product_type = "Electric vehicles"
        elif "phone" in clean_product_name.lower() or "iphone" in clean_product_name.lower() or "smartphone" in clean_product_name.lower():
            product_type = "Smartphones"
        elif "laptop" in clean_product_name.lower() or "computer" in clean_product_name.lower():
            product_type = "Computers"
        
        # Get heading description from database query
        heading_description = ""
        if hs_data and hs_data.get('heading_description'):
            heading_description = hs_data['heading_description'].strip()
            # Fix truncation issue - ensure we have the full description
            if heading_description.endswith(" for.") or heading_description.endswith(" for"):
                # Query with more specific search to get full description
                try:
                    full_desc_response = supabase.table('hs_codes_2022') \
                        .select('heading_description') \
                        .ilike('heading_description', f'{heading_description.split(" for")[0]}%') \
                        .limit(1) \
                        .execute()
                    if full_desc_response.data:
                        heading_description = full_desc_response.data[0]['heading_description'].strip()
                except:
                    pass
        else:
            # Fallback descriptions based on common HS codes
            if heading_code == "8517":
                heading_description = "Telephone sets, including smartphones and other telephones for cellular networks or for other wireless networks"
            elif heading_code == "8703":
                heading_description = "Motor cars and other motor vehicles principally designed for the transport of persons"
            elif heading_code == "8471":
                heading_description = "Automatic data processing machines and units thereof"
            else:
                heading_description = "Trade classification heading"
        
        response.append(f"{product_type} fall under HS heading {heading_code}, which covers \"{heading_description}.\"")
        
        # Add subcategory if available
        if hs_data and hs_data.get('subcategory'):
            subcategory = hs_data['subcategory'].strip()
            if subcategory and subcategory.lower() != 'none':
                response.append(f"Within this heading, it's further classified under {subcategory}.")
        
        # Specific classification
        specific_desc = ""
        if asked_about_commodity and selected_commodity:
            # For commodity code requests, use the commodity description
            specific_desc = selected_commodity.get('description', '')
        elif hs_data and hs_data.get('description'):
            specific_desc = hs_data['description'].strip()
        elif selected_commodity:
            specific_desc = selected_commodity.get('description', '')
        
        if specific_desc:
            # Clean up the description to make it more readable
            clean_desc = specific_desc.replace("Other vehicles , with only electric motor for propulsion:", "Electric vehicles")
            clean_desc = clean_desc.replace(":", "").strip()
            # Capitalize first letter
            if clean_desc:
                clean_desc = clean_desc[0].upper() + clean_desc[1:] if len(clean_desc) > 1 else clean_desc.upper()
            response.append(f"The specific classification is \"{clean_desc}.\"")
        
        response.append("")
        
        # Add commodity code info if user asked about HS codes but we have commodity info
        if not asked_about_commodity and selected_commodity:
            response.append(f"For customs declarations, the specific 10-digit commodity code is **{selected_commodity.get('tariff_code')}**.")
            response.append("")
        
        # Standard disclaimer
        if asked_about_commodity:
            response.append("Always verify the specific commodity code with customs authorities in your destination country, as they may require additional digits or have country-specific variations of the international classification.")
        else:
            response.append("Always verify the specific HS code with customs authorities in your destination country, as they may require additional digits or have country-specific variations of the international classification.")
        
    else:
        # No classification found
        code_type = "commodity code" if asked_about_commodity else "HS code"
        response.append(f"**I was unable to determine a definitive {code_type} for {clean_product_name}.**")
        response.append("")
        response.append("This product may require manual classification by a customs expert. Please consult with your local customs authority or a qualified customs broker for accurate classification.")
    
    return "\n".join(response)

def build_duties_response(results: Dict[str, Any], product_name: str) -> str:
    """Build a structured duties information response"""
    
    # Extract key data
    final_results = results.get("final_results", {})
    confirmed_code = final_results.get("confirmed_hs_code")
    
    response = []
    
    # Header
    response.append("## Import Duties Information\n")
    
    # Main content
    if confirmed_code:
        response.append(f"Based on the classification analysis, {product_name} falls under HS code **{confirmed_code}**. ")
        response.append("This classification determines the applicable duty rates and any preferential treatment under trade agreements.\n")
        
        response.append("\nImport duty rates vary significantly depending on several critical factors. ")
        response.append("The country of manufacture is typically the most important determinant, as different countries have different duty rates ")
        response.append("based on trade relationships, agreements, and economic policies.\n")
        
        # Duty rate factors
        response.append("\n## Duty Rate Factors\n")
        response.append("The final duty calculation depends on your specific circumstances and the product's origin. ")
        response.append("Most Favored Nation rates generally serve as the baseline, but numerous preferential programs may apply.\n")
        
        response.append("\n**Critical rate determinants:**\n")
        response.append("• Country of manufacture (factory location, not brand origin)\n")
        response.append("• Applicable trade agreements and preferential programs\n")
        response.append("• Product specifications and declared value\n")
        response.append("• Certificate of origin documentation\n")
        
        # Additional costs
        response.append("\n## Additional Import Costs\n")
        response.append("Beyond the basic duty rate, several additional costs typically apply to imports. ")
        response.append("Value-added taxes, goods and services taxes, and various fees can significantly impact the total import cost.\n")
        
        response.append("\n**Common additional charges:**\n")
        response.append("• Value-added tax or goods and services tax (typically 10-20%)\n")
        response.append("• Customs processing and handling fees\n")
        response.append("• Potential environmental or special levies\n")
        response.append("• Brokerage and clearance service fees\n")
        
        # Documentation requirements
        response.append("\n## Required Documentation\n")
        response.append("Accurate duty calculation requires specific documentation and product details. ")
        response.append("Incomplete or incorrect documentation can result in delays, penalties, or incorrect duty assessment.\n")
        
        response.append("\n**Essential requirements:**\n")
        response.append("• Commercial invoice with detailed product description\n")
        response.append("• Certificate of origin from the manufacturing country\n")
        response.append("• Technical specifications for classification verification\n")
        response.append("• Any applicable licenses or permits\n")
        
        # Next steps
        response.append("\n## Next Steps\n")
        response.append(f"Contact a licensed customs broker with HS code {confirmed_code} to obtain precise duty calculations for your specific situation. ")
        response.append("Customs brokers can verify applicable trade agreement benefits, ensure proper documentation, and provide comprehensive import cost estimates.\n")
        
        response.append("\nAlways verify current duty rates before making import commitments, as tariff schedules and trade agreement terms change periodically. ")
        response.append("Professional customs consultation can help optimize your import costs and ensure compliance with all applicable regulations.")
        
    else:
        response.append(f"I was unable to definitively classify {product_name}, which makes specific duty rate determination challenging. ")
        response.append("Professional customs consultation will be necessary to establish the correct classification and applicable duty rates.\n")
        
        response.append("\nWithout proper classification, duty rates cannot be accurately determined. ")
        response.append("Contact a licensed customs broker or customs authority for assistance with product classification and duty calculation.")
    
    return "".join(response)

def build_permits_response(results: Dict[str, Any], product_name: str) -> str:
    """Build a structured permits information response"""
    
    final_results = results.get("final_results", {})
    confirmed_code = final_results.get("confirmed_hs_code")
    
    response = []
    
    # Header
    response.append("## Permit Requirements\n")
    
    if confirmed_code:
        response.append(f"Based on the classification of {product_name} under HS code **{confirmed_code}**, permit requirements will depend on ")
        response.append("the specific product characteristics, intended use, and the regulatory framework of both origin and destination countries.\n")
        
        response.append("\nMany products require various permits, licenses, or authorizations for international trade. ")
        response.append("These requirements are designed to ensure safety, security, environmental protection, and compliance with international agreements.\n")
        
        # Common permit types
        response.append("\n## Common Permit Categories\n")
        response.append("Import and export permits can vary significantly by product type and jurisdiction. ")
        response.append("Some products may require multiple permits from different government agencies.\n")
        
        response.append("\n**Potential permit requirements:**\n")
        response.append("• Import/export licenses from trade authorities\n")
        response.append("• Safety and standards certifications\n")
        response.append("• Environmental compliance permits\n")
        response.append("• Industry-specific regulatory approvals\n")
        
        # Regulatory considerations
        response.append("\n## Regulatory Considerations\n")
        response.append("Permit requirements can change based on product specifications, intended use, quantity, and end-user considerations. ")
        response.append("Some products may be subject to additional scrutiny or restrictions based on security or policy concerns.\n")
        
        response.append("\n**Key factors affecting permits:**\n")
        response.append("• Product specifications and technical characteristics\n")
        response.append("• Intended use (commercial, personal, research, etc.)\n")
        response.append("• Quantity and value of shipment\n")
        response.append("• End-user and destination considerations\n")
        
        # Next steps
        response.append("\n## Next Steps\n")
        response.append(f"Contact the relevant trade authorities with HS code {confirmed_code} to determine specific permit requirements for your situation. ")
        response.append("Requirements can vary significantly between countries and may change based on current regulations and international agreements.\n")
        
        response.append("\nProfessional trade consultation is recommended to ensure compliance with all applicable permit requirements. ")
        response.append("Licensed customs brokers and trade specialists can provide guidance on the complete regulatory landscape for your specific product and trade scenario.")
        
    else:
        response.append(f"Without a definitive classification for {product_name}, specific permit requirements cannot be determined. ")
        response.append("Product classification is typically the first step in identifying applicable regulatory requirements.\n")
        
        response.append("\nContact the appropriate trade authorities or customs experts to establish proper classification, ")
        response.append("which will then enable determination of specific permit and licensing requirements.")
    
    return "".join(response)

def build_restrictions_response(results: Dict[str, Any], product_name: str) -> str:
    """Build a structured trade restrictions response"""
    
    final_results = results.get("final_results", {})
    confirmed_code = final_results.get("confirmed_hs_code")
    
    response = []
    
    # Header
    response.append("## Trade Restrictions Information\n")
    
    if confirmed_code:
        response.append(f"Trade restrictions for {product_name} under HS code **{confirmed_code}** depend on various factors including ")
        response.append("current international relations, trade policies, security considerations, and bilateral or multilateral agreements.\n")
        
        response.append("\nTrade restrictions can take many forms and may change frequently based on economic, political, or security developments. ")
        response.append("These restrictions are designed to protect domestic industries, ensure national security, or comply with international sanctions.\n")
        
        # Types of restrictions
        response.append("\n## Types of Trade Restrictions\n")
        response.append("Restrictions can range from complete prohibitions to conditional limitations based on various criteria. ")
        response.append("The specific restrictions applicable to your situation depend on the countries involved and current policy frameworks.\n")
        
        response.append("\n**Common restriction types:**\n")
        response.append("• Quantitative limits or quotas on import/export volumes\n")
        response.append("• Conditional restrictions based on end-use or end-user\n")
        response.append("• Temporary suspensions due to trade disputes or sanctions\n")
        response.append("• Special licensing requirements for sensitive products\n")
        
        # Compliance considerations
        response.append("\n## Compliance Considerations\n")
        response.append("Trade restrictions change frequently and can be implemented with little advance notice. ")
        response.append("Compliance requires ongoing monitoring of relevant government announcements and trade policy updates.\n")
        
        response.append("\n**Critical compliance factors:**\n")
        response.append("• Current sanctions and embargo lists\n")
        response.append("• Bilateral trade agreement terms and limitations\n")
        response.append("• End-user verification and documentation requirements\n")
        response.append("• Regular monitoring of policy changes and updates\n")
        
        # Verification process
        response.append("\n## Verification Process\n")
        response.append(f"To determine current restrictions for HS code {confirmed_code}, contact the appropriate government trade authorities ")
        response.append("in both origin and destination countries. Restrictions can vary significantly between trading partners and may be subject to frequent updates.\n")
        
        response.append("\nProfessional trade compliance services can provide ongoing monitoring of restriction changes and ensure continued compliance ")
        response.append("with evolving trade policies. This is particularly important for businesses engaged in regular international trade activities.")
        
    else:
        response.append(f"Without a definitive classification for {product_name}, specific trade restrictions cannot be accurately determined. ")
        response.append("Proper product classification is essential for identifying applicable restrictions and compliance requirements.\n")
        
        response.append("\nContact trade authorities or customs experts to establish proper classification, which will enable ")
        response.append("accurate assessment of any applicable trade restrictions or limitations.")
    
    return "".join(response)

@app.get("/", response_model=APIInfo)
async def root():
    """Root endpoint providing API information"""
    return {
        "name": "HS Code Classification API",
        "version": "1.0.0",
        "description": "AI-powered HS code classification with multi-stage pipeline",
        "endpoints": [
            "GET / - API information",
            "GET /health - Health check endpoint",
            "POST /classify - Classify a product (send JSON body)",
            "POST /classify/async - Start async classification (returns immediately)",
            "GET /classify/status/{task_id} - Check async classification status",
            "POST /classify/stream - Stream classification results in real-time",
            "POST /classify/continue - Continue classification with clarification answers",
            "GET /classify/{product_name} - Classify a product via URL"
        ]
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/classify", response_model=SimplifiedResponse)
async def classify_product_endpoint(request: ClassificationRequest):
    """
    Classify a product and get simplified HS code classification results with intent recognition
    
    Args:
        request: ClassificationRequest containing product_name and optional verbose flag
        
    Returns:
        SimplifiedResponse with essential classification information or clarification questions
    """
    print("🔍 DEBUG: classify_product_endpoint called!")
    try:
        print(f"🔍 DEBUG: Starting classify_product_endpoint")
        print(f"🔍 DEBUG: request.product_name = {request.product_name}")
        print(f"🔍 DEBUG: request.contextual_data = {request.contextual_data}")
        
        # Parse user intent to extract actual product name and determine intent
        parsed_intent = parse_user_intent(request.product_name)
        print(f"🔍 DEBUG: parsed_intent = {parsed_intent}")
        
        print(f"🎯 INTENT ANALYSIS:")
        print(f"   Original Query: {parsed_intent.original_query}")
        print(f"   Extracted Product: {parsed_intent.product_name}")
        print(f"   Detected Intent: {parsed_intent.intent.value}")
        print(f"   Confidence: {parsed_intent.confidence}")
        
        # Use the extracted product name for classification
        product_name = parsed_intent.product_name
        original_query = parsed_intent.original_query
        print(f"🔍 DEBUG: original_query from intent parser = {original_query}")
        print(f"🔍 DEBUG: product_name from intent parser = {product_name}")
        
        # Handle different intents
        print(f"🔍 DEBUG: parsed_intent.intent = {parsed_intent.intent}")
        print(f"🔍 DEBUG: IntentType.CLASSIFY = {IntentType.CLASSIFY}")
        if parsed_intent.intent == IntentType.CLASSIFY:
            # For classification queries, run the full pipeline with flexible context
            if request.contextual_data:
                # Use provided contextual data (for customs API requests)
                contextual_data = request.contextual_data.dict()
                print(f"🔍 DEBUG: Using provided contextual_data: {contextual_data}")
            else:
                # Restructure payload to include user_query (for individual user requests)
                contextual_data = {
                    "user_query": original_query
                }
                print(f"🔍 DEBUG: Restructured contextual_data: {contextual_data}")
            
            results = orchestrator.classify_complete_pipeline(
                product_name, 
                order_id=request.order_id, 
                original_query=original_query,
                contextual_data=contextual_data,
                user_answers=request.user_answers
            )
            
            # Defensive guard: ensure results is a dict before using .get()
            if results is None:
                raise HTTPException(status_code=500, detail="Pipeline returned no results")
            if not isinstance(results, dict):
                print(f"DEBUG: Unexpected results type: {type(results)}; coercing to empty dict")
                results = {}
            
            # Add debug block to see commodity extraction
            print(f"\n🔍 DEBUGGING COMMODITY EXTRACTION:")
            print("="*60)

            commodity_results = results.get("stage3_commodity_lookup", {})
            print(f"commodity_results type: {type(commodity_results)}")
            print(f"commodity_results keys: {list(commodity_results.keys()) if isinstance(commodity_results, dict) else 'Not a dict'}")

            if commodity_results is None:
                commodity_results = {}

            for hs_code, codes in commodity_results.items():
                print(f"\nHS Code: {hs_code}")
                print(f"  Codes type: {type(codes)}")
                print(f"  Codes value: {codes}")
                
                if codes and isinstance(codes, list) and len(codes) > 0:
                    selected_commodity = codes[0]
                    print(f"  Selected commodity type: {type(selected_commodity)}")
                    print(f"  Selected commodity keys: {list(selected_commodity.keys()) if isinstance(selected_commodity, dict) else 'Not a dict'}")
                    if isinstance(selected_commodity, dict):
                        print(f"  tariff_code value: {selected_commodity.get('tariff_code')}")
                        print(f"  description value: {selected_commodity.get('description')}")
                    break

            print("="*60)
            
            # Check if clarification is needed - return clarification questions
            if results.get("needs_clarification") and results.get("clarification_questions"):
                # Generate session ID for this clarification request
                import uuid
                session_id = str(uuid.uuid4())
                
                # Store session data for follow-up
                classification_sessions[session_id] = {
                    "product_name": product_name,
                    "original_query": original_query,
                    "intent": parsed_intent.intent.value,
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Return clarification questions
                return {
                    "product_name": product_name,
                    "hs_code": None,
                    "commodity_code": None,
                    "description": None,
                    "requires_clarification": True,
                    "clarification_questions": [
                        ClarificationQuestion(**q) for q in results["clarification_questions"]
                    ],
                    "session_id": session_id
                }
            
            # Extract final results for complete classification
            final_results = results.get("final_results", {})
            commodity_results = results.get("stage3_commodity_lookup", {})
            
            # Get the confirmed HS code and selected commodity
            confirmed_code = final_results.get("confirmed_hs_code")
            selected_commodity = None
            for hs_code, codes in commodity_results.items():
                if codes and isinstance(codes, list) and len(codes) > 0:
                    # Take the first code since commodity lookup returns [best_match] with selected=True
                    selected_commodity = codes[0]
                    break
            
            # Debug: Print selected commodity details
            print(f"\n🔍 API RESPONSE BUILDING DEBUG:")
            print(f"   confirmed_code: {confirmed_code}")
            print(f"   selected_commodity: {selected_commodity}")
            if selected_commodity:
                print(f"   selected_commodity type: {type(selected_commodity)}")
                print(f"   selected_commodity keys: {list(selected_commodity.keys()) if isinstance(selected_commodity, dict) else 'Not a dict'}")
                print(f"   tariff_code: {selected_commodity.get('tariff_code')}")
                print(f"   description: {selected_commodity.get('description')}")
            
            return {
                "product_name": product_name,
                "hs_code": confirmed_code,
                "commodity_code": selected_commodity.get("tariff_code") if selected_commodity else None,
                "description": selected_commodity.get("description") if selected_commodity else None
            }
            
        elif parsed_intent.intent == IntentType.DUTIES:
            # For duties queries, we need to classify first, then provide duty information
            contextual_data = request.contextual_data.dict() if request.contextual_data else None
            results = orchestrator.classify_complete_pipeline(
                product_name, 
                order_id=request.order_id,
                contextual_data=contextual_data
            )
            
            # Extract HS code for duty lookup
            final_results = results.get("final_results", {})
            confirmed_code = final_results.get("confirmed_hs_code")
            
            duty_message = f"To determine import duties for {product_name}, I first need to classify it."
            if confirmed_code:
                duty_message += f" The HS code is {confirmed_code}. Import duties vary by country of origin and destination. You'll need to check with your local customs authority for specific rates."
            
            return {
                "product_name": product_name,
                "hs_code": confirmed_code,
                "commodity_code": None,
                "description": f"Duties information for {product_name}"
            }
            
        elif parsed_intent.intent == IntentType.PERMITS:
            # For permit queries, classify first then provide permit information
            contextual_data = request.contextual_data.dict() if request.contextual_data else None
            results = orchestrator.classify_complete_pipeline(
                product_name, 
                order_id=request.order_id,
                contextual_data=contextual_data
            )
            
            final_results = results.get("final_results", {})
            confirmed_code = final_results.get("confirmed_hs_code")
            
            permit_message = f"For import/export permits for {product_name}, I first need to classify it."
            if confirmed_code:
                permit_message += f" The HS code is {confirmed_code}. Permit requirements depend on the specific product, country regulations, and intended use. You should check with your local trade authority."
            
            return {
                "product_name": product_name,
                "hs_code": confirmed_code,
                "commodity_code": None,
                "description": f"Permit requirements for {product_name}"
            }
            
        elif parsed_intent.intent == IntentType.RESTRICTIONS:
            # For restriction queries
            contextual_data = request.contextual_data.dict() if request.contextual_data else None
            results = orchestrator.classify_complete_pipeline(
                product_name, 
                order_id=request.order_id,
                contextual_data=contextual_data
            )
            
            final_results = results.get("final_results", {})
            confirmed_code = final_results.get("confirmed_hs_code")
            
            restriction_message = f"For trade restrictions on {product_name}, I first need to classify it."
            if confirmed_code:
                restriction_message += f" The HS code is {confirmed_code}. Trade restrictions vary by country and may include quotas, embargoes, or special licensing requirements. Check with your local customs authority."
            
            return {
                "product_name": product_name,
                "hs_code": confirmed_code,
                "commodity_code": None,
                "description": f"Trade restrictions for {product_name}"
            }
            
        else:
            # For general or unknown intents, default to classification
            if request.contextual_data:
                # Use provided contextual data (for customs API requests)
                contextual_data = request.contextual_data.dict()
                print(f"🔍 DEBUG: Using provided contextual_data: {contextual_data}")
            else:
                # Restructure payload to include user_query (for individual user requests)
                contextual_data = {
                    "user_query": original_query
                }
                print(f"🔍 DEBUG: Restructured contextual_data: {contextual_data}")
            
            results = orchestrator.classify_complete_pipeline(
                product_name, 
                order_id=request.order_id,
                original_query=original_query,
                contextual_data=contextual_data,
                user_answers=request.user_answers
            )
            
            # Add debug block to see commodity extraction
            print(f"\n🔍 DEBUGGING COMMODITY EXTRACTION (ELSE BRANCH):")
            print("="*60)

            commodity_results = results.get("stage3_commodity_lookup", {})
            print(f"commodity_results type: {type(commodity_results)}")
            print(f"commodity_results keys: {list(commodity_results.keys()) if isinstance(commodity_results, dict) else 'Not a dict'}")

            if commodity_results is None:
                commodity_results = {}

            for hs_code, codes in commodity_results.items():
                print(f"\nHS Code: {hs_code}")
                print(f"  Codes type: {type(codes)}")
                print(f"  Codes value: {codes}")
                
                if codes and isinstance(codes, list) and len(codes) > 0:
                    selected_commodity = codes[0]
                    print(f"  Selected commodity type: {type(selected_commodity)}")
                    print(f"  Selected commodity keys: {list(selected_commodity.keys()) if isinstance(selected_commodity, dict) else 'Not a dict'}")
                    if isinstance(selected_commodity, dict):
                        print(f"  tariff_code value: {selected_commodity.get('tariff_code')}")
                        print(f"  description value: {selected_commodity.get('description')}")
                    break

            print("="*60)
            
            # Check if clarification is needed - return clarification questions
            if results.get("needs_clarification") and results.get("clarification_questions"):
                # Generate session ID for this clarification request
                import uuid
                session_id = str(uuid.uuid4())
                
                # Store session data for follow-up
                classification_sessions[session_id] = {
                    "product_name": product_name,
                    "original_query": original_query,
                    "intent": parsed_intent.intent.value,
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Return clarification questions
                return {
                    "product_name": product_name,
                    "hs_code": None,
                    "commodity_code": None,
                    "description": None,
                    "requires_clarification": True,
                    "clarification_questions": [
                        ClarificationQuestion(**q) for q in results["clarification_questions"]
                    ],
                    "session_id": session_id
                }
            
            final_results = results.get("final_results", {})
            
            confirmed_code = final_results.get("confirmed_hs_code")
            
            # Extract selected commodity code (same logic as CLASSIFY branch)
            selected_commodity = None
            for hs_code, codes in commodity_results.items():
                if codes and isinstance(codes, list) and len(codes) > 0:
                    selected_commodity = codes[0]
                    break
            
            return {
                "product_name": product_name,
                "hs_code": confirmed_code,
                "commodity_code": selected_commodity.get("tariff_code") if selected_commodity else None,
                "description": selected_commodity.get("description") if selected_commodity else None
            }
            
    except Exception as e:
        print(f"❌ Classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/classify/async", response_model=Dict[str, Any])
async def classify_product_async(request: ClassificationRequest):
    """
    Start async classification and return immediately with a task ID.
    The actual classification runs in the background.
    """
    import uuid
    task_id = str(uuid.uuid4())
    
    # Store task in memory (in production, use Redis or database)
    classification_tasks[task_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat()
    }
    
    # Start background task
    asyncio.create_task(process_classification_async(task_id, request))
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Classification started. Use /classify/status/{task_id} to check progress."
    }

async def process_classification_async(task_id: str, request: ClassificationRequest):
    """
    Background task to process classification asynchronously.
    """
    try:
        # Update task status
        classification_tasks[task_id]["status"] = "processing"
        
        # Run the classification pipeline
        results = orchestrator.classify_complete_pipeline(
            request.product_name,
            order_id=request.order_id,
            original_query=request.product_name,
            contextual_data=request.contextual_data.dict() if request.contextual_data else None,
            user_answers=request.user_answers
        )
        
        # Extract final results
        final_results = results.get("final_results", {})
        commodity_results = results.get("stage3_commodity_lookup", {})
        
        # Get the confirmed HS code and selected commodity
        confirmed_code = final_results.get("confirmed_hs_code")
        selected_commodity = None
        for hs_code, codes in commodity_results.items():
            if codes and isinstance(codes, list) and len(codes) > 0:
                selected_commodity = codes[0]
                break
        
        # Build response
        response = {
            "product_name": request.product_name,
            "hs_code": confirmed_code,
            "commodity_code": selected_commodity.get("tariff_code") if selected_commodity else None,
            "description": selected_commodity.get("description") if selected_commodity else None
        }
        
        # Update task with results
        classification_tasks[task_id]["status"] = "completed"
        classification_tasks[task_id]["result"] = response
        
    except Exception as e:
        # Update task with error
        classification_tasks[task_id]["status"] = "failed"
        classification_tasks[task_id]["error"] = str(e)

@app.post("/classify/continue", response_model=SimplifiedResponse)
async def continue_classification(request: ClarificationRequest):
    """
    Continue classification with clarification answers
    
    Args:
        request: ClarificationRequest with session_id and additional_context
        
    Returns:
        SimplifiedResponse with final classification or more clarification questions
    """
    try:
        # Retrieve session data
        if request.session_id not in classification_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = classification_sessions[request.session_id]
        product_name = session_data["product_name"]
        original_query = session_data.get("original_query", product_name)
        intent = session_data.get("intent", "classify")
        
        # Continue classification with user answers - don't restart the pipeline
        # Extract user answers from additional_context
        user_answers = request.additional_context
        
        # Get the previous results to continue from where we left off
        previous_results = session_data["results"]
        
        # Continue the 10-stage workflow from Stage 8+ with user answers
        from module.commodity_code import run_10_stage_workflow
        
        # Get the HS codes and other data from previous results
        stage1_results = previous_results.get("stage1_classification", {})
        stage2_results = previous_results.get("stage2_reconciliation", {})
        final_determination = stage2_results.get("final_determination", {})
        confirmed_hs_code = final_determination.get("confirmed_hs_code")
        
        if not confirmed_hs_code or confirmed_hs_code == "NO_MATCH":
            # Fall back to original HS codes if reconciliation failed
            hs_codes = stage1_results.get("consensus_codes", [])
        else:
            hs_codes = [confirmed_hs_code]
        
        # Continue the workflow from where it paused
        commodity_results = run_10_stage_workflow(
            hs_codes=hs_codes,
            product_name=product_name,
            product_info_text=stage1_results.get("product_information", ""),
            original_question=original_query,
            order_id=session_data.get("order_id"),
            contextual_data=session_data.get("contextual_data"),
            stage1_results=stage1_results,
            user_answers=user_answers
        )
        
        # Build the results structure to match the original pipeline
        results = {
            "metadata": previous_results.get("metadata", {}),
            "stage1_classification": stage1_results,
            "stage2_reconciliation": stage2_results,
            "stage3_commodity_lookup": commodity_results,
            "final_results": None,
            "errors": []
        }
        
        # Count total commodity codes found
        total_codes = 0
        needs_clarification = False
        clarification_questions = []
        
        for hs_code, result in commodity_results.items():
            if isinstance(result, dict) and result.get('requires_clarification'):
                needs_clarification = True
                clarification_questions.extend(result.get('questions', []))
            elif isinstance(result, list):
                total_codes += len(result)
        
        # Add clarification info to results
        results["needs_clarification"] = needs_clarification
        results["clarification_questions"] = clarification_questions
        
        # Generate final results summary
        results["final_results"] = orchestrator._generate_final_summary(
            stage1_results, final_determination, commodity_results, product_name
        )
        
        # Check if more clarification is needed
        if results.get("needs_clarification") and results.get("clarification_questions"):
            # Update session data
            classification_sessions[request.session_id]["results"] = results
            
            return {
                "product_name": product_name,
                "hs_code": None,
                "commodity_code": None,
                "description": None,
                "confidence": None,
                "status": "needs_clarification",
                "clarification_questions": [
                    ClarificationQuestion(**q) for q in results["clarification_questions"]
                ],
                "session_id": request.session_id
            }
        
        # Extract final results
        final_results = results.get("final_results", {})
        commodity_results = results.get("stage3_commodity_lookup", {})
        
        # Get the confirmed HS code from final results or commodity results
        confirmed_code = final_results.get("confirmed_hs_code")
        
        # Get the selected commodity code and HS code
        selected_commodity = None
        selected_hs_code = None
        for hs_code, codes in commodity_results.items():
            if codes and isinstance(codes, list) and len(codes) > 0:
                # Take the first code since commodity lookup returns [best_match] with selected=True
                selected_commodity = codes[0]
                selected_hs_code = hs_code
                break
        
        # Use the HS code from commodity results if confirmed_code is not available
        if not confirmed_code and selected_hs_code:
            confirmed_code = selected_hs_code
        
        # Clean up session
        del classification_sessions[request.session_id]
        
        # Use the structured response format
        structured_response = build_classification_response(results, product_name)
        
        return {
            "product_name": final_results.get("product_name", product_name),
            "hs_code": confirmed_code,
            "commodity_code": selected_commodity.get("tariff_code") if selected_commodity else None,
            "description": selected_commodity.get("description") if selected_commodity else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/classify/status/{task_id}", response_model=Dict[str, Any])
async def get_classification_status(task_id: str):
    """
    Get the status and result of an async classification task.
    """
    if task_id not in classification_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = classification_tasks[task_id]
    
    if task["status"] == "completed":
        return {
            "task_id": task_id,
            "status": "completed",
            "result": task["result"]
        }
    elif task["status"] == "failed":
        return {
            "task_id": task_id,
            "status": "failed",
            "error": task["error"]
        }
    else:
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Classification in progress..."
        }

@app.get("/classify/{product_name}", response_model=SimplifiedResponse)
async def classify_product_get(
    product_name: str,
    verbose: bool = Query(False, description="Enable verbose output")
):
    try:
        results = orchestrator.classify_complete_pipeline(product_name)
        
        # Extract essential information
        final_results = results.get("final_results", {})
        commodity_results = results.get("stage3_commodity_lookup", {})
        
        # Get the confirmed HS code
        confirmed_code = final_results.get("confirmed_hs_code")
        
        # Get the selected commodity code
        selected_commodity = None
        for hs_code, codes in commodity_results.items():
            if codes and isinstance(codes, list) and len(codes) > 0:
                # Take the first code since commodity lookup returns [best_match] with selected=True
                selected_commodity = codes[0]
                break
        
        return {
            "product_name": final_results.get("product_name", "Unknown Product"),
            "hs_code": confirmed_code,
            "commodity_code": selected_commodity.get("tariff_code") if selected_commodity else None,
            "description": selected_commodity.get("description") if selected_commodity else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/classify/stream")
async def classify_product_stream_get(product_name: str = Query(..., description="Product name to classify")):
    """
    Stream classification results in real-time via GET (for EventSource compatibility)
    """
    request = ClassificationRequest(product_name=product_name)
    return await classify_product_stream(request)

@app.post("/classify/stream")
async def classify_product_stream(request: ClassificationRequest):
    """
    Stream classification results with improved response structure
    """
    async def generate_stream():
        try:
            def stream_thinking_step(step: str, message: str, replace_previous: bool = False):
                """Stream a thinking step"""
                chunk = {
                    "id": f"thinking_{int(time.time() * 1000)}",
                    "object": "classification.thinking",
                    "created": int(time.time()),
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": message,
                            "type": "thinking",
                            "step": step,
                            "replace_previous": replace_previous
                        },
                        "finish_reason": None
                    }]
                }
                return f"data: {json.dumps(chunk)}\n\n"

            async def stream_text(text: str, delay_between_words: float = 0.03):
                """Stream final response text word by word"""
                words = text.split()
                for i, word in enumerate(words):
                    chunk = {
                        "id": f"chunk_{int(time.time() * 1000)}_{i}",
                        "object": "classification.chunk", 
                        "created": int(time.time()),
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": word + " ",
                                "type": "response"
                            },
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    await asyncio.sleep(delay_between_words)
            
            # Start thinking process
            yield stream_thinking_step("start", "Processing...", True)
            await asyncio.sleep(0.5)
            
            # Stage 1: Initial Classification
            yield stream_thinking_step("stage1", "📊 **Stage 1: Initial HS Code Classification**\n\nAnalyzing product characteristics and gathering information from multiple AI models...", True)
            await asyncio.sleep(1)
            
            # Run the actual classification with contextual data
            contextual_data = request.contextual_data.dict() if request.contextual_data else None
            results = orchestrator.classify_complete_pipeline(
                request.product_name, 
                order_id=request.order_id,
                contextual_data=contextual_data
            )
            
            # Show Stage 1 results
            stage1_results = results.get("stage1_classification", {})
            consensus_codes = stage1_results.get("consensus_codes", [])
            if consensus_codes:
                yield stream_thinking_step("stage1_result", f"✅ **Stage 1 Complete**\n\nGenerated {len(consensus_codes)} HS codes: {', '.join(consensus_codes)}\n\nThese codes represent the AI models' consensus on the most likely classifications.", True)
            else:
                yield stream_thinking_step("stage1_result", "❌ **Stage 1 Issue**\n\nNo consensus codes were generated. This may require manual review.", True)
            await asyncio.sleep(1)
            
            # Stage 2: Reconciliation
            yield stream_thinking_step("stage2", "🔍 **Stage 2: HS Code Reconciliation**\n\nValidating generated codes against authoritative databases:\n• Tariff codes database\n• HS codes 2022 database\n• Cross-referencing with international standards...", True)
            await asyncio.sleep(1.5)
            
            # Show Stage 2 results
            stage2_results = results.get("stage2_reconciliation", {})
            final_determination = stage2_results.get("final_determination", {})
            confirmed_code = final_determination.get("confirmed_hs_code")
            quality_score = final_determination.get("quality_score", 0)
            
            if confirmed_code and confirmed_code != "NO_MATCH":
                yield stream_thinking_step("stage2_result", f"✅ **Stage 2 Complete**\n\nConfirmed HS code: **{confirmed_code}**\nQuality score: {quality_score}/10\n\nDatabase validation successful with high confidence.", True)
            else:
                yield stream_thinking_step("stage2_result", "⚠️ **Stage 2 Reconciliation**\n\nNo single code could be definitively confirmed. Proceeding with original consensus codes for commodity lookup.", True)
            await asyncio.sleep(1)
            
            # Stage 3: Commodity Code Lookup
            yield stream_thinking_step("stage3", "📋 **Stage 3: Commodity Code Lookup**\n\nSearching for specific 10-digit tariff codes used in customs declarations...\nAnalyzing with AI to select the most appropriate classification...", True)
            await asyncio.sleep(1)
            
            # Show Stage 3 results
            commodity_results = results.get("stage3_commodity_lookup", {})
            total_codes = 0
            selected_commodity = None
            needs_clarification = results.get("needs_clarification", False)
            
            for hs_code, codes in commodity_results.items():
                if codes and isinstance(codes, list):
                    total_codes += len(codes)
                    if len(codes) > 0:
                        # Take the first code since commodity lookup returns [best_match] with selected=True
                        selected_commodity = codes[0]
            
            if needs_clarification:
                yield stream_thinking_step("stage3_result", "📋 **Stage 3 Analysis**\n\nFound multiple commodity codes but need additional information to select the most appropriate one.", True)
                await asyncio.sleep(1)
                
                # Send clarification needed message
                yield stream_thinking_step("clarification", "🤔 **Additional Information Needed**\n\nI need some specific details about your product to provide the most accurate commodity code classification.", True)
                await asyncio.sleep(0.8)
                
                # Mark thinking complete for clarification
                thinking_complete_chunk = {
                    "id": f"thinking_complete_{int(time.time() * 1000)}",
                    "object": "classification.thinking_complete",
                    "created": int(time.time()),
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": "",
                            "type": "thinking_complete"
                        },
                        "finish_reason": "thinking_complete"
                    }]
                }
                yield f"data: {thinking_complete_chunk}\n\n"
                await asyncio.sleep(0.3)
                
                # Send clarification response
                clarification_message = f"I need some additional information to accurately classify **{request.product_name}**. Please provide the following details:"
                async for chunk in stream_text(clarification_message):
                    yield chunk
                
                # Send clarification data
                clarification_chunk = {
                    "id": f"clarification_{int(time.time() * 1000)}",
                    "object": "classification.clarification",
                    "created": int(time.time()),
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": "",
                            "type": "clarification",
                            "clarification_questions": results.get("clarification_questions", []),
                            "session_id": str(uuid.uuid4())  # Generate session ID for clarification
                        },
                        "finish_reason": "clarification_needed"
                    }]
                }
                
                # Store session for clarification
                session_id = clarification_chunk["choices"][0]["delta"]["session_id"]
                classification_sessions[session_id] = {
                    "product_name": request.product_name,
                    "original_query": request.product_name,
                    "intent": "classify",
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                }
                
                yield f"data: {json.dumps(clarification_chunk)}\n\n"
                yield "data: [DONE]\n\n"
                return
                
            elif selected_commodity:
                yield stream_thinking_step("stage3_result", f"✅ **Stage 3 Complete**\n\nSelected commodity code: **{selected_commodity.get('tariff_code')}**\nDescription: {selected_commodity.get('description')}\n\nReady to generate final classification response.", True)
            elif total_codes > 0:
                yield stream_thinking_step("stage3_result", f"📋 **Stage 3 Analysis**\n\nFound {total_codes} potential commodity codes requiring further clarification.", True)
            else:
                yield stream_thinking_step("stage3_result", "❌ **Stage 3 Issue**\n\nNo commodity codes found for the confirmed HS classification.", True)
            await asyncio.sleep(1)
            
            # Final thinking step
            yield stream_thinking_step("finalizing", "🎯 **Finalizing Response**\n\nSynthesizing analysis results and preparing comprehensive classification report...", True)
            await asyncio.sleep(0.8)
            
            # Generate the final response
            response_message = build_classification_response(results, request.product_name)
            
            # Mark thinking complete
            thinking_complete_chunk = {
                "id": f"thinking_complete_{int(time.time() * 1000)}",
                "object": "classification.thinking_complete",
                "created": int(time.time()),
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "type": "thinking_complete"
                    },
                    "finish_reason": "thinking_complete"
                }]
            }
            yield f"data: {thinking_complete_chunk}\n\n"
            await asyncio.sleep(0.3)
            
            # Stream the final response
            async for chunk in stream_text(response_message):
                yield chunk
            
            # Send the actual results
            final_results = results.get("final_results", {})
            confirmed_code = final_results.get("confirmed_hs_code")
            
            # Get commodity code if available
            commodity_code = None
            if "commodity_results" in results:
                commodity_results = results["commodity_results"]
                if isinstance(commodity_results, dict) and "selected_commodity" in commodity_results:
                    selected_commodity = commodity_results["selected_commodity"]
                    if selected_commodity:
                        commodity_code = selected_commodity.get("tariff_code")
            
            # Send results chunk
            results_chunk = {
                "id": f"results_{int(time.time() * 1000)}",
                "object": "classification.results",
                "created": int(time.time()),
                "data": {
                    "hs_code": confirmed_code,
                    "commodity_code": commodity_code,
                    "description": final_results.get("description", ""),
                    "product_name": request.product_name,
                    "success": True
                }
            }
            yield f"data: {json.dumps(results_chunk)}\n\n"
            
            # Mark completion
            final_chunk = {
                "id": f"final_{int(time.time() * 1000)}",
                "object": "classification.complete",
                "created": int(time.time()),
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant", 
                        "content": "",
                        "type": "complete"
                    },
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            error_chunk = {
                "id": f"error_{int(time.time() * 1000)}",
                "object": "classification.error",
                "created": int(time.time()),
                "error": {
                    "message": str(e),
                    "type": "classification_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)