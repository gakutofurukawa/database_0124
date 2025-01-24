#基礎設定----------------------------------------------------------------------------------------------------------------------#
from flask import Flask, render_template, request, redirect, url_for, g
import sqlite3
import os
from datetime import datetime, timedelta
from flask import session


app = Flask(__name__)
DATABASE = 'database.db'
app.secret_key = os.urandom(24)  # ランダムなバイト列を生成
# データベース接続のヘルパー関数
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

# テーブル初期化（初回実行時のみ）
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                role TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY,
                title TEXT,
                date_time DATETIME,
                location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS available_dates (
                id INTEGER PRIMARY KEY,
                member_id INTEGER,
                available_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(member_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY,
                meeting_id INTEGER,
                member_id INTEGER,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id),
                FOREIGN KEY(member_id) REFERENCES users(id)
            );
        ''')
        db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
#ホーム----------------------------------------------------------------------------------------------------------------------#
@app.route('/')
def index():
    return render_template('index.html')
#ユーザー----------------------------------------------------------------------------------------------------------------------#
# ユーザー管理画面
@app.route('/users', methods=['GET', 'POST'])
def user_management():
    db = get_db()
    if request.method == 'POST':
        try:
            # フォームデータの取得
            name = request.form['name']
            email = request.form['email']
            role = request.form['role']

            # 新規登録処理
            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO users (name, email, role) VALUES (?, ?, ?)',
                (name, email, role)
            )
            db.commit()  # コミットを明示的に実行
            return redirect(url_for('user_management'))

        except sqlite3.IntegrityError:
            db.rollback()
            return "メールアドレスが既に登録されています"
        except Exception as e:
            db.rollback()
            return f"エラーが発生しました: {str(e)}"

    # ユーザー一覧取得
    cursor = db.execute('SELECT * FROM users')
    users = cursor.fetchall()
    return render_template('user_management.html', users=users)

# 空き日程登録フォーム
@app.route('/add_availability', methods=['GET', 'POST'])
def add_availability():
    if request.method == 'POST':
        member_id = request.form['member_id']
        selected_dates = request.form['selected_dates'].split(',')
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            for date_str in selected_dates:
                date_str = date_str.strip()
                # 日付のバリデーション
                datetime.strptime(date_str, '%Y-%m-%d')
                cursor.execute('''
                    INSERT OR IGNORE INTO available_dates 
                    (member_id, available_date)
                    VALUES (?, ?)
                ''', (member_id, date_str))
            
            db.commit()
            return redirect(url_for('index'))
            
        except ValueError:
            db.rollback()
            return f"無効な日付形式です{selected_dates}"
        except sqlite3.Error as e:
            db.rollback()
            return f"データベースエラー: {str(e)}"
    return render_template('add_availability.html')    
#会議系----------------------------------------------------------------------------------------------------------------------#
@app.route('/create_meeting', methods=['GET', 'POST'])
def create_meeting():
    db = get_db()
    
    if request.method == 'GET':
        # ユーザー一覧取得
        cursor = db.execute('SELECT * FROM users')
        users = cursor.fetchall()
        return render_template('create_meeting.html', users=users)
    
    elif request.method == 'POST':
        try:
            # フォームデータ取得
            title = request.form['title']
            location = request.form['location']
            member_ids = list(map(int, request.form.getlist('members')))
            
            # 会議基本情報を保存
            cursor = db.cursor()
            cursor.execute(
                '''INSERT INTO meetings 
                (title, location) 
                VALUES (?, ?)''',
                (title, location)
            )
            meeting_id = cursor.lastrowid
            
            # 共通空き日程を計算
            candidate_dates = calculate_candidate_dates(member_ids)
            
            # セッションに保存
            session['candidate_dates'] = candidate_dates
            session['current_meeting_id'] = meeting_id
            
            db.commit()
            return redirect(url_for('select_date'))
            
        except Exception as e:
            db.rollback()
            return f"エラーが発生しました: {str(e)}"


# 会議一覧表示
@app.route('/view_meetings')
def view_meetings():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM meetings')
    meetings = cursor.fetchall()
    return render_template('view_meetings.html', meetings=meetings)

@app.route('/select_date', methods=['GET', 'POST'])
def select_date():
    candidate_dates = session.get('candidate_dates', [])
    if request.method == 'GET':
        return render_template('select_date.html', candidate_dates=candidate_dates)
    elif request.method == 'POST':
        # 選択された日付を取得
        date_time = request.form['selected_date']
        meeting_id = session.get('current_meeting_id')

        # データベースに選択された日程を保存
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            '''UPDATE meetings SET date_time = ? WHERE id = ?''',
            (date_time, meeting_id)
        )
        db.commit()
        return redirect(url_for('index'))



# 処理関数系----------------------------------------------------------------------------------------------------------------------#
# 候補日程計算関数
def calculate_candidate_dates(member_ids):
    db = get_db()
    cursor = db.cursor()

    # メンバーごとの空き日程を取得
    query = '''
        SELECT member_id, available_date 
        FROM available_dates 
        WHERE member_id IN ({})
    '''.format(','.join(['?'] * len(member_ids)))

    cursor.execute(query, member_ids)
    rows = cursor.fetchall()

    # 空き日程をメンバーごとに整理
    availability = {}
    for row in rows:
        member_id, available_date = row
        if member_id not in availability:
            availability[member_id] = set()
        availability[member_id].add(available_date)

    # 共通の日付を計算
    common_dates = set.intersection(*availability.values()) if availability else set()

    return sorted(list(common_dates))  # ソートしてリストとして返す

#その他----------------------------------------------------------------------------------------------------------------------#
if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True)