# Azure Functions Project - Development Guidelines

## 🔧 Code Quality & Maintenance

### Dependency Management
**CRITICAL**: When adding or updating Python packages:
1. **ALWAYS** update both `requirements.txt` AND `pyproject.toml` simultaneously
2. **NEVER** update only one file - they must stay in sync
3. **ALWAYS** use tools to check the latest library version before installation - **DO NOT rely on past knowledge**
4. **ALWAYS** use exact versions with `==` in BOTH files (e.g., `azure-storage-blob==12.24.0`)
5. **NEVER** use `>=` or other version ranges - pin exact versions for reproducibility
6. Maintain alphabetical order within each section for consistency

**Version Checking Workflow**:
Before adding/updating any dependency:
```bash
# Use pip index to check latest version
pip index versions <package-name>

# Or use uv (faster alternative)
uv pip search <package-name>
```

**Example Pattern** (Both files use exact versions with `==`):
```toml
# pyproject.toml
dependencies = [
    "aiohttp==3.11.10",
    "azure-cosmos==4.14.1",
    "azure-functions==1.24.0",
    "azure-identity==1.25.1",
    "azure-storage-blob==12.24.0",
    "openai==2.7.1",
    "python-dotenv==1.2.1",
]
```

```
# requirements.txt
aiohttp==3.11.10
azure-cosmos==4.14.1
azure-functions==1.24.0
azure-identity==1.25.1
azure-storage-blob==12.24.0
openai==2.7.1
python-dotenv==1.2.1
```

**Key Principles**:
- **Exact versions ensure reproducibility** - Both files must have identical version specifications
- **Check latest versions using tools** - Never guess or use outdated knowledge
- **Pin to latest stable version** - Use the most recent version at time of addition unless there's a specific compatibility reason not to
- **Update both files together** - They must always remain perfectly in sync

### Async/Parallel Execution Standards
**CRITICAL**: When implementing parallel operations or HTTP requests:
1. **ALWAYS** use `aiohttp` instead of `requests` library for HTTP calls
   - `aiohttp` provides true async I/O without blocking the event loop
   - Better performance and resource utilization for concurrent operations
   - Supports async/await patterns natively
2. **ALWAYS** use `asyncio.gather()` instead of `ThreadPoolExecutor` for parallel execution
   - True parallel I/O execution without GIL blocking
   - More efficient for I/O-bound operations
   - Better error handling with `return_exceptions=True`
   - Lower overhead compared to thread context switching
3. **ALWAYS** make route handlers and helper functions `async def` when they perform I/O operations
4. **ALWAYS** use proper type guards when processing `asyncio.gather()` results with `return_exceptions=True`

**Pattern for Async HTTP Requests**:
```python
import aiohttp
import asyncio

async def _execute_api_call(url: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Make async HTTP request."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response,
    ):
        response.raise_for_status()
        result = await response.json()
        return (url, result)
```

**Pattern for Parallel Execution**:
```python
@app.route(route="batch_operation", methods=["POST"])
@require_api_key
async def batch_operation(req: func.HttpRequest) -> func.HttpResponse:
    # Create tasks for parallel execution
    tasks = [
        _execute_operation(item)
        for item in items
    ]
    
    # Execute all tasks in parallel with exception handling
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results with proper type guards
    for result in results:
        if isinstance(result, Exception):
            # Handle exception
            logger.error(f"Operation failed: {str(result)}")
            continue
        
        if isinstance(result, tuple) and len(result) == 2:
            # Process successful result
            key, value = result
```

**Key Benefits**:
- **Performance**: True async I/O without blocking threads
- **Scalability**: Handle more concurrent operations with fewer resources
- **Error Handling**: Better exception management with `return_exceptions=True`
- **Resource Efficiency**: Lower memory and CPU overhead

### Test Documentation
**CRITICAL**: When adding new functionality:
1. **ALWAYS** add test cases to `test.http` for new routes or endpoints
2. Include multiple test scenarios:
   - Basic happy path example
   - Edge cases (empty body, missing parameters, etc.)
   - Error scenarios (missing headers, invalid authentication, etc.)
   - Different variations of valid inputs
3. Add descriptive comments for each test case
4. Update the `@variables` section if new configuration is needed
5. Test cases serve as both documentation and manual testing tools

**Test Case Pattern**:
```http
### Endpoint Name - Basic Request
POST {{baseUrl}}/endpoint_name
X-API-Key: {{apiKey}}
X-Required-Header: {{headerValue}}
Content-Type: application/json

{
  "param": "value"
}

### Endpoint Name - Edge Case
...

### Endpoint Name - Error Scenario
...
```

