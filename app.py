import os
import re
import tempfile
from flask import Flask, render_template, request, send_file, session
import pdfplumber
import pandas as pd
from werkzeug.utils import secure_filename
from flask import Response



app = Flask(__name__, static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

@app.after_request
def add_cache_control(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/', methods=['GET', 'POST'])
def index():

    keyword = request.form.get('keyword', '')

    if 'results' not in session:
        session['results'] = []

    if request.method == 'POST':
        pdf_file = request.files['pdf_file']
        keyword = request.form['keyword']
        search_rule = request.form.get('search_rule', 'Case and Symbols Sensitive')
        session['search_rule'] = search_rule

        if pdf_file:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf_file.save(temp_file.name)
            session['pdf_path'] = temp_file.name

        results = search_pdf(keyword, session.get('pdf_path', ''), search_rule)
        generate_excel(results, os.path.dirname(session.get('pdf_path', '')), keyword)

        session['status_message'] = ' Capture Success!'

        if pdf_file:
            os.close(temp_file.fileno())
            os.remove(temp_file.name)

        session['results'] = results
    
    session['keyword'] = keyword

    return render_template('index.html', results=session.get('results', []), pdf_path=session.get('pdf_path', ''), search_rule=session.get('search_rule', 'Case and Symbols Sensitive'))


def search_pdf(keyword, pdf_path, search_rule):
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            original_text = page.extract_text()

            if search_rule == "Case and Symbols Sensitive":
                search_text = original_text
                search_keyword = keyword
            elif search_rule == "Case Sensitive":
                search_text, indices = remove_symbols_with_indices(original_text)
                search_keyword = re.sub(r'[^\w\s]', '', keyword)
            else:  # Insensitive
                search_text, indices = remove_symbols_with_indices(original_text.lower())
                search_keyword = re.sub(r'[^\w\s]', '', keyword).lower()

            if search_keyword in search_text:
                footer_left, footer_right = get_footers(original_text)

                for match in re.finditer(re.escape(search_keyword), search_text):
                    start, end = match.span()
                    if search_rule != "Case and Symbols Sensitive":
                        start, end = indices[start], indices[end-1]+1
                    line_parts = original_text[:end].split('\n')[-1], original_text[end:].split('\n')[0]
                    line = ' '.join(line_parts)

                    type_part = line_parts[0][:start].split('.')[-1].strip()
                    if type_part and type_part[-1] == ':':
                        type_part = type_part[:-1]

                    results.append([i+1, footer_left, footer_right, type_part, line])

    return results

def remove_symbols_with_indices(text):
    search_text = []
    indices = []
    for i, c in enumerate(text):
        if c.isalnum() or c.isspace():
            search_text.append(c)
            indices.append(i)
    return ''.join(search_text), indices


def get_footers(page_text):
    footer_pattern = r'([A-Z\d\s]+)\s+(\d{6}\.?\d{0,2}-\d)[\s\S]*?\n'

    footer_match = re.search(footer_pattern, page_text)

    left_footer = footer_match.group(1) if footer_match else None
    right_footer = footer_match.group(2) if footer_match else None

    if left_footer:
        left_footer = left_footer.strip().split('\n')[0]

    return left_footer, right_footer


def generate_excel(results, pdf_path, keyword):
    df = pd.DataFrame(results, columns=["PAGE", "SPECIFICATION SECTION NAME", "SPECIFICATION SECTION NUMBER", "TYPE", "REFERENCE LINE"])

    output_directory = os.path.dirname(session.get('pdf_path', ''))
    output_filename = os.path.join(pdf_path, f"List of {session.get('keyword', '')}.xlsx")
  
    i = 1
    while os.path.exists(output_filename):
        output_filename = os.path.join(pdf_path, f"List of {keyword}({i}).xlsx")
        i += 1
    
    session['excel_file'] = output_filename

    df.to_excel(output_filename, index=False)


@app.route('/export', methods=['GET'])
def export_excel():
    keyword = session.get('keyword', '')
    output_filename = f"List of {session.get('keyword', '')}.xlsx"


    excel_file_path = session.get('excel_file', '')
    with open(excel_file_path, 'rb') as file:
        response = Response(
            file.read(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers['Content-Disposition'] = f'attachment; filename="{output_filename}"'

    return response

if __name__ == '__main__':
    app.secret_key = 'PDFWordHunterT1'  
    app.run(debug=True)
