from flask import Flask, render_template, request, redirect, session
import pandas as pd
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Замени на свой безопасный ключ

# Загрузка и подготовка данных
df_raw = pd.read_csv('polls_with_text.csv')
df = df_raw[df_raw["message_text"] == "Социологический опрос"].copy()

# Подготовка данных
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

# Список вопросов в случайном порядке
question_order = list(df_prepared['poll_id'].unique())
random.shuffle(question_order)
total_questions = len(question_order)

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'answers' not in session:
        session['answers'] = {}
        session['q_idx'] = 0

    if request.method == 'POST':
        selected_answer = request.form.get('answer')
        if selected_answer is not None:
            current_q = question_order[session['q_idx']]
            session['answers'][str(current_q)] = selected_answer
            session['q_idx'] += 1

    if session['q_idx'] >= total_questions:
        return redirect('/result')

    current_poll_id = question_order[session['q_idx']]
    group = df_prepared[df_prepared['poll_id'] == current_poll_id]
    question = group['question'].iloc[0]
    answers = group['answer'].unique().tolist()

    # Сортируем: сначала обычные ответы, потом "затрудняюсь ответить"
    regular = [a for a in answers if a != 'затрудняюсь ответить']
    has_difficult = len(regular) != len(answers)
    sorted_answers = sorted(regular) + (['затрудняюсь ответить'] if has_difficult else [])

    return render_template(
        'question.html',
        question=question,
        answers=sorted_answers,
        question_num=session['q_idx'] + 1,
        total=total_questions
    )

@app.route('/result')
def result():
    user_answers = session.get('answers', {})

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

    match_name = df_prepared[df_prepared['user_id'] == best_match]['user_name'].iloc[0]
    percent = (max_matches / total_questions) * 100

    return render_template(
        'result.html',
        name=match_name,
        matches=max_matches,
        total=total_questions,
        percent=percent
    )

@app.route('/reset')
def reset():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
