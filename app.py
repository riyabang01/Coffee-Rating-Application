import sqlite3
import uuid
from flask import Flask, render_template, jsonify, request, session

app = Flask(__name__)
app.secret_key = "coffee_secret_key_change_in_prod"
DB_NAME = "coffee.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_voter_id():
    if 'voter_id' not in session:
        session['voter_id'] = str(uuid.uuid4())
    return session['voter_id']

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS coffees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roast TEXT NOT NULL,
            votes INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coffee_id INTEGER NOT NULL,
            voter_id TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            UNIQUE(coffee_id, voter_id)
        )
    ''')
    
    count = conn.execute('SELECT COUNT(*) FROM coffees').fetchone()
    if count == 0:
        starter_coffees = [
            ("Espresso", "Dark Roast", 12),
            ("Caramel Macchiato", "Medium Roast", 18),
            ("Cold Brew", "Medium-Dark Roast", 25),
            ("Pour Over (Ethiopian)", "Light Roast", 9),
            ("Flat White", "Medium Roast", 15)
        ]
        conn.executemany(
            'INSERT INTO coffees (name, roast, votes) VALUES (?, ?, ?)',
            starter_coffees
        )
    conn.commit()
    conn.close()

@app.route('/')
def index():
    voter_id = get_voter_id()
    conn = get_db_connection()
    coffees = conn.execute('SELECT * FROM coffees ORDER BY votes DESC').fetchall()
    rows = conn.execute('SELECT coffee_id FROM user_votes WHERE voter_id = ?', (voter_id,)).fetchall()
    conn.close()
    
    voted_ids = [row['coffee_id'] for row in rows]
    return render_template('index.html', coffees=coffees, voted_ids=voted_ids)

@app.route('/vote/<int:coffee_id>', methods=['POST'])
def vote(coffee_id):
    voter_id = get_voter_id()
    ip_address = request.remote_addr
    conn = get_db_connection()

    existing = conn.execute(
        'SELECT id FROM user_votes WHERE coffee_id = ? AND voter_id = ?',
        (coffee_id, voter_id)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({"error": "Already voted"}), 403

    conn.execute(
        'INSERT INTO user_votes (coffee_id, voter_id, ip_address) VALUES (?, ?, ?)',
        (coffee_id, voter_id, ip_address)
    )
    conn.execute('UPDATE coffees SET votes = votes + 1 WHERE id = ?', (coffee_id,))
    conn.commit()
    
    updated = conn.execute('SELECT votes FROM coffees WHERE id = ?', (coffee_id,)).fetchone()
    conn.close()

    return jsonify({"id": coffee_id, "votes": updated["votes"], "voted": True})

@app.route('/unvote/<int:coffee_id>', methods=['POST'])
def unvote(coffee_id):
    voter_id = get_voter_id()
    conn = get_db_connection()

    existing = conn.execute(
        'SELECT id FROM user_votes WHERE coffee_id = ? AND voter_id = ?',
        (coffee_id, voter_id)
    ).fetchone()

    if not existing:
        conn.close()
        return jsonify({"error": "Vote not found"}), 400

    conn.execute('DELETE FROM user_votes WHERE coffee_id = ? AND voter_id = ?', (coffee_id, voter_id))
    conn.execute('UPDATE coffees SET votes = MAX(0, votes - 1) WHERE id = ?', (coffee_id,))
    conn.commit()

    updated = conn.execute('SELECT votes FROM coffees WHERE id = ?', (coffee_id,)).fetchone()
    conn.close()

    return jsonify({"id": coffee_id, "votes": updated["votes"], "voted": False})

@app.route('/delete/<int:coffee_id>', methods=['DELETE'])
def delete_coffee(coffee_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM user_votes WHERE coffee_id = ?', (coffee_id,))
    conn.execute('DELETE FROM coffees WHERE id = ?', (coffee_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": coffee_id})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