### Pylance Error Resolution
**CRITICAL**: After every code change or implementation:
1. **ALWAYS** check for Pylance errors immediately after completing the implementation
2. **ALWAYS** fix all Pylance errors before considering the task complete
3. **NEVER** use `# type: ignore` or `# pyright: ignore` comments to suppress errors
4. **FIX THE ROOT CAUSE** - add proper type hints, resolve import issues, correct the code logic
5. Only in extremely rare cases where a Pylance error is a false positive should you consider suppression
6. Ensure no warnings or errors remain in the code

#### Common Scenarios & Solutions

**Scenario: Azure Functions Request Headers Type Issues**
When extracting headers from `func.HttpRequest`, Pylance may report "Type is partially unknown" errors because `req.headers` lacks proper type information in the Azure Functions SDK.

```python
# ❌ PROBLEM: Type inference fails
cosmos_endpoint = req.headers.get("X-Cosmos-Endpoint")  # Type: Unknown | None

# ✅ SOLUTION: Cast headers to dict[str, str]
from typing import cast

headers = cast(dict[str, str], req.headers)
cosmos_endpoint = headers.get("X-Cosmos-Endpoint")  # Type: str | None
```

**Key principle**: Use `typing.cast()` to provide type information when working with SDKs that have incomplete type annotations, ensuring proper type inference throughout your code.

**Scenario: Azure Functions Content-Length Header Type Issues**
When extracting `Content-Length` from request headers, Pylance reports type errors because the header value is unknown and the default parameter type doesn't match.

```python
# ❌ PROBLEM: Type inference fails and int() receives unknown type
content_length = int(req.headers.get("Content-Length", 0))
# Error: Type of "get" is partially unknown
# Error: Argument type is unknown

# ✅ SOLUTION: Cast headers and use string default
headers = cast(dict[str, str], req.headers)
content_length = int(headers.get("Content-Length", "0"))
# Now Pylance knows: headers.get() returns str | None → int() receives str → result is int
```

**Key principle**: When using headers in type conversions, cast the headers dict first and use defaults that match the expected type (string defaults for string values).

**Scenario: Exception Headers with Partially Unknown Types**
When accessing headers from Azure SDK exceptions (e.g., `CosmosHttpResponseError`), Pylance reports "Type is partially unknown" because the SDK doesn't provide complete type information for exception attributes.

```python
# ❌ PROBLEM: Exception headers are partially unknown
retry_after = float(e.headers.get("x-ms-retry-after-ms", 1000)) / 1000.0
# Error: Type of "headers" is partially unknown

# ❌ PROBLEM: Even casting doesn't fully resolve it
error_headers = cast(dict[str, Any], e.headers)
# Error: Type of "headers" is still partially unknown (dict[Unknown, Unknown])

# ✅ SOLUTION: Use getattr() to safely access the attribute
headers_attr: Any = getattr(e, "headers", {})
error_headers = cast(dict[str, Any], headers_attr)
retry_after = float(error_headers.get("x-ms-retry-after-ms", 1000)) / 1000.0
# Now Pylance is satisfied - getattr returns Any which can be cast properly
```

**Key principle**: For SDK exception objects with partially unknown attributes, use `getattr()` to extract the attribute into a variable with `Any` type, then cast that variable to the desired type. This provides a clean type boundary that Pylance can verify.

**Scenario: Dictionary Initialization with Partially Unknown Types**
When initializing dictionaries with mixed value types, Pylance may infer partially unknown types if it cannot determine the complete type structure.

```python
# ❌ PROBLEM: Pylance infers dict[str, Unknown]
health_status = {"status": "healthy", "timestamp": time.time(), "checks": {}}
# Error: Type of "health_status" is partially unknown

# ✅ SOLUTION: Add explicit type annotation
health_status: dict[str, Any] = {"status": "healthy", "timestamp": time.time(), "checks": {}}
# Now Pylance knows the complete type structure
```

**Key principle**: When creating dictionaries with mixed or nested value types, add explicit type annotations to help Pylance understand the intended structure, especially when using `Any` for flexible value types.

**Scenario: Extracting Headers and Initializing Clients**
When multiple route handlers need to extract headers and initialize clients, consolidate the logic into a single function that handles both operations.

