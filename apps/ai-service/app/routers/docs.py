"""
Custom ReDoc endpoint with better error handling and fallback.
"""
from fastapi import APIRouter  # type: ignore[reportMissingImports]
from fastapi.responses import HTMLResponse  # type: ignore[reportMissingImports]

router = APIRouter()


@router.get("/redoc-custom", response_class=HTMLResponse)
async def custom_redoc():
    """
    Custom ReDoc page with better error handling.
    Use this if the default /redoc doesn't work.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PhotoGenius AI Service - ReDoc</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            #loading {
                text-align: center;
                padding: 50px;
            }
            #error {
                display: none;
                color: red;
                padding: 20px;
                background: #ffe6e6;
                margin: 20px;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div id="loading">Loading API documentation...</div>
        <div id="error"></div>
        <redoc spec-url="/openapi.json" hide-download-button="false"></redoc>
        
        <script>
            // Try multiple CDN sources for ReDoc
            const redocSources = [
                "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
                "https://unpkg.com/redoc@next/bundles/redoc.standalone.js",
                "https://cdnjs.cloudflare.com/ajax/libs/redoc/2.1.3/redoc.standalone.min.js"
            ];
            
            let currentSource = 0;
            
            function loadRedoc(source) {
                const script = document.createElement('script');
                script.src = source;
                script.onload = function() {
                    document.getElementById('loading').style.display = 'none';
                    console.log('ReDoc loaded successfully from:', source);
                };
                script.onerror = function() {
                    console.error('Failed to load ReDoc from:', source);
                    currentSource++;
                    if (currentSource < redocSources.length) {
                        loadRedoc(redocSources[currentSource]);
                    } else {
                        document.getElementById('loading').innerHTML = 
                            '<h2>Failed to load ReDoc</h2>' +
                            '<p>All CDN sources failed. Please check your internet connection or firewall settings.</p>' +
                            '<p>You can view the OpenAPI spec directly: <a href="/openapi.json">/openapi.json</a></p>' +
                            '<p>Or use Swagger UI: <a href="/docs">/docs</a></p>';
                        document.getElementById('error').style.display = 'block';
                        document.getElementById('error').innerHTML = 
                            'Error: Could not load ReDoc JavaScript library. ' +
                            'This might be due to:<br>' +
                            '1. Internet connection issues<br>' +
                            '2. Firewall blocking CDN requests<br>' +
                            '3. Ad blocker blocking CDN resources<br><br>' +
                            'Try:<br>' +
                            '- Disabling ad blockers<br>' +
                            '- Checking firewall settings<br>' +
                            '- Using Swagger UI instead: <a href="/docs">/docs</a>';
                    }
                };
                document.head.appendChild(script);
            }
            
            // Start loading
            loadRedoc(redocSources[0]);
            
            // Check if openapi.json is accessible
            fetch('/openapi.json')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to fetch OpenAPI spec');
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('OpenAPI spec loaded successfully');
                })
                .catch(error => {
                    console.error('Error loading OpenAPI spec:', error);
                    document.getElementById('error').style.display = 'block';
                    document.getElementById('error').innerHTML = 
                        'Error: Could not load OpenAPI specification. ' +
                        'Please check if the server is running correctly.';
                });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
