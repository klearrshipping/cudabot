# BOL Extraction Resilience Improvements

## Problem
BOL extraction was failing intermittently with error: `"Expecting value: line 325 column 1 (char 1782)"`

The issue occurred when:
- OpenRouter API returned HTML error pages instead of JSON
- Document-specific characteristics caused payload size issues
- API timeouts occurred due to complex processing

## Root Cause
Invoice extraction worked consistently, but BOL extraction failed on certain documents. This indicated:
1. Document-specific image sizes exceeding API limits
2. Complex BOL prompts + large images causing timeouts
3. Non-JSON error responses (HTML) breaking the extraction workflow

## Solution: Multi-Layer Resilience

### 1. **Payload Size Validation** (Lines 304-311)
```python
# Calculate and validate payload size BEFORE sending
payload_size_mb = len(payload_str) / (1024 * 1024)
if payload_size_mb > 4.5:
    raise ValueError(f"Payload size ({payload_size_mb:.2f}MB) exceeds safe limit")
```
**Benefit**: Catches oversized payloads early, preventing API errors

### 2. **Enhanced Error Handling** (Lines 313-360)
- ✅ Added explicit 60-second timeout
- ✅ Check HTTP status code before parsing JSON
- ✅ Validate Content-Type is `application/json`
- ✅ Catch and display actual error responses
- ✅ Detailed error logging with response text

**Benefit**: Provides actionable error messages instead of generic JSON parsing errors

### 3. **Progressive Quality Degradation** (Lines 67-174)
Automatic retry with 4 quality levels:
1. **Normal**: 200 DPI, 85% JPEG quality
2. **Reduced**: 150 DPI, 75% JPEG quality  
3. **Low**: 120 DPI, 65% JPEG quality
4. **Minimal**: 100 DPI, 55% JPEG quality

**Benefit**: System automatically finds the lowest quality that works for each document

### 4. **Intelligent Retry Logic** (Lines 128-165)
Different handling for different error types:
- **ValueError** (payload/JSON errors) → Try lower quality
- **Timeout** → Try lower quality for faster processing
- **Other errors** → Generic retry with degradation

**Benefit**: Context-aware recovery based on specific failure modes

### 5. **Quality-Specific Image Conversion** (Lines 256-317)
New method `_convert_pdf_to_image_with_quality()` allows precise control:
- Configurable DPI (affects resolution)
- Configurable JPEG quality (affects compression)
- Size logging for diagnostics

**Benefit**: Fine-grained control over image generation for each retry attempt

## Expected Behavior

### Success on First Attempt
```
🔄 Attempt 1/4: Processing with normal quality (DPI=200, Q=85)
📸 PDF converted to image successfully (normal quality)
   Image size: 2.3MB
✅ BOL extraction succeeded on attempt 1 with normal quality
```

### Success After Retry
```
🔄 Attempt 1/4: Processing with normal quality (DPI=200, Q=85)
📸 PDF converted to image successfully (normal quality)
   Image size: 5.8MB
⚠️ Payload size too large: 5.89MB
⚠️ Attempt 1 failed with normal quality: Payload size (5.89MB) exceeds safe limit (4.5MB)
   → Image too large, trying lower quality...

🔄 Attempt 2/4: Processing with reduced quality (DPI=150, Q=75)
📸 PDF converted to image successfully (reduced quality)
   Image size: 3.1MB
✅ BOL extraction succeeded on attempt 2 with reduced quality
```

### Complete Failure (All Attempts)
```
🔄 Attempt 1/4: Processing with normal quality (DPI=200, Q=85)
⚠️ Attempt 1 failed with normal quality: ...
   → Trying lower quality...

🔄 Attempt 2/4: Processing with reduced quality (DPI=150, Q=75)
⚠️ Attempt 2 failed with reduced quality: ...
   → Trying lower quality...

🔄 Attempt 3/4: Processing with low quality (DPI=120, Q=65)
⚠️ Attempt 3 failed with low quality: ...
   → Trying lower quality...

🔄 Attempt 4/4: Processing with minimal quality (DPI=100, Q=55)
⚠️ Attempt 4 failed with minimal quality: ...
❌ All 4 quality levels failed
❌ Error processing with OpenRouter: [detailed error]
```

## Impact on Workflow

### Before
- ❌ Single failure → Entire BOL extraction fails
- ❌ eSAD processing blocked due to missing BOL data
- ❌ No insight into failure cause

### After
- ✅ Up to 4 automatic retry attempts
- ✅ Progressive degradation finds optimal quality
- ✅ Clear diagnostic output for debugging
- ✅ Graceful failure with detailed error messages
- ✅ Metadata tracks which quality level succeeded

## Additional Improvements Needed (Future)

1. **eSAD Graceful Degradation**
   - Allow eSAD processing to proceed with invoice-only data
   - Mark fields as "pending BOL data" instead of failing

2. **Alternative Extraction Methods**
   - Text-based extraction fallback (no image)
   - Different AI models as fallback

3. **Manual Review Queue**
   - Flag failed extractions for manual processing
   - Store partial results for review

## Testing Recommendations

Test with:
1. ✅ Small, simple BOLs (< 1MB when converted)
2. ✅ Large, complex BOLs (> 5MB when converted)
3. ✅ Multi-page BOLs
4. ✅ Scanned/low-quality BOLs
5. ✅ BOLs with unusual formatting

## Metrics to Monitor

- Success rate by attempt number
- Average quality level used
- Payload sizes
- Processing times per quality level
- Failure reasons (timeout vs payload vs other)

