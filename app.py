from flask import Flask, render_template_string, send_from_directory
import os

app = Flask(__name__)

@app.route('/')
def index():
    # Read App.jsx content
    try:
        with open('frontend/App.jsx', 'r') as f:
            app_jsx_content = f.read()
    except FileNotFoundError:
        app_jsx_content = "// App.jsx not found"

    # Remove export default for browser compatibility
    app_jsx_content = app_jsx_content.replace('export default App;', '')

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TicketScout</title>
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- Import Map for Firebase and React -->
    <script type="importmap">
    {{
      "imports": {{
        "react": "https://esm.sh/react@18",
        "react-dom/client": "https://esm.sh/react-dom@18/client",
        "firebase/app": "https://esm.sh/firebase@10.7.1/app",
        "firebase/firestore": "https://esm.sh/firebase@10.7.1/firestore",
        "firebase/auth": "https://esm.sh/firebase@10.7.1/auth"
      }}
    }}
    </script>
    
    <!-- Babel for JSX -->
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    
    <!-- Fonts: Space Grotesk & Space Mono for that technical/industrial feel -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">

    <style>
        body {{ font-family: 'Space Grotesk', sans-serif; }}
        .font-mono {{ font-family: 'Space Mono', monospace; }}
        /* Custom Scrollbar for Webkit */
        ::-webkit-scrollbar {{ width: 0px; background: transparent; }}
    </style>

    <script>
      // Global error handler
      window.onerror = function(message, source, lineno, colno, error) {{
        console.error("Global Error:", message);
        document.body.innerHTML += '<div style="color:red; padding:20px; border:1px solid red; margin:20px; background:white; z-index:9999; position:relative;">' +
          '<h3>Global Error:</h3>' + message + '<br>' +
          'Source: ' + source + ':' + lineno + '</div>';
      }};

      // Global configuration placeholders
      window.__app_id = "ticket-scout-demo"; 
      window.__firebase_config = {{
        apiKey: "YOUR_API_KEY",
        authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
        projectId: "YOUR_PROJECT_ID",
        storageBucket: "YOUR_PROJECT_ID.appspot.com",
        messagingSenderId: "YOUR_SENDER_ID",
        appId: "YOUR_APP_ID"
      }};
      window.__initial_auth_token = null; 
    </script>
</head>
<body>
    <div id="root"></div>
    
    <script type="text/babel" data-type="module">
      console.log("Script starting...");
      import {{ createRoot }} from 'react-dom/client';
      console.log("React DOM imported");
      
      // Injected App.jsx content (It contains its own imports)
      {app_jsx_content}
      
      try {{
          console.log("Mounting React App...");
          const root = createRoot(document.getElementById('root'));
          root.render(<App />);
          console.log("React App mounted");
      }} catch (e) {{
          console.error("Render error:", e);
          document.body.innerHTML += '<div style="color:red">Render Error: ' + e.message + '</div>';
      }}
    </script>
</body>
</html>
"""
    return html

if __name__ == '__main__':
    app.run(debug=True, port=8080)
