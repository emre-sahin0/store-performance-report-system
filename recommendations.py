import json
import os
import pandas as pd
from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "supersecretkey"
RULES_FILE = "rules.json"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_rules():
    """JSON dosyasından kuralları yükler."""
    if not os.path.exists(RULES_FILE):
        return []
    with open(RULES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_rules(rules):
    """Kuralları JSON dosyasına kaydeder."""
    with open(RULES_FILE, "w", encoding="utf-8") as file:
        json.dump(rules, file, indent=4, ensure_ascii=False)

def generate_recommendations(df):
    """CSV'den gelen verileri, kurallara göre analiz eder ve öneriler sunar."""
    recommendations = []
    rules = load_rules()
    
    for index, row in df.iterrows():
        urun_adi = row["Malzeme Grubu"]
        satis_miktari = row["Net Satış Miktarı"]
        
        for rule in rules:
            keyword = rule["keyword"]
            threshold = rule["threshold"]
            message = rule["message"]
            
            if keyword.lower() in urun_adi.lower() and satis_miktari < threshold:
                recommendations.append(f"🔹 {urun_adi}: {message}")
    
    return "<br>".join(recommendations) if recommendations else "✅ Tüm ürünler yeterince satılmış görünüyor!"

def detect_and_extract_columns(file_path):
    """CSV dosyasındaki gerekli sütunları otomatik bulur ve temizler."""
    df = pd.read_csv(file_path, encoding="utf-8", sep=";", low_memory=False, header=None)
    df.columns = ["Malzeme Grubu", "Net Satış Miktarı"]
    df = df.dropna()
    df["Net Satış Miktarı"] = df["Net Satış Miktarı"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)
    return df

@app.route("/", methods=["GET", "POST"])
def upload_file():
    recommendations_html = None
    if request.method == "POST" and 'file' in request.files:
        file = request.files['file']
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            try:
                df_cleaned = detect_and_extract_columns(file_path)
                session['data'] = df_cleaned.to_dict(orient="records")
                recommendations_html = generate_recommendations(df_cleaned)
            except Exception as e:
                return f"Hata oluştu:<br><pre>{str(e)}</pre>"
    return render_template("index.html", recommendations=recommendations_html)

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    rules = load_rules()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            keyword = request.form.get("keyword")
            threshold = int(request.form.get("threshold"))
            message = request.form.get("message")
            rules.append({"keyword": keyword, "threshold": threshold, "message": message})
            save_rules(rules)
        elif action == "delete":
            index = int(request.form.get("index"))
            if 0 <= index < len(rules):
                del rules[index]
                save_rules(rules)
        return redirect(url_for("admin_panel"))
    return render_template("admin.html", rules=rules)

if __name__ == "__main__":
    app.run(debug=True)
