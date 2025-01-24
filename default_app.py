#!/usr/keio/Anaconda3-2023.09-0/bin/python
"""
データベースを使った Web アプリケーションのサンプル.

細田 真道
"""

import sqlite3
from typing import Final, Optional, Union
import unicodedata

from flask import Flask, g, redirect, render_template, request, url_for
from werkzeug import Response

# データベースのファイル名
DATABASE: Final[str] = 'database.db'

# Flask クラスのインスタンス
app = Flask(__name__)

# 処理結果コードとメッセージ
RESULT_MESSAGES: Final[dict[str, str]] = {
    'id-has-invalid-charactor':
    '指定された社員番号には使えない文字があります - '
    '数字のみで指定してください',
    'id-already-exists':
    '指定された社員番号は既に存在します - '
    '存在しない社員番号を指定してください',
    'id-does-not-exist':
    '指定された社員番号は存在しません',
    'id-is-manager':
    '指定された社員番号の社員には部下がいます - '
    '部下に登録された上司を変更してから削除してください',
    'manager-id-has-invalid-charactor':
    '指定された上司の社員番号には使えない文字があります - '
    '数字のみで指定してください',
    'manager-id-does-not-exist':
    '指定された上司の社員番号が存在しません - '
    '既に存在する社員番号か追加する社員の社員番号と同じものを指定してください',
    'salary-has-invalid-charactor':
    '指定された給与には使えない文字があります - '
    '数字のみで指定してください',
    'birth-year-has-invalid-charactor':
    '指定された生年には使えない文字があります - '
    '数字のみで指定してください',
    'start-year-has-invalid-charactor':
    '指定された入社年には使えない文字があります - '
    '数字のみで指定してください',
    'name-has-control-charactor':
    '指定された名前には制御文字があります - '
    '制御文字は指定しないでください',
    'database-error':
    'データベースエラー',
    'added':
    '社員を追加しました',
    'deleted':
    '削除しました',
    'updated':
    '更新しました'
}


def get_db() -> sqlite3.Connection:
    """
    データベース接続を得る.

    リクエスト処理中にデータベース接続が必要になったら呼ぶ関数。

    Flask の g にデータベース接続が保存されていたらその接続を返す。
    そうでなければデータベース接続して g に保存しつつ接続を返す。
    その際に、カラム名でフィールドにアクセスできるように設定変更する。

    https://flask.palletsprojects.com/en/3.0.x/patterns/sqlite3/
    のサンプルにある関数を流用し設定変更を追加。

    Returns:
      sqlite3.connect: データベース接続
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.execute('PRAGMA foreign_keys = ON')  # 外部キー制約を有効化
        db.row_factory = sqlite3.Row  # カラム名でアクセスできるよう設定変更
    return db


@app.teardown_appcontext
def close_connection(exception: Optional[BaseException]) -> None:
    """
    データベース接続を閉じる.

    リクエスト処理の終了時に Flask が自動的に呼ぶ関数。

    Flask の g にデータベース接続が保存されていたら閉じる。

    https://flask.palletsprojects.com/en/3.0.x/patterns/sqlite3/
    のサンプルにある関数をそのまま流用。

    Args:
      exception (Optional[BaseException]): 未処理の例外
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def has_control_character(s: str) -> bool:
    """
    文字列に制御文字が含まれているか否か判定する.

    Args:
      s (str): 判定対象文字列
    Returns:
      bool: 含まれていれば True 含まれていなければ False
    """
    return any(map(lambda c: unicodedata.category(c) == 'Cc', s))


@app.route('/')
def index() -> str:
    """
    入口のページ.

    `http://localhost:5000/` へのリクエストがあった時に Flask が呼ぶ関数。

    テンプレート index.html
    （本アプリケーションの説明や他ページへのリンクがある）
    をレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    # テンプレートへ何も渡さずにレンダリングしたものを返す
    return render_template('index.html')


@app.route('/employees')
def employees() -> str:
    """
    社員一覧のページ（全員）.

    `http://localhost:5000/employees` への GET メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。

    データベース接続を得て、SELECT 文で全社員一覧を取得し、
    テンプレート employees.html へ一覧を渡して埋め込んでレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    # データベース接続してカーソルを得る
    cur = get_db().cursor()

    # employees テーブルの全行から社員番号と氏名を取り出した一覧を取得
    e_list = cur.execute('SELECT id, name FROM employees').fetchall()

    # 一覧をテンプレートへ渡してレンダリングしたものを返す
    return render_template('employees.html', e_list=e_list)


