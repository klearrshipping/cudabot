# HS Code Classification API Documentation

## Overview

The HS Code Classification API is a FastAPI-based REST service that provides AI-powered classification of products using the Harmonized System (HS) codes and commodity codes. The API uses a multi-stage pipeline to classify products with high accuracy.

## Base URL

```
http://localhost:5000
```

## Authentication

Currently, no authentication is required. The API is configured with CORS enabled for all origins.

## API Endpoints

### 1. Root Endpoint - API Information

**GET** `/`

Returns basic API information and available endpoints.

**Response:**
```json
{
  "name": "HS Code Classification API",
  "version": "1.0.0",
  "description": "AI-powered HS code classification with multi-stage pipeline",
  "endpoints": [
    "GET / - API information",
    "GET /health - Health check endpoint",
    "POST /classify - Classify a product (send JSON body)",
    "POST /classify/stream - Stream classification results in real-time",
    "POST /classify/continue - Continue classification with clarification answers",
    "GET /classify/{product_name} - Classify a product via URL"
  ]
}
```

### 2. Health Check

**GET** `/health`

Returns the health status of the API.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### 3. Classify Product (POST)

**POST** `/classify`

Classifies a product and returns HS code and commodity code information.

**Request Body:**
```json
{
  "product_name": "string",
  "verbose": false
}
```

**Response:**
```json
{
  "product_name": "string",
  "hs_code": "string",
  "commodity_code": "string",
  "description": "string"
}
```

### 4. Classify Product (GET)

**GET** `/classify/{product_name}`

Classifies a product using URL parameters.

**Parameters:**
- `product_name` (path): The product to classify
- `verbose` (query, optional): Enable verbose output (default: false)

**Response:**
```json
{
  "product_name": "string",
  "hs_code": "string",
  "commodity_code": "string",
  "description": "string"
}
```

### 5. Stream Classification

**POST** `/classify/stream`

Streams classification results in real-time with thinking process.

**Request Body:**
```json
{
  "product_name": "string"
}
```

**Response:** Server-Sent Events (SSE) stream with real-time updates.

### 6. Continue Classification

**POST** `/classify/continue`

Continues classification with clarification answers.

**Request Body:**
```json
{
  "session_id": "string",
  "additional_context": {
    "key": "value"
  }
}
```

## Connection Examples

### Python Examples

#### 1. Basic Classification Request

```python
import requests
import json

# API endpoint
API_BASE_URL = "http://localhost:5000"

def classify_product(product_name):
    """Classify a product using the API"""
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/classify",
            json={"product_name": product_name},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Product: {result['product_name']}")
            print(f"HS Code: {result['hs_code']}")
            print(f"Commodity Code: {result['commodity_code']}")
            print(f"Description: {result['description']}")
            return result
        else:
            print(f"Error: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("Connection failed. Make sure the API is running on http://localhost:5000")
    except Exception as e:
        print(f"Error: {str(e)}")

# Example usage
result = classify_product("2022 Tesla Model Y")
```

#### 2. GET Request Example

```python
import requests
from urllib.parse import quote

def classify_product_get(product_name):
    """Classify a product using GET request"""
    
    try:
        # URL encode the product name
        encoded_name = quote(product_name)
        
        response = requests.get(
            f"{API_BASE_URL}/classify/{encoded_name}",
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error: {str(e)}")

# Example usage
result = classify_product_get("iPhone 15 Pro")
```

#### 3. Streaming Classification

```python
import requests
import json

def stream_classification(product_name):
    """Stream classification results in real-time"""
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/classify/stream",
            json={"product_name": product_name},
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=120
        )
        
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            print(f"Received: {data}")
                        except json.JSONDecodeError:
                            pass
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

# Example usage
stream_classification("Samsung Galaxy S24")
```

#### 4. Health Check

```python
def check_api_health():
    """Check if the API is running and healthy"""
    
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"API Status: {health_data['status']}")
            print(f"Version: {health_data['version']}")
            print(f"Timestamp: {health_data['timestamp']}")
            return True
        else:
            print(f"API not healthy: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("API is not running or not accessible")
        return False
    except Exception as e:
        print(f"Error checking health: {str(e)}")
        return False

# Example usage
check_api_health()
```