```python
# ❌ PROBLEM: Separate functions create unnecessary complexity
def extract_cosmos_headers(req, request_id):
    headers = cast(dict[str, str], req.headers)
    endpoint = headers.get("X-Cosmos-Endpoint")
    # ... validation and return tuple or error response

def get_cosmos_container(request_id, endpoint, db_name, container_name):
    # ... initialize client
    return container

# Then in each route:
result = extract_cosmos_headers(req, request_id)
if isinstance(result, func.HttpResponse):
    return result
endpoint, db_name, container_name = result
container = get_cosmos_container(request_id, endpoint, db_name, container_name)

# ✅ SOLUTION: Merge into single function
def get_cosmos_container(req: func.HttpRequest, request_id: str) -> Any | func.HttpResponse:
    """Extract headers and initialize container client."""
    headers = cast(dict[str, str], req.headers)
    endpoint = headers.get("X-Cosmos-Endpoint")
    # ... validation, client initialization
    # Return container or error response directly

# Then in each route (much simpler):
container = get_cosmos_container(req, request_id)
if isinstance(container, func.HttpResponse):
    return container
```

**Key principle**: When operations are always performed together, merge them into a single function that returns either the successful result or an error response. This reduces code complexity and improves maintainability.

### Code Reusability
**CRITICAL**: Before implementing any functionality:
1. **ALWAYS** check if similar logic exists elsewhere in the codebase
2. **ALWAYS** create reusable helper functions instead of duplicating code across routes
3. Extract common patterns into shared utility functions
4. Avoid copy-pasting code between different route handlers
5. When two functions are always called together in sequence, consider merging them into one

### Feature Removal and Cleanup
**CRITICAL**: When removing features or dependencies:
1. **Remove from all locations systematically**:
   - Dependencies: Both `requirements.txt` AND `pyproject.toml`
   - Imports: All import statements
   - Configuration: Setup code, constants, and environment variables
   - Helper functions: Any utility functions specific to the feature
   - Usage: All calls throughout the codebase (use grep_search to find all occurrences)
   - Documentation: Configuration templates and comments
2. **Use targeted replacements** with proper context (3-5 lines before/after)
3. **Verify complete removal** using grep_search after changes
4. **Run lint checks** to ensure no errors introduced
5. **Document the reason** for removal in commit messages

**Example: Removing Telemetry/Metrics**
When we removed the opencensus-ext-azure telemetry feature:
- ✅ Removed package from requirements.txt and pyproject.toml
- ✅ Removed opencensus imports (2 import statements)
- ✅ Removed Application Insights configuration (~80 lines)
- ✅ Removed _record_metric() helper function (~15 lines)
- ✅ Removed all _record_metric() calls (23 locations across routes)
- ✅ Removed APPLICATIONINSIGHTS_CONNECTION_STRING from .env.template
- ✅ Verified zero remaining references using grep_search
- ✅ Confirmed no Pylance errors after cleanup
- **Result**: Clean removal of 382 lines (17% code reduction)

---

## ✅ Core Best Practices

### KISS (Keep It Simple, Stupid)
- Write simple, clear, and understandable code
- Avoid unnecessary complexity
- Prefer straightforward solutions over clever tricks

### DRY (Don't Repeat Yourself)
- Eliminate code duplication by abstracting common logic into reusable components
- Create utility functions for repeated operations
- Use decorators or middleware for cross-cutting concerns

### YAGNI (You Aren't Gonna Need It)
- Don't implement features until they are actually needed
- Focus on current requirements, not hypothetical future needs
- Avoid over-engineering solutions

### SOLID Principles
1. **Single Responsibility Principle**: Each function/class should have one reason to change
2. **Open/Closed Principle**: Open for extension, closed for modification
3. **Liskov Substitution Principle**: Subtypes must be substitutable for their base types
4. **Interface Segregation Principle**: Don't force clients to depend on unused interfaces
5. **Dependency Inversion Principle**: Depend on abstractions, not concretions

These principles help in designing maintainable and scalable object-oriented systems.

### Separation of Concerns
- Divide the system into distinct sections, each handling a specific responsibility
- Keep business logic separate from infrastructure code
- Separate data access, business logic, and presentation layers

### Code Reusability
- Design components and modules that can be reused across projects
- Create generic utility functions that solve common problems
- Build composable functions that can be combined in different ways

### Modularity
- Break down the system into independent modules for easier maintenance
- Each module should have a clear, well-defined purpose
- Minimize coupling between modules

### Testability & Automated Testing
- Write unit tests for individual functions
- Implement integration tests for end-to-end workflows
- Adopt TDD (Test-Driven Development) where possible
- Ensure code is designed to be testable (avoid hard dependencies)

### Version Control
- Use Git for collaboration and history tracking
- Write meaningful commit messages
- Use feature branches for new development
- Review code before merging

