from flask import Flask, request, jsonify, render_template, send_file, abort, redirect, url_for
import base64
import socket
import os
import json
from datetime import datetime
import logging
import uuid

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("server.log"),
                              logging.StreamHandler()])

# Configuration
KEY_PATH = "rustdesk_config.txt"  # Path to your RustDesk public key
CLIENTS_FILE = "clients.json"  # File to store client information
TEMPLATE_DIR = "templates"  # Directory for HTML templates

# Initialize clients file if it doesn't exist
if not os.path.exists(CLIENTS_FILE):
    with open(CLIENTS_FILE, 'w') as f:
        json.dump([], f)

def get_local_ip():
    """Get the local IP of the system"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"
    return local_ip

def convert_rustdesk_config(filepath):
    """Read rustdesk string from a file, convert to JSON format with local IP"""
    with open(filepath, 'r') as file:
        original = file.read().strip()  # read and remove surrounding whitespace/newlines

    local_ip = get_local_ip()

    # Parse original config into dictionary
    fields = {}
    for item in original.split(','):
        if '=' in item:
            key, value = item.split('=', 1)
            fields[key.replace('rustdesk-host', 'host')] = local_ip if value == 'serverip' else value

    # Add missing 'api' field if not present
    fields.setdefault('api', '')

    # Arrange keys in a specified order
    ordered_fields = {
        'host': fields.get('host', ''),
        'relay': fields.get('relay', ''),
        'api': fields.get('api', ''),
        'key': fields.get('key', '')
    }
    json_str = json.dumps(ordered_fields)
    base64_encoded = base64.b64encode(json_str.encode()).decode()
    reversed_result = base64_encoded[::-1]
    # Generate JSON string
    return reversed_result


def load_clients():
    """Load clients from the JSON file."""
    try:
        with open(CLIENTS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        app.logger.error(f"Failed to load clients: {str(e)}")
        return []

def save_clients(clients):
    """Save clients to the JSON file."""
    try:
        with open(CLIENTS_FILE, 'w') as f:
            json.dump(clients, f, indent=2)
        return True
    except Exception as e:
        app.logger.error(f"Failed to save clients: {str(e)}")
        return False

@app.route('/rustdesk_config.txt', methods=['GET'])
def get_key():
    """Serve the RustDesk public key."""
    try:
        if not os.path.exists(KEY_PATH):
            app.logger.error("RustDesk key file not found")
            abort(404)
        return send_file(KEY_PATH, mimetype='application/octet-stream')
    except Exception as e:
        app.logger.error(f"Error serving key file: {str(e)}")
        abort(500)

@app.route('/update-notes', methods=['POST'])
def update_notes():
    """Update notes for a client."""
    client_id = request.form.get('client_id')
    notes = request.form.get('notes', '')
    
    if not client_id:
        return redirect(url_for('client_list', error="Client ID is required"))
    
    clients = load_clients()
    updated = False
    
    for i, client in enumerate(clients):
        if client["client_id"] == client_id:
            clients[i]["notes"] = notes
            clients[i]["last_seen"] = datetime.now().isoformat()
            updated = True
            break
    
    if not updated:
        return redirect(url_for('client_list', error="Client not found"))
    
    if save_clients(clients):
        return redirect(url_for('client_list'))
    else:
        return redirect(url_for('client_list', error="Failed to save client data"))

@app.route('/register', methods=['POST'])
def register_client():
    """Register a new RustDesk client."""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    required_fields = ["client_id", "hostname"]
    for field in required_fields:
        if field not in data:
            return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400
    
    # Get the IP address from the request
    ip_address = request.remote_addr
    
    # Load existing clients
    clients = load_clients()
    
    # Check if client already exists
    for i, client in enumerate(clients):
        if client["client_id"] == data["client_id"]:
            # Update existing client
            clients[i] = {**client, **data, "ip_address": ip_address, "last_seen": datetime.now().isoformat()}
            
            if save_clients(clients):
                return jsonify({"status": "success", "message": "Client updated"}), 200
            else:
                return jsonify({"status": "error", "message": "Failed to save client data"}), 500
    
    # Add new client
    new_client = {
        **data,
        "ip_address": ip_address,
        "registered_at": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat()
    }
    clients.append(new_client)
    
    if save_clients(clients):
        return jsonify({"status": "success", "message": "Client registered"}), 201
    else:
        return jsonify({"status": "error", "message": "Failed to save client data"}), 500

@app.route('/', methods=['GET'])
def client_list():
    """Display the list of registered clients."""
    pasteconfig = convert_rustdesk_config(KEY_PATH)
    clients = load_clients()
    return render_template('clients.html', clients=clients, pasteconfig=pasteconfig)

@app.route('/add', methods=['GET', 'POST'])
def add_client():
    """Add a client manually through a form."""
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        hostname = request.form.get('hostname')
        ip_address = request.form.get('ip_address')
        connection_string = request.form.get('connection_string')
        os = request.form.get('os', '')
        notes = request.form.get('notes', '')
        
        if not client_id or not hostname:
            return render_template('add_client.html', error="Client ID and Hostname are required fields")
        
        clients = load_clients()
        
        # Check if client already exists
        for i, client in enumerate(clients):
            if client["client_id"] == client_id:
                # Update existing client
                clients[i] = {
                    **client,
                    "hostname": hostname,
                    "ip_address": ip_address,
                    "os": os,
                    "notes": notes,
                    "connection_string": connection_string,
                    "last_seen": datetime.now().isoformat(),
                    "manually_added": True
                }
                
                if save_clients(clients):
                    return redirect(url_for('client_list'))
                else:
                    return render_template('add_client.html', error="Failed to save client data")
        
        # Add new client
        new_client = {
            "client_id": client_id,
            "hostname": hostname,
            "ip_address": ip_address,
            "os": os,
            "notes": notes,
            "connection_string": connection_string,
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "manually_added": True
        }
        clients.append(new_client)
        
        if save_clients(clients):
            return redirect(url_for('client_list'))
        else:
            return render_template('add_client.html', error="Failed to save client data")
    
    return render_template('add_client.html')

@app.route('/delete/<client_id>', methods=['POST'])
def delete_client(client_id):
    """Delete a client from the registry."""
    clients = load_clients()
    clients = [c for c in clients if c["client_id"] != client_id]
    
    if save_clients(clients):
        return redirect(url_for('client_list'))
    else:
        return redirect(url_for('client_list', error="Failed to delete client"))

if __name__ == '__main__':
    # Make sure the template directory exists
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    
    # Create templates if they don't exist
    template_path = os.path.join(TEMPLATE_DIR, 'clients.html')
    if not os.path.exists(template_path):
        with open(template_path, 'w') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>RustDesk Clients</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap">
    <style>
        body {
            font-family: 'Roboto', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f2f5;
            color: #333;
        }
        .header-container {
            text-align: center;
            margin-bottom: 40px;
        }
        h1 {
            color: #2c3e50;
            display: inline-block;
            font-size: 2.5rem;
            margin: 0;
            padding: 10px 30px;
            background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            letter-spacing: 1px;
        }
        .add-button-container {
            text-align: center;
            margin-bottom: 30px;
        }
        .add-button {
            background-color: #27ae60;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 50px;
            font-weight: 500;
            box-shadow: 0 4px 6px rgba(39, 174, 96, 0.2);
            transition: all 0.3s ease;
            font-size: 1rem;
            display: inline-block;
        }
        .add-button:hover {
            background-color: #2ecc71;
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(39, 174, 96, 0.3);
        }
        .client-list {
            display: flex;
            flex-wrap: wrap;
            gap: 25px;
            justify-content: center;
            max-width: 1400px;
            margin: 0 auto;
        }
        .client-card {
            position: relative;
            width: 320px;
            padding: 0;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .client-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 20px rgba(0,0,0,0.15);
        }
        .monitor {
            background-color: #2c3e50;
            border-radius: 10px 10px 3px 3px;
            padding: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            position: relative;
        }
        .monitor:before {
            content: '';
            position: absolute;
            bottom: -15px;
            left: 50%;
            transform: translateX(-50%);
            width: 60px;
            height: 15px;
            background-color: #34495e;
            border-radius: 0 0 5px 5px;
            z-index: -1;
        }
        .monitor:after {
            content: '';
            position: absolute;
            bottom: -20px;
            left: 50%;
            transform: translateX(-50%);
            width: 100px;
            height: 5px;
            background-color: #34495e;
            border-radius: 5px;
            z-index: -2;
        }
        .screen {
            background-color: #ecf0f1;
            border-radius: 5px;
            padding: 15px;
            position: relative;
            min-height: 180px;
        }
        .client-id-display {
            font-family: 'Courier New', monospace;
            background-color: #2c3e50;
            color: #2ecc71;
            padding: 8px 12px;
            border-radius: 5px;
            font-size: 0.9rem;
            margin: 10px 0;
            text-align: center;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.3);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .power-button {
            position: absolute;
            right: 10px;
            top: 10px;
            width: 10px;
            height: 10px;
            background-color: #e74c3c;
            border-radius: 50%;
            border: 2px solid #c0392b;
        }
        .power-light {
            position: absolute;
            right: 30px;
            top: 12px;
            width: 6px;
            height: 6px;
            background-color: #2ecc71;
            border-radius: 50%;
            animation: blink 5s infinite;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        .client-header {
            font-weight: 500;
            font-size: 1.3rem;
            margin-bottom: 10px;
            color: #2c3e50;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .client-details {
            margin-bottom: 15px;
            font-size: 0.9rem;
            color: #7f8c8d;
        }
        .action-buttons {
            margin-top: 15px;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        }
        .connect-button {
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.85rem;
            border: none;
            flex: 1;
            text-align: center;
            transition: all 0.2s ease;
            box-shadow: 0 2px 5px rgba(52, 152, 219, 0.3);
            white-space: nowrap;
        }
        .connect-button:hover {
            background-color: #2980b9;
            box-shadow: 0 4px 8px rgba(52, 152, 219, 0.4);
        }
        .edit-button {
            display: inline-block;
            background-color: #f39c12;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.85rem;
            border: none;
            flex: 1;
            text-align: center;
            transition: all 0.2s ease;
            box-shadow: 0 2px 5px rgba(243, 156, 18, 0.3);
            cursor: pointer;
            white-space: nowrap;
        }
        .edit-button:hover {
            background-color: #e67e22;
            box-shadow: 0 4px 8px rgba(243, 156, 18, 0.4);
        }
        .delete-form {
            display: inline;
            flex: 1;
        }
        .delete-button {
            background-color: #e74c3c;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85rem;
            width: 100%;
            transition: all 0.2s ease;
            box-shadow: 0 2px 5px rgba(231, 76, 60, 0.3);
        }
        .delete-button:hover {
            background-color: #c0392b;
            box-shadow: 0 4px 8px rgba(231, 76, 60, 0.4);
        }
        .timestamp {
            font-size: 0.8rem;
            color: #95a5a6;
            margin-top: 10px;
            text-align: center;
        }
        .manually-added {
            position: absolute;
            top: -10px;
            right: -10px;
            font-size: 0.7rem;
            background-color: #f39c12;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            z-index: 10;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .notes {
            font-style: italic;
            color: #7f8c8d;
            border-top: 1px solid #eee;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .no-clients {
            text-align: center;
            margin-top: 50px;
            font-size: 1.2rem;
            color: #7f8c8d;
        }
        .os-icon {
            margin-right: 5px;
            font-size: 0.9rem;
        }
        .monitor-ports {
            position: absolute;
            bottom: -10px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 5px;
        }
        .port {
            width: 8px;
            height: 3px;
            background-color: #7f8c8d;
            border-radius: 1px;
        }
        /* Modal styles */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
            z-index: 100;
            align-items: center;
            justify-content: center;
        }
        .modal-content {
            background-color: white;
            padding: 25px;
            border-radius: 10px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
            position: relative;
        }
        .modal-title {
            margin-top: 0;
            color: #2c3e50;
            border-bottom: 1px solid #eee;
            padding-bottom: 15px;
        }
        .close-button {
            position: absolute;
            top: 15px;
            right: 20px;
            font-size: 1.5rem;
            color: #95a5a6;
            cursor: pointer;
            transition: color 0.2s;
        }
        .close-button:hover {
            color: #7f8c8d;
        }
        textarea.notes-input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            min-height: 120px;
            margin: 15px 0;
            font-family: 'Roboto', sans-serif;
            font-size: 0.95rem;
            resize: vertical;
        }
        .modal-buttons {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 20px;
        }
        .save-notes-button {
            background-color: #27ae60;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 500;
        }
        .save-notes-button:hover {
            background-color: #2ecc71;
        }
        .cancel-notes-button {
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 500;
        }
        .cancel-notes-button:hover {
            background-color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="header-container">
        <h1>RustDesk Clients</h1>
    </div>
    <div class="add-button-container">
        <a id="copyconfig" href="#" onclick="copyconfig();" class="add-button">Copy Server Config for Importing</a>
    </div>
    <div class="add-button-container">
        <a href="/add" class="add-button">+ Add Client</a>
    </div>

    {% if clients %}
    <div class="client-list">
        {% for client in clients %}
        <div class="client-card">
            {% if client.manually_added %}
            <span class="manually-added">Manually Added</span>
            {% endif %}

            <div class="monitor">
                <div class="power-button"></div>
                <div class="power-light"></div>

                <div class="screen">
                    <div class="client-header">{{ client.hostname }}</div>

                    <div class="client-id-display">{{ client.client_id }}</div>

                    <div class="client-details">
                        <div><i class="os-icon">🖥️</i> {% if client.os %}{{ client.os }}{% else %}Unknown OS{% endif %}</div>
                        <div><i class="os-icon">🌐</i> {{ client.ip_address }}</div>
                    {% if client.notes %}
                    <div class="notes"><i class="os-icon">📝</i> {{ client.notes }}</div>
                    {% endif %}
                    </div>

                    <div class="action-buttons">
                        <a href="{{ client.connection_string }}" class="connect-button">Connect</a>
                        <button class="edit-button" onclick="openNotesModal('{{ client.client_id }}', '{{ client.notes|default('') }}')">Edit Notes</button>
                        <form class="delete-form" action="/delete/{{ client.client_id }}" method="post" onsubmit="return confirm('Are you sure you want to remove this client?');">
                            <button type="submit" class="delete-button">Delete</button>
                        </form>
                    </div>
                </div>

                <div class="monitor-ports">
                    <div class="port"></div>
                    <div class="port"></div>
                    <div class="port"></div>
                </div>
            </div>
            <br>
            <div class="timestamp">
                Added: {{ client.registered_at.split('T')[0] }}
                <br>Last seen: {{ client.last_seen.split('T')[0] }}
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="no-clients">
        <p>No clients registered yet. Click "Add Client" to add your first client.</p>
    </div>
    {% endif %}

    <!-- Notes Modal -->
    <div id="notesModal" class="modal">
        <div class="modal-content">
            <h3 class="modal-title">Edit Client Notes</h3>
            <span class="close-button" onclick="closeNotesModal()">&times;</span>

            <form id="notesForm" action="/update-notes" method="post">
                <input type="hidden" id="clientIdInput" name="client_id">
                <textarea class="notes-input" id="clientNotesInput" name="notes" placeholder="Enter notes about this client..."></textarea>

                <div class="modal-buttons">
                    <button type="button" class="cancel-notes-button" onclick="closeNotesModal()">Cancel</button>
                    <button type="submit" class="save-notes-button">Save Notes</button>
                </div>
            </form>
        </div>
    </div>

    <script>
function copyconfig() {
const textArea = document.createElement("textarea");
        textArea.value = "{{ pasteconfig }}";
            
        // Move textarea out of the viewport so it's not visible
        textArea.style.position = "absolute";
        textArea.style.left = "-999999px";
            
        document.body.prepend(textArea);
        textArea.select();

        try {
            document.execCommand('copy');
        } catch (error) {
            console.error(error);
        } finally {
            textArea.remove();
        }

}
        // Modal functionality
        var modal = document.getElementById("notesModal");
        var clientIdInput = document.getElementById("clientIdInput");
        var clientNotesInput = document.getElementById("clientNotesInput");

        function openNotesModal(clientId, notes) {
            clientIdInput.value = clientId;
            clientNotesInput.value = notes;
            modal.style.display = "flex";
        }

        function closeNotesModal() {
            modal.style.display = "none";
        }

        // Close the modal if the user clicks outside of it
        window.onclick = function(event) {
            if (event.target == modal) {
                closeNotesModal();
            }
        }
    </script>
</body>
</html>""")
    
    add_template_path = os.path.join(TEMPLATE_DIR, 'add_client.html')
    if not os.path.exists(add_template_path):
        with open(add_template_path, 'w') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Add RustDesk Client</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap">
    <style>
        body {
            font-family: 'Roboto', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f2f5;
            color: #333;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            max-width: 600px;
            width: 100%;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2rem;
        }
        .form-group {
            margin-bottom: 25px;
            position: relative;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #2c3e50;
        }
        input[type="text"],
        textarea {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            box-sizing: border-box;
            font-family: 'Roboto', sans-serif;
            font-size: 1rem;
            transition: border-color 0.3s, box-shadow 0.3s;
        }
        input[type="text"]:focus,
        textarea:focus {
            border-color: #3498db;
            outline: none;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.2);
        }
        textarea {
            height: 120px;
            resize: vertical;
        }
        .button-group {
            margin-top: 30px;
            display: flex;
            justify-content: center;
            gap: 15px;
        }
        .submit-button {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 50px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.3s ease;
            min-width: 140px;
            box-shadow: 0 4px 6px rgba(52, 152, 219, 0.3);
        }
        .submit-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(52, 152, 219, 0.4);
        }
        .cancel-button {
            background: linear-gradient(135deg, #95a5a6, #7f8c8d);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 50px;
            cursor: pointer;
            min-width: 140px;
            text-decoration: none;
            text-align: center;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(127, 140, 141, 0.3);
            display: inline-block;
        }
        .cancel-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(127, 140, 141, 0.4);
        }
        .error-message {
            background-color: #fceaea;
            border-left: 4px solid #e74c3c;
            color: #c0392b;
            padding: 12px 15px;
            margin-bottom: 25px;
            border-radius: 4px;
        }
        .required {
            color: #e74c3c;
            margin-left: 3px;
        }
        .monitor-icon {
            text-align: center;
            margin-bottom: 20px;
            font-size: 60px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="monitor-icon">🖥️</div>
        <h1>Add RustDesk Client</h1>

        {% if error %}
        <div class="error-message">{{ error }}</div>
        {% endif %}

        <form method="post">
            <div class="form-group">
                <label for="client_id">Client ID <span class="required">*</span></label>
                <input type="text" id="client_id" name="client_id" required placeholder="Enter RustDesk client ID">
            </div>

            <div class="form-group">
                <label for="hostname">Hostname <span class="required">*</span></label>
                <input type="text" id="hostname" name="hostname" required placeholder="Computer name">
            </div>

            <div class="form-group">
                <label for="ip_address">IP Address</label>
                <input type="text" id="ip_address" name="ip_address" placeholder="Optional: 192.168.1.100">
            </div>

            <div class="form-group">
                <label for="os">Operating System</label>
                <input type="text" id="os" name="os" placeholder="Optional: Windows 11, Ubuntu 22.04, etc.">
            </div>

            <div class="form-group">
                <label for="connection_string">Connection String</label>
                <input type="text" id="connection_string" name="connection_string" placeholder="Optional: rustdesk://new/connection/clientid?password=password">
</div>
            <div class="form-group">
                <label for="notes">Notes</label>
                <textarea id="notes" name="notes" placeholder="Add any additional information about this client"></textarea>
            </div>

            <div class="button-group">
                <button type="submit" class="submit-button">Add Client</button>
                <a href="/" class="cancel-button">Cancel</a>
            </div>
        </form>
    </div>
</body>
</html>""")
    
    app.logger.info("Starting RustDesk Client Management Server")
    app.run(host='0.0.0.0', port=httpportchangeme)