### JavaScript/Node.js Examples

#### 1. Basic Classification with Fetch

```javascript
async function classifyProduct(productName) {
    try {
        const response = await fetch('http://localhost:5000/classify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                product_name: productName
            })
        });

        if (response.ok) {
            const result = await response.json();
            console.log('Product:', result.product_name);
            console.log('HS Code:', result.hs_code);
            console.log('Commodity Code:', result.commodity_code);
            console.log('Description:', result.description);
            return result;
        } else {
            console.error('Error:', await response.text());
            return null;
        }
    } catch (error) {
        console.error('Error:', error);
        return null;
    }
}

// Example usage
classifyProduct('MacBook Pro M3');
```

#### 2. Streaming Classification with EventSource

```javascript
function streamClassification(productName) {
    const eventSource = new EventSource(`http://localhost:5000/classify/stream?product_name=${encodeURIComponent(productName)}`);
    
    eventSource.onmessage = function(event) {
        if (event.data === '[DONE]') {
            eventSource.close();
            return;
        }
        
        try {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
            
            // Handle different types of data
            if (data.object === 'classification.thinking') {
                console.log('Thinking:', data.choices[0].delta.content);
            } else if (data.object === 'classification.chunk') {
                console.log('Response chunk:', data.choices[0].delta.content);
            }
        } catch (e) {
            console.error('Error parsing data:', e);
        }
    };
    
    eventSource.onerror = function(event) {
        console.error('EventSource error:', event);
        eventSource.close();
    };
}

// Example usage
streamClassification('Tesla Model 3');
```

### cURL Examples

#### 1. Basic Classification

```bash
curl -X POST "http://localhost:5000/classify" \
  -H "Content-Type: application/json" \
  -d '{"product_name": "iPhone 15 Pro Max"}'
```

#### 2. GET Request

```bash
curl "http://localhost:5000/classify/iPhone%2015%20Pro%20Max"
```

#### 3. Health Check

```bash
curl "http://localhost:5000/health"
```

#### 4. API Information

```bash
curl "http://localhost:5000/"
```

### PowerShell Examples

#### 1. Basic Classification

```powershell
$body = @{
    product_name = "Samsung Galaxy S24 Ultra"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:5000/classify" -Method POST -Body $body -ContentType "application/json"
Write-Output $response
```

#### 2. Health Check

```powershell
$response = Invoke-RestMethod -Uri "http://localhost:5000/health" -Method GET
Write-Output $response
```

## Error Handling

The API returns standard HTTP status codes:

- **200**: Success
- **404**: Session not found (for continue endpoint)
- **422**: Additional information needed (clarification required)
- **500**: Internal server error

### Error Response Format

```json
{
  "detail": "Error message description"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. However, the API uses AI models that may have their own rate limits.

## Timeout Considerations

- Classification requests can take 30-120 seconds depending on complexity
- Use appropriate timeout values in your client code
- Streaming requests should handle connection timeouts gracefully

## Best Practices

1. **Always check API health** before making classification requests
2. **Use appropriate timeouts** (120+ seconds for classification)
3. **Handle clarification requests** - some products may need additional information
4. **Use streaming** for better user experience with long-running requests
5. **Cache results** when possible to avoid repeated API calls
6. **Handle errors gracefully** and provide meaningful feedback to users

## Testing the API

You can use the provided `test_api.py` script to test the API:

```bash
# Test with default product
python test_api.py

# Test with custom product
python test_api.py "Custom Product Name"
```

## Configuration

The API requires the following environment variables:
- `OPENROUTER_API_KEY`: API key for OpenRouter AI services
- `HS_CODES_SUPABASE_URL`: Supabase database URL
- `HS_CODES_SUPABASE_ANON_KEY`: Supabase anonymous key

Make sure these are properly configured in your environment before starting the API server.
