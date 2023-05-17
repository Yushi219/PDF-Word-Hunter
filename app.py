import os
import re
import tempfile
from flask import Flask, render_template, request, send_file
import pdfplumber
import pandas as pd
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, send_file, session
from flask import Flask, make_response
from flask import Response


app = Flask(__name__, static_url_path='/static')

@app.after_request
def add_cache_control(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'results' not in session:
        session['results'] = []  # Initialize an empty results list

    if request.method == 'POST':
        pdf_file = request.files['pdf_file']
        keyword = request.form['keyword']

        if pdf_file:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf_file.save(temp_file.name)
            session['pdf_path'] = temp_file.name

        results = search_pdf(keyword, session.get('pdf_path', ''))
        generate_excel(results, os.path.dirname(session.get('pdf_path', '')), keyword)

        if pdf_file:
            os.close(temp_file.fileno())  # Explicitly close the file descriptor
            os.remove(temp_file.name)

        session['results'] = results
    
    session['keyword'] = keyword

    return render_template('index.html', results=session.get('results', []), pdf_path=session.get('pdf_path', ''))




def search_pdf(keyword, pdf_path):
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()

            if keyword in text:
                footer_left, footer_right = get_footers(text)

                for match in re.finditer(re.escape(keyword), text):
                    start, end = match.span()
                    line_parts = text[:end].split('\n')[-1], text[end:].split('\n')[0]
                    line = ' '.join(line_parts)

                    type_part = line_parts[0][:start].split('.')[-1].strip()
                    if type_part[-1] == ':':
                        type_part = type_part[:-1]

                    results.append([i+1, footer_left, footer_right, type_part, line])

    return results


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