@app.route('/employees', methods=['POST'])
def employees_filtered() -> str:
    """
    社員一覧のページ（絞り込み）.

    `http://localhost:5000/employees` への POST メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。
    絞り込み用の氏名が POST のパラメータ `name_filter` に入っている。

    データベース接続を得て、
    SELECT 文でリクエストされた氏名で絞り込んだ社員一覧を取得、
    テンプレート employees.html へ一覧を渡して埋め込んでレンダリングして返す。
    （これは PRG パターンではない）

    Returns:
      str: ページのコンテンツ
    """
    # データベース接続してカーソルを得る
    con = get_db()
    cur = con.cursor()

    # employees テーブルから氏名で絞り込み、
    # 得られた全行から社員番号と氏名を取り出した一覧を取得
    e_list = cur.execute('SELECT id, name FROM employees WHERE name LIKE ?',
                         (request.form['name_filter'], )).fetchall()

    # 一覧をテンプレートへ渡してレンダリングしたものを返す
    return render_template('employees.html', e_list=e_list)


@app.route('/employee/<id>')
def employee(id: str) -> str:
    """
    社員詳細ページ.

    `http://localhost:5000/employee/<id>` への GET メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。

    データベース接続を得て、
    URL 中の `<id>` で指定された社員番号の社員の全情報を取得し、
    テンプレート employee.html へ情報を渡して埋め込んでレンダリングして返す。
    指定された社員が見つからない場合は
    テンプレート employee-not-found.html
    （社員が見つからない旨が記載されている）
    をレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    # データベース接続してカーソルを得る
    con = get_db()
    cur = con.cursor()

    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        id_num = int(id)
    except ValueError:
        # 社員番号が整数型へ変換できない→不正な社員番号が指定された
        # →データベースにあたるまでもなくそのような社員は見つからない
        return render_template('employee-not-found.html')

    # employees テーブルから指定された社員番号の行を 1 行だけ取り出す
    employee = cur.execute('SELECT * FROM employees WHERE id = ?',
                           (id_num,)).fetchone()

    if employee is None:
        # 指定された社員番号の行が無かった
        return render_template('employee-not-found.html')

    # 社員の情報をテンプレートへ渡してレンダリングしたものを返す
    return render_template('employee.html', employee=employee)


@app.route('/employee-add')
def employee_add() -> str:
    """
    社員追加ページ.

    `http://localhost:5000/employee-add` への GET メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。

    テンプレート employee-add.html
    （社員追加フォームがあり、追加ボタンで社員追加実行の POST ができる）
    をレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    # テンプレートへ何も渡さずにレンダリングしたものを返す
    return render_template('employee-add.html')


