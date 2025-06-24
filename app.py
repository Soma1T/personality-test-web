from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import random
import json
import base64

app = Flask(__name__)

# Загрузка и подготовка данных
df_raw = pd.read_csv('polls_with_text.csv')
df = df_raw[df_raw["message_text"] == "Социологический опрос"].copy()

def prepare_data(df):
    df = df.drop_duplicates(['poll_id', 'user_id'], keep='last')
    question_stats = df.groupby('poll_id')['answer'].agg(['nunique', 'count'])
    single_answer_questions = question_stats[question_stats['nunique'] == 1].index
    df = df[~df['poll_id'].isin(single_answer_questions)]
    all_combinations = pd.MultiIndex.from_product(
        [df['poll_id'].unique(), df['user_id'].unique()],
        names=['poll_id', 'user_id']
    )
    df_full = df.set_index(['poll_id', 'user_id']).reindex(all_combinations).reset_index()
    df_full['answer'] = df_full['answer'].fillna('затрудняюсь ответить')
    user_map = df.drop_duplicates('user_id').set_index('user_id')['user_name']
    question_map = df.drop_duplicates('poll_id').set_index('poll_id')['question']
    df_full['user_name'] = df_full['user_id'].map(user_map)
    df_full['question'] = df_full['poll_id'].map(question_map)
    return df_full

df_prepared = prepare_data(df)
question_order = list(df_prepared['poll_id'].unique())
total_questions = len(question_order)

def encode_answers(answers_dict):
    # Сериализуем словарь ответов в строку (для передачи в форме)
    json_str = json.dumps(answers_dict)
    b64 = base64.urlsafe_b64encode(json_str.encode()).decode()
    return b64

def decode_answers(encoded_str):
    try:
        json_str = base64.urlsafe_b64decode(encoded_str.encode()).decode()
        return json.loads(json_str)
    except Exception:
        return {}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Получаем ответы и индекс из формы
        encoded_answers = request.form.get('answers', '')
        answers = decode_answers(encoded_answers)
        q_idx = int(request.form.get('q_idx', 0))
        selected_answer = request.form.get('answer')
        if selected_answer is not None:
            current_poll_id = question_order[q_idx]
            answers[str(current_poll_id)] = selected_answer
            q_idx += 1
    else:
        # Начинаем с чистого листа при GET
        answers = {}
        q_idx = 0

    if q_idx >= total_questions:
        # Переходим на результат, передав ответы в query string
        encoded = encode_answers(answers)
        return redirect(url_for('result', answers=encoded))

    current_poll_id = question_order[q_idx]
    group = df_prepared[df_prepared['poll_id'] == current_poll_id]
    question = group['question'].iloc[0]
    answers_list = group['answer'].unique().tolist()

    regular = [a for a in answers_list if a != 'затрудняюсь ответить']
    has_difficult = len(regular) != len(answers_list)
    sorted_answers = sorted(regular) + (['затрудняюсь ответить'] if has_difficult else [])

    encoded = encode_answers(answers)
    return render_template(
        'question.html',
        question=question,
        answers=sorted_answers,
        question_num=q_idx + 1,
        total=total_questions,
        q_idx=q_idx,
        answers_encoded=encoded
    )

@app.route('/result')
def result():
    encoded_answers = request.args.get('answers', '')
    user_answers = decode_answers(encoded_answers)

    pivot_df = df_prepared.pivot_table(
        index='user_id',
        columns='poll_id',
        values='answer',
        aggfunc='first'
    ).fillna('затрудняюсь ответить')

    max_matches = -1
    best_match = None

    for user_id, row in pivot_df.iterrows():
        matches = sum(
            1 for q_id, ans in user_answers.items()
            if str(q_id) in row.index and row[int(q_id)] == ans
        )
        if matches > max_matches:
            max_matches = matches
            best_match = user_id

    if best_match is None:
        match_name = "Не найдено совпадений"
        percent = 0
        max_matches = 0
    else:
        match_name = df_prepared[df_prepared['user_id'] == best_match]['user_name'].iloc[0]
        percent = (max_matches / total_questions) * 100

    return render_template(
        'result.html',
        name=match_name,
        matches=max_matches,
        total=total_questions,
        percent=percent
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)