### Continuous Integration/Continuous Deployment (CI/CD)
- Automate builds, tests, and deployments
- Ensure fast feedback on code changes
- Deploy safely and frequently with automated checks

### Documentation & Code Comments
- Maintain clear documentation for public APIs and complex logic
- Write meaningful comments that explain "why", not "what"
- Keep documentation up-to-date with code changes
- Avoid redundant comments that simply restate the code

### Refactoring
- Regularly improve code structure without changing functionality
- Refactor when you see duplication or complexity growing
- Make small, incremental improvements
- Always have tests in place before refactoring

### Error Handling & Logging
- Implement robust error handling for all failure scenarios
- Use meaningful error messages that help with debugging
- Log important events, errors, and warnings
- Include context in logs (request IDs, user IDs, etc.)
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Performance & Scalability Considerations
- Optimize only when necessary; measure before making changes
- Profile code to identify actual bottlenecks
- Consider caching strategies for frequently accessed data
- Design for horizontal scalability when needed
- Be mindful of database query performance

### Security Best Practices
- **Validate all inputs** from external sources
- **Manage secrets securely** using Azure Key Vault or environment variables
- Follow **OWASP guidelines** for common vulnerabilities
- Use parameterized queries to prevent SQL injection
- Implement proper authentication and authorization
- Sanitize output to prevent XSS attacks
- Keep dependencies up-to-date to avoid known vulnerabilities

---

## 📋 Azure Functions Specific Guidelines

### Function Structure
- Keep function handlers thin; delegate to service/business logic layers
- Use dependency injection for better testability
- Handle Azure Functions bindings appropriately

### Standardized Response Format
**CRITICAL**: All API routes must follow a consistent response structure for success and error cases.

#### Success Response Structure
Every successful response must include:
```python
{
    # Core response data (varies by endpoint)
    "results": [...],           # For query/search endpoints
    "document": {...},          # For upsert endpoints
    
    # Standard metadata fields (REQUIRED)
    "request_id": "abc123",     # 8-character UUID for request tracking
    "performance": {            # Performance metrics in milliseconds
        "operation_ms": 123.45,  # Main operation time (e.g., query_ms)
        "total_ms": 150.67       # Total request processing time
    },
    
    # Additional context fields (as needed)
    "count": 10,                # Result count
    "message": "Operation successful"  # Optional success message
}
```

#### Error Response Structure
Every error response must include:
```python
{
    "error": "Error Category",           # Brief error type (e.g., "Validation error")
    "message": "Detailed explanation",   # Clear, actionable error message
    "request_id": "abc123"              # Include when available
}
```

#### Response Status Codes
Use appropriate HTTP status codes:
- `200 OK` - Successful operation
- `400 Bad Request` - Validation errors, missing required fields
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Invalid authentication credentials
- `500 Internal Server Error` - Server-side errors, exceptions

#### Implementation Guidelines
1. **Always include `request_id`** - Generate at the start of each route handler using `str(uuid.uuid4())[:8]`
2. **Always include `performance` metrics** - Track operation timing using `time.time()`
3. **Use consistent field names** - Follow existing patterns (e.g., `result_count`, `total_results`)
4. **Provide actionable error messages** - Tell users what went wrong and how to fix it
5. **Log all errors with context** - Include request_id, operation type, and error details

#### Example Implementation Pattern
```python
@app.route(route="example", methods=["POST"])
@require_api_key
async def example_route(req: func.HttpRequest) -> func.HttpResponse:
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info(f"[{request_id}] Operation initiated")
    
    try:
        # Operation logic here
        operation_start = time.time()
        result = await perform_operation()  # Use async operations
        operation_time = time.time() - operation_start
        
        total_time = time.time() - start_time
        
        return func.HttpResponse(
            body=json.dumps({
                "result": result,
                "request_id": request_id,
                "performance": {
                    "operation_ms": round(operation_time * 1000, 2),
                    "total_ms": round(total_time * 1000, 2),
                }
            }),
            mimetype="application/json",
            status_code=200,
        )
    
    except Exception as e:
        logger.error(f"[{request_id}] Operation failed: {str(e)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({
                "error": "Operation failed",
                "message": str(e),
                "request_id": request_id
            }),
            mimetype="application/json",
            status_code=500,
        )
```

### Environment Configuration
- Use `local.settings.json` for local development (never commit this file)
- Store sensitive configuration in Azure Key Vault
- Use environment-specific configuration when deploying