@app.route('/employee-add', methods=['POST'])
def employee_add_execute() -> Response:
    """
    社員追加実行.

    `http://localhost:5000/employee-add` への POST メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。
    追加する社員の情報が POST パラメータの
    `id`, `name`, `salary`, `manager_id`, `birth_year`, `start_year`
    に入っている。

    データベース接続を得て、POST パラメータの各内容をチェック、
    問題なければ新しい社員として追加し、
    employee_add_results へ処理結果コードを入れてリダイレクトする。
    （PRG パターンの P を受けて R を返す）

    Returns:
      Response: リダイレクト情報
    """
    # データベース接続してカーソルを得る
    con = get_db()
    cur = con.cursor()

    # リクエストされた POST パラメータの内容を取り出す
    id_str = request.form['id']
    name = request.form['name']
    salary_str = request.form['salary']
    manager_id_str = request.form['manager_id']
    birth_year_str = request.form['birth_year']
    start_year_str = request.form['start_year']

    #
    # 社員番号チェック
    #
    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        id = int(id_str)
    except ValueError:
        # 社員番号が整数型へ変換できない
        return redirect(url_for('employee_add_results',
                                code='id-has-invalid-charactor'))
    # 社員番号の存在チェックをする：
    # employees テーブルで同じ社員番号の行を 1 行だけ取り出す
    employee = cur.execute('SELECT id FROM employees WHERE id = ?',
                           (id,)).fetchone()
    if employee is not None:
        # 指定された社員番号の行が既に存在
        return redirect(url_for('employee_add_results',
                                code='id-already-exists'))

    #
    # 上司の社員番号チェック
    #
    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        manager_id = int(manager_id_str)
    except ValueError:
        # 社員番号が整数型へ変換できない
        return redirect(url_for('employee_add_results',
                                code='manager-id-has-invalid-charactor'))
    if id != manager_id:
        # 指定された社員番号と上司の社員番号が不一致
        # →上司が別に存在する必要がある→上司の存在チェックをする：
        # employees テーブルで指定された上司の社員番号を持つ社員
        # の行を 1 行だけ取り出す
        manager = cur.execute('SELECT id FROM employees WHERE id = ?',
                              (manager_id,)).fetchone()
        if manager is None:
            # 指定された上司が存在しない
            return redirect(url_for('employee_add_results',
                                    code='manager-id-does-not-exist'))

    #
    # 給与チェック
    #
    try:
        # 文字列型で渡された給与を整数型へ変換する
        salary = int(salary_str)
    except ValueError:
        # 給与が整数型へ変換できない
        return redirect(url_for('employee_add_results',
                                code='salary-has-invalid-charactor'))

    #
    # 生年チェック
    #
    try:
        # 文字列型で渡された生年を整数型へ変換する
        birth_year = int(birth_year_str)
    except ValueError:
        # 生年が整数型へ変換できない
        return redirect(url_for('employee_add_results',
                                code='birth-year-has-invalid-charactor'))

    #
    # 入社年チェック
    #
    try:
        # 文字列型で渡された入社年を整数型へ変換する
        start_year = int(start_year_str)
    except ValueError:
        # 入社年が整数型へ変換できない
        return redirect(url_for('employee_add_results',
                                code='start-year-has-invalid-charactor'))

    #
    # 名前チェック
    #
    if has_control_character(name):
        # 名前に制御文字が含まれる
        return redirect(url_for('employee_add_results',
                                code='name-has-control-charactor'))

    # データベースへ社員を追加
    try:
        # employees テーブルに指定されたパラメータの行を挿入
        cur.execute('INSERT INTO employees '
                    '(id, name, salary, manager_id, birth_year, start_year) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    (id, name, salary, manager_id, birth_year, start_year))
    except sqlite3.Error:
        # データベースエラーが発生
        return redirect(url_for('employee_add_results',
                                code='database-error'))
    # コミット（データベース更新処理を確定）
    con.commit()

    # 社員追加完了
    return redirect(url_for('employee_add_results',
                            code='added'))


@app.route('/employee-add-results/<code>')
def employee_add_results(code: str) -> str:
    """
    社員追加結果ページ.

    `http://localhost:5000/employee-add-result/<code>`
    への GET メソッドによるリクエストがあった時に Flask が呼ぶ関数。

    PRG パターンで社員追加実行の POST 後にリダイレクトされてくる。
    テンプレート employee-add-results.html
    へ処理結果コード code に基づいたメッセージを渡してレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    return render_template('employee-add-results.html',
                           results=RESULT_MESSAGES.get(code, 'code error'))


@app.route('/employee-del/<id>')
def employee_del(id: str) -> str:
    """
    社員削除確認ページ.

    `http://localhost:5000/employee-del/<id>` への GET メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。

    データベース接続を得て URL 中の `<id>` で指定された社員情報を取得し、
    削除できるなら
    テンプレート employee-del.html
    （社員削除してよいかの確認ページ）
    へ社員番号を渡してレンダリングして返す。
    削除できないなら
    テンプレート employee-del-results.html
    へ理由を渡してレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    # データベース接続してカーソルを得る
    con = get_db()
    cur = con.cursor()

    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        id_num = int(id)
    except ValueError:
        # 社員番号が整数型へ変換できない
        return render_template('employee-del-results.html',
                               results='指定された社員番号には'
                               '使えない文字があります')
    # 社員番号の存在チェックをする：
    # employees テーブルで同じ社員番号の行を 1 行だけ取り出す
    employee = cur.execute('SELECT id FROM employees WHERE id = ?',
                           (id_num,)).fetchone()
    if employee is None:
        # 指定された社員番号の行が無い
        return render_template('employee-del-results.html',
                               results='指定された社員番号は存在しません')

    # 部下の存在チェック：
    # employees テーブルで指定された社員番号を上司にしている社員、かつ、
    # 自分自身ではない、行を 1 行だけ取り出す
    member = cur.execute('SELECT id FROM employees '
                         'WHERE manager_id = ? AND id != ?',
                         (id_num, id_num)).fetchone()
    if member is not None:
        # 部下が存在する
        return render_template('employee-del-results.html',
                               results='指定された社員番号の社員には'
                               '部下がいます - '
                               '部下に登録された上司を変更してから'
                               '削除してください')

    # 削除対象の社員番号をテンプレートに渡してレンダリングしたものを返す
    return render_template('employee-del.html', id=id_num)


@app.route('/employee-del/<id>', methods=['POST'])
def employee_del_execute(id: str) -> Response:
    """
    社員削除実行.

    `http://localhost:5000/employee-del/<id>` への POST メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。
    POST パラメータは無し。

    データベース接続を得て URL 中の `<id>` で指定された社員情報を取得し、
    削除できるならして、
    employee_del_results へ処理結果コードを入れてリダイレクトする。
    （PRG パターンの P を受けて R を返す）

    Returns:
      Response: リダイレクト情報
    """
    # データベース接続してカーソルを得る
    con = get_db()
    cur = con.cursor()

    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        id_num = int(id)
    except ValueError:
        # 社員番号が整数型へ変換できない
        return redirect(url_for('employee_del_results',
                                code='id-has-invalid-charactor'))
    # 社員番号の存在チェックをする：
    # employees テーブルで同じ社員番号の行を 1 行だけ取り出す
    employee = cur.execute('SELECT id FROM employees WHERE id = ?',
                           (id_num,)).fetchone()
    if employee is None:
        # 指定された社員番号の行が無い
        return redirect(url_for('employee_del_results',
                                code='id-does-not-exsit'))

    # 部下の存在チェック：
    # employees テーブルで指定された社員番号を上司にしている社員、かつ、
    # 自分自身ではない、行を 1 行だけ取り出す
    member = cur.execute('SELECT id FROM employees '
                         'WHERE manager_id = ? AND id != ?',
                         (id_num, id_num)).fetchone()
    if member is not None:
        # 部下が存在する
        return redirect(url_for('employee_del_results',
                                code='id-is-manager'))

    # データベースから削除
    try:
        # employees テーブルの指定された行を削除
        cur.execute('DELETE FROM employees WHERE id = ?', (id_num,))
    except sqlite3.Error:
        # データベースエラーが発生
        return redirect(url_for('employee_add_results',
                                code='database-error'))
    # コミット（データベース更新処理を確定）
    con.commit()

    # 社員追加完了
    return redirect(url_for('employee_add_results',
                            code='deleted'))


@app.route('/employee-del-results/<code>')
def employee_del_results(code: str) -> str:
    """
    社員削除結果ページ.

    `http://localhost:5000/employee-del-result/<code>`
    への GET メソッドによるリクエストがあった時に Flask が呼ぶ関数。

    PRG パターンで社員削除実行の POST 後にリダイレクトされてくる。
    テンプレート employee-del-results.html
    へ処理結果コード code に基づいたメッセージを渡してレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    return render_template('employee-del-results.html',
                           results=RESULT_MESSAGES.get(code, 'code error'))


@app.route('/employee-edit/<id>')
def employee_edit(id: str) -> str:
    """
    社員編集ページ.

    `http://localhost:5000/employee-edit/<id>` への GET メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。

    データベース接続を得て URL 中の `<id>` で指定された社員情報を取得し、
    編集できるなら
    テンプレート employee-edit.html
    （社員編集フォームがあり、決定ボタンで社員編集更新の POST ができる）
    へ情報を渡してレンダリングして返す。
    編集できないなら
    テンプレート employee-edit-results.html
    へ理由を渡してレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    # データベース接続してカーソルを得る
    con = get_db()
    cur = con.cursor()

    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        id_num = int(id)
    except ValueError:
        # 社員番号が整数型へ変換できない
        return render_template('employee-edit-results.html',
                               results='指定された社員番号には'
                               '使えない文字があります')
    # 社員の存在チェックと編集対象となる社員情報の取得：
    # employees テーブルで同じ社員番号の行を 1 行だけ取り出す
    employee = cur.execute('SELECT * FROM employees WHERE id = ?',
                           (id_num,)).fetchone()
    if employee is None:
        # 指定された社員番号の行が無い
        return render_template('employee-edit-results.html',
                               results='指定された社員番号は存在しません')

    # 編集対象の社員情報をテンプレートへ渡してレンダリングしたものを返す
    return render_template('employee-edit.html', employee=employee)


@app.route('/employee-edit/<id>', methods=['POST'])
def employee_edit_update(id: str) -> Response:
    """
    社員編集更新.

    `http://localhost:5000/employee-edit/<id>` への POST メソッドによる
    リクエストがあった時に Flask が呼ぶ関数。
    編集後の社員の情報が POST パラメータの
    `name`, `salary`, `manager_id`, `birth_year`, `start_year`
    に入っている（社員番号は編集できない）。

    データベース接続を得て URL 中の `<id>` で指定された社員情報を取得し、
    編集できるなら、POST パラメータの社員情報をチェック、
    問題なければ社員情報を更新し、
    テンプレート employee-edit-results.html
    employee_edit_results へ処理結果コードを入れてリダイレクトする。
    （PRG パターンの P を受けて R を返す）

    Returns:
      Response: リダイレクト情報
    """
    # データベース接続してカーソルを得る
    con = get_db()
    cur = con.cursor()

    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        id_num = int(id)
    except ValueError:
        # 社員番号が整数型へ変換できない
        return redirect(url_for('employee_edit_results',
                                code='id-has-invalid-charactor'))
    # 社員番号の存在チェックをする：
    # employees テーブルで同じ社員番号の行を 1 行だけ取り出す
    employee = cur.execute('SELECT id FROM employees WHERE id = ?',
                           (id_num,)).fetchone()
    if employee is None:
        # 指定された社員番号の行が無い
        return redirect(url_for('employee_edit_results',
                                code='id-does-not-exist'))

    # リクエストされた POST パラメータの内容を取り出す
    name = request.form['name']
    salary_str = request.form['salary']
    manager_id_str = request.form['manager_id']
    birth_year_str = request.form['birth_year']
    start_year_str = request.form['start_year']

    #
    # 上司の社員番号チェック
    #
    try:
        # 文字列型で渡された社員番号を整数型へ変換する
        manager_id = int(manager_id_str)
    except ValueError:
        # 社員番号が整数型へ変換できない
        return redirect(url_for('employee_edit_results',
                                code='manager-id-has-invalid-charactor'))
    if id_num != manager_id:
        # 指定された社員番号と上司の社員番号が不一致
        # →上司が別に存在する必要がある→上司の存在チェックをする：
        # employees テーブルで指定された上司の社員番号を持つ社員
        # の行を 1 行だけ取り出す
        manager = cur.execute('SELECT id FROM employees WHERE id = ?',
                              (manager_id,)).fetchone()
        if manager is None:
            # 指定された上司が存在しない
            return redirect(url_for('employee_edit_results',
                                    code='manager-id-does-not-exist'))

    #
    # 給与チェック
    #
    try:
        # 文字列型で渡された給与を整数型へ変換する
        salary = int(salary_str)
    except ValueError:
        # 給与が整数型へ変換できない
        return redirect(url_for('employee_edit_results',
                                code='salary-has-invalid-charactor'))

    #
    # 生年チェック
    #
    try:
        # 文字列型で渡された生年を整数型へ変換する
        birth_year = int(birth_year_str)
    except ValueError:
        # 生年が整数型へ変換できない
        return redirect(url_for('employee_edit_results',
                                code='birth-year-has-invalid-charactor'))

    #
    # 入社年チェック
    #
    try:
        # 文字列型で渡された入社年を整数型へ変換する
        start_year = int(start_year_str)
    except ValueError:
        # 入社年が整数型へ変換できない
        return redirect(url_for('employee_edit_results',
                                code='start-year-has-invalid-charactor'))

    #
    # 名前チェック
    #
    if has_control_character(name):
        # 名前に制御文字が含まれる
        return redirect(url_for('employee_edit_results',
                                code='name-has-control-charactor'))

    # データベースを更新
    try:
        # employees テーブルの指定された行のパラメータを更新
        cur.execute('UPDATE employees '
                    'SET name = ?, salary = ?, manager_id = ?, '
                    'birth_year = ?, start_year = ? '
                    'WHERE id = ?',
                    (name, salary, manager_id, birth_year, start_year, id_num))
    except sqlite3.Error:
        # データベースエラーが発生
        return redirect(url_for('employee_edit_results',
                                code='database-error'))
    # コミット（データベース更新処理を確定）
    con.commit()

    # 社員編集完了
    return redirect(url_for('employee_edit_results',
                            code='updated'))


@app.route('/employee-edit-results/<code>')
def employee_edit_results(code: str) -> str:
    """
    社員編集結果ページ.

    `http://localhost:5000/employee-edit-result/<code>`
    への GET メソッドによるリクエストがあった時に Flask が呼ぶ関数。

    PRG パターンで社員編集更新の POST 後にリダイレクトされてくる。
    テンプレート employee-edit-results.html
    へ処理結果コード code に基づいたメッセージを渡してレンダリングして返す。

    Returns:
      str: ページのコンテンツ
    """
    return render_template('employee-edit-results.html',
                           results=RESULT_MESSAGES.get(code, 'code error'))


if __name__ == '__main__':
    # このスクリプトを直接実行したらデバッグ用 Web サーバで起動する
    app.run(debug=True)
