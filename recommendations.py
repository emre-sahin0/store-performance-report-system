def generate_recommendations(df):
    """Öneri sistemini çalıştırır ve belirli kurallara göre öneriler üretir."""
    recommendations = []

    for index, row in df.iterrows():
        urun_adi = row["Malzeme Grubu"]
        satis_miktari = row["Net Satış Miktarı"]

        

        if "Yılbaşı" in urun_adi and satis_miktari < 20:
            recommendations.append(f"🎄 {urun_adi} ürünü yılbaşı temalı ama düşük satış yapmış. Reklam desteği ekleyin!")

        if "Mobilya" in urun_adi and satis_miktari < 5:
            recommendations.append(f"🪑 {urun_adi} ürünü düşük satış yapıyor. Mobilya reyonunu genişletmeyi düşünün!")

        if "Katalog" in urun_adi and satis_miktari == 0:
            recommendations.append(f"📖 {urun_adi} ürünü hiç satılmamış! Katalog tanıtımlarını artırın!")

    return "<br>".join(recommendations) if recommendations else "✅ Tüm ürünler yeterince satılmış görünüyor!"