### Cosmos DB Best Practices
- Refer to the main Azure Cosmos DB instructions for data modeling
- Use appropriate partition keys for optimal performance
- Minimize cross-partition queries
- Handle rate limiting (429 errors) with proper retry logic

---

## 🎯 Implementation Checklist

Before marking any task as complete, ensure:
- [ ] All Pylance errors are resolved
- [ ] No code duplication exists (check for reusable patterns)
- [ ] Code follows SOLID principles
- [ ] Error handling is implemented
- [ ] Logging is added for debugging
- [ ] Security best practices are followed
- [ ] Code is documented where necessary
- [ ] Tests are written (if applicable)
- [ ] Response follows standardized format with `request_id` and `performance` fields
- [ ] Appropriate HTTP status codes are used
- [ ] Error responses include actionable messages
- [ ] **Both `requirements.txt` and `pyproject.toml` are updated and in sync** (if dependencies changed)
- [ ] **Test cases added to `test.http`** (if new functionality/routes added)
- [ ] **Use `aiohttp` for HTTP requests, not `requests` library**
- [ ] **Use `asyncio.gather()` for parallel execution, not `ThreadPoolExecutor`**
- [ ] **Route handlers and I/O functions are declared as `async def`**

---

## 📚 Past Implementation Examples

### Code Quality Improvements (P0/P1/P2 Priorities)
A comprehensive code quality improvement was performed addressing:

**P0 - Critical Security & Architecture**:
- ✅ API keys moved from query parameters to headers (X-API-Key header with query fallback)
- ✅ Converted sync routes to async (query_cosmosdb, upsert_cosmosdb, get_blob, save_blob)
- ✅ Implemented client pooling/singleton pattern (CosmosClient, BlobServiceClient, AzureOpenAI)
  - Prevents resource exhaustion from repeated client creation
  - Module-level cache with factory functions (_get_cosmos_client, etc.)

**P1 - Reliability & Performance**:
- ✅ Implemented Cosmos DB 429 retry logic with exponential backoff
  - _retry_cosmos_operation() helper with configurable attempts and base delay
  - Handles rate limiting gracefully without failing requests
- ✅ Fixed blocking operations in async routes
  - Wrapped OpenAI sync calls with asyncio.to_thread()
  - Wrapped blob operations with asyncio.to_thread()
- ✅ Added request size validation (configurable MAX_REQUEST_SIZE_MB)

**P2 - Operations & Observability**:
- ✅ Enhanced health check endpoint
  - Tests Cosmos DB connectivity
  - Tests Blob Storage connectivity
  - Returns detailed status per service
- ✅ Added timeout configurations (DEFAULT_TIMEOUT_SECONDS for external calls)
- ✅ Implemented sanitized logging (no sensitive data exposure)
- ✅ Standardized response format with request_id and performance metrics

**Implementation Approach**:
1. Used `multi_replace_string_in_file` for batch operations (efficiency)
2. Made incremental changes with verification between steps
3. Ran lint checks after each major change
4. Verified no Pylance errors throughout
5. Created comprehensive documentation (MIGRATION_GUIDE.md, etc.)

### Feature Removal Example: Telemetry/Metrics
When telemetry feature was not desired, performed complete systematic removal:

**Removal Steps**:
1. **Dependencies** - Removed opencensus-ext-azure from both requirements.txt and pyproject.toml
2. **Imports** - Removed `from opencensus.ext.azure import metrics_exporter` and stats imports
3. **Configuration** - Removed APPLICATIONINSIGHTS_CONNECTION_STRING and metrics setup (~80 lines)
4. **Helper Functions** - Removed _record_metric() function (~15 lines)
5. **Usage** - Found all _record_metric() calls using grep_search (23 locations)
   - Removed from helper functions (_query_with_embeddings, _upsert_document, _delete_document, etc.)
   - Removed from route handlers (query_cosmosdb, upsert_cosmosdb, get_blob, save_blob, etc.)
6. **Templates** - Removed APPLICATIONINSIGHTS_CONNECTION_STRING from .env.template
7. **Verification** - Used grep_search to confirm zero remaining references
8. **Lint Check** - Ran get_errors to ensure no issues introduced

**Results**:
- Clean removal: 382 lines eliminated (17% code reduction)
- Zero Pylance errors
- All core improvements (P0/P1/P2) preserved
- No remnants of telemetry code anywhere in the project

**Key Lessons**:
- Use grep_search extensively to find all occurrences before removal
- Remove in logical order: dependencies → imports → setup → helpers → usage → config
- Use multi_replace_string_in_file for batch removals (efficiency)
- Verify each step to catch any missed references
- Always preserve unrelated improvements when removing specific features
