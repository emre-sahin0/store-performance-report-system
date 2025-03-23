import json
import os

RULES_FILE = "rules.json"
MISSING_RULES_FILE = "missing_rules.json"

def load_rules():
    if not os.path.exists(RULES_FILE):
        with open(RULES_FILE, "w", encoding="utf-8") as file:
            json.dump([], file)
    with open(RULES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as file:
        json.dump(rules, file, indent=4, ensure_ascii=False)

def load_missing_rules():
    if not os.path.exists(MISSING_RULES_FILE):
        with open(MISSING_RULES_FILE, "w", encoding="utf-8") as file:
            json.dump([], file)
    with open(MISSING_RULES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_missing_rules(rules):
    with open(MISSING_RULES_FILE, "w", encoding="utf-8") as file:
        json.dump(rules, file, indent=4, ensure_ascii=False)

def generate_recommendations(df):
    rules = load_rules()
    recommendations = []

    grouped_df = df.groupby("Malzeme Grubu", as_index=False).sum()

    for rule in rules:
        keyword = rule["keyword"]
        threshold = rule["threshold"]
        message = rule["message"]

        filtered_df = grouped_df[grouped_df["Malzeme Grubu"].str.contains(keyword, case=False, na=False)]
        total_sales = filtered_df["Net Satış Miktarı"].sum()

        if total_sales > 0 and total_sales < threshold:
            recommendations.append(f"🔹 <b>'{keyword}'</b> içeren ürünlerin toplam satışı <b>({total_sales})</b>  Eşik değerimizin <b>({threshold})</b> altında. Önerimiz;. {message}")

    return "<br>".join(recommendations) if recommendations else "✅ Tüm ürünler yeterince satılmış görünüyor!"

def generate_missing_recommendations(satilmayan_urunler):
    rules = load_missing_rules()
    messages = []

    for rule in rules:
        keyword = rule["keyword"]
        message = rule["message"]
        if any(keyword.lower() in urun.lower() for urun in satilmayan_urunler):
            messages.append(f"🔹 '{keyword}' ile ilgili öneri: {message}")

    return "<br>".join(messages) if messages else "✅ Satılmayan ürünler için özel bir öneri bulunmamaktadır."
